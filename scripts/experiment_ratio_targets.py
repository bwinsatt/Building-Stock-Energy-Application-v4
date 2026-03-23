#!/usr/bin/env python3
"""
Experiment: Ratio-based delta targets vs absolute delta targets.

Instead of training on absolute savings (baseline - upgrade in kWh/ft²),
train on the savings ratio: (baseline - upgrade) / baseline.

At inference, multiply predicted ratio by actual baseline to get savings.
This should naturally bound predictions relative to consumption and produce
better results for buildings with unusual fuel mixes (e.g., district heating).

Test upgrades: 18 (Electric Resistance Boilers), 12 (VRF with DOAS),
               31 (Chiller Replacement)

Compares:
  - Current approach: absolute delta targets
  - New approach: ratio targets (savings / baseline)
  - Evaluation on ALL buildings and specifically on DISTRICT HEATING buildings
"""
import os
import sys
import time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import (
    encode_features, train_single_model, evaluate_model,
    prepare_catboost_data, train_lightgbm_model, train_catboost_model,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')

# Test across measure categories:
# Fuel-switching: 18 (Elec Resist Boilers), 15 (HP Boiler Elec Backup)
# HVAC replacement: 12 (VRF+DOAS), 31 (Chiller Replacement)
# Controls: 20 (DCV), 25 (Thermostat Setbacks)
# Envelope: 49 (Roof Insulation)
# Lighting: 43 (LED Lighting)
# PV: 46 (PV 40% Roof)
TEST_UPGRADES = [18, 15, 12, 31, 20, 25, 49, 43, 46]

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
    'hdd65f',
    'cdd65f',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
    'floor_plate_sqft',
    'baseline_electricity',
    'baseline_natural_gas',
    'baseline_fuel_oil',
    'baseline_propane',
    'baseline_district_heating',
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
    'in.building_subtype',
    'in.aspect_ratio',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
]

# Columns to load from parquet
LOAD_COLS = ['bldg_id', 'completed_status', 'applicability',
             'in.as_simulated_nhgis_county_gisjoin'] + FEATURE_COLS + list(FUEL_TYPES.values()) + [
    'out.params.hdd65f', 'out.params.cdd65f',
    'in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
]
LOAD_COLS = [c for c in LOAD_COLS if c not in ('cluster_name', 'hdd65f', 'cdd65f',
                                                 'floor_plate_sqft',
                                                 'baseline_electricity', 'baseline_natural_gas',
                                                 'baseline_fuel_oil', 'baseline_propane',
                                                 'baseline_district_heating')]
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))

# Minimum baseline EUI to compute ratio (avoid division by near-zero)
RATIO_FLOOR = 0.01  # kWh/ft²

# XGBoost default params
DEFAULT_PARAMS = {
    'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
    'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
}

KWH_TO_KBTU = 3.412


# ==============================================================================
# DATA LOADING (copied from train_comstock_deltas.py)
# ==============================================================================

def load_cluster_lookup():
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_baseline_data(cluster_lookup):
    fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    df = pd.read_parquet(fname, columns=LOAD_COLS)
    df = df.drop_duplicates(subset='bldg_id')

    df = df.merge(cluster_lookup, left_on='in.as_simulated_nhgis_county_gisjoin',
                  right_on='nhgis_county_gisjoin', how='left')
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    fuel_cols = list(FUEL_TYPES.values())
    df = df.dropna(subset=fuel_cols, how='all')
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

    df = df.rename(columns={'out.params.hdd65f': 'hdd65f', 'out.params.cdd65f': 'cdd65f'})

    tstat_cols = ['in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
                  'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
                  'in.weekend_operating_hours..hr']
    for col in tstat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df.loc[df[col] >= 999, col] = float('nan')

    df['floor_plate_sqft'] = (pd.to_numeric(df['in.sqft..ft2'], errors='coerce')
                               / pd.to_numeric(df['in.number_stories'], errors='coerce').clip(lower=1))

    for fuel_name in FUEL_TYPES:
        df[f'baseline_{fuel_name}'] = float('nan')

    return df


def load_paired_data(upgrade_id, df_baseline, cluster_lookup):
    fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}_agg.parquet')
    if not os.path.exists(fname):
        return None, 0, 0

    upgrade_load_cols = ['bldg_id', 'completed_status', 'applicability'] + list(FUEL_TYPES.values())
    df_upg = pd.read_parquet(fname, columns=upgrade_load_cols)
    df_upg = df_upg.drop_duplicates(subset='bldg_id')
    df_upg = df_upg[df_upg['completed_status'] == 'Success']
    df_upg = df_upg[df_upg['applicability'] == True]
    n_applicable = len(df_upg)

    fuel_rename = {col: f"upgrade_{col}" for col in FUEL_TYPES.values()}
    df_upg = df_upg.rename(columns=fuel_rename)
    df_upg = df_upg.drop(columns=['completed_status', 'applicability'])

    for col in fuel_rename.values():
        df_upg[col] = df_upg[col].fillna(0)

    df = df_baseline.merge(df_upg, on='bldg_id', how='inner')
    n_paired = len(df)

    # Compute absolute deltas
    for fuel_name, fuel_col in FUEL_TYPES.items():
        df[f"delta_{fuel_name}"] = df[fuel_col] - df[f"upgrade_{fuel_col}"]

    # Compute ratio targets: savings / baseline (only where baseline > floor)
    for fuel_name, fuel_col in FUEL_TYPES.items():
        baseline_vals = df[fuel_col]
        delta_vals = df[f"delta_{fuel_name}"]
        # Ratio = savings / baseline; set to 0 where baseline is near-zero
        ratio = np.where(baseline_vals > RATIO_FLOOR,
                         delta_vals / baseline_vals,
                         0.0)
        # Clip ratio to [-5, 1] — savings can't exceed 100% of baseline,
        # but fuel-switching can increase consumption up to 5x (generous bound)
        df[f"ratio_{fuel_name}"] = np.clip(ratio, -5.0, 1.0)

    # Baseline EUI features
    FUEL_COL_MAP = {
        'out.electricity.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_electricity',
        'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_natural_gas',
        'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_fuel_oil',
        'out.propane.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_propane',
        'out.district_heating.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_district_heating',
    }
    for orig_col, new_col in FUEL_COL_MAP.items():
        if orig_col in df.columns:
            df[new_col] = df[orig_col]

    df = df.drop(columns=['bldg_id', 'completed_status', 'applicability',
                           'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
                  errors='ignore')

    for col in fuel_rename.values():
        df = df.drop(columns=[col], errors='ignore')

    return df, n_applicable, n_paired


# ==============================================================================
# EVALUATION HELPERS
# ==============================================================================

def evaluate_on_subset(y_true, y_pred, label=""):
    """Compute metrics on a subset, return dict."""
    if len(y_true) == 0:
        return {'n': 0, 'mae_kbtu_sf': np.nan, 'rmse_kwh_ft2': np.nan, 'r2': np.nan}
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        'n': len(y_true),
        'mae_kbtu_sf': mae * KWH_TO_KBTU,
        'rmse_kwh_ft2': rmse,
        'r2': r2,
    }


def evaluate_ratio_as_absolute(ratio_pred, baseline_vals, y_true_absolute):
    """Convert ratio predictions back to absolute savings and evaluate."""
    # Predicted absolute savings = predicted ratio * actual baseline
    y_pred_absolute = ratio_pred * baseline_vals
    return evaluate_on_subset(y_true_absolute, y_pred_absolute)


# ==============================================================================
# MAIN EXPERIMENT
# ==============================================================================

def run_experiment():
    print("=" * 80)
    print("EXPERIMENT: Ratio-based targets vs Absolute delta targets")
    print("=" * 80)

    cluster_lookup = load_cluster_lookup()
    print("\nLoading baseline data...")
    df_baseline = load_baseline_data(cluster_lookup)
    print(f"  Baseline buildings: {len(df_baseline):,}")

    # Count district heating buildings
    dh_col = FUEL_TYPES['district_heating']
    n_dh_baseline = (df_baseline[dh_col] > RATIO_FLOOR).sum()
    print(f"  District heating buildings (baseline > {RATIO_FLOOR}): {n_dh_baseline:,}")

    all_results = []

    for uid in TEST_UPGRADES:
        print(f"\n{'=' * 70}")
        print(f"UPGRADE {uid}")
        print(f"{'=' * 70}")

        df, n_applicable, n_paired = load_paired_data(uid, df_baseline, cluster_lookup)
        if df is None or n_paired < 100:
            print(f"  SKIPPED: insufficient data ({n_paired} rows)")
            continue

        print(f"  Applicable: {n_applicable:,}  |  Paired: {n_paired:,}")

        # Identify district heating buildings in paired data
        dh_mask = df[FUEL_TYPES['district_heating']] > RATIO_FLOOR
        # Standard gas-heated buildings: meaningful gas, no district heating
        gas_mask = ((df[FUEL_TYPES['natural_gas']] > RATIO_FLOOR)
                    & ~dh_mask)
        print(f"  District heating buildings: {dh_mask.sum():,} ({dh_mask.mean()*100:.1f}%)")
        print(f"  Standard gas-heated buildings: {gas_mask.sum():,} ({gas_mask.mean()*100:.1f}%)")

        # Encode features
        X_enc, encoders = encode_features(df, FEATURE_COLS)
        cat_indices = [i for i, col in enumerate(FEATURE_COLS) if col in CAT_FEATURE_NAMES]

        # Single train/test split
        train_idx, test_idx = train_test_split(
            np.arange(len(X_enc)), test_size=0.2, random_state=42
        )

        dh_test_mask = dh_mask.values[test_idx]
        gas_test_mask = gas_mask.values[test_idx]

        for fuel_name, fuel_col in FUEL_TYPES.items():
            target_abs = f"delta_{fuel_name}"
            target_ratio = f"ratio_{fuel_name}"

            y_abs = df[target_abs].values
            y_ratio = df[target_ratio].values
            baseline_vals = df[fuel_col].values

            # Skip if all absolute targets are constant
            if np.std(y_abs[train_idx]) < 1e-10:
                print(f"\n  {fuel_name:>18}: SKIPPED (constant target)")
                continue

            # Check if ratio target has signal
            ratio_std = np.std(y_ratio[train_idx])
            if ratio_std < 1e-10:
                print(f"\n  {fuel_name:>18}: SKIPPED (constant ratio target)")
                continue

            print(f"\n  --- {fuel_name} ---")

            # =============================================
            # Approach A: Absolute delta (current approach)
            # =============================================
            model_abs = train_single_model(X_enc.iloc[train_idx], y_abs[train_idx], DEFAULT_PARAMS)
            pred_abs = model_abs.predict(X_enc.iloc[test_idx])


            metrics_abs_all = evaluate_on_subset(y_abs[test_idx], pred_abs, "abs_all")
            metrics_abs_dh = evaluate_on_subset(
                y_abs[test_idx][dh_test_mask], pred_abs[dh_test_mask], "abs_dh"
            )

            # =============================================
            # Approach B: Ratio target (new approach)
            # =============================================
            model_ratio = train_single_model(X_enc.iloc[train_idx], y_ratio[train_idx], DEFAULT_PARAMS)
            pred_ratio = model_ratio.predict(X_enc.iloc[test_idx])

            # Convert ratio predictions back to absolute for apples-to-apples comparison
            baseline_test = baseline_vals[test_idx]
            metrics_ratio_all = evaluate_ratio_as_absolute(
                pred_ratio, baseline_test, y_abs[test_idx]
            )
            metrics_ratio_dh = evaluate_ratio_as_absolute(
                pred_ratio[dh_test_mask], baseline_vals[test_idx][dh_test_mask],
                y_abs[test_idx][dh_test_mask]
            )
            metrics_ratio_gas = evaluate_ratio_as_absolute(
                pred_ratio[gas_test_mask], baseline_vals[test_idx][gas_test_mask],
                y_abs[test_idx][gas_test_mask]
            )

            # Also evaluate absolute model on gas subset
            metrics_abs_gas = evaluate_on_subset(
                y_abs[test_idx][gas_test_mask], pred_abs[gas_test_mask], "abs_gas"
            )

            # =============================================
            # Physical violation check: how often does predicted savings > baseline?
            # =============================================
            # Absolute model violations
            has_fuel = baseline_test > RATIO_FLOOR
            abs_violations = np.sum((pred_abs > 0) & (pred_abs > baseline_test) & has_fuel)
            abs_violation_pct = abs_violations / max(1, np.sum(has_fuel)) * 100

            # Ratio model violations (after converting to absolute)
            pred_ratio_abs = pred_ratio * baseline_test
            ratio_violations = np.sum((pred_ratio_abs > 0) & (pred_ratio_abs > baseline_test) & has_fuel)
            ratio_violation_pct = ratio_violations / max(1, np.sum(has_fuel)) * 100

            # Print comparison
            print(f"    {'':30s} {'MAE (kBtu/sf)':>14s} {'RMSE (kWh/ft²)':>16s} {'R²':>8s} {'Violations':>12s}")
            print(f"    {'Absolute (all)':30s} {metrics_abs_all['mae_kbtu_sf']:14.4f} {metrics_abs_all['rmse_kwh_ft2']:16.4f} {metrics_abs_all['r2']:8.4f} {abs_violation_pct:10.1f}%")
            print(f"    {'Ratio→Abs (all)':30s} {metrics_ratio_all['mae_kbtu_sf']:14.4f} {metrics_ratio_all['rmse_kwh_ft2']:16.4f} {metrics_ratio_all['r2']:8.4f} {ratio_violation_pct:10.1f}%")

            if gas_test_mask.sum() > 0:
                bl_gas = baseline_test[gas_test_mask]
                pred_abs_gas_v = pred_abs[gas_test_mask]
                pred_ratio_abs_gas = pred_ratio_abs[gas_test_mask]
                abs_viol_gas = np.sum((pred_abs_gas_v > 0) & (pred_abs_gas_v > bl_gas) & (bl_gas > RATIO_FLOOR)) / max(1, np.sum(bl_gas > RATIO_FLOOR)) * 100
                ratio_viol_gas = np.sum((pred_ratio_abs_gas > 0) & (pred_ratio_abs_gas > bl_gas) & (bl_gas > RATIO_FLOOR)) / max(1, np.sum(bl_gas > RATIO_FLOOR)) * 100

                print(f"    {'Absolute (gas-heated)':30s} {metrics_abs_gas['mae_kbtu_sf']:14.4f} {metrics_abs_gas['rmse_kwh_ft2']:16.4f} {metrics_abs_gas['r2']:8.4f} {abs_viol_gas:10.1f}%")
                print(f"    {'Ratio→Abs (gas-heated)':30s} {metrics_ratio_gas['mae_kbtu_sf']:14.4f} {metrics_ratio_gas['rmse_kwh_ft2']:16.4f} {metrics_ratio_gas['r2']:8.4f} {ratio_viol_gas:10.1f}%")
                print(f"    (n_gas_test={gas_test_mask.sum()})")

            if dh_test_mask.sum() > 0:
                bl_dh = baseline_test[dh_test_mask]
                pred_abs_dh = pred_abs[dh_test_mask]
                pred_ratio_abs_dh = pred_ratio_abs[dh_test_mask]
                abs_viol_dh = np.sum((pred_abs_dh > 0) & (pred_abs_dh > bl_dh) & (bl_dh > RATIO_FLOOR)) / max(1, np.sum(bl_dh > RATIO_FLOOR)) * 100
                ratio_viol_dh = np.sum((pred_ratio_abs_dh > 0) & (pred_ratio_abs_dh > bl_dh) & (bl_dh > RATIO_FLOOR)) / max(1, np.sum(bl_dh > RATIO_FLOOR)) * 100

                print(f"    {'Absolute (district heat)':30s} {metrics_abs_dh['mae_kbtu_sf']:14.4f} {metrics_abs_dh['rmse_kwh_ft2']:16.4f} {metrics_abs_dh['r2']:8.4f} {abs_viol_dh:10.1f}%")
                print(f"    {'Ratio→Abs (district heat)':30s} {metrics_ratio_dh['mae_kbtu_sf']:14.4f} {metrics_ratio_dh['rmse_kwh_ft2']:16.4f} {metrics_ratio_dh['r2']:8.4f} {ratio_viol_dh:10.1f}%")
                print(f"    (n_dh_test={dh_test_mask.sum()})")
            else:
                print(f"    (no district heating buildings in test set)")

            # Store results
            for approach, m_all, m_dh, m_gas in [
                ('absolute', metrics_abs_all, metrics_abs_dh, metrics_abs_gas),
                ('ratio', metrics_ratio_all, metrics_ratio_dh, metrics_ratio_gas),
            ]:
                all_results.append({
                    'upgrade_id': uid,
                    'fuel': fuel_name,
                    'approach': approach,
                    'mae_all': m_all['mae_kbtu_sf'],
                    'r2_all': m_all['r2'],
                    'mae_gas': m_gas['mae_kbtu_sf'],
                    'r2_gas': m_gas['r2'],
                    'n_gas': m_gas['n'],
                    'mae_dh': m_dh['mae_kbtu_sf'],
                    'r2_dh': m_dh['r2'],
                    'n_dh': m_dh['n'],
                })

    # ==============================================================================
    # SUMMARY TABLE
    # ==============================================================================
    print("\n\n" + "=" * 80)
    print("SUMMARY: Ratio vs Absolute (MAE in kBtu/sf, lower is better)")
    print("=" * 80)

    if all_results:
        results_df = pd.DataFrame(all_results)

        for uid in TEST_UPGRADES:
            df_u = results_df[results_df['upgrade_id'] == uid]
            if df_u.empty:
                continue
            print(f"\n  Upgrade {uid}:")

            for subset, mae_col in [('All Buildings', 'mae_all'), ('Gas-Heated', 'mae_gas'), ('District Heat', 'mae_dh')]:
                print(f"\n    {subset}:")
                print(f"    {'Fuel':>18s} | {'Absolute':>10s} {'Ratio':>10s} {'Δ%':>8s}")
                print(f"    {'-'*18}-+-{'-'*10}-{'-'*10}-{'-'*8}")

                for fuel in FUEL_TYPES:
                    abs_row = df_u[(df_u['fuel'] == fuel) & (df_u['approach'] == 'absolute')]
                    ratio_row = df_u[(df_u['fuel'] == fuel) & (df_u['approach'] == 'ratio')]
                    if abs_row.empty or ratio_row.empty:
                        continue

                    mae_a = abs_row.iloc[0][mae_col]
                    mae_r = ratio_row.iloc[0][mae_col]
                    pct = (mae_r - mae_a) / mae_a * 100 if mae_a > 0 else 0
                    flag = "✓" if pct < 0 else ("=" if abs(pct) < 0.5 else "✗")

                    print(f"    {fuel:>18s} | {mae_a:10.4f} {mae_r:10.4f} {pct:+7.1f}%{flag}")

        # Save results
        out_path = os.path.join(PROJECT_ROOT, 'scripts',
                                f'experiment_ratio_targets_results.csv')
        results_df.to_csv(out_path, index=False)
        print(f"\n  Results saved to {out_path}")

    print("\n  Negative Δ% = ratio approach is better (lower MAE)")
    print("  DH columns show performance specifically on district heating buildings")


if __name__ == '__main__':
    run_experiment()
