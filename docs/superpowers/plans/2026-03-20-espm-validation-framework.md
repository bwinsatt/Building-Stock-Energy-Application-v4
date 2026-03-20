# ESPM/CBECS Validation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a diagnostic script that runs real-building assessments through the full pipeline and outputs a CSV report for manual review of baseline EUI, savings, costs, and payback.

**Architecture:** Single script (`scripts/validate_espm_buildings.py`) with three phases: parse building data from ESPM spreadsheet + CBECS CSV, run assessments via `_assess_single()` in-process, write CSV + console anomaly flags. No tests — this is itself a validation/diagnostic tool.

**Tech Stack:** Python, openpyxl, csv, existing backend services (ModelManager, CostCalculatorService, ImputationService, _assess_single)

**Spec:** `docs/superpowers/specs/2026-03-20-espm-validation-framework-design.md`

---

### Task 1: Create output directory and script skeleton

**Files:**
- Create: `scripts/validate_espm_buildings.py`
- Create: `scripts/validation_results/.gitkeep`

- [ ] **Step 1: Create the output directory**

```bash
mkdir -p scripts/validation_results
touch scripts/validation_results/.gitkeep
```

Also create `scripts/validation_results/.gitignore` to exclude CSV output from version control:
```
*
!.gitignore
!.gitkeep
```

- [ ] **Step 2: Write the script skeleton with imports and constants**

Create `scripts/validate_espm_buildings.py` with:

```python
#!/usr/bin/env python3
"""
ESPM/CBECS Validation: Run real-building assessments through the full
pipeline and output structured CSV results for manual review.

Usage:
    python scripts/validate_espm_buildings.py
"""

import csv
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add backend to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.schemas.request import BuildingInput
from app.inference.model_manager import ModelManager
from app.inference.imputation_service import ImputationService
from app.services.cost_calculator import CostCalculatorService
from app.services.assessment import _assess_single

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

from app.constants import KWH_TO_KBTU

KBTU_PER_THERM = 100.0

OUTPUT_DIR = REPO_ROOT / "scripts" / "validation_results"

ESPM_PATH = REPO_ROOT / "Validation" / "ESPM Properties Testing_MetaAnalysis.xlsx"
CBECS_PATH = REPO_ROOT / "Validation" / "CBECS" / "cbecs2018_mapped_for_xgb.csv"

# Bin-to-numeric mappings (apply to both ESPM and CBECS)
STORY_BIN_MAP = {"1-3": 2, "4-7": 5, "8+": 10}
YEAR_BIN_MAP = {
    "<1946": 1930,
    "1946-1959": 1953,
    "1960-1979": 1970,
    "1980-1999": 1990,
    "2000-2009": 2005,
    ">2010": 2015,
}

# ESPM building_type -> BuildingInput.building_type
ESPM_BT_MAP = {
    "Multi-Family": "Multi-Family",
    "MediumOffice": "Office",
    "Warehouse": "Warehouse and Storage",
    "LargeHotel": "Lodging",
    "SmallHotel": "Lodging",
}

# CBECS building_type -> BuildingInput.building_type
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

# CBECS census division -> representative zipcode
CENDIV_TO_ZIP = {
    1: "02101",  # Boston
    2: "10001",  # New York
    3: "60601",  # Chicago
    4: "55401",  # Minneapolis
    5: "20001",  # Washington DC
    6: "37201",  # Nashville
    7: "75201",  # Dallas
    8: "80201",  # Denver
    9: "90001",  # Los Angeles
}

# CSV output columns
CSV_COLUMNS = [
    "source", "building_name", "building_type", "sqft", "climate_zone",
    "zipcode", "heating_fuel", "calibrated",
    "baseline_predicted_eui_kbtu", "baseline_actual_eui_kbtu", "baseline_pct_error",
    "measure_name", "upgrade_id", "applicable",
    "savings_pct", "savings_kbtu_sf",
    "electricity_savings_kwh", "gas_savings_therms", "other_fuel_savings_kbtu",
    "installed_cost_total", "installed_cost_per_sf",
    "payback_years", "emissions_reduction_pct",
]


def main():
    pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify the script runs without error**

Run: `cd backend && python -c "from app.services.assessment import _assess_single; print('OK')"`
Run: `python scripts/validate_espm_buildings.py`
Expected: Both exit cleanly with no errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_espm_buildings.py scripts/validation_results/.gitkeep scripts/validation_results/.gitignore
git commit -m "feat: add validation script skeleton with constants and mappings"
```

---

### Task 2: Build ESPM building profiles

**Files:**
- Modify: `scripts/validate_espm_buildings.py`

Select ~8 diverse buildings from the ESPM spreadsheet. The spreadsheet has header row at row 4, data starting at row 5. Key columns (0-indexed):
- 0: Ref (PM ID)
- 2: Project Name
- 3: ENERGY STAR Score
- 4: Total EUI
- 5: Zipcode
- 6: Building Square Foot
- 7: Building Type
- 8: HVAC Heating Fuel
- 9: DHW Fuel
- 10: HVAC Type
- 11: ASHRAE Climate Zone
- 13: Story Bin
- 14: Year Bin

- [ ] **Step 1: Add ESPM building selection function**

Add a function `get_espm_buildings()` that returns a list of dicts. Each dict has keys: `name`, `source`, `building_type`, `sqft`, `zipcode`, `num_stories`, `year_built`, `heating_fuel`, `dhw_fuel`, `hvac_system_type`, `climate_zone`, `actual_eui_kbtu`.

Hardcode ~8 ESPM building selections by PM ID (Ref column), chosen for diversity:
- Multi-Family: 2 buildings (different climates/sizes/fuels — e.g. "The Union" CZ=5A 8+ stories gas heat, "Oakland Hills Apartments" CZ=2A electric-only)
- MediumOffice: 2 buildings (e.g. "Warner Building" CZ=4A 750k sqft high EUI=92.9, "5950 Nancy Ridge" CZ=3B low EUI=11.9)
- Warehouse: 2 buildings (e.g. "B702 - Altoona RDC" CZ=5A EUI=37.5, "8500 Kerns" CZ=3B very low EUI=3.5)
- LargeHotel: 1 building (e.g. "The Westin Stonebriar" CZ=3A EUI=88.7)
- SmallHotel: 1 building (e.g. "Rodeway Inn" CZ=3C EUI=48.6)

Read the ESPM spreadsheet via openpyxl. For each selected PM ID, find the row, extract fields, apply bin mappings, and apply `ESPM_BT_MAP` for building_type.

```python
def get_espm_buildings() -> list[dict]:
    """Parse selected buildings from ESPM spreadsheet."""
    import openpyxl

    SELECTED_REFS = {210132, 231829, 210957, 231454,  # Multi-Family (diverse)
                     210439,                            # (dropped, pick from below)
                     # Offices
                     # MediumOffice Warner Building (Ref 232591-ish) — find actual refs
                     }
    # ... implementation parses spreadsheet, finds matching rows, returns list of dicts

    wb = openpyxl.load_workbook(ESPM_PATH, read_only=True, data_only=True)
    ws = wb["Sheet1"]

    # Selected PM IDs for diversity (see spec for selection criteria)
    selected_refs = set()  # Populated with actual Ref values after inspection

    buildings = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        ref = row[0]
        if ref is None or ref not in selected_refs:
            continue
        bt_raw = row[7]
        bt = ESPM_BT_MAP.get(bt_raw)
        if bt is None:
            continue
        buildings.append({
            "name": row[2],
            "source": "ESPM",
            "building_type": bt,
            "sqft": float(row[6]),
            "zipcode": str(row[5]).zfill(5),
            "num_stories": STORY_BIN_MAP.get(row[13], 2),
            "year_built": YEAR_BIN_MAP.get(row[14], 1990),
            "heating_fuel": row[8],
            "dhw_fuel": row[9],
            "hvac_system_type": row[10] if row[10] != "Unitary/Split/DX" else None,
            "climate_zone": row[11],
            "actual_eui_kbtu": float(row[4]) if row[4] is not None else None,
            "per_fuel_eui": None,  # ESPM has no per-fuel data
        })
    wb.close()
    return buildings
```

**Implementation note:** The actual PM ID (Ref) values for the ~8 selected buildings need to be looked up from the spreadsheet during implementation. The implementer should pick buildings matching the diversity criteria listed above, selecting from the spreadsheet data explored during brainstorming.

- [ ] **Step 2: Verify ESPM parsing works**

Add a temporary print at the end of `main()`:
```python
buildings = get_espm_buildings()
for b in buildings:
    print(f"  {b['name']:40s} | {b['building_type']:20s} | EUI={b['actual_eui_kbtu']} | zip={b['zipcode']}")
```

Run: `python scripts/validate_espm_buildings.py`
Expected: 8 buildings printed with correct fields.

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_espm_buildings.py
git commit -m "feat: add ESPM building parsing with diverse 8-building subset"
```

---

### Task 3: Build CBECS building profiles

**Files:**
- Modify: `scripts/validate_espm_buildings.py`

Select ~5 diverse buildings from `Validation/CBECS/cbecs2018_mapped_for_xgb.csv`. Choose buildings where `other_fuel_eui` is near zero (to avoid the unmapped fuel issue). Pick for diversity of building type and fuel mix:
- 1 with district heating (e.g. a LargeOffice with CENDIV=2)
- 1 electricity-only (e.g. a Warehouse or SmallHotel)
- 1 natural gas primary heating (e.g. a MediumOffice)
- 1 from a warm climate (CENDIV 7 or 9)
- 1 from a cold climate (CENDIV 1 or 4)

- [ ] **Step 1: Add CBECS building selection function**

```python
def get_cbecs_buildings() -> list[dict]:
    """Parse selected buildings from CBECS mapped CSV."""
    import csv as csv_mod

    buildings = []
    with open(CBECS_PATH) as f:
        reader = csv_mod.DictReader(f)
        all_rows = list(reader)

    # Select ~5 diverse buildings by scanning for good candidates
    # Criteria: known building type, low other_fuel_eui, diverse types/fuels
    selected = []
    # Implementation: iterate all_rows, find one building matching each
    # diversity criterion, append to selected

    for row in selected:
        bt_raw = row["in.building_type"]
        bt = CBECS_BT_MAP.get(bt_raw)
        if bt is None:
            continue

        cendiv = int(row.get("CENDIV", 5))
        zipcode = CENDIV_TO_ZIP.get(cendiv, "20001")
        sqft = float(row["SQFT"])

        elec_eui = float(row["electricity_eui"])
        gas_eui = float(row["natural_gas_eui"])
        dh_eui = float(row["district_heating_eui"])
        total_eui = float(row["total_site_eui"])

        buildings.append({
            "name": f"CBECS-{row['PUBID']}",
            "source": "CBECS",
            "building_type": bt,
            "sqft": sqft,
            "zipcode": zipcode,
            "num_stories": STORY_BIN_MAP.get(row["num_of_stories"], 2),
            "year_built": YEAR_BIN_MAP.get(row["year_built"], 1990),
            "heating_fuel": row["in.heating_fuel"],
            "dhw_fuel": row["in.water_heater_fuel"],
            "hvac_system_type": None,
            "climate_zone": row["climate_zone_ashrae_2006"],
            "actual_eui_kbtu": total_eui,
            "per_fuel_eui": {
                "electricity_kbtu_sf": elec_eui,
                "natural_gas_kbtu_sf": gas_eui,
                "district_heating_kbtu_sf": dh_eui,
            },
        })
    return buildings
```

**Key implementation detail:** The CBECS selection should scan all 6,436 rows and pick the first row matching each diversity criterion (building type + fuel + climate combination). Store the PUBID values as constants once identified so the selection is deterministic on re-runs.

- [ ] **Step 2: Verify CBECS parsing works**

Add to the temporary print block in `main()`:
```python
cbecs = get_cbecs_buildings()
for b in cbecs:
    pf = b["per_fuel_eui"]
    print(f"  {b['name']:40s} | {b['building_type']:20s} | EUI={b['actual_eui_kbtu']:.1f} | elec={pf['electricity_kbtu_sf']:.1f} | gas={pf['natural_gas_kbtu_sf']:.1f}")
```

Run: `python scripts/validate_espm_buildings.py`
Expected: 5 CBECS buildings with per-fuel EUI data.

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_espm_buildings.py
git commit -m "feat: add CBECS building parsing with diverse 5-building subset"
```

---

### Task 4: Assessment runner

**Files:**
- Modify: `scripts/validate_espm_buildings.py`

- [ ] **Step 1: Add service initialization**

```python
def init_services():
    """Initialize ModelManager, CostCalculatorService, and ImputationService."""
    model_dir = os.environ.get("MODEL_DIR", str(REPO_ROOT / "XGB_Models"))

    mm = ModelManager(model_dir=model_dir)
    count = mm.index_all()
    logger.info("Models indexed: %d", count)

    cc = CostCalculatorService()

    imputation_dir = os.path.join(model_dir, "Imputation")
    imp = ImputationService(imputation_dir)
    imp.load()

    return mm, cc, imp
```

- [ ] **Step 2: Add assessment runner function**

This function takes a building profile dict, constructs a `BuildingInput`, and calls `_assess_single()`. Returns a `BuildingResult` or None on error. For CBECS buildings with per-fuel data, also runs a calibrated assessment.

```python
def run_assessment(profile: dict, model_manager, cost_calculator, imputation_service, calibrated: bool = False):
    """Run _assess_single() for a building profile. Returns BuildingResult or None."""
    try:
        input_kwargs = {
            "building_type": profile["building_type"],
            "sqft": profile["sqft"],
            "num_stories": profile["num_stories"],
            "zipcode": profile["zipcode"],
            "year_built": profile["year_built"],
        }
        # Optional fields
        if profile.get("heating_fuel"):
            input_kwargs["heating_fuel"] = profile["heating_fuel"]
        if profile.get("dhw_fuel"):
            input_kwargs["dhw_fuel"] = profile["dhw_fuel"]
        if profile.get("hvac_system_type"):
            input_kwargs["hvac_system_type"] = profile["hvac_system_type"]

        # Inject calibration data if requested and available
        if calibrated and profile.get("per_fuel_eui"):
            pf = profile["per_fuel_eui"]
            sqft = profile["sqft"]
            elec_kbtu = pf["electricity_kbtu_sf"]
            gas_kbtu = pf["natural_gas_kbtu_sf"]
            dh_kbtu = pf["district_heating_kbtu_sf"]

            if elec_kbtu > 0:
                input_kwargs["annual_electricity_kwh"] = elec_kbtu * sqft / KWH_TO_KBTU
            if gas_kbtu > 0:
                input_kwargs["annual_natural_gas_therms"] = gas_kbtu * sqft / KBTU_PER_THERM
            if dh_kbtu > 0:
                input_kwargs["annual_district_heating_kbtu"] = dh_kbtu * sqft

        building = BuildingInput(**input_kwargs)
        result = _assess_single(building, 0, model_manager, cost_calculator, imputation_service)
        return result
    except Exception as e:
        logger.error("Assessment failed for %s (calibrated=%s): %s", profile["name"], calibrated, e)
        return None
```

- [ ] **Step 3: Test with one building**

Add to `main()`:
```python
mm, cc, imp = init_services()
buildings = get_espm_buildings()
if buildings:
    result = run_assessment(buildings[0], mm, cc, imp, calibrated=False)
    if result:
        print(f"Baseline EUI: {result.baseline.total_eui_kbtu_sf:.1f} kBtu/sf")
        print(f"Measures: {len(result.measures)} ({sum(1 for m in result.measures if m.applicable)} applicable)")
```

Run: `python scripts/validate_espm_buildings.py`
Expected: Baseline EUI and measure count printed for the first ESPM building.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_espm_buildings.py
git commit -m "feat: add assessment runner with service initialization"
```

---

### Task 5: CSV output and anomaly flags

**Files:**
- Modify: `scripts/validate_espm_buildings.py`

- [ ] **Step 1: Add result-to-CSV-rows function**

```python
def result_to_rows(profile: dict, result, calibrated: bool) -> list[dict]:
    """Convert a BuildingResult into CSV rows (one per measure + summary row)."""
    actual_eui = profile["actual_eui_kbtu"]
    predicted_eui = result.baseline.total_eui_kbtu_sf
    pct_error = ((predicted_eui - actual_eui) / actual_eui) if actual_eui else None

    base = {
        "source": profile["source"],
        "building_name": profile["name"],
        "building_type": profile["building_type"],
        "sqft": profile["sqft"],
        "climate_zone": result.input_summary.climate_zone,
        "zipcode": profile["zipcode"],
        "heating_fuel": profile.get("heating_fuel", ""),
        "calibrated": calibrated,
        "baseline_predicted_eui_kbtu": round(predicted_eui, 2),
        "baseline_actual_eui_kbtu": round(actual_eui, 2) if actual_eui else "",
        "baseline_pct_error": round(pct_error, 4) if pct_error is not None else "",
    }

    rows = []
    # Summary row (no measure data)
    summary = {**base}
    for col in CSV_COLUMNS:
        if col not in summary:
            summary[col] = ""
    rows.append(summary)

    # One row per measure
    for m in result.measures:
        row = {
            **base,
            "measure_name": m.name,
            "upgrade_id": m.upgrade_id,
            "applicable": m.applicable,
            "savings_pct": round(m.savings_pct, 4) if m.savings_pct is not None else "",
            "savings_kbtu_sf": round(m.savings_kbtu_sf, 4) if m.savings_kbtu_sf is not None else "",
            "electricity_savings_kwh": round(m.electricity_savings_kwh, 6) if m.electricity_savings_kwh is not None else "",
            "gas_savings_therms": round(m.gas_savings_therms, 6) if m.gas_savings_therms is not None else "",
            "other_fuel_savings_kbtu": round(m.other_fuel_savings_kbtu, 4) if m.other_fuel_savings_kbtu is not None else "",
            "installed_cost_total": round(m.cost.installed_cost_total, 2) if m.cost else "",
            "installed_cost_per_sf": round(m.cost.installed_cost_per_sf, 4) if m.cost else "",
            "payback_years": round(m.simple_payback_years, 2) if m.simple_payback_years is not None else "",
            "emissions_reduction_pct": round(m.emissions_reduction_pct, 4) if m.emissions_reduction_pct is not None else "",
        }
        rows.append(row)
    return rows
```

- [ ] **Step 2: Add anomaly detection function**

```python
def check_anomalies(profile: dict, result, calibrated: bool) -> list[str]:
    """Return list of anomaly strings for console output."""
    flags = []
    name = profile["name"]
    cal = " [CAL]" if calibrated else ""
    actual_eui = profile["actual_eui_kbtu"]
    predicted_eui = result.baseline.total_eui_kbtu_sf

    if actual_eui and actual_eui > 0:
        pct_err = abs(predicted_eui - actual_eui) / actual_eui
        if pct_err > 0.30:
            flags.append(f"  BASELINE ERROR {pct_err:.0%}: {name}{cal} predicted={predicted_eui:.1f} actual={actual_eui:.1f}")

    for m in result.measures:
        if not m.applicable:
            continue
        if m.savings_pct is not None:
            if m.savings_pct < 0.005:
                flags.append(f"  LOW SAVINGS {m.savings_pct:.1%}: {name}{cal} → {m.name}")
            elif m.savings_pct > 0.60:
                flags.append(f"  HIGH SAVINGS {m.savings_pct:.1%}: {name}{cal} → {m.name}")
        if m.simple_payback_years is not None:
            if m.simple_payback_years > 100:
                flags.append(f"  LONG PAYBACK {m.simple_payback_years:.0f}yr: {name}{cal} → {m.name}")
            elif m.simple_payback_years < 0.5:
                flags.append(f"  SHORT PAYBACK {m.simple_payback_years:.1f}yr: {name}{cal} → {m.name}")

        # Cross-fuel anomaly: electricity near-zero but gas savings significant (or vice versa)
        # This catches cases like the Empire State Building roof insulation issue
        elec = m.electricity_savings_kwh or 0
        gas = m.gas_savings_therms or 0
        if abs(elec) < 0.001 and abs(gas) > 0.1:
            flags.append(f"  ELEC-NEAR-ZERO: {name}{cal} → {m.name} (elec={elec:.4f} kWh, gas={gas:.4f} therms)")
        if abs(gas) < 0.001 and abs(elec) > 0.01:
            flags.append(f"  GAS-NEAR-ZERO: {name}{cal} → {m.name} (elec={elec:.4f} kWh, gas={gas:.4f} therms)")

    return flags
```

- [ ] **Step 3: Add calibration shift detection**

```python
def check_calibration_shifts(profile: dict, uncal_result, cal_result) -> list[str]:
    """Compare calibrated vs uncalibrated results for the same building."""
    flags = []
    name = profile["name"]

    uncal_measures = {m.upgrade_id: m for m in uncal_result.measures if m.applicable}
    cal_measures = {m.upgrade_id: m for m in cal_result.measures if m.applicable}

    for uid, uncal_m in uncal_measures.items():
        cal_m = cal_measures.get(uid)
        if cal_m is None or uncal_m.savings_pct is None or cal_m.savings_pct is None:
            continue
        if uncal_m.savings_pct > 0:
            shift = abs(cal_m.savings_pct - uncal_m.savings_pct) / uncal_m.savings_pct
            if shift > 0.50:
                flags.append(
                    f"  CAL SHIFT {shift:.0%}: {name} → {uncal_m.name} "
                    f"(uncal={uncal_m.savings_pct:.1%} → cal={cal_m.savings_pct:.1%})"
                )
    return flags
```

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_espm_buildings.py
git commit -m "feat: add CSV output formatter and anomaly detection"
```

---

### Task 6: Wire up main() and run full validation

**Files:**
- Modify: `scripts/validate_espm_buildings.py`

- [ ] **Step 1: Implement main()**

```python
def main():
    logger.info("Initializing services...")
    mm, cc, imp = init_services()

    logger.info("Loading building profiles...")
    buildings = get_espm_buildings() + get_cbecs_buildings()
    logger.info("Loaded %d buildings (%d ESPM, %d CBECS)",
                len(buildings),
                sum(1 for b in buildings if b["source"] == "ESPM"),
                sum(1 for b in buildings if b["source"] == "CBECS"))

    all_rows = []
    all_anomalies = []

    for i, profile in enumerate(buildings):
        logger.info("[%d/%d] Assessing %s (%s)...",
                    i + 1, len(buildings), profile["name"], profile["building_type"])

        # Uncalibrated run
        uncal_result = run_assessment(profile, mm, cc, imp, calibrated=False)
        if uncal_result is None:
            continue

        all_rows.extend(result_to_rows(profile, uncal_result, calibrated=False))
        all_anomalies.extend(check_anomalies(profile, uncal_result, calibrated=False))

        # Calibrated run (CBECS only — has per-fuel data)
        if profile.get("per_fuel_eui"):
            cal_result = run_assessment(profile, mm, cc, imp, calibrated=True)
            if cal_result:
                all_rows.extend(result_to_rows(profile, cal_result, calibrated=True))
                all_anomalies.extend(check_anomalies(profile, cal_result, calibrated=True))
                all_anomalies.extend(check_calibration_shifts(profile, uncal_result, cal_result))

    # Write CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"espm_validation_{timestamp}.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info("CSV written: %s (%d rows)", csv_path, len(all_rows))

    # Print anomalies
    if all_anomalies:
        print(f"\n{'='*60}")
        print(f"ANOMALY FLAGS ({len(all_anomalies)} total)")
        print(f"{'='*60}")
        for flag in all_anomalies:
            print(flag)
    else:
        print("\nNo anomalies detected.")

    print(f"\nResults saved to: {csv_path}")
```

- [ ] **Step 2: Run the full validation**

Run: `python scripts/validate_espm_buildings.py`
Expected: Script processes all ~13 buildings, prints progress, writes CSV, shows any anomaly flags.

- [ ] **Step 3: Inspect the CSV output**

Open the CSV and verify:
- Each building has a summary row (no measure data) + one row per measure
- CBECS buildings have both calibrated=True and calibrated=False rows
- ESPM buildings have only calibrated=False rows
- baseline_pct_error is populated for buildings with actual EUI data
- Savings, costs, and payback columns are populated for applicable measures

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_espm_buildings.py
git commit -m "feat: wire up main validation loop with CSV output and anomaly flags"
```

---

### Task 7: Run validation and interpret results

This is the manual analysis step — not code changes.

- [ ] **Step 1: Run the validation script**

```bash
python scripts/validate_espm_buildings.py
```

- [ ] **Step 2: Review and interpret results**

Open the CSV output. For each building, check:
1. **Baseline accuracy**: How close is predicted EUI to actual? Flag >30% error.
2. **Measure savings**: Do savings percentages look reasonable for the measure type?
3. **Per-fuel breakdown**: Is electricity savings near-zero for envelope measures on gas-heated buildings? (This was the Empire State Building issue.)
4. **Costs and payback**: Are installed costs in reasonable ranges? Is payback realistic?
5. **Calibration effect**: For CBECS buildings, how does calibration change savings predictions?

Report findings conversationally to the user.
