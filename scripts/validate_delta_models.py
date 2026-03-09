#!/usr/bin/env python3
"""
Validate delta/savings models vs. current absolute-subtraction approach.

Compares two approaches head-to-head on the same held-out test set:
  1. Current: baseline_model.predict() - upgrade_model.predict()
  2. Delta:   delta_model.predict() (trained on true simulation deltas)

Usage:
    python scripts/validate_delta_models.py                  # Default: upgrade 13 (Duct Sealing)
    python scripts/validate_delta_models.py --upgrade 11     # Test another upgrade
    python scripts/validate_delta_models.py --skip-tuning    # Use default hyperparameters
"""
import os
import sys
import json
import argparse
import time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import encode_features, tune_hyperparameters, train_single_model

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ResStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
MODEL_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Upgrades_2025_R1')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'scripts', 'validation_results')

KWH_TO_KBTU = 3.412

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

LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + FEATURE_COLS + list(FUEL_TYPES.values())
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


def load_paired_data(upgrade_id, cluster_lookup):
    """Load baseline and upgrade parquets, join on bldg_id, compute deltas.

    Returns:
        df: DataFrame with features, baseline EUI, upgrade EUI, and delta columns
        n_baseline: raw baseline count
        n_paired: final paired count after filtering
    """
    baseline_path = os.path.join(RAW_DIR, 'upgrade0.parquet')
    upgrade_path = os.path.join(RAW_DIR, f'upgrade{upgrade_id}.parquet')

    if not os.path.exists(upgrade_path):
        raise FileNotFoundError(f"Upgrade file not found: {upgrade_path}")

    print(f"  Loading baseline (upgrade 0)...")
    df_base = pd.read_parquet(baseline_path, columns=LOAD_COLS)
    n_baseline = len(df_base)

    print(f"  Loading upgrade {upgrade_id}...")
    # For upgrade, only need bldg_id, applicability, and fuel columns
    upgrade_load_cols = ['bldg_id', 'applicability'] + list(FUEL_TYPES.values())
    df_upg = pd.read_parquet(upgrade_path, columns=upgrade_load_cols)

    # Filter upgrade to applicable only
    df_upg = df_upg[df_upg['applicability'] == True]
    print(f"  Applicable buildings in upgrade {upgrade_id}: {len(df_upg)}")

    # Rename upgrade fuel columns to avoid collision
    fuel_rename = {col: f"upgrade_{col}" for col in FUEL_TYPES.values()}
    df_upg = df_upg.rename(columns=fuel_rename)
    df_upg = df_upg.drop(columns=['applicability'])

    # Inner join on bldg_id — only buildings with both baseline and upgrade data
    df = df_base.merge(df_upg, on='bldg_id', how='inner')
    print(f"  Paired buildings (inner join): {len(df)}")

    # Filter to MF 4+ occupied
    df = filter_mf_occupied(df)
    print(f"  After MF 4+ occupied filter: {len(df)}")

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
        df[f"upgrade_{col}"] = df[f"upgrade_{col}"].fillna(0)

    # Compute deltas (baseline - upgrade = savings; positive = energy saved)
    for fuel_name, fuel_col in FUEL_TYPES.items():
        df[f"delta_{fuel_name}"] = df[fuel_col] - df[f"upgrade_{fuel_col}"]

    # Compute total delta
    df['delta_total_kwh'] = sum(df[f"delta_{fuel}"] for fuel in FUEL_TYPES)
    df['delta_total_kbtu'] = df['delta_total_kwh'] * KWH_TO_KBTU

    n_paired = len(df)

    # Drop metadata columns
    df = df.drop(columns=['applicability',
                           'in.geometry_building_number_units_mf', 'in.vacancy_status',
                           'in.county', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df, n_baseline, n_paired


# ==============================================================================
# EXISTING MODEL PREDICTIONS (absolute subtraction approach)
# ==============================================================================

def load_existing_model(model_dir, upgrade_id, fuel_name):
    """Load a pre-trained model bundle from disk."""
    import joblib

    model_name = f"XGB_upgrade{upgrade_id}_{fuel_name}"
    pkl_path = os.path.join(model_dir, f"{model_name}.pkl")
    enc_path = os.path.join(model_dir, f"{model_name}_encoders.pkl")
    meta_path = os.path.join(model_dir, f"{model_name}_meta.json")

    if not os.path.exists(pkl_path):
        return None

    model = joblib.load(pkl_path)
    encoders = joblib.load(enc_path)
    with open(meta_path) as f:
        meta = json.load(f)

    return {'model': model, 'encoders': encoders, 'meta': meta}


def predict_with_existing(bundles, X_features, feature_cols):
    """Predict per-fuel EUI using existing absolute models.

    Returns dict of fuel -> array of predictions.
    """
    results = {}
    for fuel_name, bundle in bundles.items():
        meta = bundle['meta']
        model_features = meta['feature_columns']
        log_target = meta.get('log_target', False)

        # Build DataFrame with model's expected features
        row_data = {col: X_features[col] if col in X_features.columns
                    else np.nan for col in model_features}
        df = pd.DataFrame(row_data)

        # Encode using saved encoders
        df_enc, _ = encode_features(df, model_features, encoders=bundle['encoders'])

        preds = bundle['model'].predict(df_enc)
        if log_target:
            preds = np.expm1(preds)

        results[fuel_name] = preds

    return results


# ==============================================================================
# EVALUATION
# ==============================================================================

def compute_metrics(true_savings, pred_savings, label):
    """Compute comparison metrics for a savings prediction approach."""
    mae = mean_absolute_error(true_savings, pred_savings)
    rmse = np.sqrt(mean_squared_error(true_savings, pred_savings))
    r2 = r2_score(true_savings, pred_savings)
    n_negative = (pred_savings < 0).sum()
    pct_negative = n_negative / len(pred_savings) * 100

    return {
        'approach': label,
        'mae_kwh_sf': mae,
        'mae_kbtu_sf': mae * KWH_TO_KBTU,
        'rmse_kwh_sf': rmse,
        'rmse_kbtu_sf': rmse * KWH_TO_KBTU,
        'r2': r2,
        'n_negative_savings': int(n_negative),
        'pct_negative_savings': pct_negative,
        'n_samples': len(true_savings),
    }


def print_comparison(metrics_abs, metrics_delta):
    """Print a side-by-side comparison table."""
    print(f"\n{'=' * 70}")
    print(f"{'METRIC':<35} {'ABSOLUTE':>15} {'DELTA':>15}")
    print(f"{'=' * 70}")

    rows = [
        ('MAE (kBtu/sf)', 'mae_kbtu_sf', '.3f'),
        ('RMSE (kBtu/sf)', 'rmse_kbtu_sf', '.3f'),
        ('R² (savings)', 'r2', '.4f'),
        ('Negative savings predictions', 'n_negative_savings', 'd'),
        ('% negative savings', 'pct_negative_savings', '.1f'),
        ('Test samples', 'n_samples', 'd'),
    ]

    for label, key, fmt in rows:
        val_abs = metrics_abs[key]
        val_delta = metrics_delta[key]
        print(f"  {label:<33} {val_abs:>15{fmt}} {val_delta:>15{fmt}}")

    print(f"{'=' * 70}")

    # Highlight winner
    mae_improvement = (metrics_abs['mae_kbtu_sf'] - metrics_delta['mae_kbtu_sf']) / metrics_abs['mae_kbtu_sf'] * 100
    neg_reduction = metrics_abs['n_negative_savings'] - metrics_delta['n_negative_savings']
    print(f"\n  Delta MAE improvement: {mae_improvement:+.1f}%")
    print(f"  Negative savings reduction: {neg_reduction:+d} buildings")


# ==============================================================================
# MAIN
# ==============================================================================

def run_validation(upgrade_id, skip_tuning=False, tune_trials=30):
    """Run the full validation comparison for one upgrade."""
    start_time = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n{'=' * 70}")
    print(f"DELTA vs ABSOLUTE VALIDATION — Upgrade {upgrade_id}")
    print(f"{'=' * 70}")

    # ------------------------------------------------------------------
    # Phase 1: Load paired data
    # ------------------------------------------------------------------
    print("\n--- Phase 1: Loading paired data ---")
    cluster_lookup = load_cluster_lookup()
    df, n_baseline, n_paired = load_paired_data(upgrade_id, cluster_lookup)

    # Quick stats on true deltas
    print(f"\n  True delta stats (total savings, kBtu/sf):")
    delta_total = df['delta_total_kbtu']
    print(f"    Mean:   {delta_total.mean():.3f}")
    print(f"    Median: {delta_total.median():.3f}")
    print(f"    Std:    {delta_total.std():.3f}")
    print(f"    Min:    {delta_total.min():.3f}")
    print(f"    Max:    {delta_total.max():.3f}")
    n_true_negative = (delta_total < 0).sum()
    print(f"    True negative savings: {n_true_negative} ({n_true_negative/len(delta_total)*100:.1f}%)")

    # ------------------------------------------------------------------
    # Phase 2: Train/test split
    # ------------------------------------------------------------------
    print("\n--- Phase 2: Train/test split ---")
    train_idx, test_idx = train_test_split(
        np.arange(len(df)), test_size=0.2, random_state=42
    )
    df_train = df.iloc[train_idx]
    df_test = df.iloc[test_idx]
    print(f"  Train: {len(df_train)}, Test: {len(df_test)}")

    # Encode features (shared across delta models)
    X_enc, encoders = encode_features(df, FEATURE_COLS)
    X_train = X_enc.iloc[train_idx]
    X_test = X_enc.iloc[test_idx]

    # ------------------------------------------------------------------
    # Phase 3: Train delta models
    # ------------------------------------------------------------------
    print("\n--- Phase 3: Training delta models ---")

    # Hyperparameter tuning on electricity delta (largest signal)
    if skip_tuning:
        params = {
            'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
            'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
        }
        print("  Using default hyperparameters (--skip-tuning)")
    else:
        print("  Tuning hyperparameters on electricity delta...")
        y_tune = df_train['delta_electricity'].values
        if len(X_train) > 30000:
            idx = np.random.RandomState(42).choice(len(X_train), 30000, replace=False)
            X_tune, y_tune = X_train.iloc[idx], y_tune[idx]
        else:
            X_tune = X_train
        params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        print(f"  Best params: {params}")

    delta_models = {}
    for fuel_name in FUEL_TYPES:
        target_col = f"delta_{fuel_name}"
        y_train = df_train[target_col].values
        y_test = df_test[target_col].values

        t0 = time.time()
        model = train_single_model(X_train, y_train, params)
        train_time = time.time() - t0

        # Quick per-fuel eval
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred) * KWH_TO_KBTU
        r2 = r2_score(y_test, y_pred)
        n_neg = (y_pred < 0).sum()

        print(f"  {fuel_name:>15}: MAE={mae:.3f} kBtu/sf, R²={r2:.4f}, "
              f"neg={n_neg}/{len(y_test)}, time={train_time:.1f}s")

        delta_models[fuel_name] = model

    # ------------------------------------------------------------------
    # Phase 4: Load existing absolute models and predict
    # ------------------------------------------------------------------
    print("\n--- Phase 4: Loading existing absolute models ---")

    baseline_bundles = {}
    upgrade_bundles = {}
    for fuel_name in FUEL_TYPES:
        b = load_existing_model(MODEL_DIR, 0, fuel_name)
        u = load_existing_model(MODEL_DIR, upgrade_id, fuel_name)
        if b is None:
            print(f"  WARNING: No baseline model for {fuel_name}")
        if u is None:
            print(f"  WARNING: No upgrade model for {fuel_name}")
        if b:
            baseline_bundles[fuel_name] = b
        if u:
            upgrade_bundles[fuel_name] = u

    # Predict with existing models on test set features
    # Need raw (unencoded) features for existing models (they have their own encoders)
    X_test_raw = df.iloc[test_idx][FEATURE_COLS]

    print("  Predicting with existing baseline models...")
    baseline_preds = predict_with_existing(baseline_bundles, X_test_raw, FEATURE_COLS)

    print("  Predicting with existing upgrade models...")
    upgrade_preds = predict_with_existing(upgrade_bundles, X_test_raw, FEATURE_COLS)

    # Compute absolute-approach savings: baseline - upgrade
    abs_savings_total = np.zeros(len(df_test))
    for fuel_name in FUEL_TYPES:
        if fuel_name in baseline_preds and fuel_name in upgrade_preds:
            fuel_savings = baseline_preds[fuel_name] - upgrade_preds[fuel_name]
            abs_savings_total += fuel_savings

    # ------------------------------------------------------------------
    # Phase 5: Compute delta-approach savings on test set
    # ------------------------------------------------------------------
    print("\n--- Phase 5: Computing delta predictions ---")

    delta_savings_total = np.zeros(len(df_test))
    delta_preds_by_fuel = {}
    for fuel_name, model in delta_models.items():
        preds = model.predict(X_test)
        delta_preds_by_fuel[fuel_name] = preds
        delta_savings_total += preds

    # True savings from simulation data
    true_savings_total = df_test['delta_total_kwh'].values

    # ------------------------------------------------------------------
    # Phase 6: Compare
    # ------------------------------------------------------------------
    print("\n--- Phase 6: Results ---")

    metrics_abs = compute_metrics(true_savings_total, abs_savings_total, 'absolute')
    metrics_delta = compute_metrics(true_savings_total, delta_savings_total, 'delta')

    print_comparison(metrics_abs, metrics_delta)

    # Per-fuel breakdown
    print(f"\n{'=' * 70}")
    print(f"PER-FUEL BREAKDOWN (negative savings counts on test set)")
    print(f"{'=' * 70}")
    print(f"  {'Fuel':<18} {'True neg':>10} {'Abs neg':>10} {'Delta neg':>10}")
    print(f"  {'-'*48}")

    per_fuel_metrics = {}
    for fuel_name in FUEL_TYPES:
        true_delta = df_test[f"delta_{fuel_name}"].values
        abs_delta = (baseline_preds.get(fuel_name, np.zeros(len(df_test)))
                     - upgrade_preds.get(fuel_name, np.zeros(len(df_test))))
        delta_pred = delta_preds_by_fuel[fuel_name]

        n_true_neg = (true_delta < 0).sum()
        n_abs_neg = (abs_delta < 0).sum()
        n_delta_neg = (delta_pred < 0).sum()

        print(f"  {fuel_name:<18} {n_true_neg:>10} {n_abs_neg:>10} {n_delta_neg:>10}")

        per_fuel_metrics[fuel_name] = {
            'absolute': compute_metrics(true_delta, abs_delta, 'absolute'),
            'delta': compute_metrics(true_delta, delta_pred, 'delta'),
        }

    # ------------------------------------------------------------------
    # Phase 7: Save results
    # ------------------------------------------------------------------
    print(f"\n--- Phase 7: Saving results ---")

    # Per-building CSV
    results_df = pd.DataFrame({
        'bldg_id': df.iloc[test_idx]['bldg_id'].values,
        'true_savings_kwh_sf': true_savings_total,
        'true_savings_kbtu_sf': true_savings_total * KWH_TO_KBTU,
        'absolute_savings_kwh_sf': abs_savings_total,
        'absolute_savings_kbtu_sf': abs_savings_total * KWH_TO_KBTU,
        'delta_savings_kwh_sf': delta_savings_total,
        'delta_savings_kbtu_sf': delta_savings_total * KWH_TO_KBTU,
    })

    # Add per-fuel columns
    for fuel_name in FUEL_TYPES:
        results_df[f'true_delta_{fuel_name}'] = df_test[f"delta_{fuel_name}"].values
        results_df[f'abs_delta_{fuel_name}'] = (
            baseline_preds.get(fuel_name, np.zeros(len(df_test)))
            - upgrade_preds.get(fuel_name, np.zeros(len(df_test)))
        )
        results_df[f'delta_pred_{fuel_name}'] = delta_preds_by_fuel[fuel_name]

    csv_path = os.path.join(OUTPUT_DIR, f'delta_vs_absolute_upgrade{upgrade_id}.csv')
    results_df.to_csv(csv_path, index=False)
    print(f"  Per-building results: {csv_path}")

    # Summary JSON
    summary = {
        'upgrade_id': upgrade_id,
        'n_paired_buildings': n_paired,
        'n_test': len(df_test),
        'hyperparameters': params,
        'total_savings': {
            'absolute': metrics_abs,
            'delta': metrics_delta,
        },
        'per_fuel': per_fuel_metrics,
        'true_delta_stats': {
            'mean_kbtu_sf': float(delta_total.mean()),
            'median_kbtu_sf': float(delta_total.median()),
            'std_kbtu_sf': float(delta_total.std()),
            'pct_true_negative': float(n_true_negative / len(delta_total) * 100),
        },
    }

    json_path = os.path.join(OUTPUT_DIR, f'summary_upgrade{upgrade_id}.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary: {json_path}")

    elapsed = time.time() - start_time
    print(f"\n  Total time: {elapsed:.1f}s")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description='Validate delta savings models vs. absolute subtraction approach'
    )
    parser.add_argument('--upgrade', type=int, default=13,
                        help='Upgrade ID to validate (default: 13, Duct Sealing)')
    parser.add_argument('--skip-tuning', action='store_true',
                        help='Skip hyperparameter tuning, use defaults')
    parser.add_argument('--tune-trials', type=int, default=30,
                        help='Number of Optuna tuning trials (default: 30)')
    args = parser.parse_args()

    run_validation(args.upgrade, skip_tuning=args.skip_tuning, tune_trials=args.tune_trials)


if __name__ == '__main__':
    main()
