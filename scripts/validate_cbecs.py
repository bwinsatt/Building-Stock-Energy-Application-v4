#!/usr/bin/env python3
"""
Validate ComStock baseline model predictions against CBECS 2018 real-world data.

Loads the trained baseline model (upgrade 0) and compares predictions to actual
EUI values from the CBECS 2018 survey. CBECS is an approximation of real-world
data — the mappings are approximate and results may diverge for reasons beyond
model accuracy.

Usage:
    python3 scripts/validate_cbecs.py
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

CBECS_PATH = os.path.join(PROJECT_ROOT, 'Validation', 'CBECS', 'cbecs2018_mapped_for_xgb.csv')
MODEL_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3')
BASELINE_MODEL = os.path.join(MODEL_DIR, 'XGB_upgrade0.pkl')
BASELINE_ENCODERS = os.path.join(MODEL_DIR, 'XGB_upgrade0_encoders.pkl')
BASELINE_META = os.path.join(MODEL_DIR, 'XGB_upgrade0_meta.json')

# CBECS column -> ComStock feature mapping
# CBECS was mapped to the OLD model features (9 categorical, binned).
# Our new model uses 25 features with raw values.
# We need to map CBECS columns to the new feature names.
CBECS_TO_COMSTOCK = {
    'in.building_type': 'in.comstock_building_type_group',
    'SQFT': 'in.sqft..ft2',
    'NFLOOR': 'in.number_stories',
    'climate_zone_ashrae_2006': 'in.as_simulated_ashrae_iecc_climate_zone_2006',
    'cluster_name': 'cluster_name',
    'year_built': 'in.vintage',
    'in.heating_fuel': 'in.heating_fuel',
    'in.water_heater_fuel': 'in.service_water_heating_fuel',
    'in.hvac_category': 'in.hvac_category',
}

# Building type mapping: CBECS uses detailed types, ComStock uses groups
BT_TO_GROUP = {
    'SmallOffice': 'Office', 'MediumOffice': 'Office', 'LargeOffice': 'Office',
    'SmallHotel': 'Lodging', 'LargeHotel': 'Lodging',
    'QuickServiceRestaurant': 'Food Service', 'FullServiceRestaurant': 'Food Service',
    'Outpatient': 'Healthcare', 'Hospital': 'Healthcare',
    'PrimarySchool': 'Education', 'SecondarySchool': 'Education',
    'RetailStandalone': 'Mercantile', 'RetailStripmall': 'Mercantile',
    'Warehouse': 'Warehouse and Storage',
}

# Vintage mapping: CBECS bins -> ComStock vintage values
YEARBUILT_TO_VINTAGE = {
    '<1946': 'Before 1980',
    '1946-1959': 'Before 1980',
    '1960-1979': 'Before 1980',
    '1980-1999': '1980 to 1989',  # approximation
    '2000-2009': '2000 to 2012',
    '>2010': '2013+',
}


def main():
    print("=" * 70)
    print("CBECS 2018 VALIDATION")
    print("NOTE: CBECS is an approximation of real-world data.")
    print("Mappings are approximate. Results may diverge from model predictions")
    print("for reasons beyond model accuracy.")
    print("=" * 70)

    # Check model exists
    if not os.path.exists(BASELINE_MODEL):
        print(f"\nERROR: Baseline model not found at {BASELINE_MODEL}")
        print("Run train_comstock_upgrades.py --upgrades 0 first.")
        sys.exit(1)

    # Load CBECS data
    cbecs = pd.read_csv(CBECS_PATH)
    print(f"\nLoaded CBECS: {len(cbecs)} buildings")

    # Filter to buildings with valid building type and EUI
    cbecs = cbecs[cbecs['in.building_type'].notna()].copy()
    cbecs = cbecs[cbecs['total_site_eui'].notna() & (cbecs['total_site_eui'] > 0)].copy()
    print(f"After filtering: {len(cbecs)} buildings with valid type + EUI")

    # Load model and metadata
    model = joblib.load(BASELINE_MODEL)
    encoders = joblib.load(BASELINE_ENCODERS)
    with open(BASELINE_META) as f:
        meta = json.load(f)
    feature_cols = meta['feature_columns']

    # Map CBECS columns to model features
    # Start with the features the model expects, fill what we can from CBECS
    pred_df = pd.DataFrame(index=cbecs.index)

    # Map building type to group
    pred_df['in.comstock_building_type_group'] = cbecs['in.building_type'].map(BT_TO_GROUP)
    pred_df['in.sqft..ft2'] = cbecs['SQFT'].astype(float)
    pred_df['in.number_stories'] = cbecs['NFLOOR'].astype(str)
    pred_df['in.as_simulated_ashrae_iecc_climate_zone_2006'] = cbecs['climate_zone_ashrae_2006']
    pred_df['cluster_name'] = cbecs['cluster_name'].fillna('Unknown')
    pred_df['in.vintage'] = cbecs['year_built'].map(YEARBUILT_TO_VINTAGE).fillna('1980 to 1989')
    pred_df['in.heating_fuel'] = cbecs['in.heating_fuel'].fillna('NaturalGas')
    pred_df['in.service_water_heating_fuel'] = cbecs['in.water_heater_fuel'].fillna('NaturalGas')
    pred_df['in.hvac_category'] = cbecs['in.hvac_category'].fillna('Small Packaged Unit')

    # Fill remaining features with most common values (imputation)
    # These features aren't available in CBECS
    defaults = {
        'in.hvac_cool_type': 'DX',
        'in.hvac_heat_type': 'Furnace',
        'in.hvac_system_type': 'PSZ-AC with gas coil',
        'in.hvac_vent_type': 'Central Single-zone RTU',
        'in.wall_construction_type': 'SteelFramed',
        'in.window_type': 'Double - No LowE - Clear - Aluminum',
        'in.window_to_wall_ratio_category': '11_25pct',
        'in.airtightness..m3_per_m2_h': '20',
        'in.interior_lighting_generation': 'gen2_t8_halogen',
        'in.weekday_operating_hours..hr': '9',
        'in.building_subtype': 'NA',
        'in.aspect_ratio': '1',
        'in.energy_code_followed_during_last_hvac_replacement': 'ComStock DOE Ref 1980-2004',
        'in.energy_code_followed_during_last_roof_replacement': 'ComStock DOE Ref Pre-1980',
        'in.energy_code_followed_during_last_walls_replacement': 'ComStock DOE Ref Pre-1980',
        'in.energy_code_followed_during_last_svc_water_htg_replacement': 'ComStock DOE Ref Pre-1980',
    }
    for col, default in defaults.items():
        if col in feature_cols:
            pred_df[col] = default

    # Drop rows where building type mapping failed
    valid_mask = pred_df['in.comstock_building_type_group'].notna()
    pred_df = pred_df[valid_mask]
    cbecs_valid = cbecs[valid_mask]
    print(f"After building type mapping: {len(pred_df)} buildings")

    # Encode features using the trained encoders
    from scripts.training_utils import encode_features
    X_enc, _ = encode_features(pred_df, feature_cols, encoders=encoders)

    # Predict
    y_pred_kwh = model.predict(X_enc)
    y_pred_kbtu = y_pred_kwh * 3.412  # Convert to kBtu/sf
    y_actual_kbtu = cbecs_valid['total_site_eui'].values

    # Overall metrics
    mae = mean_absolute_error(y_actual_kbtu, y_pred_kbtu)
    rmse = np.sqrt(mean_squared_error(y_actual_kbtu, y_pred_kbtu))
    r2 = r2_score(y_actual_kbtu, y_pred_kbtu)
    mape = np.mean(np.abs((y_actual_kbtu - y_pred_kbtu) / np.maximum(y_actual_kbtu, 1))) * 100

    print(f"\n{'=' * 50}")
    print(f"OVERALL RESULTS (n={len(y_actual_kbtu)})")
    print(f"{'=' * 50}")
    print(f"  MAE:  {mae:.1f} kBtu/sf")
    print(f"  RMSE: {rmse:.1f} kBtu/sf")
    print(f"  R²:   {r2:.4f}")
    print(f"  MAPE: {mape:.1f}%")
    print(f"  Actual mean EUI:    {y_actual_kbtu.mean():.1f} kBtu/sf")
    print(f"  Predicted mean EUI: {y_pred_kbtu.mean():.1f} kBtu/sf")

    # Per building type
    print(f"\n{'=' * 50}")
    print(f"RESULTS BY BUILDING TYPE")
    print(f"{'=' * 50}")
    bt_col = pred_df['in.comstock_building_type_group'].values
    results_by_bt = []
    for bt in sorted(set(bt_col)):
        mask = bt_col == bt
        if mask.sum() < 5:
            continue
        bt_mae = mean_absolute_error(y_actual_kbtu[mask], y_pred_kbtu[mask])
        bt_r2 = r2_score(y_actual_kbtu[mask], y_pred_kbtu[mask]) if mask.sum() > 1 else float('nan')
        bt_actual_mean = y_actual_kbtu[mask].mean()
        bt_pred_mean = y_pred_kbtu[mask].mean()
        results_by_bt.append({
            'building_type': bt, 'n': mask.sum(),
            'actual_mean_eui': bt_actual_mean, 'predicted_mean_eui': bt_pred_mean,
            'mae_kbtu_sf': bt_mae, 'r2': bt_r2,
        })
        print(f"  {bt:<25} n={mask.sum():<5} actual={bt_actual_mean:6.1f}  pred={bt_pred_mean:6.1f}  "
              f"MAE={bt_mae:5.1f}  R²={bt_r2:.3f}")

    # Save results
    output_dir = os.path.join(PROJECT_ROOT, 'Validation', 'CBECS')
    results_df = pd.DataFrame(results_by_bt)
    results_df.to_excel(os.path.join(output_dir, 'cbecs_validation_results.xlsx'), index=False)

    # Save predictions for inspection
    comparison = cbecs_valid[['PUBID', 'in.building_type', 'SQFT', 'climate_zone_ashrae_2006',
                               'total_site_eui']].copy()
    comparison['predicted_total_eui_kbtu'] = y_pred_kbtu
    comparison['residual'] = y_actual_kbtu - y_pred_kbtu
    comparison.to_csv(os.path.join(output_dir, 'cbecs_predictions_vs_actual.csv'), index=False)

    print(f"\nResults saved to {output_dir}")


if __name__ == '__main__':
    main()
