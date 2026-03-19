#!/usr/bin/env python3
"""
Validation experiment: does adding baseline EUI as a feature improve delta predictions?

Usage:
    python3 scripts/validate_baseline_feature.py --dataset comstock
    python3 scripts/validate_baseline_feature.py --dataset both --upgrades 1,5,10,15,20
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from scripts.training_utils import encode_features, train_single_model, evaluate_model

# ==============================================================================
# DATASET CONFIGS
# ==============================================================================

COMSTOCK_CONFIG = {
    'name': 'comstock',
    'raw_dir': os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data'),
    'lookup_path': os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv'),
    'baseline_file': 'upgrade0_agg.parquet',
    'upgrade_file_pattern': 'upgrade{uid}_agg.parquet',
    'cluster_join_col': 'in.as_simulated_nhgis_county_gisjoin',
    'lookup_join_col': 'nhgis_county_gisjoin',
    'has_completed_status': True,
    'dedup_bldg_id': True,
    'mf_filter': False,
    'extra_drop_cols': ['completed_status', 'applicability',
                        'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
    'load_extra_cols': ['bldg_id', 'completed_status', 'applicability',
                        'in.as_simulated_nhgis_county_gisjoin'],
    'fuel_types': {
        'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
        'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
        'fuel_oil': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
        'propane': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
        'district_heating': 'out.district_heating.total.energy_consumption_intensity..kwh_per_ft2',
    },
    'feature_cols': [
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
    ],
    'default_top_upgrades': [1, 5, 10, 15, 20],
}

RESSTOCK_CONFIG = {
    'name': 'resstock',
    'raw_dir': os.path.join(PROJECT_ROOT, 'ResStock', 'raw_data'),
    'lookup_path': os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv'),
    'baseline_file': 'upgrade0.parquet',
    'upgrade_file_pattern': 'upgrade{uid}.parquet',
    'cluster_join_col': 'in.county',
    'lookup_join_col': 'nhgis_county_gisjoin',
    'has_completed_status': False,
    'dedup_bldg_id': False,
    'mf_filter': True,
    'extra_drop_cols': ['applicability', 'in.geometry_building_number_units_mf',
                        'in.vacancy_status', 'in.county', 'nhgis_county_gisjoin'],
    'load_extra_cols': ['bldg_id', 'applicability',
                        'in.geometry_building_number_units_mf', 'in.vacancy_status',
                        'in.county'],
    'fuel_types': {
        'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
        'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
        'fuel_oil': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
        'propane': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
    },
    'feature_cols': [
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
    ],
    'default_top_upgrades': [1, 4, 9, 17, 18],
}

# Default XGBoost hyperparameters (same as training scripts)
DEFAULT_PARAMS = {
    'n_estimators': 300,
    'max_depth': 6,
    'learning_rate': 0.1,
    'min_child_weight': 5,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
}

RANDOM_SEED = 42


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup(lookup_path):
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(lookup_path, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def filter_mf_occupied(df):
    """Filter ResStock to multi-family 4+ units, occupied only."""
    units = df['in.geometry_building_number_units_mf'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    mf_mask = units >= 4
    occ_mask = df['in.vacancy_status'] == 'Occupied'
    return df[mf_mask & occ_mask].copy()


def load_baseline_data(cfg, cluster_lookup):
    """Load baseline (upgrade 0) data with cluster_name joined in."""
    fuel_cols = list(cfg['fuel_types'].values())
    load_cols = cfg['load_extra_cols'] + cfg['feature_cols'] + fuel_cols
    # Remove cluster_name since it comes from the join, avoid duplicates
    load_cols = list(dict.fromkeys([c for c in load_cols if c != 'cluster_name']))

    fname = os.path.join(cfg['raw_dir'], cfg['baseline_file'])
    df = pd.read_parquet(fname, columns=load_cols)

    if cfg['dedup_bldg_id']:
        df = df.drop_duplicates(subset='bldg_id')

    if cfg['mf_filter']:
        df = filter_mf_occupied(df)

    # Join cluster_name
    df = df.merge(
        cluster_lookup,
        left_on=cfg['cluster_join_col'],
        right_on=cfg['lookup_join_col'],
        how='left'
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Fill null fuel EUIs with 0
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

    # Drop rows where ALL fuel EUIs are null (ComStock pattern)
    if cfg['dedup_bldg_id']:
        df = df.dropna(subset=fuel_cols, how='all')

    return df


def load_paired_data(cfg, upgrade_id, df_baseline):
    """
    Load upgrade parquet and merge with baseline to produce a DataFrame with:
      - FEATURE_COLS (from baseline)
      - baseline_{fuel} columns (ground-truth baseline EUI per fuel)
      - delta_{fuel} columns (savings = baseline - upgrade)

    Returns (df, n_applicable, n_paired) or (None, 0, 0) on failure.
    """
    fuel_types = cfg['fuel_types']
    fuel_cols = list(fuel_types.values())

    fname_pattern = cfg['upgrade_file_pattern'].format(uid=upgrade_id)
    fname = os.path.join(cfg['raw_dir'], fname_pattern)
    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    # Load upgrade: only need bldg_id, applicability, and fuel columns
    upg_load_cols = ['bldg_id', 'applicability'] + fuel_cols
    if cfg['has_completed_status']:
        upg_load_cols = ['bldg_id', 'completed_status', 'applicability'] + fuel_cols
    df_upg = pd.read_parquet(fname, columns=upg_load_cols)

    if cfg['dedup_bldg_id']:
        df_upg = df_upg.drop_duplicates(subset='bldg_id')

    if cfg['has_completed_status']:
        df_upg = df_upg[df_upg['completed_status'] == 'Success']

    df_upg = df_upg[df_upg['applicability'] == True]
    n_applicable = len(df_upg)

    # Rename upgrade fuel cols to avoid collision with baseline
    fuel_rename = {col: f"upgrade_{col}" for col in fuel_cols}
    df_upg = df_upg.rename(columns=fuel_rename)
    drop_upg_meta = ['applicability']
    if cfg['has_completed_status']:
        drop_upg_meta.append('completed_status')
    df_upg = df_upg.drop(columns=drop_upg_meta)

    for col in fuel_rename.values():
        df_upg[col] = df_upg[col].fillna(0)

    # Inner join with baseline
    df = df_baseline.merge(df_upg, on='bldg_id', how='inner')
    n_paired = len(df)

    if n_paired == 0:
        return None, n_applicable, 0

    # Rename baseline fuel cols to baseline_{fuel_name} for clarity
    for fuel_name, fuel_col in fuel_types.items():
        df[f"baseline_{fuel_name}"] = df[fuel_col]

    # Compute delta targets (positive = energy saved)
    for fuel_name, fuel_col in fuel_types.items():
        df[f"delta_{fuel_name}"] = df[fuel_col] - df[f"upgrade_{fuel_col}"]

    # Drop metadata/join columns we no longer need
    drop_cols = ['bldg_id'] + cfg['extra_drop_cols']
    # Drop upgrade fuel columns — delta already computed
    drop_cols += list(fuel_rename.values())
    df = df.drop(columns=drop_cols, errors='ignore')

    return df, n_applicable, n_paired


# ==============================================================================
# METRICS HELPERS
# ==============================================================================

def compute_metrics(y_true, y_pred):
    """Return MAE, RMSE, and R² for a prediction array."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    return mae, rmse, r2


def train_and_evaluate(X_train, y_train, X_test, y_test, params=None):
    """Train a single XGBoost model and return (mae, rmse, r2) on test set."""
    if params is None:
        params = DEFAULT_PARAMS
    model = XGBRegressor(
        objective='reg:squarederror',
        random_state=RANDOM_SEED,
        n_jobs=-1,
        enable_categorical=True,
        **params
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mae, rmse, r2 = compute_metrics(y_test, y_pred)
    return model, mae, rmse, r2


# ==============================================================================
# EXPERIMENT LOGIC
# ==============================================================================

def run_upgrade_experiment(cfg, upgrade_id, df):
    """
    Run all four experiment conditions for a single upgrade and return a list
    of result dicts (one per fuel type).

    Conditions:
      1. Control:     FEATURE_COLS only
      2. Experiment:  FEATURE_COLS + ground-truth baseline EUI per fuel
      3. Error Prop:  FEATURE_COLS + predicted baseline EUI (from a baseline
                      model trained on the training split only)
      4. Noise10%:    FEATURE_COLS + baseline EUI with 10% Gaussian noise added
      5. Noise20%:    FEATURE_COLS + baseline EUI with 20% Gaussian noise added
    """
    fuel_types = cfg['fuel_types']
    feature_cols = cfg['feature_cols']
    baseline_feature_cols = [f"baseline_{fn}" for fn in fuel_types]

    # ---- Encode base features (categorical → pandas Categorical for XGBoost) ----
    X_base, encoders = encode_features(df, feature_cols)

    # ---- 80/20 split (fixed seed for reproducibility) ----
    train_idx, test_idx = train_test_split(
        np.arange(len(X_base)), test_size=0.2, random_state=RANDOM_SEED
    )
    X_base_train = X_base.iloc[train_idx]
    X_base_test = X_base.iloc[test_idx]

    # ---- Extract ground-truth baseline EUI arrays ----
    baseline_train = {}
    baseline_test = {}
    for fuel_name in fuel_types:
        col = f"baseline_{fuel_name}"
        baseline_train[fuel_name] = df[col].values[train_idx]
        baseline_test[fuel_name] = df[col].values[test_idx]

    # ---- Error-propagation: train a baseline prediction model per fuel ----
    # Use the SAME training features (FEATURE_COLS only) to predict baseline EUI.
    # The predicted baseline for test rows simulates the real inference scenario
    # where we don't have ground-truth baseline — only model predictions.
    predicted_baseline_test = {}
    for fuel_name in fuel_types:
        y_bl_train = baseline_train[fuel_name]
        y_bl_test = baseline_test[fuel_name]
        bl_model, _, _, _ = train_and_evaluate(
            X_base_train, y_bl_train, X_base_test, y_bl_test
        )
        predicted_baseline_test[fuel_name] = bl_model.predict(X_base_test)

    # ---- Per-fuel experiment loop ----
    results = []

    for fuel_name in fuel_types:
        target_col = f"delta_{fuel_name}"
        y = df[target_col].values
        y_train = y[train_idx]
        y_test = y[test_idx]

        # Skip fuels with no variance in the delta (e.g., unused fuel type)
        if np.std(y_train) < 1e-9:
            print(f"    {fuel_name}: skipped (zero variance in training delta)")
            continue

        # ---------- 1. Control ----------
        _, ctrl_mae, ctrl_rmse, ctrl_r2 = train_and_evaluate(
            X_base_train, y_train, X_base_test, y_test
        )

        # ---------- 2. Experiment (ground-truth baseline EUI as feature) ----------
        bl_gt_train_col = baseline_train[fuel_name].reshape(-1, 1)
        bl_gt_test_col = baseline_test[fuel_name].reshape(-1, 1)

        X_exp_train = np.hstack([X_base_train.values, bl_gt_train_col])
        X_exp_test = np.hstack([X_base_test.values, bl_gt_test_col])

        # Rebuild as DataFrame so XGBoost sees categorical dtypes for original cols
        exp_col_names = list(X_base_train.columns) + [f"baseline_{fuel_name}"]
        X_exp_train_df = pd.DataFrame(X_exp_train, columns=exp_col_names)
        X_exp_test_df = pd.DataFrame(X_exp_test, columns=exp_col_names)
        # Restore categorical dtypes for the base feature columns
        for col in X_base_train.columns:
            if hasattr(X_base_train[col], 'cat'):
                X_exp_train_df[col] = pd.Categorical(
                    X_exp_train_df[col], categories=X_base_train[col].cat.categories
                )
                X_exp_test_df[col] = pd.Categorical(
                    X_exp_test_df[col], categories=X_base_test[col].cat.categories
                )

        _, exp_mae, exp_rmse, exp_r2 = train_and_evaluate(
            X_exp_train_df, y_train, X_exp_test_df, y_test
        )

        # ---------- 3. Error propagation (predicted baseline as feature) ----------
        bl_pred_test_col = predicted_baseline_test[fuel_name].reshape(-1, 1)
        # Training still uses ground-truth baseline (at inference time, we'd have
        # a predicted baseline from the baseline model)
        X_ep_train_df = X_exp_train_df.copy()
        X_ep_test = np.hstack([X_base_test.values, bl_pred_test_col])
        X_ep_test_df = pd.DataFrame(X_ep_test, columns=exp_col_names)
        for col in X_base_test.columns:
            if hasattr(X_base_test[col], 'cat'):
                X_ep_test_df[col] = pd.Categorical(
                    X_ep_test_df[col], categories=X_base_test[col].cat.categories
                )

        # Retrain with gt baseline as feature (same model as experiment), evaluate
        # on test set using *predicted* baseline feature
        ep_model = XGBRegressor(
            objective='reg:squarederror',
            random_state=RANDOM_SEED,
            n_jobs=-1,
            enable_categorical=True,
            **DEFAULT_PARAMS
        )
        ep_model.fit(X_exp_train_df, y_train)
        ep_pred = ep_model.predict(X_ep_test_df)
        ep_mae, ep_rmse, ep_r2 = compute_metrics(y_test, ep_pred)

        # ---------- 4. Noise 10% ----------
        rng = np.random.RandomState(RANDOM_SEED)
        noise_std_10 = 0.10 * np.std(baseline_train[fuel_name])

        bl_noisy10_train = baseline_train[fuel_name] + rng.normal(0, noise_std_10, size=len(train_idx))
        bl_noisy10_test = baseline_test[fuel_name] + rng.normal(0, noise_std_10, size=len(test_idx))

        X_n10_train = np.hstack([X_base_train.values, bl_noisy10_train.reshape(-1, 1)])
        X_n10_test = np.hstack([X_base_test.values, bl_noisy10_test.reshape(-1, 1)])
        X_n10_train_df = pd.DataFrame(X_n10_train, columns=exp_col_names)
        X_n10_test_df = pd.DataFrame(X_n10_test, columns=exp_col_names)
        for col in X_base_train.columns:
            if hasattr(X_base_train[col], 'cat'):
                X_n10_train_df[col] = pd.Categorical(
                    X_n10_train_df[col], categories=X_base_train[col].cat.categories
                )
                X_n10_test_df[col] = pd.Categorical(
                    X_n10_test_df[col], categories=X_base_test[col].cat.categories
                )

        _, n10_mae, n10_rmse, n10_r2 = train_and_evaluate(
            X_n10_train_df, y_train, X_n10_test_df, y_test
        )

        # ---------- 5. Noise 20% ----------
        rng2 = np.random.RandomState(RANDOM_SEED)
        noise_std_20 = 0.20 * np.std(baseline_train[fuel_name])

        bl_noisy20_train = baseline_train[fuel_name] + rng2.normal(0, noise_std_20, size=len(train_idx))
        bl_noisy20_test = baseline_test[fuel_name] + rng2.normal(0, noise_std_20, size=len(test_idx))

        X_n20_train = np.hstack([X_base_train.values, bl_noisy20_train.reshape(-1, 1)])
        X_n20_test = np.hstack([X_base_test.values, bl_noisy20_test.reshape(-1, 1)])
        X_n20_train_df = pd.DataFrame(X_n20_train, columns=exp_col_names)
        X_n20_test_df = pd.DataFrame(X_n20_test, columns=exp_col_names)
        for col in X_base_train.columns:
            if hasattr(X_base_train[col], 'cat'):
                X_n20_train_df[col] = pd.Categorical(
                    X_n20_train_df[col], categories=X_base_train[col].cat.categories
                )
                X_n20_test_df[col] = pd.Categorical(
                    X_n20_test_df[col], categories=X_base_test[col].cat.categories
                )

        _, n20_mae, n20_rmse, n20_r2 = train_and_evaluate(
            X_n20_train_df, y_train, X_n20_test_df, y_test
        )

        delta_r2 = exp_r2 - ctrl_r2
        print(
            f"    {fuel_name:>18}: Ctrl R²={ctrl_r2:.4f}  Exp R²={exp_r2:.4f}  "
            f"Δ={delta_r2:+.4f}  ErrProp R²={ep_r2:.4f}  "
            f"Noise10%={n10_r2:.4f}  Noise20%={n20_r2:.4f}"
        )

        results.append({
            'dataset': cfg['name'],
            'upgrade_id': upgrade_id,
            'fuel': fuel_name,
            'n_paired': len(df),
            'n_train': len(train_idx),
            'n_test': len(test_idx),
            # Control
            'ctrl_mae': ctrl_mae,
            'ctrl_rmse': ctrl_rmse,
            'ctrl_r2': ctrl_r2,
            # Experiment (ground-truth baseline as feature)
            'exp_mae': exp_mae,
            'exp_rmse': exp_rmse,
            'exp_r2': exp_r2,
            'delta_r2': delta_r2,
            # Error propagation (predicted baseline as feature)
            'errprop_mae': ep_mae,
            'errprop_rmse': ep_rmse,
            'errprop_r2': ep_r2,
            # Noise 10%
            'noise10_mae': n10_mae,
            'noise10_rmse': n10_rmse,
            'noise10_r2': n10_r2,
            # Noise 20%
            'noise20_mae': n20_mae,
            'noise20_rmse': n20_rmse,
            'noise20_r2': n20_r2,
        })

    return results


# ==============================================================================
# OUTPUT / REPORTING
# ==============================================================================

def print_summary_table(all_results):
    """Print a formatted console summary table."""
    header = (
        f"{'Dataset':<10} | {'Upgrade':>7} | {'Fuel':<18} | "
        f"{'Control R²':>10} | {'Experiment R²':>13} | {'Delta R²':>8} | "
        f"{'ErrProp R²':>10} | {'Noise10% R²':>11} | {'Noise20% R²':>11}"
    )
    sep = "-" * len(header)
    print("\n" + sep)
    print(header)
    print(sep)
    for r in all_results:
        print(
            f"{r['dataset']:<10} | {r['upgrade_id']:>7} | {r['fuel']:<18} | "
            f"{r['ctrl_r2']:>10.3f} | {r['exp_r2']:>13.3f} | {r['delta_r2']:>+8.3f} | "
            f"{r['errprop_r2']:>10.3f} | {r['noise10_r2']:>11.3f} | {r['noise20_r2']:>11.3f}"
        )
    print(sep)


def save_csv(all_results, output_path):
    """Save detailed results to CSV."""
    df = pd.DataFrame(all_results)
    df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")


# ==============================================================================
# CLI / MAIN
# ==============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Validation experiment: does adding baseline EUI as a feature "
            "improve delta (savings) model predictions?"
        )
    )
    parser.add_argument(
        '--dataset',
        choices=['comstock', 'resstock', 'both'],
        default='comstock',
        help='Which dataset(s) to run experiments on (default: comstock)'
    )
    parser.add_argument(
        '--upgrades',
        default='auto',
        help=(
            'Comma-separated upgrade IDs to test, e.g. "1,5,10,15,20", '
            'or "auto" to use the default top 5 per dataset (default: auto)'
        )
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Path for output CSV file (default: scripts/validate_baseline_feature_results_<timestamp>.csv)'
    )
    return parser.parse_args()


def resolve_datasets(dataset_arg):
    """Return list of config dicts based on --dataset argument."""
    if dataset_arg == 'comstock':
        return [COMSTOCK_CONFIG]
    elif dataset_arg == 'resstock':
        return [RESSTOCK_CONFIG]
    else:  # 'both'
        return [COMSTOCK_CONFIG, RESSTOCK_CONFIG]


def resolve_upgrades(upgrades_arg, cfg):
    """Return list of upgrade IDs to process for a given dataset config."""
    if upgrades_arg == 'auto':
        return cfg['default_top_upgrades']
    try:
        return [int(u.strip()) for u in upgrades_arg.split(',') if u.strip()]
    except ValueError as e:
        raise ValueError(
            f"--upgrades must be a comma-separated list of integers or 'auto'. Got: {upgrades_arg!r}"
        ) from e


def main():
    args = parse_args()

    datasets = resolve_datasets(args.dataset)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = args.output or os.path.join(
        PROJECT_ROOT, 'scripts', f'validate_baseline_feature_results_{timestamp}.csv'
    )

    all_results = []

    for cfg in datasets:
        dataset_name = cfg['name']
        upgrade_ids = resolve_upgrades(args.upgrades, cfg)

        print(f"\n{'=' * 70}")
        print(f"DATASET: {dataset_name.upper()}  |  Upgrades: {upgrade_ids}")
        print(f"{'=' * 70}")

        # Load shared lookups and baseline data once per dataset
        cluster_lookup = load_cluster_lookup(cfg['lookup_path'])

        print(f"Loading baseline data for {dataset_name}...")
        df_baseline = load_baseline_data(cfg, cluster_lookup)
        print(f"  Baseline buildings loaded: {len(df_baseline)}")

        for uid in upgrade_ids:
            print(f"\n  Upgrade {uid}:")
            df_paired, n_applicable, n_paired = load_paired_data(cfg, uid, df_baseline)

            if df_paired is None or n_paired < 50:
                print(f"    SKIPPED — insufficient paired data (n={n_paired})")
                continue

            print(f"    n_applicable={n_applicable}, n_paired={n_paired}")

            upgrade_results = run_upgrade_experiment(cfg, uid, df_paired)
            all_results.extend(upgrade_results)

    if not all_results:
        print("\nNo results generated — check that parquet files exist and upgrades are valid.")
        return

    print_summary_table(all_results)
    save_csv(all_results, output_path)


if __name__ == '__main__':
    main()
