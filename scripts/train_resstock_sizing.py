#!/usr/bin/env python3
"""
Train XGBoost models for ResStock sizing targets (Multi-Family 4+ units, occupied).
Produces 2 capacity models used for upgrade cost estimation.

Targets:
  - heating_capacity (kBtu/hr)
  - cooling_capacity (kBtu/hr)

Usage:
    python3 scripts/train_resstock_sizing.py                  # Train all targets (with tuning)
    python3 scripts/train_resstock_sizing.py --skip-tuning    # Use saved hyperparameters
    python3 scripts/train_resstock_sizing.py --tune-trials 30 # Fewer Optuna trials
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
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Sizing')

# Only capacity targets — wall/roof/window area are computed geometrically
# in assessment.py, not via ML sizing models
SIZING_TARGETS = {
    'heating_capacity': 'out.params.size_heating_system_primary..kbtu_per_hr',
    'cooling_capacity': 'out.params.size_cooling_system_primary..kbtu_per_hr',
}

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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
    'floor_plate_sqft',
]

# Must match train_resstock_deltas.py exactly (updated by feature pipeline fixes)
CAT_FEATURE_NAMES = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
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
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
]

HDD_CDD_PATH = os.path.join(PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json')

# Columns to load from parquet (cluster_name is merged separately)
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + \
            [c for c in FEATURE_COLS if c not in (
                'cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft',
                'in.geometry_building_type_height',  # derived from stories
            )] + \
            list(SIZING_TARGETS.values())
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))  # deduplicate


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
    """Load and clean ResStock baseline data (upgrade0) for sizing models."""
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

    # HDD/CDD from cluster lookup (ResStock lacks out.params HDD/CDD)
    with open(HDD_CDD_PATH) as f:
        cluster_hdd_cdd = json.load(f)
    df['hdd65f'] = df['cluster_name'].map(
        lambda c: cluster_hdd_cdd.get(c, {}).get('hdd65f', 4800.0))
    df['cdd65f'] = df['cluster_name'].map(
        lambda c: cluster_hdd_cdd.get(c, {}).get('cdd65f', 1400.0))

    # Derived features
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.geometry_stories'], errors='coerce').clip(lower=1)
    )

    # Building type height from stories (derived, not loaded from parquet)
    stories = pd.to_numeric(df['in.geometry_stories'], errors='coerce').fillna(1)
    df['in.geometry_building_type_height'] = stories.apply(
        lambda s: '1-3' if s <= 3 else ('4-7' if s <= 7 else '8+')
    )

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
    """Train sizing models for all targets."""
    total_start = time.time()

    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data once (baseline only for sizing)
    print("=" * 70)
    print("LOADING BASELINE DATA")
    print("=" * 70)
    df, n_raw, n_clean = load_baseline_data(cluster_lookup)

    # Phase 1: Hyperparameter tuning
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ResStock Sizing)")
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
        # Tune on first valid target (heating_capacity is typically well-populated)
        tune_target_name = 'heating_capacity'
        tune_target_col = SIZING_TARGETS[tune_target_name]

        mask = df[tune_target_col].notna() & (df[tune_target_col] > 0)
        df_tune = df[mask]
        print(f"\nTuning on '{tune_target_name}' ({len(df_tune):,} valid samples)...")

        X_enc, _ = encode_features(df_tune, FEATURE_COLS)
        y = df_tune[tune_target_col].values

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
    print("PHASE 2: MODEL TRAINING (ResStock Sizing)")
    print("=" * 70)

    from sklearn.model_selection import train_test_split
    all_results = []
    n_models_trained = 0

    for target_name, target_col in SIZING_TARGETS.items():
        print(f"\n--- Target: {target_name} ({target_col}) ---")

        # Filter to rows with valid (non-null, positive) target values
        mask = df[target_col].notna() & (df[target_col] > 0)
        df_target = df[mask]

        if len(df_target) < 50:
            print(f"  SKIPPED: insufficient data ({len(df_target)} rows)")
            all_results.append({
                'target': target_name,
                'target_col': target_col,
                'status': 'skipped',
                'reason': f'insufficient data ({len(df_target)} rows)',
            })
            continue

        print(f"  Valid samples: {len(df_target):,}")

        # Encode features
        X_enc, encoders = encode_features(df_target, FEATURE_COLS)
        y = df_target[target_col].values

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

        # Evaluate (convert_kbtu=False since targets are not EUI)
        train_metrics = evaluate_model(model, X_train, y_train, convert_kbtu=False)
        test_metrics = evaluate_model(model, X_test, y_test, convert_kbtu=False)

        print(f"  Train MAE: {train_metrics['mae_kwh_ft2']:.4f}, R2: {train_metrics['r2']:.4f}")
        print(f"  Test  MAE: {test_metrics['mae_kwh_ft2']:.4f}, R2: {test_metrics['r2']:.4f}, "
              f"Time: {train_time:.1f}s")

        # Save
        model_name = f'XGB_sizing_{target_name}'
        save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                             OUTPUT_DIR, model_name)
        n_models_trained += 1

        all_results.append({
            'target': target_name,
            'target_col': target_col,
            'status': 'success',
            'n_raw': n_raw,
            'n_valid': len(df_target),
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
    print(f"COMPLETE: {n_models_trained} sizing models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description='Train ResStock MF sizing models')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials (default: 50)')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    print(f"Training ResStock sizing models for {len(SIZING_TARGETS)} targets")
    print(f"Output directory: {OUTPUT_DIR}")

    train_all(tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
