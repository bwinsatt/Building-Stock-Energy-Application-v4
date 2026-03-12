# Measures Table Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the measures table from 6 to 12 columns, adding per-fuel savings, emissions reduction, useful life, and NREL descriptions with a horizontal scroll layout.

**Architecture:** Backend-first approach. Create a constants module, emissions calculation service, and expose per-fuel savings in the API response. Then update the frontend table to render all 12 columns. Data pipeline scripts populate NREL descriptions and eGRID emission factors into existing JSON files.

**Tech Stack:** Python/FastAPI (backend), Vue 3/TypeScript (frontend), XGBoost models (inference), Pydantic v2 (schemas)

---

### Task 1: Create Constants Module

**Files:**
- Create: `backend/app/constants.py`
- Modify: `backend/app/services/assessment.py:31-32`
- Modify: `backend/app/services/address_lookup.py:146`
- Test: `backend/tests/test_constants.py`

**Step 1: Write the test**

Create `backend/tests/test_constants.py`:

```python
"""Tests for shared constants module."""

from app.constants import (
    KWH_TO_KBTU,
    KWH_TO_THERMS,
    TONS_TO_KBTUH,
    SQFT_PER_M2,
    M2_PER_SQFT,
    FOSSIL_FUEL_EMISSION_FACTORS,
)


def test_kwh_to_kbtu():
    assert KWH_TO_KBTU == 3.412


def test_kwh_to_therms():
    assert KWH_TO_THERMS == 0.03412


def test_tons_to_kbtuh():
    assert TONS_TO_KBTUH == 12.0


def test_sqft_m2_roundtrip():
    """Converting sqft -> m2 -> sqft should return approximately the same value."""
    sqft = 1000.0
    m2 = sqft * M2_PER_SQFT
    back = m2 * SQFT_PER_M2
    assert abs(back - sqft) < 0.01


def test_fossil_fuel_emission_factors_keys():
    expected_fuels = {"natural_gas", "propane", "fuel_oil", "district_heating"}
    assert set(FOSSIL_FUEL_EMISSION_FACTORS.keys()) == expected_fuels


def test_fossil_fuel_emission_factors_positive():
    for fuel, factor in FOSSIL_FUEL_EMISSION_FACTORS.items():
        assert factor > 0, f"{fuel} emission factor should be positive"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_constants.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.constants'`

**Step 3: Write the constants module**

Create `backend/app/constants.py`:

```python
"""
Shared constants for unit conversions and emission factors.

All conversion constants used across the application should live here
to avoid duplication and ensure consistency.
"""

# Energy unit conversions
KWH_TO_KBTU = 3.412
KWH_TO_THERMS = 0.03412
TONS_TO_KBTUH = 12.0

# Area conversions
SQFT_PER_M2 = 10.7639
M2_PER_SQFT = 1 / SQFT_PER_M2  # ~0.0929

# Fossil fuel emission factors (kg CO2e per kBtu)
# Source: NREL archive calculations, standard EPA factors
FOSSIL_FUEL_EMISSION_FACTORS = {
    "natural_gas": 0.05311,
    "propane": 0.06195,
    "fuel_oil": 0.07421,
    "district_heating": 0.0664,
}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_constants.py -v`
Expected: All 6 tests PASS

**Step 5: Update existing imports**

In `backend/app/services/assessment.py`, replace lines 31-32:
```python
# kWh -> kBtu conversion factor
KWH_TO_KBTU = 3.412
```
with:
```python
from app.constants import KWH_TO_KBTU
```

In `backend/app/services/address_lookup.py`, replace line 146:
```python
SQFT_PER_M2 = 10.7639
```
with:
```python
from app.constants import SQFT_PER_M2
```

**Step 6: Run existing tests to verify no regressions**

Run: `cd backend && pytest tests/test_schemas.py tests/test_preprocessor.py -v`
Expected: All existing tests PASS

**Step 7: Commit**

```bash
git add backend/app/constants.py backend/tests/test_constants.py backend/app/services/assessment.py backend/app/services/address_lookup.py
git commit -m "feat: add shared constants module and consolidate unit conversions"
```

---

### Task 2: Enrich Zipcode Lookup with eGRID Emission Factors

**Files:**
- Create: `scripts/enrich_zipcode_egrid.py`
- Modify: `backend/app/data/zipcode_lookup.json`
- Reference: `Resources/Zipcode to Emission Factor, kgCO2e.xlsx`

**Step 1: Write the enrichment script**

Create `scripts/enrich_zipcode_egrid.py`:

```python
"""
One-time script to merge eGRID electricity emission factors into zipcode_lookup.json.

Reads the Excel file at Resources/Zipcode to Emission Factor, kgCO2e.xlsx,
maps each zipcode to its 3-digit prefix, and adds:
  - egrid_subregion
  - electricity_emission_factor_kg_co2e_per_kwh

to each prefix entry in backend/app/data/zipcode_lookup.json.
"""

import json
import os
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH = os.path.join(REPO_ROOT, "Resources", "Zipcode to Emission Factor, kgCO2e.xlsx")
LOOKUP_PATH = os.path.join(REPO_ROOT, "backend", "app", "data", "zipcode_lookup.json")


def main():
    # Load Excel — inspect columns first
    df = pd.read_excel(EXCEL_PATH)
    print(f"Excel columns: {list(df.columns)}")
    print(f"Excel shape: {df.shape}")
    print(f"Sample rows:\n{df.head()}")

    # Detect column names (may vary — adapt as needed)
    # Expected columns: Zip Code, Emission Factor (or similar), eGRID Subregion
    zip_col = None
    ef_col = None
    subregion_col = None

    for col in df.columns:
        col_lower = str(col).lower()
        if 'zip' in col_lower and 'code' in col_lower:
            zip_col = col
        elif 'emission' in col_lower and 'factor' in col_lower:
            ef_col = col
        elif 'egrid' in col_lower or 'subregion' in col_lower:
            subregion_col = col

    if zip_col is None or ef_col is None:
        print(f"Could not auto-detect columns. Found: {list(df.columns)}")
        print("Please update script with correct column names.")
        return

    print(f"\nUsing columns: zip={zip_col}, ef={ef_col}, subregion={subregion_col}")

    # Convert zipcodes to 3-digit prefixes, aggregate by prefix (mean EF)
    df['prefix'] = df[zip_col].astype(str).str.zfill(5).str[:3]

    agg = {'ef': (ef_col, 'mean')}
    if subregion_col:
        # Take the most common subregion per prefix
        agg['subregion'] = (subregion_col, lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else '')

    prefix_groups = df.groupby('prefix').agg(**agg).reset_index()

    # Load existing zipcode lookup
    with open(LOOKUP_PATH) as fh:
        lookup = json.load(fh)

    # Merge
    updated = 0
    missing = 0
    for _, row in prefix_groups.iterrows():
        prefix = row['prefix']
        if prefix in lookup['prefixes']:
            lookup['prefixes'][prefix]['electricity_emission_factor_kg_co2e_per_kwh'] = round(float(row['ef']), 6)
            if subregion_col and 'subregion' in row:
                lookup['prefixes'][prefix]['egrid_subregion'] = str(row['subregion'])
            updated += 1
        else:
            missing += 1

    print(f"\nUpdated {updated} prefixes, {missing} prefixes not in lookup")

    # Write back
    with open(LOOKUP_PATH, 'w') as fh:
        json.dump(lookup, fh, indent=2)

    print(f"Wrote updated lookup to {LOOKUP_PATH}")


if __name__ == "__main__":
    main()
```

**Step 2: Run the script and inspect output**

Run: `cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation" && python scripts/enrich_zipcode_egrid.py`

Inspect the output to verify column detection worked. If columns don't auto-detect, manually update the script with the correct column names from the Excel file.

**Step 3: Verify the enriched JSON**

Run: `cd backend && python -c "import json; d=json.load(open('app/data/zipcode_lookup.json')); e=d['prefixes']['200']; print(e)"`

Expected: Entry includes `electricity_emission_factor_kg_co2e_per_kwh` and `egrid_subregion` fields.

**Step 4: Update the zipcode lookup class to return emission factor**

In `backend/app/services/preprocessor.py`, the `_ZipcodeLookup.lookup()` method (line 877) currently returns `(state, climate_zone, cluster_name)`. We need to also return the emission factor. However, changing this return type would break many callers. Instead, add a new method:

Add to `_ZipcodeLookup` class in `backend/app/services/preprocessor.py` after the `lookup` method (~line 903):

```python
def get_emission_factor(self, zipcode: str) -> float | None:
    """Return the electricity emission factor (kg CO2e/kWh) for a zipcode.

    Returns None if the factor is not available for this prefix.
    """
    if self._prefixes is None:
        self._load()
    assert self._prefixes is not None

    prefix = zipcode[:3]
    entry = self._prefixes.get(prefix)
    if entry is not None:
        return entry.get("electricity_emission_factor_kg_co2e_per_kwh")
    return None
```

Also expose it via a module-level function, near the existing `resolve_zipcode` function (~line 989):

```python
def get_electricity_emission_factor(zipcode: str) -> float | None:
    """Return the electricity emission factor (kg CO2e/kWh) for a zipcode."""
    return _zip_lookup.get_emission_factor(zipcode)
```

**Step 5: Commit**

```bash
git add scripts/enrich_zipcode_egrid.py backend/app/data/zipcode_lookup.json backend/app/services/preprocessor.py
git commit -m "feat: enrich zipcode lookup with eGRID emission factors"
```

---

### Task 3: Create Emissions Calculation Module

**Files:**
- Create: `backend/app/services/emissions.py`
- Test: `backend/tests/test_emissions.py`

**Step 1: Write the tests**

Create `backend/tests/test_emissions.py`:

```python
"""Tests for emissions calculation module."""

import pytest
from app.services.emissions import calculate_emissions


class TestCalculateEmissions:
    """Tests for calculate_emissions function."""

    def test_electricity_only(self):
        """Electricity emissions use the provided emission factor."""
        energy = {"electricity": 10.0}  # 10 kWh/sf
        ef = 0.4  # kg CO2e/kWh
        result = calculate_emissions(energy, electricity_ef=ef)
        assert abs(result - 4.0) < 0.001  # 10 * 0.4 = 4.0

    def test_natural_gas_only(self):
        """Natural gas: kWh -> kBtu -> kg CO2e."""
        energy = {"natural_gas": 10.0}  # 10 kWh/sf
        result = calculate_emissions(energy, electricity_ef=0.0)
        # 10 kWh * 3.412 kBtu/kWh * 0.05311 kg/kBtu = 1.8121
        assert abs(result - 1.8121) < 0.01

    def test_all_fuels(self):
        """All fuels contribute to total emissions."""
        energy = {
            "electricity": 5.0,
            "natural_gas": 3.0,
            "fuel_oil": 1.0,
            "propane": 0.5,
            "district_heating": 0.0,
        }
        ef = 0.3
        result = calculate_emissions(energy, electricity_ef=ef)
        assert result > 0

    def test_zero_energy_returns_zero(self):
        """All-zero energy should return zero emissions."""
        energy = {"electricity": 0.0, "natural_gas": 0.0}
        result = calculate_emissions(energy, electricity_ef=0.4)
        assert result == 0.0

    def test_empty_energy_returns_zero(self):
        """Empty dict should return zero emissions."""
        result = calculate_emissions({}, electricity_ef=0.4)
        assert result == 0.0

    def test_no_electricity_ef_ignores_electricity(self):
        """When electricity_ef is None, electricity is skipped."""
        energy = {"electricity": 10.0, "natural_gas": 5.0}
        result = calculate_emissions(energy, electricity_ef=None)
        # Only natural gas contributes
        expected_gas = 5.0 * 3.412 * 0.05311
        assert abs(result - expected_gas) < 0.01

    def test_unknown_fuel_ignored(self):
        """Unknown fuel types are ignored (no crash)."""
        energy = {"electricity": 5.0, "unknown_fuel": 10.0}
        result = calculate_emissions(energy, electricity_ef=0.3)
        # Only electricity contributes
        assert abs(result - 1.5) < 0.001


class TestEmissionsReductionPct:
    """Test the percentage reduction calculation."""

    def test_basic_reduction(self):
        """50% energy reduction should yield ~50% emissions reduction (same fuel mix)."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0, "natural_gas": 5.0}
        post_upgrade = {"electricity": 5.0, "natural_gas": 2.5}
        ef = 0.4

        result = calculate_emissions_reduction_pct(baseline, post_upgrade, ef)
        assert abs(result - 50.0) < 0.1

    def test_zero_baseline_returns_zero(self):
        """Zero baseline emissions should return 0% reduction (avoid division by zero)."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 0.0}
        post_upgrade = {"electricity": 0.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert result == 0.0

    def test_full_elimination(self):
        """Eliminating all energy should yield 100% reduction."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0}
        post_upgrade = {"electricity": 0.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert abs(result - 100.0) < 0.001
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_emissions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.emissions'`

**Step 3: Implement the emissions module**

Create `backend/app/services/emissions.py`:

```python
"""
Emissions calculation module.

Calculates carbon emissions (kg CO2e) from per-fuel energy consumption.
Designed to be reusable for both baseline and post-upgrade energy values.
"""

from __future__ import annotations

from typing import Optional

from app.constants import KWH_TO_KBTU, FOSSIL_FUEL_EMISSION_FACTORS


def calculate_emissions(
    energy_by_fuel_kwh: dict[str, float],
    electricity_ef: Optional[float] = None,
) -> float:
    """Calculate total emissions in kg CO2e/sf from per-fuel energy.

    Args:
        energy_by_fuel_kwh: dict of fuel_type -> energy in kWh/sf.
        electricity_ef: electricity emission factor in kg CO2e/kWh
            (region-specific, from eGRID via zipcode lookup).
            If None, electricity emissions are excluded.

    Returns:
        Total emissions in kg CO2e/sf.
    """
    total = 0.0

    for fuel, kwh in energy_by_fuel_kwh.items():
        if kwh == 0.0:
            continue

        if fuel == "electricity":
            if electricity_ef is not None:
                total += kwh * electricity_ef
        elif fuel in FOSSIL_FUEL_EMISSION_FACTORS:
            kbtu = kwh * KWH_TO_KBTU
            total += kbtu * FOSSIL_FUEL_EMISSION_FACTORS[fuel]

    return total


def calculate_emissions_reduction_pct(
    baseline_energy_kwh: dict[str, float],
    post_upgrade_energy_kwh: dict[str, float],
    electricity_ef: Optional[float] = None,
) -> float:
    """Calculate emissions reduction as a percentage.

    Args:
        baseline_energy_kwh: baseline per-fuel energy in kWh/sf.
        post_upgrade_energy_kwh: post-upgrade per-fuel energy in kWh/sf.
        electricity_ef: electricity emission factor in kg CO2e/kWh.

    Returns:
        Emissions reduction percentage (0-100). Returns 0.0 if baseline
        emissions are zero.
    """
    baseline_emissions = calculate_emissions(baseline_energy_kwh, electricity_ef)
    post_emissions = calculate_emissions(post_upgrade_energy_kwh, electricity_ef)

    if baseline_emissions <= 0:
        return 0.0

    return (baseline_emissions - post_emissions) / baseline_emissions * 100
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_emissions.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/emissions.py backend/tests/test_emissions.py
git commit -m "feat: add emissions calculation module with eGRID support"
```

---

### Task 4: Add Per-Fuel Savings and Emissions to Response Schema

**Files:**
- Modify: `backend/app/schemas/response.py:28-39`
- Modify: `backend/tests/test_schemas.py:84-93`

**Step 1: Update the test to include new fields**

In `backend/tests/test_schemas.py`, update the measure dict in `test_assessment_response_roundtrip` (line 85-93) to include new fields:

```python
                    {
                        "upgrade_id": 1,
                        "name": "HP-RTU",
                        "category": "hvac",
                        "applicable": True,
                        "post_upgrade_eui_kbtu_sf": 70.0,
                        "savings_kbtu_sf": 15.0,
                        "savings_pct": 0.176,
                        "electricity_savings_kwh": 3.5,
                        "gas_savings_therms": 1.2,
                        "other_fuel_savings_kbtu": 0.0,
                        "emissions_reduction_pct": 18.5,
                        "description": "Variable speed HP RTU with electric backup.",
                    }
```

Add a new test to verify the new fields serialize correctly:

```python
def test_measure_result_new_fields():
    """New per-fuel savings and description fields should be optional."""
    # Minimal — no new fields
    m1 = MeasureResult(upgrade_id=1, name="Test", category="hvac", applicable=True)
    assert m1.electricity_savings_kwh is None
    assert m1.gas_savings_therms is None
    assert m1.other_fuel_savings_kbtu is None
    assert m1.description is None

    # With new fields
    m2 = MeasureResult(
        upgrade_id=2, name="Test2", category="envelope", applicable=True,
        electricity_savings_kwh=5.0,
        gas_savings_therms=1.2,
        other_fuel_savings_kbtu=0.8,
        emissions_reduction_pct=15.0,
        description="LED lighting retrofit.",
    )
    assert m2.electricity_savings_kwh == 5.0
    assert m2.description == "LED lighting retrofit."
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_schemas.py::test_measure_result_new_fields -v`
Expected: FAIL — fields don't exist on MeasureResult yet

**Step 3: Update the schema**

In `backend/app/schemas/response.py`, add to `MeasureResult` class (after line 39):

```python
class MeasureResult(BaseModel):
    upgrade_id: int
    name: str
    category: str
    applicable: bool
    post_upgrade_eui_kbtu_sf: Optional[float] = None
    savings_kbtu_sf: Optional[float] = None
    savings_pct: Optional[float] = None
    cost: Optional[CostEstimate] = None
    utility_bill_savings_per_sf: Optional[float] = None
    simple_payback_years: Optional[float] = None
    emissions_reduction_pct: Optional[float] = None
    electricity_savings_kwh: Optional[float] = None
    gas_savings_therms: Optional[float] = None
    other_fuel_savings_kbtu: Optional[float] = None
    description: Optional[str] = None
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_schemas.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/app/schemas/response.py backend/tests/test_schemas.py
git commit -m "feat: add per-fuel savings, description fields to MeasureResult schema"
```

---

### Task 5: Wire Emissions and Per-Fuel Savings into Assessment Pipeline

**Files:**
- Modify: `backend/app/services/assessment.py:1-32, 158-325`
- Modify: `backend/app/services/preprocessor.py` (add emission factor lookup)

**Step 1: Update preprocessor to return emission factor**

The `preprocess` function in `preprocessor.py` currently returns `(features, imputed_details, dataset, climate_zone, state)`. We need the zipcode available in `_assess_single` for the emission factor lookup. The zipcode is already on the `building` input object (`building.zipcode`), so we can call the new `get_electricity_emission_factor` directly in assessment.py.

**Step 2: Update assessment.py imports**

At the top of `backend/app/services/assessment.py`, update imports:

```python
from app.constants import KWH_TO_KBTU, KWH_TO_THERMS
from app.services.emissions import calculate_emissions_reduction_pct
from app.services.preprocessor import preprocess, year_to_vintage, get_electricity_emission_factor
```

Remove the old `KWH_TO_KBTU = 3.412` line (already done in Task 1).

**Step 3: Add a helper to get the upgrade description**

Add after `_get_upgrade_category` function (~line 89):

```python
def _get_upgrade_description(
    upgrade_id: int,
    dataset: str,
    cost_calculator: CostCalculatorService,
) -> str | None:
    """Return the measure description from the cost lookup."""
    catalog = (
        cost_calculator._comstock
        if dataset == "comstock"
        else cost_calculator._resstock
    )
    entry = catalog.get(str(upgrade_id), {})
    return entry.get("description")
```

**Step 4: Update `_assess_single` to compute per-fuel savings and emissions**

In `_assess_single`, after the line `savings_kwh = {fuel: max(0.0, d) for fuel, d in delta.items()}` (line 235), add the per-fuel display unit conversion and emissions calculation.

Replace the `measures.append(MeasureResult(...))` block for applicable measures (lines 312-325) with:

```python
        # Per-fuel savings in display units
        elec_savings_kwh = round(savings_kwh.get("electricity", 0.0), 2)
        gas_savings_therms = round(
            savings_kwh.get("natural_gas", 0.0) * KWH_TO_THERMS, 4
        )
        other_fuels = ["fuel_oil", "propane", "district_heating"]
        other_savings_kbtu = round(
            sum(savings_kwh.get(f, 0.0) for f in other_fuels) * KWH_TO_KBTU, 2
        )

        # Emissions reduction
        electricity_ef = get_electricity_emission_factor(building.zipcode)
        emissions_pct = calculate_emissions_reduction_pct(
            baseline_eui, post_eui, electricity_ef
        )

        measures.append(
            MeasureResult(
                upgrade_id=uid,
                name=_get_upgrade_name(uid, dataset, cost_calculator),
                category=category,
                applicable=True,
                post_upgrade_eui_kbtu_sf=round(total_post_kbtu, 2),
                savings_kbtu_sf=round(savings_kbtu, 2),
                savings_pct=round(savings_pct, 1),
                cost=cost,
                utility_bill_savings_per_sf=round(bill_savings_per_sf, 4),
                simple_payback_years=round(payback, 1) if payback else None,
                electricity_savings_kwh=elec_savings_kwh if elec_savings_kwh else None,
                gas_savings_therms=gas_savings_therms if gas_savings_therms else None,
                other_fuel_savings_kbtu=other_savings_kbtu if other_savings_kbtu else None,
                emissions_reduction_pct=round(emissions_pct, 1) if emissions_pct else None,
                description=_get_upgrade_description(uid, dataset, cost_calculator),
            )
        )
```

**Step 5: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/app/services/assessment.py backend/app/services/preprocessor.py
git commit -m "feat: wire per-fuel savings and emissions reduction into assessment pipeline"
```

---

### Task 6: Add NREL Descriptions to Cost Lookup

**Files:**
- Create: `scripts/fetch_comstock_descriptions.py`
- Modify: `backend/app/data/upgrade_cost_lookup.json`

**Step 1: Write the ComStock description fetcher**

Create `scripts/fetch_comstock_descriptions.py`:

```python
"""
Fetch official NREL measure descriptions from ComStock GitHub repo.

Each measure directory in resources/measures/upgrade_* contains a measure.xml
with a <description> element. This script fetches them and maps to our
upgrade_cost_lookup.json entries by matching upgrade names.
"""

import json
import os
import xml.etree.ElementTree as ET
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOKUP_PATH = os.path.join(REPO_ROOT, "backend", "app", "data", "upgrade_cost_lookup.json")

GITHUB_API = "https://api.github.com/repos/NREL/ComStock/contents/resources/measures"


def fetch_measure_descriptions() -> dict[str, str]:
    """Fetch all upgrade measure descriptions from ComStock GitHub."""
    descriptions = {}

    # List all measure directories
    resp = requests.get(GITHUB_API, headers={"Accept": "application/vnd.github.v3+json"})
    resp.raise_for_status()

    measure_dirs = [item for item in resp.json() if item["type"] == "dir" and "upgrade" in item["name"].lower()]

    print(f"Found {len(measure_dirs)} upgrade measure directories")

    for mdir in measure_dirs:
        name = mdir["name"]
        xml_url = f"{GITHUB_API}/{name}/measure.xml"

        try:
            xml_resp = requests.get(xml_url, headers={"Accept": "application/vnd.github.raw+json"})
            xml_resp.raise_for_status()

            root = ET.fromstring(xml_resp.text)
            desc = root.findtext("description", "").strip()
            display_name = root.findtext("display_name", name).strip()

            if desc and desc.upper() != "TODO":
                descriptions[display_name] = desc
                print(f"  {display_name}: {desc[:80]}...")
            else:
                print(f"  {display_name}: (no description)")

        except Exception as e:
            print(f"  {name}: ERROR - {e}")

    return descriptions


def main():
    descriptions = fetch_measure_descriptions()
    print(f"\nFetched {len(descriptions)} descriptions")

    # Load cost lookup
    with open(LOOKUP_PATH) as fh:
        lookup = json.load(fh)

    # Match descriptions to comstock entries by upgrade_name
    updated = 0
    for entry in lookup.get("comstock", []):
        upgrade_name = entry.get("upgrade_name", "")

        # Try exact match first, then fuzzy
        if upgrade_name in descriptions:
            entry["description"] = descriptions[upgrade_name]
            updated += 1
        else:
            # Try partial matching
            for display_name, desc in descriptions.items():
                if display_name.lower() in upgrade_name.lower() or upgrade_name.lower() in display_name.lower():
                    entry["description"] = desc
                    updated += 1
                    break

    print(f"Updated {updated} ComStock entries with descriptions")

    # Write back
    with open(LOOKUP_PATH, 'w') as fh:
        json.dump(lookup, fh, indent=2)

    print(f"Wrote updated lookup to {LOOKUP_PATH}")

    # Report unmatched
    matched_names = {e.get("upgrade_name") for e in lookup.get("comstock", []) if "description" in e}
    unmatched = [e.get("upgrade_name") for e in lookup.get("comstock", []) if "description" not in e]
    if unmatched:
        print(f"\nUnmatched ComStock entries ({len(unmatched)}):")
        for name in unmatched:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
```

**Step 2: Run the script**

Run: `cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation" && python scripts/fetch_comstock_descriptions.py`

Review the output. Some entries may not auto-match — these will need manual description strings.

**Step 3: Write ResStock descriptions manually**

For ResStock entries in `upgrade_cost_lookup.json`, manually add a `"description"` field to each entry based on the NREL state factsheet descriptions identified during brainstorming. For package measures, include component details in the description.

Example ResStock descriptions to add:

```json
{"upgrade_id": 1, "description": "Replaces existing furnace with a 95% AFUE natural gas furnace for all dwelling units with duct systems."},
{"upgrade_id": 4, "description": "Installs a variable-speed cold climate ducted air source heat pump (SEER 22, HSPF 10) meeting NEEP Cold Climate ASHP Specification, with electric resistance backup."},
{"upgrade_id": 6, "description": "Installs a single-speed ground-source heat pump with thermally enhanced grout and high-density polyethylene pipes for vertical bore ground heat exchangers."},
{"upgrade_id": 9, "description": "Installs an 80-gallon ENERGY STAR heat pump water heater with an energy factor of 2.0 or greater, replacing existing electric water heaters."},
{"upgrade_id": 11, "description": "Achieves a 25% reduction in building enclosure infiltration as measured by blower door test. Based on analysis of 23,000 before/after retrofit measurements."},
{"upgrade_id": 12, "description": "Adds blown-in attic floor insulation up to R-49 or R-60 (varies by climate) in vented attics with unfinished space."},
{"upgrade_id": 13, "description": "Seals and insulates HVAC supply and return ductwork outside conditioned space to 10% leakage at 25 Pa with R-8 insulation."},
{"upgrade_id": 17, "description": "Replaces existing windows with ENERGY STAR certified high-performance windows."},
{"upgrade_id": 30, "description": "Combined package: General air sealing (25% infiltration reduction), attic floor insulation (R-49/R-60), and duct sealing with insulation (10% leakage, R-8)."}
```

Complete descriptions for all 32 ResStock measures following this pattern.

**Step 4: Verify descriptions load correctly**

Run: `cd backend && python -c "import json; d=json.load(open('app/data/upgrade_cost_lookup.json')); cs=[e for e in d['comstock'] if 'description' in e]; rs=[e for e in d['resstock'] if 'description' in e]; print(f'ComStock: {len(cs)} with desc, ResStock: {len(rs)} with desc')"`

**Step 5: Commit**

```bash
git add scripts/fetch_comstock_descriptions.py backend/app/data/upgrade_cost_lookup.json
git commit -m "feat: add NREL measure descriptions to cost lookup"
```

---

### Task 7: Update Frontend TypeScript Types

**Files:**
- Modify: `frontend/src/types/assessment.ts:45-57`

**Step 1: Update MeasureResult interface**

In `frontend/src/types/assessment.ts`, update the `MeasureResult` interface to add the new fields:

```typescript
export interface MeasureResult {
  upgrade_id: number
  name: string
  category: string
  applicable: boolean
  post_upgrade_eui_kbtu_sf?: number
  savings_kbtu_sf?: number
  savings_pct?: number
  cost?: CostEstimate
  utility_bill_savings_per_sf?: number
  simple_payback_years?: number
  emissions_reduction_pct?: number
  electricity_savings_kwh?: number
  gas_savings_therms?: number
  other_fuel_savings_kbtu?: number
  description?: string
}
```

**Step 2: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS (new fields are optional, no existing code breaks)

**Step 3: Commit**

```bash
git add frontend/src/types/assessment.ts
git commit -m "feat: add per-fuel savings and description to MeasureResult type"
```

---

### Task 8: Update MeasuresTable Component — Category Mapping & Header Fixes

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue:114-131, 207-209`

**Step 1: Update getCategoryConfig to use friendly display names**

Replace the `getCategoryConfig` function (lines 123-132) with:

```typescript
const CATEGORY_DISPLAY_MAP: Record<string, { variant: BadgeVariant; label: string }> = {
  hvac: { variant: 'primary', label: 'HVAC' },
  envelope: { variant: 'success', label: 'Envelope' },
  lighting: { variant: 'warning', label: 'Lighting' },
  demand_flex: { variant: 'secondary', label: 'Demand Flex' },
  water_heating: { variant: 'neutral', label: 'Water Heating' },
  kitchen: { variant: 'neutral', label: 'Kitchen' },
  package: { variant: 'primary', label: 'Package' },
}

function getCategoryConfig(category: string): CategoryConfig {
  const lower = category.toLowerCase()
  for (const [key, config] of Object.entries(CATEGORY_DISPLAY_MAP)) {
    if (lower.includes(key)) return config
  }
  return { variant: 'neutral', label: category }
}
```

**Step 2: Update the Annual Bill Savings header**

In the template, change line 209 from:
```html
              Annual Bill Savings
```
to:
```html
              Annual Bill Savings ($)
```

**Step 3: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add friendly category labels and $ to bill savings header"
```

---

### Task 9: Add New Columns to MeasuresTable

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue`

This is the main frontend change. Add 6 new column headers and cells to both the applicable and non-applicable table sections.

**Step 1: Add new column headers**

After the Payback header (line 226), add:

```html
            <PTableHead class="measures-th measures-th--numeric">
              Electricity Savings (kWh)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Gas Savings (therms)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Other Fuel Savings (kBtu)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Emissions Reduction (%)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Useful Life (yrs)
            </PTableHead>
            <PTableHead class="measures-th measures-th--desc">
              Description
            </PTableHead>
```

**Step 2: Add new cells to applicable rows**

After the Payback cell (line 275), add:

```html
            <!-- Electricity Savings -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.electricity_savings_kwh != null ? formatNumber(m.electricity_savings_kwh) : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Gas Savings -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.gas_savings_therms != null ? formatNumber(m.gas_savings_therms, 2) : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Other Fuel Savings -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.other_fuel_savings_kbtu != null ? formatNumber(m.other_fuel_savings_kbtu) : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Emissions Reduction -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.emissions_reduction_pct != null ? formatNumber(m.emissions_reduction_pct) + '%' : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Useful Life -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.cost?.useful_life_years != null ? m.cost.useful_life_years : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Description -->
            <PTableCell class="measures-cell measures-cell--desc">
              <PTypography variant="body2" component="span">
                {{ m.description ?? '\u2014' }}
              </PTypography>
            </PTableCell>
```

**Step 3: Add matching dash cells to non-applicable rows**

After the last non-applicable dash cell (line 323), add 6 more dash cells:

```html
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--desc">
                <PTypography variant="body2" component="span">
                  {{ m.description ?? '&#8212;' }}
                </PTypography>
              </PTableCell>
```

Note: Non-applicable measures should still show their description if available.

**Step 4: Add CSS for description column**

Add to the `<style scoped>` section:

```css
.measures-th--desc {
  min-width: 250px;
}

.measures-cell--desc {
  max-width: 350px;
  white-space: normal;
  line-height: 1.4;
}
```

**Step 5: Run type check and dev server**

Run: `cd frontend && npm run type-check`
Expected: PASS

Run: `cd frontend && npm run dev`
Visually verify the table renders with all 12 columns and horizontal scroll works.

**Step 6: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add 6 new columns to measures table (per-fuel savings, emissions, useful life, description)"
```

---

### Task 10: Integration Testing

**Files:**
- Modify: `backend/tests/test_schemas.py` (already updated in Task 4)
- Reference: `backend/tests/test_integration_pipeline.py`

**Step 1: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: All tests PASS

**Step 2: Run frontend type check and build**

Run: `cd frontend && npm run type-check && npm run build`
Expected: Both PASS with no errors

**Step 3: Manual smoke test**

Start the backend: `cd backend && uvicorn app.main:app --reload`
Start the frontend: `cd frontend && npm run dev`

1. Enter a building (e.g., Office, 50000 sqft, 3 stories, 20001, 1985)
2. Run assessment
3. Verify the measures table shows all 12 columns
4. Verify horizontal scroll works
5. Verify per-fuel savings show numbers for applicable fuels and dashes for zero
6. Verify emissions reduction % shows values
7. Verify useful life shows years
8. Verify descriptions appear
9. Verify category badges show friendly names (HVAC, Envelope, etc.)
10. Verify non-applicable measures show dashes for numeric columns but still show description

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete measures table enhancements with 12 columns"
```
