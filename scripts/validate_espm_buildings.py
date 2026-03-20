"""
ESPM / CBECS Validation Script
==============================
Runs real-building profiles through the full assessment pipeline and writes
structured CSV results for manual review.

Data sources:
  - ESPM: Validation/ESPM Properties Testing_MetaAnalysis.xlsx (78 buildings)
  - CBECS: Validation/CBECS/cbecs2018_mapped_for_xgb.csv (6,436 rows)
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.constants import KWH_TO_KBTU
from app.inference.imputation_service import ImputationService
from app.inference.model_manager import ModelManager
from app.schemas.request import BuildingInput
from app.schemas.response import BuildingResult
from app.services.assessment import _assess_single
from app.services.cost_calculator import CostCalculatorService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & mappings
# ---------------------------------------------------------------------------
STORY_BIN_MAP = {"1-3": 2, "4-7": 5, "8+": 10}
YEAR_BIN_MAP = {
    "<1946": 1930,
    "1946-1959": 1953,
    "1960-1979": 1970,
    "1980-1999": 1990,
    "2000-2009": 2005,
    ">2010": 2015,
}

ESPM_BT_MAP = {
    "Multi-Family": "Multi-Family",
    "MediumOffice": "Office",
    "Warehouse": "Warehouse and Storage",
    "LargeHotel": "Lodging",
    "SmallHotel": "Lodging",
}

CBECS_BT_MAP = {
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

CENDIV_TO_ZIP = {
    1: "02101",
    2: "10001",
    3: "60601",
    4: "55401",
    5: "20001",
    6: "37201",
    7: "75201",
    8: "80201",
    9: "90001",
}

CSV_COLUMNS = [
    "source",
    "building_name",
    "building_type",
    "sqft",
    "climate_zone",
    "zipcode",
    "heating_fuel",
    "calibrated",
    "baseline_predicted_eui_kbtu",
    "baseline_actual_eui_kbtu",
    "baseline_pct_error",
    "measure_name",
    "upgrade_id",
    "applicable",
    "savings_pct",
    "savings_kbtu_sf",
    "electricity_savings_kwh",
    "gas_savings_therms",
    "other_fuel_savings_kbtu",
    "installed_cost_total",
    "installed_cost_per_sf",
    "payback_years",
    "emissions_reduction_pct",
]

# ---------------------------------------------------------------------------
# Hardcoded ESPM Ref values (PM IDs from the spreadsheet)
# ---------------------------------------------------------------------------
ESPM_TARGET_REFS = {
    210132,   # The Union (Multi-Family, CZ=5A)
    231829,   # Oakland Hills Apartments (Multi-Family, CZ=2A)
    233572,   # Warner Building (MediumOffice, CZ=4A)
    222887,   # 5950 Nancy Ridge (MediumOffice, CZ=3B)
    234770,   # B702 - Altoona RDC (Warehouse, CZ=5A)
    234425,   # 8500 Kerns (Warehouse, CZ=3B)
    233251,   # The Westin Stonebriar (LargeHotel, CZ=3A)
    235146,   # Rodeway Inn (SmallHotel, CZ=3C)
}

# Hardcoded CBECS PUBIDs
CBECS_TARGET_PUBIDS = {
    1,    # LargeOffice, district heating, CENDIV=5
    7,    # PrimarySchool, electricity-only, CENDIV=8
    10,   # SecondarySchool, gas primary, CENDIV=2
    2,    # MediumOffice, warm climate (CENDIV=9)
    44,   # LargeOffice, cold climate (CENDIV=1)
}

THERMS_TO_KBTU = 100.0  # 1 therm = 100 kBtu


# ---------------------------------------------------------------------------
# Task 2: ESPM building profiles
# ---------------------------------------------------------------------------
def get_espm_buildings() -> list[dict]:
    """Parse the ESPM spreadsheet and return profiles for target buildings."""
    import openpyxl

    xlsx_path = REPO_ROOT / "Validation" / "ESPM Properties Testing_MetaAnalysis.xlsx"
    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)
    ws = wb.active

    buildings = []
    for row in ws.iter_rows(min_row=5, max_row=83, values_only=True):
        ref = row[0]
        try:
            ref_int = int(ref) if ref is not None else None
        except (ValueError, TypeError):
            continue
        if ref_int is None or ref_int not in ESPM_TARGET_REFS:
            continue

        name = str(row[2]) if row[2] else f"ESPM-{ref}"
        bt_raw = str(row[7]) if row[7] else ""
        bt_mapped = ESPM_BT_MAP.get(bt_raw)
        if bt_mapped is None:
            log.warning("Skipping ESPM Ref=%s — unmapped building type %r", ref, bt_raw)
            continue

        story_bin = str(row[13]) if row[13] else "1-3"
        year_bin = str(row[14]) if row[14] else "1980-1999"

        zipcode = str(row[5]).zfill(5) if row[5] else "00000"
        sqft = float(row[6]) if row[6] else 0.0
        eui = float(row[4]) if row[4] else 0.0
        heating_fuel = str(row[8]) if row[8] else None
        dhw_fuel = str(row[9]) if row[9] else None
        hvac_type = str(row[10]) if row[10] else None
        climate_zone = str(row[11]) if row[11] else ""

        buildings.append({
            "name": name,
            "source": "ESPM",
            "building_type": bt_mapped,
            "sqft": sqft,
            "zipcode": zipcode,
            "num_stories": STORY_BIN_MAP.get(story_bin, 2),
            "year_built": YEAR_BIN_MAP.get(year_bin, 1990),
            "heating_fuel": heating_fuel,
            "dhw_fuel": dhw_fuel,
            "hvac_system_type": hvac_type,
            "climate_zone": climate_zone,
            "actual_eui_kbtu": eui,
            "per_fuel_eui": None,  # ESPM doesn't provide per-fuel EUI
        })

    wb.close()
    log.info("Loaded %d ESPM buildings", len(buildings))
    return buildings


# ---------------------------------------------------------------------------
# Task 3: CBECS building profiles
# ---------------------------------------------------------------------------
def get_cbecs_buildings() -> list[dict]:
    """Parse the CBECS CSV and return profiles for target buildings."""
    csv_path = REPO_ROOT / "Validation" / "CBECS" / "cbecs2018_mapped_for_xgb.csv"

    buildings = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pubid = int(row["PUBID"])
            if pubid not in CBECS_TARGET_PUBIDS:
                continue

            bt_raw = row["in.building_type"]
            bt_mapped = CBECS_BT_MAP.get(bt_raw)
            if bt_mapped is None:
                log.warning("Skipping CBECS PUBID=%d — unmapped building type %r", pubid, bt_raw)
                continue

            cendiv = int(row["CENDIV"])
            sqft = float(row["SQFT"])
            story_bin = row["num_of_stories"]
            year_bin = row["year_built"]

            elec_eui = float(row["electricity_eui"] or 0)
            gas_eui = float(row["natural_gas_eui"] or 0)
            dh_eui = float(row["district_heating_eui"] or 0)
            total_eui = float(row["total_site_eui"] or 0)

            buildings.append({
                "name": f"CBECS-{pubid}",
                "source": "CBECS",
                "building_type": bt_mapped,
                "sqft": sqft,
                "zipcode": CENDIV_TO_ZIP.get(cendiv, "20001"),
                "num_stories": STORY_BIN_MAP.get(story_bin, 2),
                "year_built": YEAR_BIN_MAP.get(year_bin, 1990),
                "heating_fuel": row["in.heating_fuel"] or None,
                "dhw_fuel": row["in.water_heater_fuel"] or None,
                "hvac_system_type": None,
                "climate_zone": row.get("climate_zone_ashrae_2006", ""),
                "actual_eui_kbtu": total_eui,
                "per_fuel_eui": {
                    "electricity_kbtu_sf": elec_eui,
                    "natural_gas_kbtu_sf": gas_eui,
                    "district_heating_kbtu_sf": dh_eui,
                },
            })

    log.info("Loaded %d CBECS buildings", len(buildings))
    return buildings


# ---------------------------------------------------------------------------
# Task 4: Assessment runner
# ---------------------------------------------------------------------------
def init_services():
    """Initialize ModelManager, CostCalculatorService, and ImputationService."""
    model_dir = os.environ.get("MODEL_DIR", str(REPO_ROOT / "XGB_Models"))
    mm = ModelManager(model_dir=model_dir)
    mm.index_all()
    cc = CostCalculatorService()
    imp = ImputationService(str(Path(model_dir) / "Imputation"))
    imp.load()
    log.info("Services initialized (model_dir=%s)", model_dir)
    return mm, cc, imp


def run_assessment(
    profile: dict,
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service: ImputationService,
    calibrated: bool = False,
) -> BuildingResult | None:
    """Build a BuildingInput from profile and run _assess_single."""
    try:
        kwargs: dict = {
            "building_type": profile["building_type"],
            "sqft": profile["sqft"],
            "num_stories": profile["num_stories"],
            "zipcode": profile["zipcode"],
            "year_built": profile["year_built"],
        }

        # Optional fields
        if profile.get("heating_fuel"):
            kwargs["heating_fuel"] = profile["heating_fuel"]
        if profile.get("dhw_fuel"):
            kwargs["dhw_fuel"] = profile["dhw_fuel"]
        if profile.get("hvac_system_type"):
            kwargs["hvac_system_type"] = profile["hvac_system_type"]

        # Calibration: inject per-fuel EUI as utility bill data
        if calibrated and profile.get("per_fuel_eui"):
            pf = profile["per_fuel_eui"]
            sqft = profile["sqft"]

            elec_kbtu_sf = pf.get("electricity_kbtu_sf", 0) or 0
            gas_kbtu_sf = pf.get("natural_gas_kbtu_sf", 0) or 0
            dh_kbtu_sf = pf.get("district_heating_kbtu_sf", 0) or 0

            # Convert kBtu/sf → total utility units
            if elec_kbtu_sf > 0:
                kwargs["annual_electricity_kwh"] = (elec_kbtu_sf * sqft) / KWH_TO_KBTU
            if gas_kbtu_sf > 0:
                kwargs["annual_natural_gas_therms"] = (gas_kbtu_sf * sqft) / THERMS_TO_KBTU
            if dh_kbtu_sf > 0:
                kwargs["annual_district_heating_kbtu"] = dh_kbtu_sf * sqft

        building = BuildingInput(**kwargs)
        result = _assess_single(
            building, 0, model_manager, cost_calculator, imputation_service
        )
        return result

    except Exception:
        log.error(
            "Assessment failed for %s: %s",
            profile.get("name", "?"),
            traceback.format_exc(),
        )
        return None


# ---------------------------------------------------------------------------
# Task 5: CSV output and anomaly flags
# ---------------------------------------------------------------------------
def result_to_rows(profile: dict, result: BuildingResult, calibrated: bool) -> list[dict]:
    """Convert a BuildingResult into CSV rows (1 summary + N measure rows)."""
    predicted_eui = result.baseline.total_eui_kbtu_sf
    actual_eui = profile.get("actual_eui_kbtu") or 0.0
    pct_error = (
        ((predicted_eui - actual_eui) / actual_eui * 100.0)
        if actual_eui > 0
        else None
    )

    base = {
        "source": profile["source"],
        "building_name": profile["name"],
        "building_type": profile["building_type"],
        "sqft": profile["sqft"],
        "climate_zone": profile.get("climate_zone", ""),
        "zipcode": profile["zipcode"],
        "heating_fuel": profile.get("heating_fuel", ""),
        "calibrated": calibrated,
        "baseline_predicted_eui_kbtu": round(predicted_eui, 2),
        "baseline_actual_eui_kbtu": round(actual_eui, 2) if actual_eui else "",
        "baseline_pct_error": round(pct_error, 1) if pct_error is not None else "",
    }

    # Summary row — measure columns blank
    summary = {**base}
    for col in CSV_COLUMNS:
        if col not in summary:
            summary[col] = ""
    rows = [summary]

    # One row per measure
    for m in result.measures:
        mrow = {**base}
        mrow["measure_name"] = m.name
        mrow["upgrade_id"] = m.upgrade_id
        mrow["applicable"] = m.applicable
        mrow["savings_pct"] = round(m.savings_pct, 2) if m.savings_pct is not None else ""
        mrow["savings_kbtu_sf"] = round(m.savings_kbtu_sf, 3) if m.savings_kbtu_sf is not None else ""
        mrow["electricity_savings_kwh"] = (
            round(m.electricity_savings_kwh, 2) if m.electricity_savings_kwh is not None else ""
        )
        mrow["gas_savings_therms"] = (
            round(m.gas_savings_therms, 3) if m.gas_savings_therms is not None else ""
        )
        mrow["other_fuel_savings_kbtu"] = (
            round(m.other_fuel_savings_kbtu, 3) if m.other_fuel_savings_kbtu is not None else ""
        )
        mrow["installed_cost_total"] = (
            round(m.cost.installed_cost_total, 0) if m.cost else ""
        )
        mrow["installed_cost_per_sf"] = (
            round(m.cost.installed_cost_per_sf, 2) if m.cost else ""
        )
        mrow["payback_years"] = (
            round(m.simple_payback_years, 1) if m.simple_payback_years is not None else ""
        )
        mrow["emissions_reduction_pct"] = (
            round(m.emissions_reduction_pct, 2)
            if m.emissions_reduction_pct is not None
            else ""
        )
        rows.append(mrow)

    return rows


def check_anomalies(profile: dict, result: BuildingResult, calibrated: bool) -> list[str]:
    """Return a list of anomaly description strings."""
    anomalies = []
    name = profile["name"]
    cal_tag = " [calibrated]" if calibrated else ""

    # Baseline prediction error
    actual = profile.get("actual_eui_kbtu") or 0.0
    predicted = result.baseline.total_eui_kbtu_sf
    if actual > 0:
        pct_err = abs((predicted - actual) / actual) * 100
        if pct_err > 30:
            anomalies.append(
                f"{name}{cal_tag}: baseline error {pct_err:.1f}% "
                f"(predicted={predicted:.1f}, actual={actual:.1f})"
            )

    for m in result.measures:
        if not m.applicable:
            continue

        # Savings range check
        if m.savings_pct is not None:
            sp = m.savings_pct  # already in percentage form (e.g. 15.0 = 15%)
            if sp < 0.5:
                anomalies.append(f"{name}{cal_tag}: {m.name} savings only {sp:.2f}%")
            elif sp > 60:
                anomalies.append(f"{name}{cal_tag}: {m.name} savings {sp:.1f}% (>60%)")

        # Payback range check
        if m.simple_payback_years is not None:
            if m.simple_payback_years > 100:
                anomalies.append(
                    f"{name}{cal_tag}: {m.name} payback {m.simple_payback_years:.0f}yr (>100)"
                )
            elif m.simple_payback_years < 0.5:
                anomalies.append(
                    f"{name}{cal_tag}: {m.name} payback {m.simple_payback_years:.1f}yr (<0.5)"
                )

        # Cross-fuel anomaly
        elec = m.electricity_savings_kwh or 0.0
        gas = m.gas_savings_therms or 0.0
        if abs(elec) < 0.001 and abs(gas) > 0.1:
            anomalies.append(
                f"{name}{cal_tag}: {m.name} gas savings={gas:.2f} therms but elec~0"
            )
        elif abs(gas) < 0.001 and abs(elec) > 0.1:
            # Only flag if there is natural gas in the building baseline
            baseline_gas = result.baseline.eui_by_fuel.natural_gas
            if baseline_gas > 0.5:
                anomalies.append(
                    f"{name}{cal_tag}: {m.name} elec savings={elec:.2f} kWh but gas~0 "
                    f"(baseline gas EUI={baseline_gas:.1f})"
                )

    return anomalies


def check_calibration_shifts(
    profile: dict,
    uncal_result: BuildingResult,
    cal_result: BuildingResult,
) -> list[str]:
    """Compare same measure across calibrated/uncalibrated, flag >50% relative change."""
    anomalies = []
    name = profile["name"]

    # Build lookup by upgrade_id
    uncal_map = {m.upgrade_id: m for m in uncal_result.measures}

    for cm in cal_result.measures:
        um = uncal_map.get(cm.upgrade_id)
        if um is None or not cm.applicable or not um.applicable:
            continue

        us = um.savings_pct or 0.0
        cs = cm.savings_pct or 0.0

        if us == 0 and cs == 0:
            continue

        denom = abs(us) if us != 0 else abs(cs)
        rel_change = abs(cs - us) / denom * 100 if denom > 0 else 0

        if rel_change > 50:
            anomalies.append(
                f"{name}: {cm.name} savings shifted {rel_change:.0f}% "
                f"(uncal={us:.1f}% -> cal={cs:.1f}%)"
            )

    return anomalies


# ---------------------------------------------------------------------------
# Task 6: Main
# ---------------------------------------------------------------------------
def main():
    log.info("Starting ESPM/CBECS validation run")

    # 1. Initialize services
    mm, cc, imp = init_services()

    # 2. Gather building profiles
    espm_buildings = get_espm_buildings()
    cbecs_buildings = get_cbecs_buildings()
    all_buildings = espm_buildings + cbecs_buildings
    log.info("Total buildings to assess: %d", len(all_buildings))

    all_rows: list[dict] = []
    all_anomalies: list[str] = []

    # 3. Run assessments
    for profile in all_buildings:
        log.info("Assessing %s (%s) ...", profile["name"], profile["source"])

        # Uncalibrated run
        uncal_result = run_assessment(profile, mm, cc, imp, calibrated=False)
        if uncal_result is None:
            all_anomalies.append(f"{profile['name']}: ASSESSMENT FAILED (uncalibrated)")
            continue

        all_rows.extend(result_to_rows(profile, uncal_result, calibrated=False))
        all_anomalies.extend(check_anomalies(profile, uncal_result, calibrated=False))

        # Calibrated run (only if per-fuel EUI available)
        if profile.get("per_fuel_eui"):
            cal_result = run_assessment(profile, mm, cc, imp, calibrated=True)
            if cal_result is None:
                all_anomalies.append(f"{profile['name']}: ASSESSMENT FAILED (calibrated)")
                continue

            all_rows.extend(result_to_rows(profile, cal_result, calibrated=True))
            all_anomalies.extend(check_anomalies(profile, cal_result, calibrated=True))
            all_anomalies.extend(
                check_calibration_shifts(profile, uncal_result, cal_result)
            )

    # 4. Write CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "scripts" / "validation_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"espm_validation_{timestamp}.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    log.info("Wrote %d rows to %s", len(all_rows), csv_path)

    # 5. Print anomaly summary
    print("\n" + "=" * 70)
    print(f"VALIDATION COMPLETE — {len(all_buildings)} buildings, {len(all_rows)} CSV rows")
    print(f"Output: {csv_path}")
    print("=" * 70)

    if all_anomalies:
        print(f"\n  ANOMALIES ({len(all_anomalies)}):")
        for a in all_anomalies:
            print(f"    - {a}")
    else:
        print("\n  No anomalies detected.")

    print()


if __name__ == "__main__":
    main()
