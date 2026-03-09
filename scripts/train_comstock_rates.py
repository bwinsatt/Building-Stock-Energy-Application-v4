#!/usr/bin/env python3
"""
Train XGBoost models for ComStock effective utility rates ($/kWh) per fuel type.
Produces 4 models: electricity, natural_gas, fuel_oil, propane.

The effective rate is derived as:
    rate = bill_intensity_usd_per_ft2 / consumption_intensity_kwh_per_ft2

Buildings with consumption intensity < 0.1 kWh/ft2 are excluded per fuel to
avoid division-by-zero artifacts.

Usage:
    python3 scripts/train_comstock_rates.py                   # Train all 4 fuels
    python3 scripts/train_comstock_rates.py --skip-tuning     # Use saved hyperparameters
    python3 scripts/train_comstock_rates.py --tune-only       # Only run hyperparameter tuning
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from datetime import timedelta

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import (
    encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Rates')

# Bill intensity and consumption intensity columns per fuel type.
# Effective rate = bill_col / consumption_col  -> $/kWh
RATE_TARGETS = {
    'electricity': {
        'bill_col': 'out.utility_bills.electricity_bill_mean_intensity..usd_per_ft2',
        'consumption_col': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    },
    'natural_gas': {
        'bill_col': 'out.utility_bills.natural_gas_bill_state_average_intensity..usd_per_ft2',
        'consumption_col': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
    },
    'fuel_oil': {
        'bill_col': 'out.utility_bills.fuel_oil_bill_state_average_intensity..usd_per_ft2',
        'consumption_col': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
    },
    'propane': {
        'bill_col': 'out.utility_bills.propane_bill_state_average_intensity..usd_per_ft2',
        'consumption_col': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
    },
}

# Minimum consumption intensity (kWh/ft2) to include a row for rate derivation.
MIN_CONSUMPTION_THRESHOLD = 0.1

FEATURE_COLS = [
    'in.comstock_building_type_group',
    'in.sqft..ft2',
    'in.number_stories',
    'in.as_simulated_ashrae_iecc_climate_zone_2006',
    'cluster_name',
    'in.vintage',
    'in.heating_fuel',
    'in.service_water_heating_fuel',
    'in.hvac_category',
    'in.hvac_cool_type',
    'in.hvac_heat_type',
    'in.hvac_system_type',
    'in.hvac_vent_type',
    'in.wall_construction_type',
    'in.window_type',
    'in.window_to_wall_ratio_category',
    'in.airtightness..m3_per_m2_h',
    'in.interior_lighting_generation',
    'in.weekday_operating_hours..hr',
    'in.building_subtype',
    'in.aspect_ratio',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
]

# Columns to load from parquet (features + bill/consumption cols + metadata)
_BILL_COLS = [v['bill_col'] for v in RATE_TARGETS.values()]
_CONSUMPTION_COLS = [v['consumption_col'] for v in RATE_TARGETS.values()]
LOAD_COLS = (
    ['bldg_id', 'in.as_simulated_nhgis_county_gisjoin']
    + [c for c in FEATURE_COLS if c != 'cluster_name']
    + _BILL_COLS
    + _CONSUMPTION_COLS
)
# Deduplicate in case of overlap
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))

# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_baseline_data(cluster_lookup):
    """
    Load and clean baseline (upgrade 0) data for rate model training.

    Returns:
        df: cleaned DataFrame with features + bill/consumption columns
        n_raw: number of raw rows
        n_clean: number of clean rows
    """
    fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)

    # Deduplicate by bldg_id
    df = df.drop_duplicates(subset='bldg_id')

    # Merge cluster_name from spatial lookup
    df = df.merge(
        cluster_lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
        right_on='nhgis_county_gisjoin',
        how='left',
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows where ALL bill columns are null
    df = df.dropna(subset=_BILL_COLS, how='all')

    n_clean = len(df)

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'in.as_simulated_nhgis_county_gisjoin',
                           'nhgis_county_gisjoin'], errors='ignore')

    return df, n_raw, n_clean


def derive_rate(df, bill_col, consumption_col):
    """
    Derive effective utility rate and filter to valid rows.

    Returns:
        mask: boolean Series of valid rows (consumption > threshold)
        rate: Series of effective rates ($/kWh) for valid rows
    """
    consumption = df[consumption_col].fillna(0)
    bill = df[bill_col].fillna(0)
    mask = consumption > MIN_CONSUMPTION_THRESHOLD
    rate = pd.Series(np.nan, index=df.index)
    rate[mask] = bill[mask] / consumption[mask]
    return mask, rate


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def train_all(tune_trials=50, skip_tuning=False, tune_only=False):
    """Train rate models for all fuel types."""
    total_start = time.time()

    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load baseline data once
    print("Loading baseline data...")
    df, n_raw, n_clean = load_baseline_data(cluster_lookup)
    if df is None or n_clean < 100:
        print(f"Insufficient baseline data ({n_clean} rows). Aborting.")
        return
    print(f"  Loaded {n_clean} buildings (from {n_raw} raw rows)")

    # Phase 1: Hyperparameter tuning (single group — tune on electricity, apply to all)
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING")
    print("=" * 70)

    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters.json')

    if skip_tuning:
        if os.path.exists(params_path):
            with open(params_path) as f:
                tuned_params = json.load(f)
            print(f"\nLoaded saved hyperparameters from {params_path}")
        else:
            print(f"\nWARNING: --skip-tuning but no saved params at {params_path}")
            print("  Will use default hyperparameters.")
            tuned_params = None
    else:
        # Tune on electricity rate (largest sample, representative)
        elec_cfg = RATE_TARGETS['electricity']
        mask, rate = derive_rate(df, elec_cfg['bill_col'], elec_cfg['consumption_col'])
        df_tune = df[mask].copy()
        y_tune_full = rate[mask].values

        print(f"\nTuning on electricity rate ({mask.sum()} samples)...")

        X_enc, _ = encode_features(df_tune, FEATURE_COLS)

        # Subsample for tuning if dataset is very large
        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y_tune_full[idx]
        else:
            X_tune, y_tune = X_enc, y_tune_full

        tuned_params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        print(f"  Best params: {tuned_params}")

        # Save tuned params
        with open(params_path, 'w') as f:
            json.dump(tuned_params, f, indent=2)
        print(f"Saved tuned params to {params_path}")

    if tune_only:
        print("\n--tune-only specified. Skipping model training.")
        return

    # Phase 2: Train one model per fuel type
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (per fuel type)")
    print("=" * 70)

    if tuned_params is None:
        tuned_params = {
            'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
            'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
        }

    from sklearn.model_selection import train_test_split

    all_results = []
    n_models_trained = 0

    for fuel_name, fuel_cfg in RATE_TARGETS.items():
        bill_col = fuel_cfg['bill_col']
        consumption_col = fuel_cfg['consumption_col']

        # Derive rate and filter
        mask, rate = derive_rate(df, bill_col, consumption_col)
        n_valid = mask.sum()

        if n_valid < 50:
            print(f"\n  {fuel_name}: SKIPPED (only {n_valid} valid rows)")
            all_results.append({
                'fuel_type': fuel_name, 'status': 'skipped',
                'reason': f'insufficient data ({n_valid} rows)',
            })
            continue

        df_fuel = df[mask].copy()
        y = rate[mask].values

        # Encode features
        X_enc, encoders = encode_features(df_fuel, FEATURE_COLS)

        # Train/test split
        train_idx, test_idx = train_test_split(
            np.arange(len(X_enc)), test_size=0.2, random_state=42
        )
        X_train, X_test = X_enc.iloc[train_idx], X_enc.iloc[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Train
        t0 = time.time()
        model = train_single_model(X_train, y_train, tuned_params)
        train_time = time.time() - t0

        # Evaluate (convert_kbtu=False since target is $/kWh, not EUI)
        train_metrics = evaluate_model(model, X_train, y_train, convert_kbtu=False)
        test_metrics = evaluate_model(model, X_test, y_test, convert_kbtu=False)

        print(f"\n  {fuel_name:>15}: MAE={test_metrics['mae_kwh_ft2']:.4f} $/kWh, "
              f"R²={test_metrics['r2']:.4f}, n={n_valid}, Time={train_time:.1f}s")

        # Save model
        model_name = f'XGB_rate_{fuel_name}'
        save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                             OUTPUT_DIR, model_name)
        n_models_trained += 1

        all_results.append({
            'fuel_type': fuel_name,
            'status': 'success',
            'n_valid': n_valid,
            'train_mae': train_metrics['mae_kwh_ft2'],
            'train_r2': train_metrics['r2'],
            'test_mae': test_metrics['mae_kwh_ft2'],
            'test_r2': test_metrics['r2'],
            'test_rmse': test_metrics['rmse_kwh_ft2'],
            'train_time_s': train_time,
        })

    # Save summary results
    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_summary.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} rate models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train ComStock effective utility rate models')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials (default: 50)')
    parser.add_argument('--tune-only', action='store_true',
                        help='Only run hyperparameter tuning, skip model training')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    print(f"Training {len(RATE_TARGETS)} ComStock rate models ($/kWh)")
    print(f"Output directory: {OUTPUT_DIR}")
    if not args.skip_tuning:
        print(f"Tune trials: {args.tune_trials}")

    train_all(tune_trials=args.tune_trials,
              skip_tuning=args.skip_tuning, tune_only=args.tune_only)


if __name__ == '__main__':
    main()
