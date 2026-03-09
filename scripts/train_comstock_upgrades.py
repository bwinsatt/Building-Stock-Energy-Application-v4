#!/usr/bin/env python3
"""
Train XGBoost models for ComStock 2025 R3 upgrade measures.
Produces 5 models per upgrade (one per fuel type) x 66 upgrades = 330 models.
Total site EUI = sum of fuel-type EUIs at inference time.

Usage:
    python3 scripts/train_comstock_upgrades.py                       # Train all
    python3 scripts/train_comstock_upgrades.py --upgrades 0 1 43     # Train specific upgrades
    python3 scripts/train_comstock_upgrades.py --skip-tuning         # Use saved hyperparameters
    python3 scripts/train_comstock_upgrades.py --tune-only           # Only run hyperparameter tuning
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
    load_upgrades_lookup, encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
UPGRADES_JSON = os.path.join(RAW_DIR, 'upgrades_lookup.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3')

# Per-fuel-type EUI target columns
FUEL_TYPES = {
    'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
    'fuel_oil': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
    'propane': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
    'district_heating': 'out.district_heating.total.energy_consumption_intensity..kwh_per_ft2',
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
]

# Columns to load from parquet (features + all fuel targets + metadata)
LOAD_COLS = ['bldg_id', 'completed_status', 'applicability',
             'in.as_simulated_nhgis_county_gisjoin'] + FEATURE_COLS + list(FUEL_TYPES.values())
# Remove cluster_name from LOAD_COLS since it's derived
LOAD_COLS = [c for c in LOAD_COLS if c != 'cluster_name']

# Hyperparameter tuning groups: tune on representative, apply to similar measures
TUNE_GROUPS = {
    'baseline': [0],
    'hvac': list(range(1, 32)),
    'demand_flex': list(range(32, 43)),
    'lighting': [43, 44],
    'other': [45, 46, 47],
    'envelope': list(range(48, 54)),
    'packages': list(range(54, 66)),
}
# Representative upgrade to tune for each group
TUNE_REPRESENTATIVES = {
    'baseline': 0,
    'hvac': 1,       # HP-RTU (most common HVAC measure)
    'demand_flex': 32,
    'lighting': 43,  # LED
    'envelope': 49,  # Roof Insulation (100% applicability)
    'packages': 55,  # Package 2
    'other': 46,
}

# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    # Deduplicate to one cluster per county
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_upgrade_data(upgrade_id, cluster_lookup):
    """
    Load and clean data for a single upgrade.

    Returns:
        df: cleaned DataFrame with features + fuel-type targets, or None if file doesn't exist
        n_raw: number of raw rows
        n_clean: number of clean rows
    """
    if upgrade_id == 0:
        fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    else:
        fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}_agg.parquet')

    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)

    # Deduplicate by bldg_id (ComStock has duplicate rows with different weights)
    df = df.drop_duplicates(subset='bldg_id')

    # Filter to successful simulations only
    if upgrade_id > 0:
        df = df[df['completed_status'] == 'Success']
        df = df[df['applicability'] == True]

    # Merge cluster_name from spatial lookup
    df = df.merge(
        cluster_lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    # Fill missing clusters (shouldn't happen, but safety)
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows where ALL fuel-type EUIs are null
    fuel_cols = list(FUEL_TYPES.values())
    df = df.dropna(subset=fuel_cols, how='all')

    # Fill individual null fuel EUIs with 0 (building doesn't use that fuel)
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

    n_clean = len(df)

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'completed_status', 'applicability',
                           'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df, n_raw, n_clean


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def get_group_for_upgrade(uid):
    """Find which tuning group an upgrade belongs to."""
    for group, uids in TUNE_GROUPS.items():
        if uid in uids:
            return group
    return 'other'


def train_all(upgrade_ids, tune_trials=50, skip_tuning=False, tune_only=False):
    """Train models for specified upgrade IDs."""
    total_start = time.time()

    upgrades_lookup = load_upgrades_lookup(UPGRADES_JSON)
    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: Hyperparameter tuning
    print("=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING")
    print("=" * 70)

    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters.json')

    if skip_tuning:
        if os.path.exists(params_path):
            with open(params_path) as f:
                tuned_params = json.load(f)
            print(f"\nLoaded saved hyperparameters from {params_path}")
            print(f"  Groups: {list(tuned_params.keys())}")
        else:
            print(f"\nWARNING: --skip-tuning but no saved params at {params_path}")
            print("  Will use default hyperparameters.")
            tuned_params = {}
    else:
        tuned_params = {}
        groups_needed = set(get_group_for_upgrade(uid) for uid in upgrade_ids)

        # Use electricity EUI for tuning (largest signal, representative)
        tune_target = FUEL_TYPES['electricity']

        for group in groups_needed:
            rep_uid = TUNE_REPRESENTATIVES[group]
            print(f"\nTuning group '{group}' using upgrade {rep_uid} "
                  f"({upgrades_lookup.get(str(rep_uid), '?')})...")

            df, n_raw, n_clean = load_upgrade_data(rep_uid, cluster_lookup)
            if df is None or n_clean < 100:
                print(f"  Insufficient data ({n_clean} rows). Using defaults.")
                tuned_params[group] = None
                continue

            X_enc, _ = encode_features(df, FEATURE_COLS)
            y = df[tune_target].values

            # Use a subset for tuning if dataset is very large
            if len(X_enc) > 30000:
                idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
                X_tune, y_tune = X_enc.iloc[idx], y[idx]
            else:
                X_tune, y_tune = X_enc, y

            params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
            tuned_params[group] = params
            print(f"  Best params: {params}")

        # Save tuned params
        with open(params_path, 'w') as f:
            json.dump({k: v for k, v in tuned_params.items() if v is not None}, f, indent=2)
        print(f"\nSaved tuned params to {params_path}")

    if tune_only:
        print("\n--tune-only specified. Skipping model training.")
        return

    # Phase 2: Train all models (one per fuel type per upgrade)
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (per fuel type)")
    print("=" * 70)

    all_results = []
    from sklearn.model_selection import train_test_split
    n_models_trained = 0

    for uid in upgrade_ids:
        measure_name = upgrades_lookup.get(str(uid), f'upgrade_{uid}')
        group = get_group_for_upgrade(uid)
        params = tuned_params.get(group)

        if params is None:
            # Fallback defaults
            params = {
                'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
                'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
            }

        print(f"\n{'=' * 60}")
        print(f"Upgrade {uid}: {measure_name} (group: {group})")
        print(f"{'=' * 60}")

        df, n_raw, n_clean = load_upgrade_data(uid, cluster_lookup)
        if df is None or n_clean < 50:
            print(f"  SKIPPED: insufficient data ({n_clean} rows)")
            all_results.append({
                'upgrade_id': uid, 'measure_name': measure_name,
                'fuel_type': 'all', 'status': 'skipped',
                'reason': f'insufficient data ({n_clean} rows)',
            })
            continue

        # Encode features once per upgrade (shared across fuel types)
        X_enc, encoders = encode_features(df, FEATURE_COLS)

        # Same train/test split for all fuel types within an upgrade
        train_idx, test_idx = train_test_split(
            np.arange(len(X_enc)), test_size=0.2, random_state=42
        )
        X_train, X_test = X_enc.iloc[train_idx], X_enc.iloc[test_idx]

        for fuel_name, fuel_col in FUEL_TYPES.items():
            y = df[fuel_col].values
            y_train, y_test = y[train_idx], y[test_idx]

            # Train model
            t0 = time.time()
            model = train_single_model(X_train, y_train, params)
            train_time = time.time() - t0

            # Evaluate
            train_metrics = evaluate_model(model, X_train, y_train)
            test_metrics = evaluate_model(model, X_test, y_test)

            print(f"  {fuel_name:>18}: MAE={test_metrics['mae_kbtu_sf']:6.2f} kBtu/sf, "
                  f"R²={test_metrics['r2']:.4f}, Time={train_time:.1f}s")

            # Save model with fuel type in name
            model_name = f'XGB_upgrade{uid}_{fuel_name}'
            save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                                 OUTPUT_DIR, model_name)
            n_models_trained += 1

            # Record results
            all_results.append({
                'upgrade_id': uid,
                'measure_name': measure_name,
                'fuel_type': fuel_name,
                'group': group,
                'status': 'success',
                'n_raw': n_raw,
                'n_applicable': n_clean,
                'train_mae_kbtu_sf': train_metrics['mae_kbtu_sf'],
                'train_r2': train_metrics['r2'],
                'test_mae_kbtu_sf': test_metrics['mae_kbtu_sf'],
                'test_r2': test_metrics['r2'],
                'test_rmse_kwh_ft2': test_metrics['rmse_kwh_ft2'],
                'train_time_s': train_time,
            })

        print(f"  Samples: {n_clean} applicable")

    # Save summary results
    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_summary.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train ComStock upgrade models')
    parser.add_argument('--upgrades', nargs='+', type=int, default=None,
                        help='Specific upgrade IDs to train (default: all 0-65)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials per tuning group (default: 50)')
    parser.add_argument('--tune-only', action='store_true',
                        help='Only run hyperparameter tuning, skip model training')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    if args.upgrades is None:
        upgrade_ids = list(range(0, 66))
    else:
        upgrade_ids = args.upgrades

    print(f"Training {len(upgrade_ids)} ComStock upgrades x {len(FUEL_TYPES)} fuel types")
    print(f"Output directory: {OUTPUT_DIR}")
    if not args.skip_tuning:
        print(f"Tune trials per group: {args.tune_trials}")

    train_all(upgrade_ids, tune_trials=args.tune_trials,
              skip_tuning=args.skip_tuning, tune_only=args.tune_only)


if __name__ == '__main__':
    main()
