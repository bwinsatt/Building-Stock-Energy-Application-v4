#!/usr/bin/env python3
"""
Train XGBoost models for ComStock building sizing predictions.
Produces 2 capacity models used for upgrade cost estimation.

Targets:
  - heating_capacity  (kBtu/hr)
  - cooling_capacity  (tons)

Usage:
    python3 scripts/train_comstock_sizing.py                   # Train all targets
    python3 scripts/train_comstock_sizing.py --targets heating_capacity cooling_capacity
    python3 scripts/train_comstock_sizing.py --skip-tuning     # Use saved hyperparameters
    python3 scripts/train_comstock_sizing.py --tune-only       # Only run hyperparameter tuning
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
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Sizing')

# Sizing target columns — only capacity targets (wall/roof/window area
# are computed geometrically in assessment.py, not via ML sizing models)
SIZING_TARGETS = {
    'heating_capacity': 'out.params.heating_equipment..kbtu_per_hr',
    'cooling_capacity': 'out.params.cooling_equipment_capacity..tons',
}

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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
    'floor_plate_sqft',
]

# Must match train_comstock_deltas.py exactly (updated by feature pipeline fixes)
CAT_FEATURE_NAMES = [
    'in.comstock_building_type_group',
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
    'in.interior_lighting_generation',
    'in.weekday_operating_hours..hr',
    'in.building_subtype',
    'in.aspect_ratio',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
]

# Columns to load from parquet (features + all sizing targets + metadata)
LOAD_COLS = ['bldg_id', 'completed_status',
             'in.as_simulated_nhgis_county_gisjoin'] + \
            [c for c in FEATURE_COLS if c not in (
                'cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft',
            )] + \
            list(SIZING_TARGETS.values()) + [
                'out.params.hdd65f', 'out.params.cdd65f',
            ]
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))  # deduplicate

# Single tuning group: tune on heating_capacity, apply to all targets
TUNE_TARGET_KEY = 'heating_capacity'

# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    # Deduplicate to one cluster per county
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_baseline_data(cluster_lookup):
    """
    Load and clean baseline (upgrade0) data for sizing model training.

    Returns:
        df: cleaned DataFrame with features + sizing targets, or None if file doesn't exist
        n_raw: number of raw rows
        n_clean: number of clean rows
    """
    fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')

    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)

    # Deduplicate by bldg_id (ComStock has duplicate rows with different weights)
    df = df.drop_duplicates(subset='bldg_id')

    # No applicability filter for baseline data

    # Merge cluster_name from spatial lookup
    df = df.merge(
        cluster_lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    # Fill missing clusters (shouldn't happen, but safety)
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows where ALL sizing targets are null
    target_cols = list(SIZING_TARGETS.values())
    df = df.dropna(subset=target_cols, how='all')

    # Fill individual null targets with 0
    for col in target_cols:
        df[col] = df[col].fillna(0)

    # Rename HDD/CDD to match inference names
    df = df.rename(columns={
        'out.params.hdd65f': 'hdd65f',
        'out.params.cdd65f': 'cdd65f',
    })

    # Clean thermostat sentinel values (999 = no data → NaN)
    tstat_cols = [
        'in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
        'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
        'in.weekend_operating_hours..hr',
    ]
    for col in tstat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df.loc[df[col] >= 999, col] = float('nan')

    # Derived features
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.number_stories'], errors='coerce').clip(lower=1)
    )

    n_clean = len(df)

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'completed_status',
                           'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df, n_raw, n_clean


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def train_all(target_keys, tune_trials=50, skip_tuning=False, tune_only=False):
    """Train sizing models for specified targets."""
    total_start = time.time()

    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load baseline data (shared across all targets)
    print("\nLoading baseline data...")
    df, n_raw, n_clean = load_baseline_data(cluster_lookup)
    if df is None or n_clean < 100:
        print(f"FATAL: insufficient baseline data ({n_clean} rows). Aborting.")
        return

    print(f"  Raw rows: {n_raw:,}")
    print(f"  Clean rows: {n_clean:,}")

    # Phase 1: Hyperparameter tuning
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
        # Tune on heating_capacity, apply to all targets
        tune_target_col = SIZING_TARGETS[TUNE_TARGET_KEY]
        print(f"\nTuning on '{TUNE_TARGET_KEY}' ({tune_target_col})...")

        X_enc, _ = encode_features(df, FEATURE_COLS)
        y_tune = df[tune_target_col].values

        # Use a subset for tuning if dataset is very large
        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y_tune[idx]
        else:
            X_tune = X_enc

        tuned_params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        print(f"  Best params: {tuned_params}")

        # Save tuned params
        with open(params_path, 'w') as f:
            json.dump(tuned_params, f, indent=2)
        print(f"\nSaved tuned params to {params_path}")

    if tune_only:
        print("\n--tune-only specified. Skipping model training.")
        return

    # Phase 2: Train one model per sizing target
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (per sizing target)")
    print("=" * 70)

    params = tuned_params
    if params is None:
        # Fallback defaults
        params = {
            'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
            'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
        }

    # Encode features once (shared across all targets)
    X_enc, encoders = encode_features(df, FEATURE_COLS)

    # Same train/test split for all targets
    from sklearn.model_selection import train_test_split
    train_idx, test_idx = train_test_split(
        np.arange(len(X_enc)), test_size=0.2, random_state=42
    )
    X_train, X_test = X_enc.iloc[train_idx], X_enc.iloc[test_idx]

    all_results = []
    n_models_trained = 0

    for target_key in target_keys:
        target_col = SIZING_TARGETS[target_key]
        print(f"\n  Training: {target_key} ({target_col})")

        y = df[target_col].values
        y_train, y_test = y[train_idx], y[test_idx]

        # Train model
        t0 = time.time()
        model = train_single_model(X_train, y_train, params)
        train_time = time.time() - t0

        # Evaluate (convert_kbtu=False since these are capacity/area, not EUI)
        train_metrics = evaluate_model(model, X_train, y_train, convert_kbtu=False)
        test_metrics = evaluate_model(model, X_test, y_test, convert_kbtu=False)

        print(f"    MAE={test_metrics['mae_kwh_ft2']:,.2f}, "
              f"R²={test_metrics['r2']:.4f}, Time={train_time:.1f}s")

        # Save model
        model_name = f'XGB_sizing_{target_key}'
        save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                             OUTPUT_DIR, model_name)
        n_models_trained += 1

        # Record results
        all_results.append({
            'target': target_key,
            'target_column': target_col,
            'status': 'success',
            'n_raw': n_raw,
            'n_clean': n_clean,
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
    print(f"COMPLETE: {n_models_trained} sizing models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train ComStock sizing models')
    parser.add_argument('--targets', nargs='+', type=str, default=None,
                        choices=list(SIZING_TARGETS.keys()),
                        help='Specific targets to train (default: all)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials for tuning (default: 50)')
    parser.add_argument('--tune-only', action='store_true',
                        help='Only run hyperparameter tuning, skip model training')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    target_keys = args.targets if args.targets else list(SIZING_TARGETS.keys())

    print(f"Training {len(target_keys)} ComStock sizing models")
    print(f"  Targets: {target_keys}")
    print(f"  Output directory: {OUTPUT_DIR}")
    if not args.skip_tuning:
        print(f"  Tune trials: {args.tune_trials}")

    train_all(target_keys, tune_trials=args.tune_trials,
              skip_tuning=args.skip_tuning, tune_only=args.tune_only)


if __name__ == '__main__':
    main()
