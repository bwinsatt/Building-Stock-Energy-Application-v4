#!/usr/bin/env python3
"""
Train XGBoost delta/savings models for ComStock 2025 R3 upgrade measures.
Produces 5 models per upgrade (one per fuel type) targeting per-fuel savings
(baseline EUI - upgrade EUI) instead of absolute post-upgrade EUI.

Usage:
    python3 scripts/train_comstock_deltas.py                    # Train all (with tuning)
    python3 scripts/train_comstock_deltas.py --upgrades 4 13 17 # Train specific upgrades
    python3 scripts/train_comstock_deltas.py --skip-tuning      # Use saved hyperparameters
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

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
UPGRADES_JSON = os.path.join(RAW_DIR, 'upgrades_lookup.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3')

# Per-fuel-type EUI target columns (5 fuels including district_heating)
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

# Columns to load from parquet (cluster_name is derived from county join)
LOAD_COLS = ['bldg_id', 'completed_status', 'applicability',
             'in.as_simulated_nhgis_county_gisjoin'] + FEATURE_COLS + list(FUEL_TYPES.values())
LOAD_COLS = [c for c in LOAD_COLS if c != 'cluster_name']

# Hyperparameter tuning groups (same grouping as absolute models)
TUNE_GROUPS = {
    'baseline': [0],
    'hvac': list(range(1, 32)),
    'demand_flex': list(range(32, 43)),
    'lighting': [43, 44],
    'other': [45, 46, 47],
    'envelope': list(range(48, 54)),
    'packages': list(range(54, 66)),
}
TUNE_REPRESENTATIVES = {
    'hvac': 1,
    'demand_flex': 32,
    'lighting': 43,
    'envelope': 49,
    'packages': 55,
    'other': 46,
}


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_baseline_data(cluster_lookup):
    """Load baseline (upgrade 0) aggregated data with cluster_name."""
    fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    df = pd.read_parquet(fname, columns=LOAD_COLS)

    # Deduplicate by bldg_id (ComStock has duplicate rows with different weights)
    df = df.drop_duplicates(subset='bldg_id')

    # Merge cluster_name from spatial lookup
    df = df.merge(
        cluster_lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
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

    return df


def load_paired_data(upgrade_id, df_baseline, cluster_lookup):
    """Load upgrade parquet, join with baseline on bldg_id, compute deltas.

    Returns:
        df: DataFrame with features and delta_{fuel} columns
        n_applicable: number of applicable buildings before join
        n_paired: final paired count
    """
    fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}_agg.parquet')
    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    # Load only bldg_id, status, applicability, and fuel columns from upgrade
    upgrade_load_cols = ['bldg_id', 'completed_status', 'applicability'] + list(FUEL_TYPES.values())
    df_upg = pd.read_parquet(fname, columns=upgrade_load_cols)

    # Deduplicate by bldg_id
    df_upg = df_upg.drop_duplicates(subset='bldg_id')

    # Filter to successful simulations with applicable upgrades
    df_upg = df_upg[df_upg['completed_status'] == 'Success']
    df_upg = df_upg[df_upg['applicability'] == True]
    n_applicable = len(df_upg)

    # Rename upgrade fuel columns
    fuel_rename = {col: f"upgrade_{col}" for col in FUEL_TYPES.values()}
    df_upg = df_upg.rename(columns=fuel_rename)
    df_upg = df_upg.drop(columns=['completed_status', 'applicability'])

    # Fill null upgrade fuel EUIs with 0
    for col in fuel_rename.values():
        df_upg[col] = df_upg[col].fillna(0)

    # Inner join with baseline on bldg_id
    df = df_baseline.merge(df_upg, on='bldg_id', how='inner')
    n_paired = len(df)

    # Compute deltas (positive = energy saved)
    for fuel_name, fuel_col in FUEL_TYPES.items():
        df[f"delta_{fuel_name}"] = df[fuel_col] - df[f"upgrade_{fuel_col}"]

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'completed_status', 'applicability',
                           'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
                  errors='ignore')

    # Drop upgrade fuel columns (no longer needed)
    for col in fuel_rename.values():
        df = df.drop(columns=[col], errors='ignore')

    return df, n_applicable, n_paired


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def get_group_for_upgrade(uid):
    """Find which tuning group an upgrade belongs to."""
    for group, uids in TUNE_GROUPS.items():
        if uid in uids:
            return group
    return 'other'  # fallback


def train_all(upgrade_ids, tune_trials=50, skip_tuning=False):
    """Train delta models for specified upgrade IDs."""
    total_start = time.time()

    upgrades_lookup = load_upgrades_lookup(UPGRADES_JSON)
    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load baseline once (reused for all upgrades)
    print("Loading baseline data (upgrade 0)...")
    df_baseline = load_baseline_data(cluster_lookup)
    print(f"  Baseline buildings: {len(df_baseline)}")

    # Phase 1: Tune hyperparameters
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ComStock, delta targets)")
    print("=" * 70)

    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters_delta.json')

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
        # Remove 'baseline' — no delta model for baseline
        groups_needed.discard('baseline')

        # Tune on electricity delta (largest signal)
        for group in groups_needed:
            if group not in TUNE_REPRESENTATIVES:
                print(f"\n  No tuning representative for group '{group}', using defaults.")
                tuned_params[group] = None
                continue

            rep_uid = TUNE_REPRESENTATIVES[group]
            print(f"\nTuning group '{group}' using upgrade {rep_uid} "
                  f"({upgrades_lookup.get(str(rep_uid), '?')})...")

            df, n_applicable, n_paired = load_paired_data(rep_uid, df_baseline, cluster_lookup)
            if df is None or n_paired < 100:
                print(f"  Insufficient data ({n_paired} rows). Using defaults.")
                tuned_params[group] = None
                continue

            X_enc, _ = encode_features(df, FEATURE_COLS)
            y = df['delta_electricity'].values

            if len(X_enc) > 30000:
                idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
                X_tune, y_tune = X_enc.iloc[idx], y[idx]
            else:
                X_tune, y_tune = X_enc, y

            params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
            tuned_params[group] = params
            print(f"  Best params: {params}")

        with open(params_path, 'w') as f:
            json.dump({k: v for k, v in tuned_params.items() if v is not None}, f, indent=2)
        print(f"\nSaved tuned params to {params_path}")

    # Phase 2: Train all delta models
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ComStock, delta/savings per fuel type)")
    print("=" * 70)

    all_results = []
    from sklearn.model_selection import train_test_split
    n_models_trained = 0

    for uid in upgrade_ids:
        if uid == 0:
            print(f"\n  Skipping upgrade 0 (baseline) — no delta model needed.")
            continue

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

        df, n_applicable, n_paired = load_paired_data(uid, df_baseline, cluster_lookup)
        if df is None or n_paired < 50:
            print(f"  SKIPPED: insufficient data ({n_paired} rows)")
            all_results.append({
                'upgrade_id': uid, 'measure_name': measure_name,
                'fuel_type': 'all', 'status': 'skipped',
                'reason': f'insufficient data ({n_paired} rows)',
            })
            continue

        # Encode features once per upgrade
        X_enc, encoders = encode_features(df, FEATURE_COLS)

        # Same train/test split for all fuel types
        train_idx, test_idx = train_test_split(
            np.arange(len(X_enc)), test_size=0.2, random_state=42
        )
        X_train, X_test = X_enc.iloc[train_idx], X_enc.iloc[test_idx]

        for fuel_name in FUEL_TYPES:
            target_col = f"delta_{fuel_name}"
            y = df[target_col].values
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

            # Save with same naming convention
            model_name = f'XGB_upgrade{uid}_{fuel_name}'
            save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                                 OUTPUT_DIR, model_name)
            n_models_trained += 1

            all_results.append({
                'upgrade_id': uid,
                'measure_name': measure_name,
                'fuel_type': fuel_name,
                'group': group,
                'status': 'success',
                'model_type': 'delta',
                'n_applicable': n_applicable,
                'n_paired': n_paired,
                'train_mae_kbtu_sf': train_metrics['mae_kbtu_sf'],
                'train_r2': train_metrics['r2'],
                'test_mae_kbtu_sf': test_metrics['mae_kbtu_sf'],
                'test_r2': test_metrics['r2'],
                'test_rmse_kwh_ft2': test_metrics['rmse_kwh_ft2'],
                'train_time_s': train_time,
            })

        print(f"  Samples: {n_paired} paired buildings")

    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_delta.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} delta models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train ComStock delta/savings models')
    parser.add_argument('--upgrades', nargs='+', type=int, default=None,
                        help='Specific upgrade IDs to train (default: all 1-65)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials per tuning group (default: 50)')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    if args.upgrades is None:
        # All upgrades except 0 (baseline has no delta)
        upgrade_ids = list(range(1, 66))
    else:
        upgrade_ids = args.upgrades

    print(f"Training {len(upgrade_ids)} ComStock delta models x {len(FUEL_TYPES)} fuel types")
    print(f"Output directory: {OUTPUT_DIR}")
    if not args.skip_tuning:
        print(f"Tune trials per group: {args.tune_trials}")

    train_all(upgrade_ids, tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
