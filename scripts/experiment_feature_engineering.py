#!/usr/bin/env python3
"""
Experiment: Feature Engineering Validation
Tests whether new features (HDD/CDD, thermostat setpoints, derived features)
improve baseline EUI prediction accuracy vs. the existing feature set.

Runs on the full ComStock dataset (~91K buildings) by default.
Does NOT modify any training scripts or app code.

Usage:
    python3 scripts/experiment_feature_engineering.py
    python3 scripts/experiment_feature_engineering.py --sample-size 10000  # faster
"""
import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Project root = worktree root (scripts/../)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

# Try imports — fail fast with clear message
try:
    from xgboost import XGBRegressor
except ImportError:
    sys.exit("Missing xgboost: pip install xgboost")
try:
    from lightgbm import LGBMRegressor
except ImportError:
    sys.exit("Missing lightgbm: pip install lightgbm")
try:
    from catboost import CatBoostRegressor
except ImportError:
    sys.exit("Missing catboost: pip install catboost")


# =============================================================================
# FIND COMSTOCK ROOT (handles worktree nesting)
# =============================================================================

def find_comstock_root():
    """
    Return the directory that contains the 'ComStock' subdirectory.

    Check PROJECT_ROOT first (normal case), then walk up the directory tree
    to handle worktrees nested inside .claude/worktrees/<name>/.
    """
    candidate = PROJECT_ROOT
    for _ in range(6):  # walk up at most 6 levels
        if os.path.isdir(os.path.join(candidate, 'ComStock')):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    raise FileNotFoundError(
        "Could not find a 'ComStock' directory at or above: "
        f"{PROJECT_ROOT}\n"
        "Make sure you are running this script from within the project tree."
    )


# =============================================================================
# FEATURE CONFIGURATION
# =============================================================================

FUEL_TARGETS = {
    'electricity':   'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    'natural_gas':   'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
}

# Baseline features (same as existing experiment / training pipeline)
OLD_FEATURE_COLS = [
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

# New features to add (all numeric — no new categoricals)
NEW_FEATURES = [
    'hdd65f',                            # renamed from out.params.hdd65f
    'cdd65f',                            # renamed from out.params.cdd65f
    'in.tstat_clg_sp_f..f',             # cooling setpoint
    'in.tstat_htg_sp_f..f',             # heating setpoint
    'in.tstat_clg_delta_f..delta_f',    # cooling setback delta
    'in.tstat_htg_delta_f..delta_f',    # heating setback delta
    'in.weekend_operating_hours..hr',   # weekend operating hours
    'floor_plate_sqft',                  # derived: sqft / stories
]

NEW_FEATURE_COLS = OLD_FEATURE_COLS + NEW_FEATURES

# Categorical columns (same for both old and new — all new features are numeric)
CAT_FEATURE_NAMES = [
    'in.comstock_building_type_group',
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
    'in.building_subtype',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
]


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(sample_size):
    """Load ComStock baseline, join clusters, engineer new features."""
    comstock_root = find_comstock_root()
    raw_dir = os.path.join(comstock_root, 'ComStock', 'raw_data')
    lookup_path = os.path.join(comstock_root, 'ComStock', 'spatial_tract_lookup_table.csv')

    print("Loading baseline data...")

    # Columns to load: all old features + new parquet columns + targets + metadata
    parquet_new_cols = [
        'out.params.hdd65f',
        'out.params.cdd65f',
        'in.tstat_clg_sp_f..f',
        'in.tstat_htg_sp_f..f',
        'in.tstat_clg_delta_f..delta_f',
        'in.tstat_htg_delta_f..delta_f',
        'in.weekend_operating_hours..hr',
    ]
    load_cols = (
        ['bldg_id', 'in.as_simulated_nhgis_county_gisjoin']
        + [c for c in OLD_FEATURE_COLS if c != 'cluster_name']
        + parquet_new_cols
        + list(FUEL_TARGETS.values())
    )
    # Deduplicate while preserving order
    seen = set()
    load_cols_dedup = []
    for c in load_cols:
        if c not in seen:
            seen.add(c)
            load_cols_dedup.append(c)

    df = pd.read_parquet(
        os.path.join(raw_dir, 'upgrade0_agg.parquet'),
        columns=load_cols_dedup,
    )
    df = df.drop_duplicates(subset='bldg_id')

    # Join cluster_name
    lookup = pd.read_csv(
        lookup_path,
        usecols=['nhgis_county_gisjoin', 'cluster_name'],
        low_memory=False,
    )
    lookup = lookup.drop_duplicates(subset='nhgis_county_gisjoin')
    df = df.merge(
        lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
        right_on='nhgis_county_gisjoin',
        how='left',
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows with all-null targets
    fuel_cols = list(FUEL_TARGETS.values())
    df = df.dropna(subset=fuel_cols, how='all')
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

    # Rename HDD/CDD columns
    df = df.rename(columns={
        'out.params.hdd65f': 'hdd65f',
        'out.params.cdd65f': 'cdd65f',
    })

    # Clean thermostat columns: convert from string to numeric, replace 999 sentinel → NaN
    # ComStock uses 999 to indicate "no thermostat data" for ~26% of buildings
    tstat_cols = [
        'in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
        'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
        'in.weekend_operating_hours..hr',
    ]
    for col in tstat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df.loc[df[col] >= 999, col] = float('nan')

    n_nan_tstat = df['in.tstat_htg_sp_f..f'].isna().sum() if 'in.tstat_htg_sp_f..f' in df.columns else 0
    print(f"  Thermostat sentinels cleaned: {n_nan_tstat:,} buildings ({n_nan_tstat/len(df)*100:.1f}%) have NaN setpoints")

    # Derive floor_plate_sqft
    stories = pd.to_numeric(df['in.number_stories'], errors='coerce').fillna(1).clip(lower=1)
    df['floor_plate_sqft'] = pd.to_numeric(df['in.sqft..ft2'], errors='coerce') / stories

    # Drop metadata cols used only for joining
    df = df.drop(
        columns=['bldg_id', 'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
        errors='ignore',
    )

    print(f"  Full dataset: {len(df):,} buildings")

    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)
        print(f"  Sampled down to: {len(df):,} buildings")

    return df


# =============================================================================
# MODEL BUILDERS
# =============================================================================

def build_xgboost(X_train, y_train, cat_indices):
    """Train XGBoost with categorical support."""
    model = XGBRegressor(
        objective='reg:squarederror',
        n_estimators=300, max_depth=6, learning_rate=0.1,
        min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
        random_state=42, n_jobs=-1, enable_categorical=True,
    )
    model.fit(X_train, y_train)
    return model


def build_lightgbm(X_train, y_train, cat_indices):
    """Train LightGBM with categorical support."""
    model = LGBMRegressor(
        objective='regression',
        n_estimators=300, max_depth=6, learning_rate=0.1,
        min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
        random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_train, y_train, categorical_feature=cat_indices)
    return model


def build_catboost(X_train, y_train, cat_indices):
    """Train CatBoost with native categorical support."""
    model = CatBoostRegressor(
        iterations=300, depth=6, learning_rate=0.1,
        random_seed=42, verbose=0, cat_features=cat_indices,
    )
    model.fit(X_train, y_train)
    return model


# =============================================================================
# DATA PREPARATION HELPERS
# =============================================================================

def encode_features_preserve_nan(df, feature_cols, cat_feature_names):
    """
    Encode features for XGBoost/LightGBM, preserving NaN in numeric columns.
    XGBoost and LightGBM handle NaN natively — fillna(0) destroys that signal.
    """
    df_enc = df[feature_cols].copy()
    encoders = {}
    for col in feature_cols:
        if col in cat_feature_names:
            df_enc[col] = df_enc[col].astype(str)
            categories = sorted(df_enc[col].unique().tolist())
            encoders[col] = categories
            df_enc[col] = pd.Categorical(df_enc[col], categories=categories)
        else:
            df_enc[col] = pd.to_numeric(df_enc[col], errors='coerce')
            # DO NOT fillna — XGBoost/LightGBM handle NaN natively
    return df_enc, encoders


def prepare_catboost_data(df, feature_cols, cat_feature_names):
    """
    Prepare DataFrame for CatBoost: string categoricals, numeric numerics.
    CatBoost requires string-typed categoricals, NOT pd.Categorical.
    Preserves NaN for numeric columns (CatBoost handles them natively).
    """
    df_cb = df[feature_cols].copy()
    for col in feature_cols:
        if col in cat_feature_names:
            df_cb[col] = df_cb[col].astype(str)
        else:
            df_cb[col] = pd.to_numeric(df_cb[col], errors='coerce')
            # DO NOT fillna — CatBoost handles NaN natively
    return df_cb


# =============================================================================
# EVALUATION
# =============================================================================

def eval_predictions(y_true, y_pred):
    """Return dict of metrics."""
    mae_kwh = mean_absolute_error(y_true, y_pred)
    return {
        'MAE (kWh/ft²)': mae_kwh,
        'MAE (kBtu/sf)': mae_kwh * 3.412,
        'RMSE (kWh/ft²)': np.sqrt(mean_squared_error(y_true, y_pred)),
        'R²': r2_score(y_true, y_pred),
    }


# =============================================================================
# RUN ONE FEATURE SET
# =============================================================================

def run_feature_set(label, feature_cols, df, train_idx, test_idx):
    """
    Train XGBoost, LightGBM, CatBoost on both fuel targets using `feature_cols`.
    Returns dict keyed by (fuel_name, model_name) → metrics dict.
    """
    cat_indices = [i for i, col in enumerate(feature_cols) if col in CAT_FEATURE_NAMES]

    # XGBoost / LightGBM: pd.Categorical encoding (NaN preserved for native handling)
    X_enc, _ = encode_features_preserve_nan(df, feature_cols, CAT_FEATURE_NAMES)
    X_train_enc = X_enc.iloc[train_idx]
    X_test_enc  = X_enc.iloc[test_idx]

    # CatBoost: string categoricals
    X_cb = prepare_catboost_data(df, feature_cols, CAT_FEATURE_NAMES)
    X_train_cb = X_cb.iloc[train_idx]
    X_test_cb  = X_cb.iloc[test_idx]

    model_specs = {
        'XGBoost':  (build_xgboost,  X_train_enc, X_test_enc),
        'LightGBM': (build_lightgbm, X_train_enc, X_test_enc),
        'CatBoost': (build_catboost, X_train_cb,  X_test_cb),
    }

    results = {}

    for fuel_name, fuel_col in FUEL_TARGETS.items():
        y = df[fuel_col].values
        y_train = y[train_idx]
        y_test  = y[test_idx]

        for model_name, (builder, X_tr, X_te) in model_specs.items():
            t0 = time.time()
            model = builder(X_tr, y_train, cat_indices)
            elapsed = time.time() - t0

            y_pred = model.predict(X_te)
            metrics = eval_predictions(y_test, y_pred)
            metrics['Train Time (s)'] = elapsed

            key = (fuel_name, model_name)
            results[key] = metrics
            print(f"    [{label}] {fuel_name:<12} {model_name:<10}: "
                  f"MAE={metrics['MAE (kBtu/sf)']:6.3f} kBtu/sf  "
                  f"R²={metrics['R²']:.4f}  "
                  f"({elapsed:.1f}s)")

    return results


# =============================================================================
# MAIN EXPERIMENT
# =============================================================================

def run_experiment(sample_size):
    total_start = time.time()

    df = load_data(sample_size)

    # Shared train/test split — same indices for OLD and NEW features
    indices = np.arange(len(df))
    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=42)
    print(f"\n  Train: {len(train_idx):,}  Test: {len(test_idx):,}")

    print(f"\n{'=' * 72}")
    print("  PHASE 1: OLD features")
    print(f"{'=' * 72}")
    results_old = run_feature_set('OLD', OLD_FEATURE_COLS, df, train_idx, test_idx)

    print(f"\n{'=' * 72}")
    print("  PHASE 2: NEW features (OLD + HDD/CDD + thermostat + derived)")
    print(f"{'=' * 72}")
    results_new = run_feature_set('NEW', NEW_FEATURE_COLS, df, train_idx, test_idx)

    # =========================================================================
    # COMPARISON TABLE
    # =========================================================================
    print(f"\n\n{'=' * 90}")
    print("COMPARISON TABLE — Old vs New Features  (ComStock baseline EUI prediction)")
    n_desc = "all" if not sample_size else f"{sample_size:,}"
    print(f"Dataset: {len(df):,} buildings  |  Test set: {len(test_idx):,}  |  Sample: {n_desc}")
    print(f"{'=' * 90}")

    col_w = {
        'fuel': 13, 'model': 10,
        'old_mae': 12, 'old_r2': 8,
        'new_mae': 12, 'new_r2': 8,
        'delta_mae': 12, 'delta_r2': 9,
    }
    header = (
        f"{'Fuel':<{col_w['fuel']}} "
        f"{'Model':<{col_w['model']}} "
        f"{'OLD MAE':>{col_w['old_mae']}} "
        f"{'OLD R²':>{col_w['old_r2']}} "
        f"{'NEW MAE':>{col_w['new_mae']}} "
        f"{'NEW R²':>{col_w['new_r2']}} "
        f"{'MAE Δ%':>{col_w['delta_mae']}} "
        f"{'R² Δ':>{col_w['delta_r2']}}"
    )
    print(header)
    print("-" * len(header))

    # Track natural gas improvements for the decision gate
    ng_mae_improvements = {}

    for fuel_name in FUEL_TARGETS:
        for model_name in ['XGBoost', 'LightGBM', 'CatBoost']:
            key = (fuel_name, model_name)
            o = results_old[key]
            n = results_new[key]

            old_mae = o['MAE (kBtu/sf)']
            new_mae = n['MAE (kBtu/sf)']
            old_r2  = o['R²']
            new_r2  = n['R²']

            # Negative = new is better (lower MAE)
            mae_pct = (new_mae - old_mae) / old_mae * 100
            r2_diff = new_r2 - old_r2

            if fuel_name == 'natural_gas':
                ng_mae_improvements[model_name] = -mae_pct  # positive = improvement

            flag = ''
            if mae_pct < -3.0:
                flag = ' ✓'
            elif mae_pct > 1.0:
                flag = ' !'

            print(
                f"{fuel_name:<{col_w['fuel']}} "
                f"{model_name:<{col_w['model']}} "
                f"{old_mae:>{col_w['old_mae']}.4f} "
                f"{old_r2:>{col_w['old_r2']}.4f} "
                f"{new_mae:>{col_w['new_mae']}.4f} "
                f"{new_r2:>{col_w['new_r2']}.4f} "
                f"{mae_pct:>{col_w['delta_mae']}.2f}% "
                f"{r2_diff:>{col_w['delta_r2']}.4f}"
                f"{flag}"
            )
        print()

    # =========================================================================
    # DECISION GATE
    # =========================================================================
    print(f"{'=' * 90}")
    print("DECISION GATE: Natural Gas MAE improvement > 3%?")
    print(f"{'=' * 90}")

    all_pass = True
    for model_name, improvement in ng_mae_improvements.items():
        status = "PASS" if improvement > 3.0 else "FAIL"
        if improvement <= 3.0:
            all_pass = False
        print(f"  {model_name:<10}: {improvement:+.2f}% improvement  [{status}]")

    avg_ng_improvement = np.mean(list(ng_mae_improvements.values()))
    gate_pass = avg_ng_improvement > 3.0
    print(f"\n  Average natural gas MAE improvement: {avg_ng_improvement:+.2f}%")
    print(f"  Decision gate: {'PASS — proceed to Tasks 3-6' if gate_pass else 'FAIL — re-evaluate'}")

    # Check electricity didn't get worse
    print(f"\n{'=' * 90}")
    print("ELECTRICITY SANITY CHECK: New features should not hurt electricity accuracy")
    print(f"{'=' * 90}")
    for model_name in ['XGBoost', 'LightGBM', 'CatBoost']:
        key = ('electricity', model_name)
        o = results_old[key]
        n = results_new[key]
        mae_pct = (n['MAE (kBtu/sf)'] - o['MAE (kBtu/sf)']) / o['MAE (kBtu/sf)'] * 100
        status = "OK" if mae_pct <= 1.0 else "WARN"
        print(f"  {model_name:<10}: {mae_pct:+.2f}%  [{status}]")

    total_time = time.time() - total_start
    print(f"\nTotal experiment time: {total_time:.0f}s ({total_time / 60:.1f} min)")

    return gate_pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Feature engineering validation experiment',
    )
    parser.add_argument(
        '--sample-size', type=int, default=None,
        help='Number of buildings to sample (default: use all data)',
    )
    args = parser.parse_args()
    run_experiment(args.sample_size)
