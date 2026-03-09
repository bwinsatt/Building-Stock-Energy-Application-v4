#!/usr/bin/env python3
"""
Train XGBoost models for ResStock utility rate targets (Multi-Family 4+ units, occupied).
Derives effective rate ($/kWh) = total bill ($) / total consumption (kWh).

Targets:
  - electricity rate ($/kWh)
  - natural_gas rate ($/kWh)
  - fuel_oil rate ($/kWh)
  - propane rate ($/kWh)

Usage:
    python3 scripts/train_resstock_rates.py                  # Train all targets (with tuning)
    python3 scripts/train_resstock_rates.py --skip-tuning    # Use saved hyperparameters
    python3 scripts/train_resstock_rates.py --tune-trials 30 # Fewer Optuna trials
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from datetime import timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import (
    encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ResStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Rates')

# Bill and consumption columns for deriving rates
# ResStock uses total $ and total kWh (not per ft2)
RATE_TARGETS = {
    'electricity': {
        'bill_col': 'out.utility_bills.electricity_bill..usd',
        'consumption_col': 'out.electricity.total.energy_consumption..kwh',
    },
    'natural_gas': {
        'bill_col': 'out.utility_bills.natural_gas_bill..usd',
        'consumption_col': 'out.natural_gas.total.energy_consumption..kwh',
    },
    'fuel_oil': {
        'bill_col': 'out.utility_bills.fuel_oil_bill..usd',
        'consumption_col': 'out.fuel_oil.total.energy_consumption..kwh',
    },
    'propane': {
        'bill_col': 'out.utility_bills.propane_bill..usd',
        'consumption_col': 'out.propane.total.energy_consumption..kwh',
    },
}

# Minimum consumption threshold to avoid division by near-zero
MIN_CONSUMPTION_KWH = 10

FEATURE_COLS = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
    'in.sqft..ft2',
    'in.geometry_stories',
    'in.ashrae_iecc_climate_zone_2004',
    'cluster_name',
    'in.vintage',
    'in.heating_fuel',
    'in.hvac_heating_type',
    'in.hvac_heating_efficiency',
    'in.hvac_cooling_type',
    'in.hvac_cooling_efficiency',
    'in.hvac_has_shared_system',
    'in.water_heater_fuel',
    'in.water_heater_efficiency',
    'in.geometry_wall_type',
    'in.insulation_wall',
    'in.insulation_floor',
    'in.window_areas',
    'in.windows',
    'in.lighting',
    'in.infiltration',
    'in.geometry_foundation_type',
]

# Collect all bill/consumption columns needed for loading
_bill_and_consumption_cols = []
for info in RATE_TARGETS.values():
    _bill_and_consumption_cols.append(info['bill_col'])
    _bill_and_consumption_cols.append(info['consumption_col'])

# Columns to load from parquet (cluster_name is merged separately)
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + FEATURE_COLS + _bill_and_consumption_cols
LOAD_COLS = [c for c in LOAD_COLS if c != 'cluster_name']


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def filter_mf_occupied(df):
    """Filter to multi-family 4+ units, occupied only."""
    units = df['in.geometry_building_number_units_mf'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    mf_mask = units >= 4
    occ_mask = df['in.vacancy_status'] == 'Occupied'
    return df[mf_mask & occ_mask].copy()


def load_baseline_data(cluster_lookup):
    """Load and clean ResStock baseline data (upgrade0) for rate models."""
    fname = os.path.join(RAW_DIR, 'upgrade0.parquet')

    if not os.path.exists(fname):
        raise FileNotFoundError(f"Baseline file not found: {fname}")

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)
    print(f"  Loaded {n_raw:,} rows from {fname}")

    # Filter to MF 4+ occupied
    df = filter_mf_occupied(df)
    print(f"  After MF 4+ occupied filter: {len(df):,} rows")

    # Merge cluster_name
    df = df.merge(
        cluster_lookup,
        left_on='in.county',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    n_clean = len(df)

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'applicability',
                           'in.geometry_building_number_units_mf', 'in.vacancy_status',
                           'in.county', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df, n_raw, n_clean


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def train_all(tune_trials=50, skip_tuning=False):
    """Train rate models for all fuel types."""
    total_start = time.time()

    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data once (baseline only for rates)
    print("=" * 70)
    print("LOADING BASELINE DATA")
    print("=" * 70)
    df, n_raw, n_clean = load_baseline_data(cluster_lookup)

    # Phase 1: Hyperparameter tuning
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ResStock Rates)")
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
        # Tune on electricity rate (largest sample, most representative)
        tune_fuel = 'electricity'
        tune_info = RATE_TARGETS[tune_fuel]
        bill_col = tune_info['bill_col']
        consumption_col = tune_info['consumption_col']

        mask = (df[bill_col].notna() & df[consumption_col].notna()
                & (df[consumption_col] > MIN_CONSUMPTION_KWH))
        df_tune_base = df[mask].copy()
        rate_values = df_tune_base[bill_col].values / df_tune_base[consumption_col].values

        print(f"\nTuning on '{tune_fuel}' rate ({len(df_tune_base):,} valid samples)...")

        X_enc, _ = encode_features(df_tune_base, FEATURE_COLS)
        y = rate_values

        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y[idx]
        else:
            X_tune, y_tune = X_enc, y

        tuned_params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        print(f"  Best params: {tuned_params}")

        with open(params_path, 'w') as f:
            json.dump(tuned_params, f, indent=2)

    if tuned_params is None:
        tuned_params = {
            'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
            'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
        }

    # Phase 2: Train models
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ResStock Rates)")
    print("=" * 70)

    from sklearn.model_selection import train_test_split
    all_results = []
    n_models_trained = 0

    for fuel_name, fuel_info in RATE_TARGETS.items():
        bill_col = fuel_info['bill_col']
        consumption_col = fuel_info['consumption_col']

        print(f"\n--- Target: {fuel_name} rate ($/kWh) ---")
        print(f"    bill: {bill_col}")
        print(f"    consumption: {consumption_col}")

        # Filter to rows with valid bill and sufficient consumption
        mask = (df[bill_col].notna() & df[consumption_col].notna()
                & (df[consumption_col] > MIN_CONSUMPTION_KWH))
        df_target = df[mask].copy()

        if len(df_target) < 50:
            print(f"  SKIPPED: insufficient data ({len(df_target)} rows)")
            all_results.append({
                'fuel_type': fuel_name,
                'status': 'skipped',
                'reason': f'insufficient data ({len(df_target)} rows)',
            })
            continue

        # Derive rate: total bill / total consumption = $/kWh
        rate_values = df_target[bill_col].values / df_target[consumption_col].values

        print(f"  Valid samples: {len(df_target):,}")
        print(f"  Rate stats: median={np.median(rate_values):.4f}, "
              f"mean={np.mean(rate_values):.4f}, "
              f"std={np.std(rate_values):.4f} $/kWh")

        # Encode features
        X_enc, encoders = encode_features(df_target, FEATURE_COLS)
        y = rate_values

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

        print(f"  Train MAE: {train_metrics['mae_kwh_ft2']:.6f} $/kWh, "
              f"R2: {train_metrics['r2']:.4f}")
        print(f"  Test  MAE: {test_metrics['mae_kwh_ft2']:.6f} $/kWh, "
              f"R2: {test_metrics['r2']:.4f}, Time: {train_time:.1f}s")

        # Save
        model_name = f'XGB_rate_{fuel_name}'
        save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                             OUTPUT_DIR, model_name)
        n_models_trained += 1

        all_results.append({
            'fuel_type': fuel_name,
            'status': 'success',
            'n_raw': n_raw,
            'n_valid': len(df_target),
            'rate_median': float(np.median(rate_values)),
            'rate_mean': float(np.mean(rate_values)),
            'train_mae': train_metrics['mae_kwh_ft2'],
            'train_r2': train_metrics['r2'],
            'test_mae': test_metrics['mae_kwh_ft2'],
            'test_r2': test_metrics['r2'],
            'test_rmse': test_metrics['rmse_kwh_ft2'],
            'train_time_s': train_time,
        })

    # Save results summary
    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_summary.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} rate models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description='Train ResStock MF utility rate models')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials (default: 50)')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    print(f"Training ResStock rate models for {len(RATE_TARGETS)} fuel types")
    print(f"Output directory: {OUTPUT_DIR}")

    train_all(tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
