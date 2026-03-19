# Utility Data Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to provide actual utility bill data to calibrate energy savings predictions via baseline EUI as an input feature to delta models, with SQLite persistence for project/building management.

**Architecture:** Parallel tracks — validation experiment runs independently from persistence/schema work. Delta models are retrained with baseline EUI as an additional feature (conditional on validation). Frontend adds tab navigation for projects and collapsible utility data input. SQLite with JSON blobs for disposable persistence.

**Tech Stack:** Python 3, XGBoost, FastAPI, SQLite (stdlib), Vue 3 Composition API, TypeScript, partner-components library

**Spec:** `docs/superpowers/specs/2026-03-18-utility-calibration-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `scripts/validate_baseline_feature.py` | Validation experiment — compare delta models with/without baseline EUI feature |
| `scripts/train_comstock_deltas_v2.py` | Retrain ComStock delta models with baseline EUI features |
| `scripts/train_resstock_deltas_v2.py` | Retrain ResStock delta models with baseline EUI features |
| `backend/app/services/database.py` | SQLite connection management, schema init, CRUD operations |
| `backend/app/api/projects.py` | FastAPI router for project/building/assessment CRUD endpoints |
| `backend/tests/test_calibration.py` | Tests for utility data conversion and calibrated assessment flow |
| `backend/tests/test_database.py` | Tests for SQLite CRUD operations |
| `backend/tests/test_projects_api.py` | Tests for project API endpoints |
| `frontend/src/components/ProjectsView.vue` | Project list and management view |
| `frontend/src/components/ProjectDetail.vue` | Single project with buildings and assessments |
| `frontend/src/composables/useProjects.ts` | API state management for projects CRUD |
| `frontend/src/types/projects.ts` | TypeScript interfaces for projects/buildings |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/constants.py:6-8` | Add `KWH_PER_GALLON_FUEL_OIL`, `KWH_PER_GALLON_PROPANE`, `KWH_PER_THERM` |
| `backend/app/schemas/request.py:5-23` | Add 5 optional utility data fields to `BuildingInput` |
| `backend/app/schemas/response.py:13-17,58-65` | Add `actual_eui_by_fuel`, `actual_total_eui_kbtu_sf` to `BaselineResult`; `calibrated` to `BuildingResult` |
| `backend/app/inference/model_manager.py:452-482` | Add `baseline_eui` param to `predict_delta`, merge into features copy |
| `backend/app/services/assessment.py:127-380` | Convert utility data, pass baseline EUI to `predict_delta`, cap savings at baseline |
| `backend/app/api/routes.py:43-54` | Include projects router |
| `backend/app/main.py` | Init database on startup, include projects router |
| `scripts/training_utils.py:151-178` | Add `compress=3` to `joblib.dump` |
| `frontend/src/App.vue` | Add tab navigation with `currentView` reactive, conditionally render views |
| `frontend/src/components/BuildingForm.vue` | Add collapsible utility data section |
| `frontend/src/types/assessment.ts:1-20,28-32,78-84` | Add utility fields to `BuildingInput`, calibration fields to response types |
| `frontend/src/composables/useAssessment.ts` | Pass utility data through to API |
| `backend/tests/conftest.py:39-70` | Add calibrated input fixtures |

---

## Task 1: Unit Conversion Constants

**Files:**
- Modify: `backend/app/constants.py:6-8`
- Test: `backend/tests/test_calibration.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_calibration.py`:
```python
"""Tests for utility data calibration conversions."""
from app.constants import (
    KWH_PER_GALLON_FUEL_OIL,
    KWH_PER_GALLON_PROPANE,
    KWH_PER_THERM,
    KWH_TO_THERMS,
)


def test_kwh_per_gallon_fuel_oil():
    """138,500 BTU/gallon / 3,412 BTU/kWh ≈ 40.6."""
    assert 40.0 < KWH_PER_GALLON_FUEL_OIL < 41.0


def test_kwh_per_gallon_propane():
    """91,500 BTU/gallon / 3,412 BTU/kWh ≈ 26.8."""
    assert 26.0 < KWH_PER_GALLON_PROPANE < 27.5


def test_kwh_per_therm_is_inverse():
    """KWH_PER_THERM should be the inverse of KWH_TO_THERMS."""
    assert abs(KWH_PER_THERM - (1.0 / KWH_TO_THERMS)) < 0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_calibration.py -v`
Expected: FAIL — `ImportError: cannot import name 'KWH_PER_GALLON_FUEL_OIL'`

- [ ] **Step 3: Add conversion constants**

In `backend/app/constants.py`, after line 8 (`KWH_TO_THERMS = 0.03412`), add:
```python
KWH_PER_GALLON_FUEL_OIL = 40.6    # 138,500 BTU/gallon / 3,412 BTU/kWh
KWH_PER_GALLON_PROPANE = 26.8     # 91,500 BTU/gallon / 3,412 BTU/kWh
KWH_PER_THERM = 29.31             # 1 / KWH_TO_THERMS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_calibration.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/constants.py backend/tests/test_calibration.py
git commit -m "feat: add fuel oil, propane, and therm unit conversion constants"
```

---

## Task 2: Request Schema — Utility Data Fields

**Files:**
- Modify: `backend/app/schemas/request.py:5-23`
- Test: `backend/tests/test_calibration.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_calibration.py`:
```python
from app.schemas.request import BuildingInput


def test_building_input_accepts_utility_data():
    """BuildingInput should accept optional utility data fields."""
    inp = BuildingInput(
        building_type="OfficeSmall",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        annual_electricity_kwh=500000,
        annual_natural_gas_therms=10000,
    )
    assert inp.annual_electricity_kwh == 500000
    assert inp.annual_natural_gas_therms == 10000
    assert inp.annual_fuel_oil_gallons is None
    assert inp.annual_propane_gallons is None
    assert inp.annual_district_heating_kbtu is None


def test_building_input_without_utility_data():
    """BuildingInput without utility data should still work."""
    inp = BuildingInput(
        building_type="OfficeSmall",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
    )
    assert inp.annual_electricity_kwh is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_calibration.py::test_building_input_accepts_utility_data -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'annual_electricity_kwh'`

- [ ] **Step 3: Add utility fields to BuildingInput**

In `backend/app/schemas/request.py`, add after the last optional field (around line 22):
```python
    # Utility bill data (optional, for calibration)
    annual_electricity_kwh: Optional[float] = None
    annual_natural_gas_therms: Optional[float] = None
    annual_fuel_oil_gallons: Optional[float] = None
    annual_propane_gallons: Optional[float] = None
    annual_district_heating_kbtu: Optional[float] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_calibration.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/request.py backend/tests/test_calibration.py
git commit -m "feat: add optional utility data fields to BuildingInput schema"
```

---

## Task 3: Response Schema — Calibration Fields

**Files:**
- Modify: `backend/app/schemas/response.py:13-17,58-65`
- Test: `backend/tests/test_calibration.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_calibration.py`:
```python
from app.schemas.response import BaselineResult, BuildingResult, FuelBreakdown


def test_baseline_result_with_actual_eui():
    """BaselineResult should accept actual EUI fields."""
    fuel = FuelBreakdown(
        electricity=10.0, natural_gas=5.0, fuel_oil=0, propane=0, district_heating=0,
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=51.18,
        eui_by_fuel=fuel,
        actual_eui_by_fuel=fuel,
        actual_total_eui_kbtu_sf=60.0,
    )
    assert baseline.actual_total_eui_kbtu_sf == 60.0
    assert baseline.actual_eui_by_fuel.electricity == 10.0


def test_baseline_result_without_actual_eui():
    """BaselineResult without actual EUI should default to None."""
    fuel = FuelBreakdown(
        electricity=10.0, natural_gas=5.0, fuel_oil=0, propane=0, district_heating=0,
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=51.18,
        eui_by_fuel=fuel,
    )
    assert baseline.actual_eui_by_fuel is None
    assert baseline.actual_total_eui_kbtu_sf is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_calibration.py::test_baseline_result_with_actual_eui -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'actual_eui_by_fuel'`

- [ ] **Step 3: Add calibration fields to response schemas**

In `backend/app/schemas/response.py`, add to `BaselineResult` (around line 16):
```python
    actual_eui_by_fuel: Optional[FuelBreakdown] = None
    actual_total_eui_kbtu_sf: Optional[float] = None
```

Add to `BuildingResult` (around line 63):
```python
    calibrated: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_calibration.py -v`
Expected: 7 passed

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd backend && pytest`
Expected: All existing tests still pass (new fields are optional with defaults)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/response.py backend/tests/test_calibration.py
git commit -m "feat: add calibration fields to BaselineResult and BuildingResult schemas"
```

---

## Task 4: Utility Data Conversion Helper

**Files:**
- Modify: `backend/app/services/assessment.py`
- Test: `backend/tests/test_calibration.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_calibration.py`:
```python
from app.services.assessment import convert_utility_to_eui


def test_convert_utility_to_eui_electricity_only():
    """Convert annual kWh to kWh/sqft."""
    result = convert_utility_to_eui(
        annual_electricity_kwh=500000,
        sqft=50000,
    )
    assert result["electricity"] == 10.0
    assert result["natural_gas"] == 0.0


def test_convert_utility_to_eui_all_fuels():
    """Convert all fuel types to kWh/sqft."""
    result = convert_utility_to_eui(
        annual_electricity_kwh=500000,
        annual_natural_gas_therms=10000,
        annual_fuel_oil_gallons=1000,
        annual_propane_gallons=500,
        annual_district_heating_kbtu=100000,
        sqft=50000,
    )
    assert result["electricity"] == 10.0  # 500000 / 50000
    assert abs(result["natural_gas"] - 5.862) < 0.01  # 10000 * 29.31 / 50000
    assert abs(result["fuel_oil"] - 0.812) < 0.01  # 1000 * 40.6 / 50000
    assert abs(result["propane"] - 0.268) < 0.01  # 500 * 26.8 / 50000
    assert abs(result["district_heating"] - 0.586) < 0.01  # 100000 / 3.412 / 50000


def test_convert_utility_to_eui_none_input():
    """When no utility data provided, return None."""
    result = convert_utility_to_eui(sqft=50000)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_calibration.py::test_convert_utility_to_eui_electricity_only -v`
Expected: FAIL — `ImportError: cannot import name 'convert_utility_to_eui'`

- [ ] **Step 3: Implement conversion function**

Add to `backend/app/services/assessment.py` (before `_assess_single`, near the top of the file). Note: `assessment.py` already imports from `app.constants` — merge `KWH_PER_GALLON_FUEL_OIL`, `KWH_PER_GALLON_PROPANE`, and `KWH_PER_THERM` into the existing import statement rather than adding a duplicate block. Then add the function:
```python
# (merge into existing app.constants import)
# KWH_PER_GALLON_FUEL_OIL, KWH_PER_GALLON_PROPANE, KWH_PER_THERM


def convert_utility_to_eui(
    sqft: float,
    annual_electricity_kwh: float | None = None,
    annual_natural_gas_therms: float | None = None,
    annual_fuel_oil_gallons: float | None = None,
    annual_propane_gallons: float | None = None,
    annual_district_heating_kbtu: float | None = None,
) -> dict[str, float] | None:
    """Convert user-provided annual utility data to kWh/sqft per fuel.

    Returns None if no utility data is provided.
    """
    has_data = any(v is not None for v in [
        annual_electricity_kwh, annual_natural_gas_therms,
        annual_fuel_oil_gallons, annual_propane_gallons,
        annual_district_heating_kbtu,
    ])
    if not has_data:
        return None

    return {
        "electricity": (annual_electricity_kwh or 0) / sqft,
        "natural_gas": (annual_natural_gas_therms or 0) * KWH_PER_THERM / sqft,
        "fuel_oil": (annual_fuel_oil_gallons or 0) * KWH_PER_GALLON_FUEL_OIL / sqft,
        "propane": (annual_propane_gallons or 0) * KWH_PER_GALLON_PROPANE / sqft,
        "district_heating": (annual_district_heating_kbtu or 0) / KWH_TO_KBTU / sqft,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_calibration.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assessment.py backend/tests/test_calibration.py
git commit -m "feat: add convert_utility_to_eui helper for utility bill data conversion"
```

---

## Task 5: Model Manager — baseline_eui Parameter

**Files:**
- Modify: `backend/app/inference/model_manager.py:452-482`

No dedicated test for this task — the interface change is backward-compatible (`baseline_eui` defaults to `None`). Verified by running the full test suite in Step 3.

- [ ] **Step 1: Modify predict_delta signature**

In `backend/app/inference/model_manager.py`, update `predict_delta` (line 452):

Change:
```python
def predict_delta(
    self, features_dict: dict, upgrade_id: int, dataset: str, _enc_cache: dict | None = None
) -> dict:
```

To:
```python
def predict_delta(
    self, features_dict: dict, upgrade_id: int, dataset: str,
    baseline_eui: dict[str, float] | None = None,
    _enc_cache: dict | None = None,
) -> dict:
```

Then at the top of the method body, before any model calls, add:
```python
    if baseline_eui is not None:
        features_dict = {**features_dict}  # shallow copy
        for fuel, eui_val in baseline_eui.items():
            features_dict[f"baseline_{fuel}"] = eui_val
```

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && pytest`
Expected: All existing tests pass — `baseline_eui` defaults to `None`, so no behavior change for existing callers

- [ ] **Step 3: Commit**

```bash
git add backend/app/inference/model_manager.py
git commit -m "feat: add baseline_eui parameter to predict_delta for calibration support"
```

---

## Task 6: Assessment Pipeline — Calibration Flow

**Files:**
- Modify: `backend/app/services/assessment.py:127-380`
- Test: `backend/tests/test_calibration.py`

- [ ] **Step 1: Modify _assess_single to pass baseline_eui**

In `backend/app/services/assessment.py`, in the `_assess_single` function:

After baseline prediction (line 189: `baseline_eui = model_manager.predict_baseline(...)`), add utility data conversion:
```python
    # Convert utility data to kWh/sqft if provided
    actual_baseline_eui = convert_utility_to_eui(
        sqft=building.sqft,
        annual_electricity_kwh=building.annual_electricity_kwh,
        annual_natural_gas_therms=building.annual_natural_gas_therms,
        annual_fuel_oil_gallons=building.annual_fuel_oil_gallons,
        annual_propane_gallons=building.annual_propane_gallons,
        annual_district_heating_kbtu=building.annual_district_heating_kbtu,
    )
    calibrated = actual_baseline_eui is not None
    effective_baseline = actual_baseline_eui if calibrated else baseline_eui
```

Update the `_predict_upgrade` inner function (line 225) to pass `baseline_eui`:
```python
    def _predict_upgrade(uid: int) -> tuple[int, dict]:
        return uid, model_manager.predict_delta(
            features, uid, dataset, baseline_eui=effective_baseline,
        )
```

Replace savings clamping (line 251). **Remove the existing `max(0.0, d)` clamp** — negative per-fuel savings are valid for fuel-switching measures (e.g., electrification increases electricity while eliminating gas). The old clamp was unintentional and suppressed this signal:

Change:
```python
    savings_kwh = {fuel: max(0.0, d) for fuel, d in delta.items()}
```

To:
```python
    savings_kwh = {
        fuel: d if effective_baseline.get(fuel, 0) > 0.001 else 0.0
        for fuel, d in delta.items()
    }
```

This does two things:
1. **Removes the `max(0.0, d)` clamp** — negative per-fuel savings allowed (fuel switching)
2. **Zeroes out savings for fuels with no baseline consumption** — if the building doesn't use fuel oil/propane/district heating (baseline ≈ 0), savings for those fuels are forced to zero. The 0.001 kWh/sqft threshold avoids floating-point noise.

Update post-upgrade EUI (line 254) to clamp at zero — a building cannot use negative energy for a given fuel:
```python
    post_eui = {
        fuel: max(0.0, effective_baseline.get(fuel, 0) - savings_kwh.get(fuel, 0))
        for fuel in effective_baseline
    }
```

**Note: This is an intentional behavior change.** Negative per-fuel savings are now allowed (fuel switching). Post-upgrade EUI per fuel is floored at zero. This affects ALL assessments, not just calibrated ones. Electrification measures will now correctly show increased electricity use alongside decreased gas use.

When building the response, set calibration fields:
```python
    # In the BaselineResult construction:
    actual_eui_by_fuel=FuelBreakdown(**{
        fuel: val * KWH_TO_KBTU for fuel, val in actual_baseline_eui.items()
    }) if calibrated else None,
    actual_total_eui_kbtu_sf=sum(
        val * KWH_TO_KBTU for val in actual_baseline_eui.values()
    ) if calibrated else None,

    # In the BuildingResult construction:
    calibrated=calibrated,
```

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && pytest`
Expected: All existing tests pass — no utility data in existing fixtures means `calibrated=False` and `effective_baseline=baseline_eui` (same behavior as before). The clamping change may slightly alter some savings values if any test assertions check exact savings numbers where the model over-predicted savings beyond baseline — update those assertions if needed.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/assessment.py
git commit -m "feat: wire calibration flow through assessment pipeline"
```

---

## Task 7: SQLite Database Layer

**Files:**
- Create: `backend/app/services/database.py`
- Test: `backend/tests/test_database.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_database.py`:
```python
"""Tests for SQLite database CRUD operations."""
import json
import pytest
from app.services.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    database.init()
    return database


def test_create_project(db):
    project = db.create_project("Test Project")
    assert project["id"] == 1
    assert project["name"] == "Test Project"
    assert "created_at" in project


def test_list_projects(db):
    db.create_project("Project A")
    db.create_project("Project B")
    projects = db.list_projects()
    assert len(projects) == 2
    assert projects[0]["name"] == "Project A"


def test_get_project(db):
    db.create_project("Test Project")
    project = db.get_project(1)
    assert project["name"] == "Test Project"
    assert "buildings" in project


def test_get_project_not_found(db):
    result = db.get_project(999)
    assert result is None


def test_delete_project(db):
    db.create_project("Test Project")
    db.delete_project(1)
    assert db.get_project(1) is None


def test_create_building(db):
    db.create_project("Test Project")
    building_input = {"building_type": "OfficeSmall", "sqft": 50000}
    building = db.create_building(
        project_id=1,
        address="123 Main St",
        building_input=building_input,
    )
    assert building["id"] == 1
    assert building["address"] == "123 Main St"
    assert building["building_input"] == building_input


def test_create_building_with_utility_data(db):
    db.create_project("Test Project")
    utility_data = {"annual_electricity_kwh": 500000}
    building = db.create_building(
        project_id=1,
        address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
        utility_data=utility_data,
    )
    assert building["utility_data"] == utility_data


def test_save_assessment(db):
    db.create_project("Test Project")
    db.create_building(
        project_id=1, address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
    )
    result_data = {"baseline": {"total_eui_kbtu_sf": 51.0}}
    assessment = db.save_assessment(
        building_id=1, result=result_data, calibrated=False,
    )
    assert assessment["id"] == 1
    assert assessment["calibrated"] is False
    assert assessment["result"] == result_data


def test_get_building_assessments(db):
    db.create_project("Test Project")
    db.create_building(
        project_id=1, address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
    )
    db.save_assessment(building_id=1, result={"v": 1}, calibrated=False)
    db.save_assessment(building_id=1, result={"v": 2}, calibrated=True)
    assessments = db.get_assessments(building_id=1)
    assert len(assessments) == 2


def test_cascade_delete(db):
    db.create_project("Test Project")
    db.create_building(
        project_id=1, address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
    )
    db.save_assessment(building_id=1, result={"v": 1}, calibrated=False)
    db.delete_project(1)
    assert db.get_assessments(building_id=1) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.database'`

- [ ] **Step 3: Implement Database class**

Create `backend/app/services/database.py`:
```python
"""SQLite database for project/building/assessment persistence."""
import json
import os
import sqlite3
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get(
            "DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "buildingstock.db")
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT NOT NULL,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS buildings (
                    id              INTEGER PRIMARY KEY,
                    project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    address         TEXT,
                    building_input  JSON,
                    utility_data    JSON,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    id          INTEGER PRIMARY KEY,
                    building_id INTEGER REFERENCES buildings(id) ON DELETE CASCADE,
                    result      JSON,
                    calibrated  BOOLEAN,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        for key in ("building_input", "utility_data", "result"):
            if key in d and d[key] is not None:
                d[key] = json.loads(d[key])
        return d

    # --- Projects ---

    def create_project(self, name: str) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO projects (name) VALUES (?)", (name,)
            )
            return self._row_to_dict(
                conn.execute("SELECT * FROM projects WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    def list_projects(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_project(self, project_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                return None
            project = self._row_to_dict(row)
            buildings = conn.execute(
                "SELECT * FROM buildings WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
            project["buildings"] = [self._row_to_dict(b) for b in buildings]
            return project

    def delete_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # --- Buildings ---

    def create_building(
        self, project_id: int, address: str,
        building_input: dict, utility_data: dict | None = None,
    ) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO buildings (project_id, address, building_input, utility_data) VALUES (?, ?, ?, ?)",
                (project_id, address, json.dumps(building_input),
                 json.dumps(utility_data) if utility_data else None),
            )
            return self._row_to_dict(
                conn.execute("SELECT * FROM buildings WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    # --- Assessments ---

    def save_assessment(self, building_id: int, result: dict, calibrated: bool) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO assessments (building_id, result, calibrated) VALUES (?, ?, ?)",
                (building_id, json.dumps(result), calibrated),
            )
            return self._row_to_dict(
                conn.execute("SELECT * FROM assessments WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    def get_assessments(self, building_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assessments WHERE building_id = ? ORDER BY created_at",
                (building_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/database.py backend/tests/test_database.py
git commit -m "feat: add SQLite persistence layer for projects, buildings, and assessments"
```

---

## Task 8: Project API Endpoints

**Files:**
- Create: `backend/app/api/projects.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_projects_api.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_projects_api.py`:
```python
"""Tests for project CRUD API endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

    from app.main import app
    from app.services.database import Database

    db = Database()
    db.init()
    app.state.database = db

    with TestClient(app) as c:
        yield c


def test_create_project(client):
    resp = client.post("/projects", json={"name": "Test Project"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Project"
    assert "id" in data


def test_list_projects(client):
    client.post("/projects", json={"name": "Project A"})
    client.post("/projects", json={"name": "Project B"})
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_project(client):
    client.post("/projects", json={"name": "Test Project"})
    resp = client.get("/projects/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"
    assert "buildings" in resp.json()


def test_get_project_not_found(client):
    resp = client.get("/projects/999")
    assert resp.status_code == 404


def test_delete_project(client):
    client.post("/projects", json={"name": "Test Project"})
    resp = client.delete("/projects/1")
    assert resp.status_code == 200
    assert client.get("/projects/1").status_code == 404


def test_create_building(client):
    client.post("/projects", json={"name": "Test Project"})
    resp = client.post("/projects/1/buildings", json={
        "address": "123 Main St",
        "building_input": {"building_type": "OfficeSmall", "sqft": 50000},
    })
    assert resp.status_code == 200
    assert resp.json()["address"] == "123 Main St"


def test_save_assessment(client):
    client.post("/projects", json={"name": "Test Project"})
    client.post("/projects/1/buildings", json={
        "address": "123 Main St",
        "building_input": {"building_type": "OfficeSmall"},
    })
    resp = client.post("/projects/1/buildings/1/assessments", json={
        "result": {"baseline": {"total_eui_kbtu_sf": 51.0}},
        "calibrated": False,
    })
    assert resp.status_code == 200
    assert resp.json()["calibrated"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_projects_api.py -v`
Expected: FAIL — 404s or import errors (router not registered)

- [ ] **Step 3: Create projects router**

Create `backend/app/api/projects.py`:
```python
"""Project/building/assessment CRUD endpoints."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str


class CreateBuildingRequest(BaseModel):
    address: str
    building_input: dict
    utility_data: dict | None = None


class SaveAssessmentRequest(BaseModel):
    result: dict
    calibrated: bool


@router.post("")
def create_project(req: CreateProjectRequest, request: Request):
    return request.app.state.database.create_project(req.name)


@router.get("")
def list_projects(request: Request):
    return request.app.state.database.list_projects()


@router.get("/{project_id}")
def get_project(project_id: int, request: Request):
    project = request.app.state.database.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, request: Request):
    request.app.state.database.delete_project(project_id)
    return {"ok": True}


@router.post("/{project_id}/buildings")
def create_building(project_id: int, req: CreateBuildingRequest, request: Request):
    project = request.app.state.database.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return request.app.state.database.create_building(
        project_id=project_id,
        address=req.address,
        building_input=req.building_input,
        utility_data=req.utility_data,
    )


@router.post("/{project_id}/buildings/{building_id}/assessments")
def save_assessment(
    project_id: int, building_id: int,
    req: SaveAssessmentRequest, request: Request,
):
    return request.app.state.database.save_assessment(
        building_id=building_id,
        result=req.result,
        calibrated=req.calibrated,
    )
```

- [ ] **Step 4: Register router and init database in main.py**

In `backend/app/main.py`, add the import:
```python
from app.api.projects import router as projects_router
from app.services.database import Database
```

Include the router (after the existing `app.include_router(router)` call):
```python
app.include_router(projects_router)
```

Add database initialization inside the existing `lifespan` context manager (line 12-27), before `yield`:
```python
    db = Database()
    db.init()
    app.state.database = db
```

**Important:** Do NOT use `@app.on_event("startup")` — the app already uses the `lifespan` context manager pattern, and mixing the two is deprecated and may cause the startup event to be ignored.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_projects_api.py -v`
Expected: 8 passed

- [ ] **Step 6: Run full backend test suite**

Run: `cd backend && pytest`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/projects.py backend/app/main.py backend/tests/test_projects_api.py
git commit -m "feat: add project CRUD API endpoints with SQLite persistence"
```

---

## Task 9: Model Compression

**Files:**
- Modify: `scripts/training_utils.py:151-178`

- [ ] **Step 1: Update save_model_artifacts to use compression**

In `scripts/training_utils.py`, change line ~194:

From:
```python
    joblib.dump(model, model_path)
```

To:
```python
    joblib.dump(model, model_path, compress=3)
```

Also change line ~198 for encoders:

From:
```python
    joblib.dump(encoders, enc_path)
```

To:
```python
    joblib.dump(encoders, enc_path, compress=3)
```

- [ ] **Step 2: Verify loading still works**

Run: `cd backend && pytest`
Expected: All tests pass (existing models load fine — this only affects future saves)

- [ ] **Step 3: Commit**

```bash
git add scripts/training_utils.py
git commit -m "feat: enable joblib compression (level 3) for model artifacts"
```

---

## Task 10: Validation Experiment Script

**Files:**
- Create: `scripts/validate_baseline_feature.py`

This is a standalone research script. No TDD — it's exploratory.

- [ ] **Step 1: Create the validation script**

Create `scripts/validate_baseline_feature.py`. The script should:

1. Accept CLI args: `--dataset` (comstock/resstock/both), `--upgrades` (comma-separated IDs or "auto" to pick top 5-10)
2. Load baseline (upgrade 0) parquet data
3. For each selected upgrade, load upgrade parquet and merge on `bldg_id`
4. Compute delta targets (baseline - upgrade per fuel)
5. Define feature sets:
   - Control: existing `FEATURE_COLS` from the training scripts
   - Experiment: `FEATURE_COLS` + baseline EUI columns per fuel
6. Train/test split (80/20, fixed random seed)
7. Train XGBoost with default hyperparameters (same for both)
8. **Primary test:** Compare MAE, RMSE, R² for control vs experiment
9. **Error propagation test:** Train a baseline model on the training set, predict baseline EUI for test set, use predicted baseline as feature instead of ground truth
10. **Noise robustness test:** Add gaussian noise (10%, 20%) to ground truth baseline, re-evaluate
11. Output console summary table and CSV

Reference the existing training scripts for data loading patterns:
- ComStock: `scripts/train_comstock_deltas.py` lines 99-125 for `load_baseline_data`
- ResStock: `scripts/train_resstock_deltas.py` lines 99-125
- Feature columns: `FEATURE_COLS` from each script
- Fuel types: `FUEL_TYPES` from each script

```python
"""
Validation experiment: does adding baseline EUI as a feature improve delta predictions?

Usage:
    python3 scripts/validate_baseline_feature.py --dataset comstock
    python3 scripts/validate_baseline_feature.py --dataset both --upgrades 1,5,10,15,20
"""
```

The script structure should follow the pattern in the existing training scripts (argparse, data loading, pandas merges). Output a table like:

```
Dataset   | Upgrade | Fuel        | Control R² | Experiment R² | Delta R² | ErrProp R² | Noise10% R² | Noise20% R²
comstock  | 5       | electricity | 0.712      | 0.823         | +0.111   | 0.798      | 0.815       | 0.791
```

- [ ] **Step 2: Test run with a single upgrade**

Run: `python3 scripts/validate_baseline_feature.py --dataset comstock --upgrades 5`
Expected: Script runs, prints summary table, creates `scripts/validation_results.csv`

- [ ] **Step 3: Full validation run**

Run: `python3 scripts/validate_baseline_feature.py --dataset both`
Expected: Complete results for both datasets across selected upgrades

- [ ] **Step 4: Review results and decide go/no-go**

Examine the output. If R² improvements are consistent and sustained under error propagation and noise tests, proceed with model retraining (Task 11). If not, implement simple scaling fallback.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_baseline_feature.py
git commit -m "feat: add validation experiment for baseline EUI as delta model feature"
```

---

## Task 11: V2 Training Scripts (Conditional on Validation)

**Depends on:** Task 10 results showing meaningful improvement.

**Files:**
- Create: `scripts/train_comstock_deltas_v2.py` (copy of `train_comstock_deltas.py`)
- Create: `scripts/train_resstock_deltas_v2.py` (copy of `train_resstock_deltas.py`)

- [ ] **Step 1: Copy existing training scripts**

```bash
cp scripts/train_comstock_deltas.py scripts/train_comstock_deltas_v2.py
cp scripts/train_resstock_deltas.py scripts/train_resstock_deltas_v2.py
```

- [ ] **Step 2: Modify train_comstock_deltas_v2.py**

Add baseline EUI columns to `FEATURE_COLS` (around line 67):
```python
BASELINE_EUI_COLS = [
    "baseline_electricity",
    "baseline_natural_gas",
    "baseline_fuel_oil",
    "baseline_propane",
    "baseline_district_heating",
]
FEATURE_COLS = FEATURE_COLS + BASELINE_EUI_COLS
```

In the data loading/merge section (around line 177 where deltas are computed), stop dropping the baseline fuel columns. Instead, rename them to `baseline_{fuel}` and keep them in the feature set.

The exact column names in the parquet files are like `out.electricity.total.energy_consumption_intensity..kwh_per_ft2`. Map these to `baseline_electricity`, etc., after the merge.

- [ ] **Step 3: Modify train_resstock_deltas_v2.py**

Same changes as Step 2, but with 4 baseline columns (no `district_heating`):
```python
BASELINE_EUI_COLS = [
    "baseline_electricity",
    "baseline_natural_gas",
    "baseline_fuel_oil",
    "baseline_propane",
]
```

- [ ] **Step 4: Test run v2 training on a single upgrade**

Run: `python3 scripts/train_comstock_deltas_v2.py --upgrades 5`
Expected: Trains successfully, saves models with baseline columns in `feature_columns` metadata

- [ ] **Step 5: Verify v2 model metadata includes baseline columns**

```bash
python3 -c "import json; meta = json.load(open('XGB_Models/ComStock_Upgrades_2025_R3/XGB_upgrade5_electricity_meta.json')); print(meta['feature_columns'])"
```
Expected: Feature list includes `baseline_electricity`, `baseline_natural_gas`, etc.

- [ ] **Step 6: Full retraining**

Run both v2 scripts for all upgrades:
```bash
python3 scripts/train_comstock_deltas_v2.py
python3 scripts/train_resstock_deltas_v2.py
```

Note: This is the atomic swap — v2 models overwrite v1 models in the same directory.

- [ ] **Step 7: Run full backend test suite after model swap**

Run: `cd backend && pytest`
Expected: All tests pass. The models now expect baseline columns, and `predict_delta` passes them (from Task 5). Existing tests pass because `predict_delta` passes `baseline_eui=None` which means no baseline features are injected — but wait, v2 models expect them. **Important:** After the model swap, `predict_delta` must ALWAYS receive `baseline_eui` (either predicted or actual). Verify Task 6 changes handle this.

- [ ] **Step 8: Commit**

```bash
git add scripts/train_comstock_deltas_v2.py scripts/train_resstock_deltas_v2.py
git commit -m "feat: add v2 delta training scripts with baseline EUI as input feature"
```

---

## Task 12: Frontend TypeScript Types

**Files:**
- Modify: `frontend/src/types/assessment.ts:1-20,28-32,78-84`
- Create: `frontend/src/types/projects.ts`

- [ ] **Step 1: Update BuildingInput interface**

In `frontend/src/types/assessment.ts`, add to the `BuildingInput` interface (around line 19):
```typescript
  annual_electricity_kwh?: number
  annual_natural_gas_therms?: number
  annual_fuel_oil_gallons?: number
  annual_propane_gallons?: number
  annual_district_heating_kbtu?: number
```

- [ ] **Step 2: Update BaselineResult interface**

In `frontend/src/types/assessment.ts`, add to `BaselineResult` (around line 31):
```typescript
  actual_eui_by_fuel?: FuelBreakdown
  actual_total_eui_kbtu_sf?: number
```

- [ ] **Step 3: Update BuildingResult interface**

Add to `BuildingResult` (around line 82):
```typescript
  calibrated: boolean
```

- [ ] **Step 4: Create projects types**

Create `frontend/src/types/projects.ts`:
```typescript
export interface Project {
  id: number
  name: string
  created_at: string
  updated_at: string
  buildings?: Building[]
}

export interface Building {
  id: number
  project_id: number
  address: string
  building_input: Record<string, unknown>
  utility_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface Assessment {
  id: number
  building_id: number
  result: Record<string, unknown>
  calibrated: boolean
  created_at: string
}
```

- [ ] **Step 5: Type check**

Run: `cd frontend && npm run type-check`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/assessment.ts frontend/src/types/projects.ts
git commit -m "feat: add TypeScript types for utility data, calibration, and projects"
```

---

## Task 13: Frontend — Projects Composable

**Files:**
- Create: `frontend/src/composables/useProjects.ts`

- [ ] **Step 1: Create useProjects composable**

Create `frontend/src/composables/useProjects.ts`:
```typescript
import { ref } from 'vue'
import type { Project, Building, Assessment } from '@/types/projects'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useProjects() {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchProjects() {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/projects`)
      projects.value = await resp.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id: number) {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/projects/${id}`)
      if (!resp.ok) throw new Error('Project not found')
      currentProject.value = await resp.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createProject(name: string) {
    const resp = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    const project = await resp.json()
    projects.value.push(project)
    return project
  }

  async function deleteProject(id: number) {
    await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' })
    projects.value = projects.value.filter(p => p.id !== id)
    if (currentProject.value?.id === id) {
      currentProject.value = null
    }
  }

  async function createBuilding(
    projectId: number, address: string,
    buildingInput: Record<string, unknown>,
    utilityData?: Record<string, unknown>,
  ) {
    const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address,
        building_input: buildingInput,
        utility_data: utilityData,
      }),
    })
    return await resp.json()
  }

  async function saveAssessment(
    projectId: number, buildingId: number,
    result: Record<string, unknown>, calibrated: boolean,
  ) {
    const resp = await fetch(
      `${API_BASE}/projects/${projectId}/buildings/${buildingId}/assessments`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result, calibrated }),
      },
    )
    return await resp.json()
  }

  return {
    projects, currentProject, loading, error,
    fetchProjects, fetchProject, createProject,
    deleteProject, createBuilding, saveAssessment,
  }
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useProjects.ts
git commit -m "feat: add useProjects composable for project CRUD API calls"
```

---

## Task 14: Frontend — Tab Navigation

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add reactive currentView and tab navigation**

In `frontend/src/App.vue`, add to the `<script setup>`:
```typescript
import { ref } from 'vue'
const currentView = ref<'assessment' | 'projects'>('assessment')
```

In the `<template>`, add tab navigation above the current content. Use PButton or simple styled tabs matching the SiteLynx nav pattern. Wrap the existing `AssessmentView` in a `v-if="currentView === 'assessment'"` and add `ProjectsView` with `v-if="currentView === 'projects'"`.

- [ ] **Step 2: Verify assessment view still works**

Run: `cd frontend && npm run dev`
Navigate to the app — "Energy Audit" tab should be active by default, showing the existing form.

- [ ] **Step 3: Type check and build**

Run: `cd frontend && npm run type-check && npm run build`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: add tab navigation with currentView reactive for Energy Audit and Projects"
```

---

## Task 15: Frontend — Projects View

**Files:**
- Create: `frontend/src/components/ProjectsView.vue`
- Create: `frontend/src/components/ProjectDetail.vue`

- [ ] **Step 1: Create ProjectsView component**

Create `frontend/src/components/ProjectsView.vue` using partner-components:
- PLayout for structure
- PTable or shadcn cards for project list
- PButton for "Create Project"
- PTextInput in a PPopover for project name entry
- Each project row/card is clickable — sets `selectedProjectId` to navigate to detail view
- PButton for delete with confirmation

Use `useProjects()` composable. Fetch projects on mount.

- [ ] **Step 2: Create ProjectDetail component**

Create `frontend/src/components/ProjectDetail.vue`:
- Shows project name and building list
- Each building shows address, assessment count, calibration status
- "Back to Projects" button
- PTable for buildings list
- Click building to expand and show assessment history

Use `useProjects()` composable. Fetch project detail on mount.

- [ ] **Step 3: Type check and verify**

Run: `cd frontend && npm run type-check && npm run dev`
Navigate to Projects tab — should show empty list with "Create Project" button.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ProjectsView.vue frontend/src/components/ProjectDetail.vue
git commit -m "feat: add ProjectsView and ProjectDetail components with partner-components"
```

---

## Task 16: Frontend — Utility Data Input Section

**Files:**
- Modify: `frontend/src/components/BuildingForm.vue`

- [ ] **Step 1: Add collapsible utility data section**

In `BuildingForm.vue`, add after the existing building characteristics fields:

1. A collapsible section header: "Have utility bills? (Optional)" — click toggles `showUtilityData` ref
2. When expanded, show two PNumericInput fields:
   - Annual Electricity (kWh)
   - Annual Natural Gas (therms)
3. An "Add more fuel types" link that toggles `showExtraFuels` ref
4. When expanded, show additional fields:
   - Annual Fuel Oil (gallons)
   - Annual Propane (gallons)
   - Annual District Heating (kBtu) — only rendered when building type is commercial (check against ComStock building types)

Bind all fields to the reactive form object that gets emitted on submit.

- [ ] **Step 2: Update useAssessment to pass utility data**

In `frontend/src/composables/useAssessment.ts`, ensure the utility data fields are included in the request payload when present.

- [ ] **Step 3: Type check and verify**

Run: `cd frontend && npm run type-check && npm run dev`
Fill in the form — utility section should collapse/expand. Submit should include utility data in the API call.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/BuildingForm.vue frontend/src/composables/useAssessment.ts
git commit -m "feat: add collapsible utility data input section to building form"
```

---

## Task 17: Frontend — Calibrated Results Indicator

**Files:**
- Modify: `frontend/src/components/BaselineSummary.vue` (or wherever baseline results are displayed)

- [ ] **Step 1: Add calibration indicator**

When `result.calibrated === true`:
- Show a PBadge or PChip with "Calibrated" next to the baseline EUI
- Display actual vs predicted EUI side-by-side (per fuel if `actual_eui_by_fuel` is present)

Use partner-components PBadge/PChip for the indicator.

- [ ] **Step 2: Verify with test data**

Run the dev server, submit an assessment with utility data filled in. Verify the "Calibrated" badge appears and actual/predicted comparison displays correctly.

- [ ] **Step 3: Type check and build**

Run: `cd frontend && npm run type-check && npm run build`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/BaselineSummary.vue
git commit -m "feat: show calibrated badge and actual vs predicted EUI comparison"
```

---

## Task 18: Test Fixtures and Integration

**Files:**
- Modify: `backend/tests/conftest.py:39-70`

- [ ] **Step 1: Add calibrated input fixture**

In `backend/tests/conftest.py`, add a new fixture:
```python
@pytest.fixture
def calibrated_office_input():
    """Office input with utility data for calibration testing."""
    return BuildingInput(
        building_type="OfficeSmall",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        heating_fuel="NaturalGas",
        annual_electricity_kwh=600000,
        annual_natural_gas_therms=12000,
    )
```

- [ ] **Step 2: Add integration test for calibrated path**

Append to `backend/tests/test_calibration.py`:
```python
import pytest
from app.services.assessment import _assess_single


@pytest.mark.skipif(
    not pytest.importorskip("app.inference.model_manager", reason="Models not available"),
    reason="Models not available",
)
def test_calibrated_assessment_returns_calibrated_flag(calibrated_office_input):
    """Integration test: assessment with utility data should return calibrated=True."""
    # This test requires models to be loaded — skip in CI without models
    from app.main import app
    mm = app.state.model_manager
    cc = app.state.cost_calculator
    imp = getattr(app.state, "imputation_service", None)

    result = _assess_single(calibrated_office_input, 0, mm, cc, imp)
    assert result.calibrated is True
    assert result.baseline.actual_eui_by_fuel is not None
    assert result.baseline.actual_total_eui_kbtu_sf is not None
    assert result.baseline.actual_total_eui_kbtu_sf > 0


def test_uncalibrated_assessment_returns_not_calibrated(office_input):
    """Integration test: assessment without utility data should return calibrated=False."""
    from app.main import app
    mm = app.state.model_manager
    cc = app.state.cost_calculator
    imp = getattr(app.state, "imputation_service", None)

    result = _assess_single(office_input, 0, mm, cc, imp)
    assert result.calibrated is False
    assert result.baseline.actual_eui_by_fuel is None
```

Note: These tests require models to be loaded. They will be skipped in environments without model files.

- [ ] **Step 3: Run full test suite**

Run: `cd backend && pytest`
Expected: All tests pass (integration tests may skip if models not loaded)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_calibration.py
git commit -m "feat: add calibrated building input fixture and integration tests"
```

---

## Execution Order

Tasks can be parallelized across these independent tracks:

**Track A — Validation & Training (sequential):**
Task 10 (validation) → Task 11 (v2 training, conditional)

**Track B — Schema & Pipeline (sequential):**
Task 1 (constants) → Task 2 (request schema) → Task 3 (response schema) → Task 4 (conversion helper) → Task 5 (model manager) → Task 6 (pipeline wiring) → Task 18 (fixtures)

**Track C — Persistence (sequential):**
Task 7 (database) → Task 8 (API endpoints)

**Track D — Frontend (sequential, depends on B and C):**
Task 12 (types) → Task 13 (composable) → Task 14 (navigation) → Task 15 (projects view) → Task 16 (utility input) → Task 17 (results indicator)

**Independent:**
Task 9 (compression) — can run anytime

**Tracks A, B, C, and Task 9 can all start in parallel.**
