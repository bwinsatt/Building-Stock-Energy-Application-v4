#!/usr/bin/env python3
"""
CBECS 2018 Validation: Run XGBoost baseline predictions against CBECS actual EUI.

Loads the mapped CBECS data, constructs feature dicts matching the model's
expectations, runs predictions through ModelManager, and compares to actual EUI.
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")

# Add backend to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.inference.model_manager import ModelManager
from app.services.preprocessor import year_to_vintage

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CBECS_MAPPED = Path(__file__).resolve().parent / "cbecs2018_mapped_for_xgb.csv"
KWH_TO_KBTU = 3.412

# CBECS building_type -> ComStock building_type_group
BT_TO_GROUP = {
    "LargeOffice": "Office",
    "MediumOffice": "Office",
    "SmallOffice": "Office",
    "Hospital": "Healthcare",
    "Outpatient": "Healthcare",
    "LargeHotel": "Lodging",
    "SmallHotel": "Lodging",
    "PrimarySchool": "Education",
    "SecondarySchool": "Education",
    "FullServiceRestaurant": "Food Service",
    "QuickServiceRestaurant": "Food Service",
    "RetailStandalone": "Mercantile",
    "RetailStripmall": "Mercantile",
    "Warehouse": "Warehouse and Storage",
}

# Representative clusters per census division (most common cluster in each)
CENDIV_TO_CLUSTER = {
    1: "Boston and Hartford CT-MA-NH-RI Metro Areas",
    2: "the Greater New York City Area",
    3: "Chicago-Naperville-Elgin IL-IN-WI Metro Area",
    4: "Minneapolis-St. Paul-Bloomington MN-WI Metro Area",
    5: "Washington-Arlington-Alexandria DC-VA-MD-WV Metro Area",
    6: "Nashville-Davidson-Murfreesboro-Franklin TN Metro Area",
    7: "Dallas-Fort Worth-Arlington TX Metro Area",
    8: "Denver-Aurora-Lakewood CO Metro Area",
    9: "Los Angeles-Long Beach-Anaheim CA Metro Area",
}

# CBECS HVAC mapping: try to infer hvac_category from equipment flags
# (already done in mapping script as in.hvac_category)

# Representative HVAC system types per hvac_category
HVAC_CAT_TO_SYSTEM = {
    "Central Plant": "VAV chiller with gas boiler reheat",
    "Unitary/Split/DX": "PSZ-AC with gas coil",
}

# Default feature values for features not in CBECS
DEFAULT_FEATURES = {
    "in.wall_construction_type": "Mass",
    "in.window_type": "Double - LowE - Clear - Aluminum",
    "in.window_to_wall_ratio_category": "26_50pct",
    "in.interior_lighting_generation": "gen4_led",
    "in.weekday_operating_hours..hr": 50.0,
    "in.building_subtype": "NA",
    "in.aspect_ratio": "2",
    "in.airtightness..m3_per_m2_h": 0.5,
    "in.energy_code_followed_during_last_hvac_replacement": "ComStock DEER 1985",
    "in.energy_code_followed_during_last_roof_replacement": "ComStock DEER 1985",
    "in.energy_code_followed_during_last_walls_replacement": "ComStock DEER 1985",
    "in.energy_code_followed_during_last_svc_water_htg_replacement": "ComStock DEER 1985",
}

# Heating fuel mapping: CBECS names -> ComStock model names
FUEL_MAP = {
    "NaturalGas": "NaturalGas",
    "Electricity": "Electricity",
    "FuelOil": "FuelOil",
    "Propane": "Propane",
    "DistrictHeating": "DistrictHeating",
}

# HVAC category -> cool/heat/vent types (most common in ComStock)
HVAC_DETAIL = {
    "Central Plant": {
        "in.hvac_category": "Central Plant",
        "in.hvac_cool_type": "Central Chiller",
        "in.hvac_heat_type": "Boiler",
        "in.hvac_vent_type": "Central VAV AHU",
    },
    "Unitary/Split/DX": {
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Central Single-zone RTU",
    },
}


def build_features(row: pd.Series) -> dict:
    """Convert a CBECS mapped row to a feature dict for the XGBoost model."""
    bt = row["in.building_type"]
    group = BT_TO_GROUP.get(bt)
    if group is None:
        return None

    cendiv = row.get("CENDIV", 5)
    cluster = CENDIV_TO_CLUSTER.get(int(cendiv), CENDIV_TO_CLUSTER[5])

    # Map year_built string to vintage
    year_built_str = row.get("year_built", "1980-1999")
    # Convert CBECS year bin to a representative year, then to vintage
    year_bin_to_year = {
        "<1946": 1930,
        "1946-1959": 1952,
        "1960-1979": 1970,
        "1980-1999": 1990,
        "2000-2009": 2005,
        ">2010": 2015,
    }
    rep_year = year_bin_to_year.get(year_built_str, 1990)
    vintage = year_to_vintage(rep_year, "comstock")

    hvac_cat = row.get("in.hvac_category", "Unitary/Split/DX")
    hvac_system = HVAC_CAT_TO_SYSTEM.get(hvac_cat, "PSZ-AC with gas coil")
    hvac_detail = HVAC_DETAIL.get(hvac_cat, HVAC_DETAIL["Unitary/Split/DX"])

    heating_fuel = FUEL_MAP.get(row.get("in.heating_fuel", "NaturalGas"), "NaturalGas")
    dhw_fuel = FUEL_MAP.get(row.get("in.water_heater_fuel", "NaturalGas"), "NaturalGas")

    features = {
        "in.comstock_building_type_group": group,
        "in.sqft..ft2": float(row["SQFT"]),
        "in.number_stories": row.get("num_of_stories", "1-3"),
        "in.as_simulated_ashrae_iecc_climate_zone_2006": row["climate_zone_ashrae_2006"],
        "cluster_name": cluster,
        "in.vintage": vintage,
        "in.heating_fuel": heating_fuel,
        "in.service_water_heating_fuel": dhw_fuel,
        "in.hvac_system_type": hvac_system,
    }

    # Add HVAC detail features
    features.update(hvac_detail)

    # Add default features
    features.update(DEFAULT_FEATURES)

    # Override building_subtype to match the group
    features["in.building_subtype"] = group

    return features


def main():
    print("=" * 100)
    print("CBECS 2018 VALIDATION: XGBoost Baseline Predictions vs Actual EUI")
    print("=" * 100)

    # Load mapped CBECS data
    df = pd.read_csv(CBECS_MAPPED)
    print(f"\nLoaded {len(df)} CBECS records")

    # Filter to complete, mappable cases
    valid_mask = (
        df["in.building_type"].notna()
        & df["in.building_type"].isin(BT_TO_GROUP.keys())
        & df["climate_zone_ashrae_2006"].notna()
        & df["in.heating_fuel"].notna()
        & (df["in.heating_fuel"] != "Unknown")
        & df["in.water_heater_fuel"].notna()
        & (df["in.water_heater_fuel"] != "Unknown")
        & df["total_site_eui"].notna()
        & (df["total_site_eui"] > 0)
    )
    df_valid = df[valid_mask].copy()
    print(f"Valid records for prediction: {len(df_valid)}")

    # Initialize model manager
    print("\nInitializing model manager...")
    mm = ModelManager()
    n_indexed = mm.index_all()
    print(f"Indexed {n_indexed} models")

    # Run predictions
    print("\nRunning predictions...")
    results = []
    errors = 0

    for idx, row in df_valid.iterrows():
        features = build_features(row)
        if features is None:
            errors += 1
            continue

        try:
            baseline_eui = mm.predict_baseline(features, "comstock")
            # Convert kWh/sf to kBtu/sf
            pred_kbtu = {
                fuel: max(0.0, eui * KWH_TO_KBTU)
                for fuel, eui in baseline_eui.items()
            }
            total_pred = sum(pred_kbtu.values())

            results.append({
                "PUBID": row["PUBID"],
                "in.building_type": row["in.building_type"],
                "building_type_group": BT_TO_GROUP[row["in.building_type"]],
                "SQFT": row["SQFT"],
                "climate_zone": row["climate_zone_ashrae_2006"],
                "CENDIV": row.get("CENDIV"),
                "heating_fuel": row["in.heating_fuel"],
                "hvac_category": row["in.hvac_category"],
                "actual_total_eui": row["total_site_eui"],
                "actual_elec_eui": row.get("electricity_eui", 0),
                "actual_ng_eui": row.get("natural_gas_eui", 0),
                "actual_dh_eui": row.get("district_heating_eui", 0),
                "predicted_total_eui": total_pred,
                "predicted_elec_eui": pred_kbtu.get("electricity", 0),
                "predicted_ng_eui": pred_kbtu.get("natural_gas", 0),
                "predicted_dh_eui": pred_kbtu.get("district_heating", 0),
                "residual": row["total_site_eui"] - total_pred,
                "FINALWT": row.get("FINALWT", 1),
            })
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error for PUBID {row['PUBID']}: {e}")

    print(f"\nPredictions complete: {len(results)} successful, {errors} errors")

    df_results = pd.DataFrame(results)

    # ---------------------------------------------------------------------------
    # Metrics by building type GROUP
    # ---------------------------------------------------------------------------
    print("\n\n" + "=" * 100)
    print("RESULTS BY BUILDING TYPE GROUP")
    print("=" * 100)

    print(f"\n{'Group':<25} {'n':>6} {'Actual Mean':>12} {'Pred Mean':>12} {'MAE':>10} {'RMSE':>10} {'R²':>10} {'MAPE':>10}")
    print("-" * 95)

    overall_metrics = []
    for group in sorted(df_results["building_type_group"].unique()):
        mask = df_results["building_type_group"] == group
        sub = df_results[mask]
        n = len(sub)
        actual_mean = sub["actual_total_eui"].mean()
        pred_mean = sub["predicted_total_eui"].mean()
        residuals = sub["residual"]
        mae = residuals.abs().mean()
        rmse = np.sqrt((residuals ** 2).mean())
        ss_res = (residuals ** 2).sum()
        ss_tot = ((sub["actual_total_eui"] - sub["actual_total_eui"].mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mape = (residuals.abs() / sub["actual_total_eui"].replace(0, np.nan)).mean() * 100

        print(f"{group:<25} {n:>6} {actual_mean:>12.1f} {pred_mean:>12.1f} {mae:>10.1f} {rmse:>10.1f} {r2:>10.3f} {mape:>9.1f}%")
        overall_metrics.append(sub)

    # Overall
    all_results = pd.concat(overall_metrics)
    n = len(all_results)
    actual_mean = all_results["actual_total_eui"].mean()
    pred_mean = all_results["predicted_total_eui"].mean()
    residuals = all_results["residual"]
    mae = residuals.abs().mean()
    rmse = np.sqrt((residuals ** 2).mean())
    ss_res = (residuals ** 2).sum()
    ss_tot = ((all_results["actual_total_eui"] - all_results["actual_total_eui"].mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    mape = (residuals.abs() / all_results["actual_total_eui"].replace(0, np.nan)).mean() * 100
    print("-" * 95)
    print(f"{'OVERALL':<25} {n:>6} {actual_mean:>12.1f} {pred_mean:>12.1f} {mae:>10.1f} {rmse:>10.1f} {r2:>10.3f} {mape:>9.1f}%")

    # ---------------------------------------------------------------------------
    # Metrics by DETAILED building type
    # ---------------------------------------------------------------------------
    print("\n\n" + "=" * 100)
    print("RESULTS BY DETAILED BUILDING TYPE")
    print("=" * 100)

    print(f"\n{'Type':<30} {'n':>6} {'Actual Mean':>12} {'Pred Mean':>12} {'MAE':>10} {'R²':>10} {'MAPE':>10}")
    print("-" * 90)

    for bt in sorted(df_results["in.building_type"].unique()):
        mask = df_results["in.building_type"] == bt
        sub = df_results[mask]
        n = len(sub)
        actual_mean = sub["actual_total_eui"].mean()
        pred_mean = sub["predicted_total_eui"].mean()
        residuals = sub["residual"]
        mae = residuals.abs().mean()
        ss_res = (residuals ** 2).sum()
        ss_tot = ((sub["actual_total_eui"] - sub["actual_total_eui"].mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mape = (residuals.abs() / sub["actual_total_eui"].replace(0, np.nan)).mean() * 100
        print(f"{bt:<30} {n:>6} {actual_mean:>12.1f} {pred_mean:>12.1f} {mae:>10.1f} {r2:>10.3f} {mape:>9.1f}%")

    # ---------------------------------------------------------------------------
    # Metrics by fuel type
    # ---------------------------------------------------------------------------
    print("\n\n" + "=" * 100)
    print("FUEL-SPECIFIC ACCURACY (Electricity vs Natural Gas)")
    print("=" * 100)

    for fuel_label, actual_col, pred_col in [
        ("Electricity", "actual_elec_eui", "predicted_elec_eui"),
        ("Natural Gas", "actual_ng_eui", "predicted_ng_eui"),
    ]:
        print(f"\n--- {fuel_label} ---")
        # Only include buildings with nonzero actual for this fuel
        mask = df_results[actual_col] > 0
        sub = df_results[mask]
        if len(sub) == 0:
            print("  No data")
            continue
        residuals = sub[actual_col] - sub[pred_col]
        mae = residuals.abs().mean()
        rmse = np.sqrt((residuals ** 2).mean())
        ss_res = (residuals ** 2).sum()
        ss_tot = ((sub[actual_col] - sub[actual_col].mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        print(f"  n={len(sub)}, Actual mean={sub[actual_col].mean():.1f}, Pred mean={sub[pred_col].mean():.1f}")
        print(f"  MAE={mae:.1f}, RMSE={rmse:.1f}, R²={r2:.3f}")

    # ---------------------------------------------------------------------------
    # Save results
    # ---------------------------------------------------------------------------
    output_csv = Path(__file__).resolve().parent / "cbecs_predictions_vs_actual.csv"
    df_results.to_csv(output_csv, index=False)
    print(f"\n\nResults saved to: {output_csv}")

    # Save summary to Excel
    summary_rows = []
    for group in sorted(df_results["building_type_group"].unique()):
        mask = df_results["building_type_group"] == group
        sub = df_results[mask]
        residuals = sub["residual"]
        mae = residuals.abs().mean()
        rmse = np.sqrt((residuals ** 2).mean())
        ss_res = (residuals ** 2).sum()
        ss_tot = ((sub["actual_total_eui"] - sub["actual_total_eui"].mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mape = (residuals.abs() / sub["actual_total_eui"].replace(0, np.nan)).mean() * 100
        summary_rows.append({
            "building_type": group,
            "n": len(sub),
            "actual_mean_eui": sub["actual_total_eui"].mean(),
            "predicted_mean_eui": sub["predicted_total_eui"].mean(),
            "mae_kbtu_sf": mae,
            "rmse_kbtu_sf": rmse,
            "r2": r2,
            "mape_pct": mape,
        })

    df_summary = pd.DataFrame(summary_rows)
    output_xlsx = Path(__file__).resolve().parent / "cbecs_validation_results.xlsx"
    df_summary.to_excel(output_xlsx, index=False, sheet_name="By Group")
    print(f"Summary saved to: {output_xlsx}")


if __name__ == "__main__":
    main()
