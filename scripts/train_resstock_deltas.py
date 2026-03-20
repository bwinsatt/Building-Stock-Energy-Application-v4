#!/usr/bin/env python3
"""
Train XGBoost delta/savings models for ResStock 2025 R1 upgrade measures (Multi-Family 4+ units).
Produces 4 models per upgrade (one per fuel type) targeting per-fuel savings
(baseline EUI - upgrade EUI) instead of absolute post-upgrade EUI.

Usage:
    python3 scripts/train_resstock_deltas.py                    # Train all (with tuning)
    python3 scripts/train_resstock_deltas.py --upgrades 4 13 17 # Train specific upgrades
    python3 scripts/train_resstock_deltas.py --skip-tuning      # Use saved hyperparameters
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
    prepare_catboost_data, train_lightgbm_model, train_catboost_model,
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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
    'floor_plate_sqft',
    # --- Baseline EUI features ---
    'baseline_electricity',
    'baseline_natural_gas',
    'baseline_fuel_oil',
    'baseline_propane',
]

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

# Columns to load from parquet (cluster_name is derived from county join)
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + FEATURE_COLS + list(FUEL_TYPES.values()) + [
    'in.heating_setpoint', 'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude', 'in.cooling_setpoint_offset_magnitude',
]
LOAD_COLS = [c for c in LOAD_COLS if c not in ('cluster_name', 'hdd65f', 'cdd65f',
                                                 'floor_plate_sqft',
                                                 'baseline_electricity', 'baseline_natural_gas',
                                                 'baseline_fuel_oil', 'baseline_propane')]
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))  # deduplicate while preserving order

# Hyperparameter tuning groups (same grouping as absolute models)
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
    'hvac': 4,           # Cold Climate ASHP
    'water_heating': 9,  # HPWH
    'envelope': 17,      # Windows (100% applicability)
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
    units = df['in.geometry_building_number_units_mf'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    mf_mask = units >= 4
    occ_mask = df['in.vacancy_status'] == 'Occupied'
    return df[mf_mask & occ_mask].copy()


def load_baseline_data(cluster_lookup):
    """Load baseline (upgrade 0) data, filtered and with cluster_name."""
    fname = os.path.join(RAW_DIR, 'upgrade0.parquet')
    df = pd.read_parquet(fname, columns=LOAD_COLS)
    df = filter_mf_occupied(df)

    # Merge cluster_name
    df = df.merge(
        cluster_lookup,
        left_on='in.county',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Fill null fuel EUIs with 0
    for col in FUEL_TYPES.values():
        df[col] = df[col].fillna(0)

    # Join HDD/CDD from cluster_hdd_cdd.json (built by scripts/build_hdd_cdd_lookup.py)
    hdd_cdd_path = os.path.join(PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json')
    with open(hdd_cdd_path) as f:
        cluster_hdd_cdd = json.load(f)
    df['hdd65f'] = df['cluster_name'].map(lambda c: cluster_hdd_cdd.get(c, {}).get('hdd65f', 4800.0))
    df['cdd65f'] = df['cluster_name'].map(lambda c: cluster_hdd_cdd.get(c, {}).get('cdd65f', 1400.0))

    # Derived features
    df['floor_plate_sqft'] = pd.to_numeric(df['in.sqft..ft2'], errors='coerce') / pd.to_numeric(df['in.geometry_stories'], errors='coerce').clip(lower=1)

    # Baseline EUI features are NaN for upgrade 0
    for fuel_name in FUEL_TYPES:
        df[f'baseline_{fuel_name}'] = float('nan')

    return df


def load_paired_data(upgrade_id, df_baseline, cluster_lookup):
    """Load upgrade parquet, join with baseline on bldg_id, compute deltas.

    Returns:
        df: DataFrame with features and delta_{fuel} columns
        n_applicable: number of applicable buildings before join
        n_paired: final paired count
    """
    fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}.parquet')
    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    # Load only bldg_id, applicability, and fuel columns from upgrade
    upgrade_load_cols = ['bldg_id', 'applicability'] + list(FUEL_TYPES.values())
    df_upg = pd.read_parquet(fname, columns=upgrade_load_cols)

    # Filter to applicable
    df_upg = df_upg[df_upg['applicability'] == True]
    n_applicable = len(df_upg)

    # Rename upgrade fuel columns
    fuel_rename = {col: f"upgrade_{col}" for col in FUEL_TYPES.values()}
    df_upg = df_upg.rename(columns=fuel_rename)
    df_upg = df_upg.drop(columns=['applicability'])

    # Fill null upgrade fuel EUIs with 0
    for col in fuel_rename.values():
        df_upg[col] = df_upg[col].fillna(0)

    # Inner join with baseline on bldg_id
    df = df_baseline.merge(df_upg, on='bldg_id', how='inner')
    n_paired = len(df)

    # Compute deltas (positive = energy saved)
    for fuel_name, fuel_col in FUEL_TYPES.items():
        df[f"delta_{fuel_name}"] = df[fuel_col] - df[f"upgrade_{fuel_col}"]

    # Rename baseline fuel columns for use as features
    FUEL_COL_MAP = {
        'out.electricity.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_electricity',
        'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_natural_gas',
        'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_fuel_oil',
        'out.propane.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_propane',
    }
    for orig_col, new_col in FUEL_COL_MAP.items():
        if orig_col in df.columns:
            df[new_col] = df[orig_col]

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'applicability',
                           'in.geometry_building_number_units_mf', 'in.vacancy_status',
                           'in.county', 'nhgis_county_gisjoin'],
                  errors='ignore')

    # Drop upgrade fuel columns (no longer needed)
    for col in fuel_rename.values():
        df = df.drop(columns=[col], errors='ignore')

    return df, n_applicable, n_paired


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def get_group_for_upgrade(uid):
    for group, uids in TUNE_GROUPS.items():
        if uid in uids:
            return group
    return 'envelope'  # fallback


def train_all(upgrade_ids, tune_trials=50, skip_tuning=False):
    """Train delta models for specified upgrade IDs."""
    total_start = time.time()

    upgrades_lookup = load_upgrades_lookup(UPGRADES_JSON)
    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load baseline once (reused for all upgrades)
    print("Loading baseline data (upgrade 0)...")
    df_baseline = load_baseline_data(cluster_lookup)
    print(f"  Baseline buildings (MF 4+ occupied): {len(df_baseline)}")

    # Phase 1: Tune hyperparameters
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ResStock MF, delta targets)")
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

    # Phase 2: Train all delta models
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ResStock MF, delta/savings per fuel type)")
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

        # Encode features for XGBoost/LightGBM
        X_enc, encoders = encode_features(df, FEATURE_COLS)
        cat_indices = [i for i, col in enumerate(FEATURE_COLS) if col in CAT_FEATURE_NAMES]

        # Prepare CatBoost data (string categoricals)
        X_cb = prepare_catboost_data(df, FEATURE_COLS, CAT_FEATURE_NAMES)

        # Same train/test split
        train_idx, test_idx = train_test_split(
            np.arange(len(X_enc)), test_size=0.2, random_state=42
        )

        for fuel_name in FUEL_TYPES:
            target_col = f"delta_{fuel_name}"
            y = df[target_col].values
            y_train, y_test = y[train_idx], y[test_idx]

            # Skip if all targets are constant (no signal to learn)
            if np.std(y_train) < 1e-10:
                print(f"  {fuel_name:>18}: SKIPPED (constant target)")
                continue

            trained_models = []

            # Train XGBoost
            t0 = time.time()
            xgb_model = train_single_model(X_enc.iloc[train_idx], y_train, params)
            xgb_metrics = evaluate_model(xgb_model, X_enc.iloc[test_idx], y_test)
            trained_models.append(('XGB', xgb_model, xgb_metrics))

            # Train LightGBM
            try:
                t0 = time.time()
                lgbm_model = train_lightgbm_model(X_enc.iloc[train_idx], y_train, params, cat_indices)
                lgbm_metrics = evaluate_model(lgbm_model, X_enc.iloc[test_idx], y_test)
                trained_models.append(('LGBM', lgbm_model, lgbm_metrics))
            except Exception as e:
                print(f"  {fuel_name:>18}: LGBM skipped ({e})")

            # Train CatBoost
            try:
                t0 = time.time()
                cb_model = train_catboost_model(X_cb.iloc[train_idx], y_train, params, cat_indices)
                cb_metrics = evaluate_model(cb_model, X_cb.iloc[test_idx], y_test)
                trained_models.append(('CB', cb_model, cb_metrics))
            except Exception as e:
                print(f"  {fuel_name:>18}: CB skipped ({e})")

            mae_parts = [f"{p}={m['mae_kbtu_sf']:5.2f}" for p, _, m in trained_models]
            print(f"  {fuel_name:>18}: {' '.join(mae_parts)} kBtu/sf")

            # Save trained models
            for prefix, model, metrics in trained_models:
                model_name = f'{prefix}_upgrade{uid}_{fuel_name}'
                save_model_artifacts(model, encoders, FEATURE_COLS, metrics, OUTPUT_DIR, model_name)
                n_models_trained += 1

                all_results.append({
                    'upgrade_id': uid,
                    'measure_name': measure_name,
                    'fuel_type': fuel_name,
                    'group': group,
                    'model_prefix': prefix,
                    'status': 'success',
                    'model_type': 'delta',
                    'n_applicable': n_applicable,
                    'n_paired': n_paired,
                    'test_mae_kbtu_sf': metrics['mae_kbtu_sf'],
                    'test_r2': metrics['r2'],
                    'test_rmse_kwh_ft2': metrics['rmse_kwh_ft2'],
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


def main():
    parser = argparse.ArgumentParser(description='Train ResStock MF delta/savings models')
    parser.add_argument('--upgrades', nargs='+', type=int, default=None,
                        help='Specific upgrade IDs to train (default: all 1-32)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials per tuning group (default: 50)')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Load saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    if args.upgrades is None:
        # All upgrades except 0 (baseline has no delta)
        upgrade_ids = list(range(1, 33))
    else:
        upgrade_ids = args.upgrades

    print(f"Training {len(upgrade_ids)} ResStock MF delta models x {len(FUEL_TYPES)} fuel types")
    print(f"Output directory: {OUTPUT_DIR}")

    train_all(upgrade_ids, tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
