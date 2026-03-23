#!/usr/bin/env python3
"""
Quick experiment: XGBoost vs LightGBM vs CatBoost vs Blended Ensemble
on ComStock baseline EUI prediction (electricity + natural gas only).

Samples 30K buildings to keep runtime under 10 minutes.
Does NOT modify any existing models or app code.

Usage:
    pip install lightgbm catboost  # one-time
    python3 scripts/experiment_ensemble_blend.py
    python3 scripts/experiment_ensemble_blend.py --sample-size 15000  # smaller/faster
"""
import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import encode_features

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
# CONFIG (mirrors train_comstock_deltas.py)
# =============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')

# Only electricity and natural gas for this experiment
FUEL_TARGETS = {
    'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
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

# Identify which features are categorical (string/object dtype)
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
    """Load ComStock baseline, join clusters, sample down."""
    print("Loading baseline data...")
    load_cols = (
        ['bldg_id', 'in.as_simulated_nhgis_county_gisjoin']
        + [c for c in FEATURE_COLS if c != 'cluster_name']
        + list(FUEL_TARGETS.values())
    )
    df = pd.read_parquet(
        os.path.join(RAW_DIR, 'upgrade0_agg.parquet'),
        columns=load_cols
    )
    df = df.drop_duplicates(subset='bldg_id')

    # Join cluster_name
    lookup = pd.read_csv(LOOKUP_PATH,
                         usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    lookup = lookup.drop_duplicates(subset='nhgis_county_gisjoin')
    df = df.merge(lookup,
                  left_on='in.as_simulated_nhgis_county_gisjoin',
                  right_on='nhgis_county_gisjoin',
                  how='left')
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows with all-null targets
    fuel_cols = list(FUEL_TARGETS.values())
    df = df.dropna(subset=fuel_cols, how='all')
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

    # Drop metadata cols
    df = df.drop(columns=['bldg_id', 'in.as_simulated_nhgis_county_gisjoin',
                           'nhgis_county_gisjoin'], errors='ignore')

    print(f"  Full dataset: {len(df):,} buildings")

    # Sample
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
    model.fit(
        X_train, y_train,
        categorical_feature=cat_indices,
    )
    return model


def build_catboost(X_train, y_train, cat_indices):
    """Train CatBoost with native categorical support."""
    model = CatBoostRegressor(
        iterations=300, depth=6, learning_rate=0.1,
        random_seed=42, verbose=0,
        cat_features=cat_indices,
    )
    model.fit(X_train, y_train)
    return model


# =============================================================================
# EVALUATION
# =============================================================================

def eval_predictions(y_true, y_pred):
    """Return dict of metrics."""
    return {
        'MAE (kWh/ft²)': mean_absolute_error(y_true, y_pred),
        'RMSE (kWh/ft²)': np.sqrt(mean_squared_error(y_true, y_pred)),
        'MAE (kBtu/sf)': mean_absolute_error(y_true, y_pred) * 3.412,
        'R²': r2_score(y_true, y_pred),
    }


# =============================================================================
# MAIN EXPERIMENT
# =============================================================================

def run_experiment(sample_size):
    total_start = time.time()
    df = load_data(sample_size)

    # Encode features — XGBoost/LightGBM use pd.Categorical, CatBoost uses raw strings
    X_cat, encoders = encode_features(df, FEATURE_COLS)  # pd.Categorical encoded
    cat_indices = [i for i, col in enumerate(FEATURE_COLS) if col in CAT_FEATURE_NAMES]

    # CatBoost version: string columns instead of pd.Categorical
    X_catboost = df[FEATURE_COLS].copy()
    for col in CAT_FEATURE_NAMES:
        if col in X_catboost.columns:
            X_catboost[col] = X_catboost[col].astype(str)
    for col in FEATURE_COLS:
        if col not in CAT_FEATURE_NAMES:
            X_catboost[col] = pd.to_numeric(X_catboost[col], errors='coerce').fillna(0)

    # Train/test split (same indices for all models)
    indices = np.arange(len(X_cat))
    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=42)

    X_train_xgb, X_test_xgb = X_cat.iloc[train_idx], X_cat.iloc[test_idx]
    X_train_cb, X_test_cb = X_catboost.iloc[train_idx], X_catboost.iloc[test_idx]

    models = {
        'XGBoost':  (build_xgboost,  X_train_xgb, X_test_xgb),
        'LightGBM': (build_lightgbm, X_train_xgb, X_test_xgb),
        'CatBoost': (build_catboost, X_train_cb,   X_test_cb),
    }

    all_results = {}

    for fuel_name, fuel_col in FUEL_TARGETS.items():
        print(f"\n{'=' * 70}")
        print(f"  TARGET: {fuel_name} EUI (kWh/ft²)")
        print(f"{'=' * 70}")

        y = df[fuel_col].values
        y_train, y_test = y[train_idx], y[test_idx]

        predictions = {}
        timings = {}

        for model_name, (builder, X_tr, X_te) in models.items():
            t0 = time.time()
            model = builder(X_tr, y_train, cat_indices)
            train_time = time.time() - t0
            timings[model_name] = train_time

            y_pred = model.predict(X_te)
            predictions[model_name] = y_pred

            metrics = eval_predictions(y_test, y_pred)
            all_results[(fuel_name, model_name)] = metrics
            all_results[(fuel_name, model_name)]['Train Time (s)'] = train_time

            print(f"  {model_name:>10}: MAE={metrics['MAE (kBtu/sf)']:6.2f} kBtu/sf, "
                  f"R²={metrics['R²']:.4f}, Time={train_time:.1f}s")

        # --- Ensemble: Simple Average ---
        preds_array = np.stack([predictions[m] for m in models])
        y_avg = preds_array.mean(axis=0)
        metrics_avg = eval_predictions(y_test, y_avg)
        metrics_avg['Train Time (s)'] = sum(timings.values())
        all_results[(fuel_name, 'Avg Blend')] = metrics_avg
        print(f"  {'Avg Blend':>10}: MAE={metrics_avg['MAE (kBtu/sf)']:6.2f} kBtu/sf, "
              f"R²={metrics_avg['R²']:.4f}")

        # --- Ensemble: Weighted Average (weights from 3-fold CV on training set) ---
        print(f"  {'':>10}  Computing CV weights...", end=' ', flush=True)
        cv_scores = {}
        from sklearn.model_selection import KFold
        kf = KFold(n_splits=3, shuffle=True, random_state=42)

        for mname in ['XGBoost', 'LightGBM', 'CatBoost']:
            fold_maes = []
            for fold_train, fold_val in kf.split(X_train_xgb):
                if mname == 'XGBoost':
                    m = XGBRegressor(
                        objective='reg:squarederror', n_estimators=300, max_depth=6,
                        learning_rate=0.1, min_child_weight=5, subsample=0.8,
                        colsample_bytree=0.8, random_state=42, n_jobs=-1,
                        enable_categorical=True,
                    )
                    m.fit(X_train_xgb.iloc[fold_train], y_train[fold_train])
                    preds = m.predict(X_train_xgb.iloc[fold_val])
                elif mname == 'LightGBM':
                    m = LGBMRegressor(
                        objective='regression', n_estimators=300, max_depth=6,
                        learning_rate=0.1, min_child_weight=5, subsample=0.8,
                        colsample_bytree=0.8, random_state=42, n_jobs=-1, verbose=-1,
                    )
                    m.fit(X_train_xgb.iloc[fold_train], y_train[fold_train],
                          categorical_feature=cat_indices)
                    preds = m.predict(X_train_xgb.iloc[fold_val])
                else:  # CatBoost
                    m = CatBoostRegressor(
                        iterations=300, depth=6, learning_rate=0.1,
                        random_seed=42, verbose=0, cat_features=cat_indices,
                    )
                    m.fit(X_train_cb.iloc[fold_train], y_train[fold_train])
                    preds = m.predict(X_train_cb.iloc[fold_val])
                fold_maes.append(mean_absolute_error(y_train[fold_val], preds))
            cv_scores[mname] = np.mean(fold_maes)

        # Inverse-MAE weighting (lower MAE → higher weight)
        inv_mae = {m: 1.0 / score for m, score in cv_scores.items()}
        total_inv = sum(inv_mae.values())
        weights = {m: v / total_inv for m, v in inv_mae.items()}

        y_weighted = sum(weights[m] * predictions[m] for m in models)
        metrics_w = eval_predictions(y_test, y_weighted)
        metrics_w['Train Time (s)'] = sum(timings.values())
        all_results[(fuel_name, 'Wtd Blend')] = metrics_w

        print(f"weights: {', '.join(f'{m}={w:.2f}' for m, w in weights.items())}")
        print(f"  {'Wtd Blend':>10}: MAE={metrics_w['MAE (kBtu/sf)']:6.2f} kBtu/sf, "
              f"R²={metrics_w['R²']:.4f}")

    # =========================================================================
    # SUMMARY TABLE
    # =========================================================================
    print(f"\n\n{'=' * 80}")
    print("SUMMARY — Baseline EUI Prediction (ComStock, 30K sample)")
    print(f"{'=' * 80}")

    header = f"{'Fuel':<15} {'Model':<12} {'MAE kBtu/sf':>12} {'RMSE kWh/ft²':>14} {'R²':>8} {'Time(s)':>8}"
    print(header)
    print("-" * len(header))

    for fuel_name in FUEL_TARGETS:
        for model_name in ['XGBoost', 'LightGBM', 'CatBoost', 'Avg Blend', 'Wtd Blend']:
            m = all_results[(fuel_name, model_name)]
            print(f"{fuel_name:<15} {model_name:<12} {m['MAE (kBtu/sf)']:>12.3f} "
                  f"{m['RMSE (kWh/ft²)']:>14.4f} {m['R²']:>8.4f} {m['Train Time (s)']:>8.1f}")
        print()

    # Show improvement vs XGBoost baseline
    print(f"\n{'=' * 80}")
    print("IMPROVEMENT vs XGBoost (negative = blend is better)")
    print(f"{'=' * 80}")
    for fuel_name in FUEL_TARGETS:
        xgb_mae = all_results[(fuel_name, 'XGBoost')]['MAE (kBtu/sf)']
        xgb_r2 = all_results[(fuel_name, 'XGBoost')]['R²']
        for blend in ['Avg Blend', 'Wtd Blend']:
            b_mae = all_results[(fuel_name, blend)]['MAE (kBtu/sf)']
            b_r2 = all_results[(fuel_name, blend)]['R²']
            mae_pct = (b_mae - xgb_mae) / xgb_mae * 100
            r2_diff = b_r2 - xgb_r2
            print(f"  {fuel_name:<15} {blend:<12}: MAE {mae_pct:+.2f}%, R² {r2_diff:+.4f}")

    total_time = time.time() - total_start
    print(f"\nTotal experiment time: {total_time:.0f}s ({total_time/60:.1f} min)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Ensemble blend experiment')
    parser.add_argument('--sample-size', type=int, default=30000,
                        help='Number of buildings to sample (default: 30000)')
    args = parser.parse_args()
    run_experiment(args.sample_size)
