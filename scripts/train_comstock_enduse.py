#!/usr/bin/env python3
"""
Train XGBoost end-use baseline models for ComStock 2025 R3.

Produces one ensemble (XGB + LGBM + CB) per granular end-use category,
targeting absolute EUI in kWh/ft2 (sum across all fuel types for that end use).
These models sit alongside existing fuel-type baseline models and provide
end-use proportional breakdown.

Usage:
    python3 scripts/train_comstock_enduse.py                  # Train all
    python3 scripts/train_comstock_enduse.py --enduses heating cooling  # Specific
    python3 scripts/train_comstock_enduse.py --skip-tuning    # Use saved hyperparameters
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from datetime import timedelta
from sklearn.model_selection import train_test_split

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import (
    encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
    prepare_catboost_data, train_lightgbm_model, train_catboost_model,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_EndUse')
GROUPING_PATH = os.path.join(
    PROJECT_ROOT, 'backend', 'app', 'data', 'enduse_grouping.json'
)

# All ComStock fuel types whose per-end-use columns we sum
FUEL_TYPES = [
    'electricity', 'natural_gas', 'fuel_oil',
    'propane', 'district_heating', 'district_cooling',
]

# Same 31 baseline features used by existing upgrade-0 fuel-type models
# (27 original + hdd65f, cdd65f, weekend_operating_hours, floor_plate_sqft)
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
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'hdd65f',
    'cdd65f',
    'in.weekend_operating_hours..hr',
    'floor_plate_sqft',
]

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
    'in.weekend_operating_hours..hr',
]


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_enduse_config():
    """Load the list of end uses to train from the grouping config."""
    with open(GROUPING_PATH) as f:
        cfg = json.load(f)
    return cfg['comstock']['trained_enduses']


def get_enduse_columns(enduse_name):
    """Return all fuel-specific parquet column names for a given end use."""
    cols = []
    for fuel in FUEL_TYPES:
        cols.append(f'out.{fuel}.{enduse_name}.energy_consumption_intensity..kwh_per_ft2')
    return cols


def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(
        LOOKUP_PATH,
        usecols=['nhgis_county_gisjoin', 'cluster_name'],
        low_memory=False,
    )
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_baseline_data(enduses_to_train):
    """Load baseline data with all needed feature + end-use target columns."""
    # Determine which parquet columns to load (exclude derived features)
    feature_load_cols = [c for c in FEATURE_COLS
                         if c not in ('cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft')]
    meta_cols = ['bldg_id', 'in.as_simulated_nhgis_county_gisjoin']
    enduse_cols = []
    for eu in enduses_to_train:
        enduse_cols.extend(get_enduse_columns(eu))

    # Load HDD/CDD from parquet under their raw column names
    hdd_cdd_raw = ['out.params.hdd65f', 'out.params.cdd65f']

    # Only load columns that exist in the parquet
    fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    available = set(pd.read_parquet(fname, columns=[]).columns)

    # Check for required HDD/CDD columns early
    missing_hdd_cdd = [c for c in hdd_cdd_raw if c not in available]
    if missing_hdd_cdd:
        raise ValueError(
            f"Expected HDD/CDD columns not found in parquet: {missing_hdd_cdd}. "
            f"Check that upgrade0_agg.parquet contains 'out.params.*' columns."
        )

    load_cols = list(dict.fromkeys(
        meta_cols + feature_load_cols + [c for c in enduse_cols + hdd_cdd_raw if c in available]
    ))

    df = pd.read_parquet(fname, columns=load_cols)
    df = df.drop_duplicates(subset='bldg_id')

    # Merge cluster_name
    cluster_lookup = load_cluster_lookup()
    df = df.merge(
        cluster_lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
        right_on='nhgis_county_gisjoin',
        how='left',
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Rename HDD/CDD to match feature names
    df = df.rename(columns={
        'out.params.hdd65f': 'hdd65f',
        'out.params.cdd65f': 'cdd65f',
    })

    # Clean weekend_operating_hours sentinel values (999 = no data → NaN)
    if 'in.weekend_operating_hours..hr' in df.columns:
        df['in.weekend_operating_hours..hr'] = pd.to_numeric(
            df['in.weekend_operating_hours..hr'], errors='coerce'
        )
        df.loc[df['in.weekend_operating_hours..hr'] >= 999, 'in.weekend_operating_hours..hr'] = float('nan')

    # Derived geometry feature
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.number_stories'], errors='coerce').clip(lower=1)
    )

    # Compute summed end-use targets (across all fuels)
    for eu in enduses_to_train:
        target_col = f'enduse_{eu}'
        df[target_col] = 0.0
        for fuel in FUEL_TYPES:
            src = f'out.{fuel}.{eu}.energy_consumption_intensity..kwh_per_ft2'
            if src in df.columns:
                df[target_col] += df[src].fillna(0)

    print(f"Loaded {len(df):,} baseline buildings")
    return df


# ==============================================================================
# TRAINING
# ==============================================================================

def train_all(enduses_to_train, skip_tuning=False):
    """Train one ensemble per end use."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    hp_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters_enduse.json')

    df = load_baseline_data(enduses_to_train)

    # --- Phase 1: Hyperparameter tuning (use 'heating' as representative) ---
    if not skip_tuning:
        print("\n=== Phase 1: Hyperparameter Tuning ===")
        target_col = 'enduse_heating'
        if target_col not in df.columns or df[target_col].std() < 1e-10:
            print("WARNING: heating target not available for tuning, using first end use")
            target_col = f'enduse_{enduses_to_train[0]}'

        X = df[FEATURE_COLS].copy()
        y = df[target_col]
        mask = y.notna()
        X, y = X[mask], y[mask]

        X_enc, _ = encode_features(X, FEATURE_COLS)
        best_params = tune_hyperparameters(X_enc, y, n_trials=50)

        with open(hp_path, 'w') as f:
            json.dump(best_params, f, indent=2)
        print(f"Saved hyperparameters to {hp_path}")
    else:
        with open(hp_path) as f:
            best_params = json.load(f)
        print(f"Loaded hyperparameters from {hp_path}")

    # --- Phase 2: Train each end use ---
    print("\n=== Phase 2: Training End-Use Models ===")
    results = {}
    total_start = time.time()

    for eu in enduses_to_train:
        target_col = f'enduse_{eu}'
        y = df[target_col]

        # Skip if target is missing or constant
        if y.isna().all() or y.std() < 1e-10:
            print(f"\n  SKIP {eu}: constant or all-NaN target")
            continue

        # Build training data
        mask = y.notna()
        X = df.loc[mask, FEATURE_COLS].copy()
        y = y[mask]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print(f"\n  Training: {eu} (n={len(X_train):,} train, {len(X_test):,} test)")
        eu_start = time.time()

        # Encode for XGBoost/LightGBM
        X_train_enc, encoders = encode_features(X_train, FEATURE_COLS)
        X_test_enc, _ = encode_features(X_test, FEATURE_COLS, encoders=encoders)

        # XGBoost
        cat_indices = [i for i, c in enumerate(FEATURE_COLS) if c in CAT_FEATURE_NAMES]
        xgb_model = train_single_model(X_train_enc, y_train, best_params)
        xgb_metrics = evaluate_model(xgb_model, X_test_enc, y_test)
        save_model_artifacts(
            xgb_model, encoders, FEATURE_COLS, xgb_metrics,
            OUTPUT_DIR, f'XGB_enduse_{eu}'
        )

        # LightGBM
        lgbm_metrics = None
        try:
            lgbm_model = train_lightgbm_model(X_train_enc, y_train, best_params, cat_indices)
            lgbm_metrics = evaluate_model(lgbm_model, X_test_enc, y_test)
            save_model_artifacts(
                lgbm_model, encoders, FEATURE_COLS, lgbm_metrics,
                OUTPUT_DIR, f'LGBM_enduse_{eu}'
            )
        except Exception as e:
            print(f"    LGBM skipped ({e})")

        # CatBoost
        cb_metrics = None
        try:
            X_train_cb = prepare_catboost_data(X_train, FEATURE_COLS, CAT_FEATURE_NAMES)
            X_test_cb = prepare_catboost_data(X_test, FEATURE_COLS, CAT_FEATURE_NAMES)
            cb_model = train_catboost_model(X_train_cb, y_train, best_params, cat_indices)
            cb_metrics = evaluate_model(cb_model, X_test_cb, y_test)
            save_model_artifacts(
                cb_model, encoders, FEATURE_COLS, cb_metrics,
                OUTPUT_DIR, f'CB_enduse_{eu}'
            )
        except Exception as e:
            print(f"    CB skipped ({e})")

        elapsed = time.time() - eu_start
        results[eu] = {
            'xgb_r2': xgb_metrics['r2'],
            'lgbm_r2': lgbm_metrics['r2'] if lgbm_metrics else None,
            'cb_r2': cb_metrics['r2'] if cb_metrics else None,
            'xgb_mae_kbtu': xgb_metrics['mae_kbtu_sf'],
            'n_samples': len(X_train) + len(X_test),
            'elapsed_s': round(elapsed, 1),
        }
        lgbm_r2_str = f"{lgbm_metrics['r2']:.3f}" if lgbm_metrics else 'N/A'
        cb_r2_str = f"{cb_metrics['r2']:.3f}" if cb_metrics else 'N/A'
        print(f"    XGB R²={xgb_metrics['r2']:.3f}  LGBM R²={lgbm_r2_str}  "
              f"CB R²={cb_r2_str}  MAE={xgb_metrics['mae_kbtu_sf']:.2f} kBtu/sf  "
              f"({elapsed:.0f}s)")

    total_elapsed = time.time() - total_start
    print(f"\n=== Done: {len(results)} end-use models trained in "
          f"{timedelta(seconds=int(total_elapsed))} ===")

    # Save summary
    summary_path = os.path.join(OUTPUT_DIR, 'training_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Summary saved to {summary_path}")


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train ComStock end-use baseline models')
    parser.add_argument('--enduses', nargs='+', help='Specific end uses to train')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Use saved hyperparameters instead of re-tuning')
    args = parser.parse_args()

    enduses_to_train = args.enduses or load_enduse_config()
    print(f"End uses to train: {enduses_to_train}")

    train_all(enduses_to_train, skip_tuning=args.skip_tuning)
