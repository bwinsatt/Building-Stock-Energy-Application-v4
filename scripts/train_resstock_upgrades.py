#!/usr/bin/env python3
"""
Train XGBoost models for ResStock 2025 R1 upgrade measures (Multi-Family 4+ units).
Produces 4 models per upgrade (one per fuel type) x 33 upgrades = 132 models.
Total site EUI = sum of fuel-type EUIs at inference time.

Usage:
    python3 scripts/train_resstock_upgrades.py                    # Train all (with tuning)
    python3 scripts/train_resstock_upgrades.py --upgrades 0 4 17  # Train specific upgrades
    python3 scripts/train_resstock_upgrades.py --skip-tuning      # Use saved hyperparameters
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
    load_upgrades_lookup, encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ResStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
UPGRADES_JSON = os.path.join(RAW_DIR, 'upgrades_lookup.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Upgrades_2025_R1')

# Per-fuel-type EUI target columns
FUEL_TYPES = {
    'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
    'fuel_oil': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
    'propane': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
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
]

# Columns to load from parquet
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + FEATURE_COLS + list(FUEL_TYPES.values())
LOAD_COLS = [c for c in LOAD_COLS if c != 'cluster_name']

# Hyperparameter tuning groups
TUNE_GROUPS = {
    'baseline': [0],
    'hvac': [1, 2, 3, 4, 5, 6, 7, 8],
    'water_heating': [9, 10],
    'envelope': [11, 12, 13, 14, 15, 16, 17, 29, 30],
    'packages': [18, 31, 32],
    'ev': [19, 20, 21, 22, 23],
    'demand_flex': [24, 25, 26, 27, 28],
}
TUNE_REPRESENTATIVES = {
    'baseline': 0,
    'hvac': 4,       # Cold Climate ASHP
    'water_heating': 9,  # HPWH
    'envelope': 17,  # Windows (100% applicability)
    'packages': 18,
    'ev': 20,
    'demand_flex': 24,
}

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
    # Parse number of units
    units = df['in.geometry_building_number_units_mf'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    mf_mask = units >= 4
    occ_mask = df['in.vacancy_status'] == 'Occupied'
    return df[mf_mask & occ_mask].copy()


def load_upgrade_data(upgrade_id, cluster_lookup):
    """Load and clean ResStock data for a single upgrade."""
    fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}.parquet')

    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)

    # Filter to MF 4+ occupied
    df = filter_mf_occupied(df)

    # Filter to applicable (for upgrades)
    if upgrade_id > 0:
        df = df[df['applicability'] == True]

    # Merge cluster_name
    df = df.merge(
        cluster_lookup,
        left_on='in.county',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows where ALL fuel-type EUIs are null
    fuel_cols = list(FUEL_TYPES.values())
    df = df.dropna(subset=fuel_cols, how='all')

    # Fill individual null fuel EUIs with 0 (building doesn't use that fuel)
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

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

def get_group_for_upgrade(uid):
    for group, uids in TUNE_GROUPS.items():
        if uid in uids:
            return group
    return 'envelope'  # fallback


def train_all(upgrade_ids, tune_trials=50, skip_tuning=False):
    """Train models for specified upgrade IDs."""
    total_start = time.time()

    upgrades_lookup = load_upgrades_lookup(UPGRADES_JSON)
    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: Tune hyperparameters
    print("=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ResStock MF)")
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

            if len(X_enc) > 30000:
                idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
                X_tune, y_tune = X_enc.iloc[idx], y[idx]
            else:
                X_tune, y_tune = X_enc, y

            params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
            tuned_params[group] = params
            print(f"  Best params: {params}")

        params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters.json')
        with open(params_path, 'w') as f:
            json.dump({k: v for k, v in tuned_params.items() if v is not None}, f, indent=2)

    # Phase 2: Train all models (one per fuel type per upgrade)
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ResStock MF, per fuel type)")
    print("=" * 70)

    all_results = []
    from sklearn.model_selection import train_test_split
    n_models_trained = 0

    for uid in upgrade_ids:
        measure_name = upgrades_lookup.get(str(uid), f'upgrade_{uid}')
        group = get_group_for_upgrade(uid)
        params = tuned_params.get(group)

        if params is None:
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

    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_summary.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description='Train ResStock MF upgrade models')
    parser.add_argument('--upgrades', nargs='+', type=int, default=None,
                        help='Specific upgrade IDs to train (default: all 0-32)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials per tuning group (default: 50)')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    if args.upgrades is None:
        upgrade_ids = list(range(0, 33))
    else:
        upgrade_ids = args.upgrades

    print(f"Training {len(upgrade_ids)} ResStock MF upgrades x {len(FUEL_TYPES)} fuel types")
    print(f"Output directory: {OUTPUT_DIR}")

    train_all(upgrade_ids, tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
