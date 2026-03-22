# Measure Selection & Projected ENERGY STAR Score — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to select upgrade measures from the assessment table, persist selections to SQLite, compute a projected post-upgrade EUI, and calculate a projected ENERGY STAR score displayed alongside the baseline.

**Architecture:** Backend adds `savings_by_fuel` and `constituent_upgrade_ids` to `MeasureResult`, a new `measure_selections` SQLite table, and a `/energy-star/projected-score` endpoint. Frontend adds a `useMeasureSelections` composable for selection state + persistence, checkboxes to the measures table, and expands the ENERGY STAR score card into a four-state split layout. Projected EUI is computed client-side (sum of per-fuel deltas); projected ESPM score is fetched on-demand via button.

**Tech Stack:** Python/FastAPI, Pydantic v2, SQLite, Vue 3 Composition API, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-22-measure-selection-projected-score-design.md`

---

## File Map

### Backend — Create
- `backend/tests/test_measure_selections.py` — Tests for selection persistence + projected score endpoint

### Backend — Modify
- `backend/app/schemas/response.py` — Add `savings_by_fuel` and `constituent_upgrade_ids` to `MeasureResult`
- `backend/app/services/assessment.py:413-431` — Populate `savings_by_fuel` and `constituent_upgrade_ids` on `MeasureResult`
- `backend/app/inference/applicability.py` — Add `PACKAGE_CONSTITUENTS` mapping constant
- `backend/app/services/database.py:21-52` — Add `measure_selections` table + CRUD functions
- `backend/app/api/projects.py` — Add GET/PUT selections endpoints (alongside existing project/building CRUD)
- `backend/app/api/routes.py` — Add POST projected-score endpoint
- `backend/app/services/energy_star.py` — Support synthetic `BaselineResult` for projected score

### Frontend — Create
- `frontend/src/composables/useMeasureSelections.ts` — Selection state management + persistence + projected EUI computation

### Frontend — Modify
- `frontend/src/types/assessment.ts:52-68` — Add `savings_by_fuel`, `constituent_upgrade_ids`, `ProjectedEui` type
- `frontend/src/components/MeasuresTable.vue` — Add checkbox column, package lockout, auto-replace
- `frontend/src/components/EnergyStarScore.vue` — Four-state split layout, projected gauge
- `frontend/src/composables/useEnergyStarScore.ts` — No changes needed (projected score fetch lives in `useMeasureSelections`)
- `frontend/src/views/AssessmentView.vue:15-34` — Wire up `useMeasureSelections`
- `frontend/src/components/SavedAssessmentView.vue:29-69` — Wire up `useMeasureSelections`

---

## Task 1: Add `savings_by_fuel` and `constituent_upgrade_ids` to MeasureResult (Backend Schema)

**Files:**
- Modify: `backend/app/schemas/response.py:30-45`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_schemas.py`, add:

```python
from app.schemas.response import MeasureResult, FuelBreakdown


def test_measure_result_savings_by_fuel():
    m = MeasureResult(
        upgrade_id=1,
        name="Test",
        category="hvac",
        applicable=True,
        savings_by_fuel=FuelBreakdown(
            electricity=5.0,
            natural_gas=2.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )
    assert m.savings_by_fuel is not None
    assert m.savings_by_fuel.electricity == 5.0


def test_measure_result_constituent_upgrade_ids():
    m = MeasureResult(
        upgrade_id=54,
        name="Package 1",
        category="package",
        applicable=True,
        constituent_upgrade_ids=[48, 50, 51],
    )
    assert m.constituent_upgrade_ids == [48, 50, 51]


def test_measure_result_defaults_none():
    m = MeasureResult(
        upgrade_id=1, name="Test", category="hvac", applicable=True
    )
    assert m.savings_by_fuel is None
    assert m.constituent_upgrade_ids is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_schemas.py::test_measure_result_savings_by_fuel -v`
Expected: FAIL — `savings_by_fuel` not a valid field

- [ ] **Step 3: Add fields to MeasureResult**

In `backend/app/schemas/response.py`, add two fields to `MeasureResult` (after `description`):

```python
class MeasureResult(BaseModel):
    # ... existing fields ...
    description: Optional[str] = None
    savings_by_fuel: Optional[FuelBreakdown] = None
    constituent_upgrade_ids: Optional[list[int]] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_schemas.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/response.py backend/tests/test_schemas.py
git commit -m "feat: add savings_by_fuel and constituent_upgrade_ids to MeasureResult schema"
```

---

## Task 2: Add `PACKAGE_CONSTITUENTS` mapping to applicability.py

**Files:**
- Modify: `backend/app/inference/applicability.py`
- Test: `backend/tests/test_applicability.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_applicability.py`, add:

```python
from app.inference.applicability import PACKAGE_CONSTITUENTS


def test_package_constituents_mapping_exists():
    assert isinstance(PACKAGE_CONSTITUENTS, dict)
    # Package 1 (54) = wall + roof + windows
    assert 54 in PACKAGE_CONSTITUENTS
    assert isinstance(PACKAGE_CONSTITUENTS[54], list)
    assert len(PACKAGE_CONSTITUENTS[54]) > 0


def test_package_constituents_no_self_reference():
    """Package constituent lists should not include the package's own ID."""
    for pkg_id, constituents in PACKAGE_CONSTITUENTS.items():
        assert pkg_id not in constituents, f"Package {pkg_id} contains itself"


def test_package_constituents_are_valid_upgrade_ids():
    """All constituent IDs should be individual upgrade IDs, not other packages."""
    all_package_ids = set(PACKAGE_CONSTITUENTS.keys())
    for pkg_id, constituents in PACKAGE_CONSTITUENTS.items():
        for c in constituents:
            assert c not in all_package_ids, (
                f"Package {pkg_id} references another package {c}"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_applicability.py::test_package_constituents_mapping_exists -v`
Expected: FAIL — `PACKAGE_CONSTITUENTS` not importable

- [ ] **Step 3: Add the mapping constant**

In `backend/app/inference/applicability.py`, add at module level (before the `ApplicabilityChecker` class). Derive from the package rule comments already in the file:

```python
# Mapping of ComStock package upgrade IDs → their constituent individual upgrade IDs.
# Used to enforce package/individual lockout in the measure selection UI.
# ResStock does not have packages.
#
# IMPORTANT: These mappings are approximate — they list the individual upgrade IDs
# whose savings conceptually overlap with the package. The purpose is UI lockout
# (preventing double-selection), not exact model equivalence. HP-RTU variants (1-10)
# are represented by whichever variant the applicability rules check for that package.
# GHP variants (28, 29, 30) are included when any GHP is part of the package.
#
# Verify against _check_comstock_applicability() rules in this file before finalizing.
PACKAGE_CONSTITUENTS: dict[int, list[int]] = {
    54: [48, 50, 51],               # Package 1: Wall Insulation + Secondary Windows + Window Film
    55: [43, 1],                     # Package 2: LED + HP-RTU (upgrade 1 = HP-RTU representative)
    56: [43, 4],                     # Package 3: LED + Std HP-RTU (upgrade 4 per applicability check)
    57: [48, 50, 51, 43, 1],         # Package 4: Package 1 + Package 2
    58: [1, 19, 20, 21],             # Package 5: HP-RTU + Economizer + DCV + Energy Recovery
    59: [28, 29, 30],                # Package 6: GHP (Hydronic/Packaged/Console variants)
    63: [48, 50, 51, 28, 29, 30],    # Package 10: Package 1 + Package 6
    64: [48, 50, 51, 28, 29, 30, 43],# Package 11: Package 10 + LED
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applicability.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "feat: add PACKAGE_CONSTITUENTS mapping for measure selection lockout"
```

---

## Task 3: Populate `savings_by_fuel` and `constituent_upgrade_ids` in assessment.py

**Files:**
- Modify: `backend/app/services/assessment.py:308-431`
- Test: `backend/tests/test_integration_pipeline.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_integration_pipeline.py`, add (using existing fixtures and patterns from conftest.py):

```python
def test_measure_result_has_savings_by_fuel(office_input):
    """After assessment, applicable MeasureResults should include per-fuel savings."""
    from app.services.assessment import assess_buildings
    from app.inference.model_manager import ModelManager
    from app.services.cost_calculator import CostCalculator
    from app.inference.imputation_service import ImputationService

    mm = ModelManager()
    cc = CostCalculator()
    imp = ImputationService()
    results = assess_buildings([office_input], mm, cc, imp)
    applicable = [m for m in results[0].measures if m.applicable]
    assert len(applicable) > 0, "No applicable measures"

    for m in applicable:
        assert m.savings_by_fuel is not None, f"Upgrade {m.upgrade_id} missing savings_by_fuel"
        # All fuel fields should be present (may be 0.0)
        assert hasattr(m.savings_by_fuel, "electricity")
        assert hasattr(m.savings_by_fuel, "natural_gas")


def test_package_measures_have_constituent_ids(office_input):
    """Package measures should have constituent_upgrade_ids populated."""
    from app.services.assessment import assess_buildings
    from app.inference.model_manager import ModelManager
    from app.services.cost_calculator import CostCalculator
    from app.inference.imputation_service import ImputationService

    mm = ModelManager()
    cc = CostCalculator()
    imp = ImputationService()
    results = assess_buildings([office_input], mm, cc, imp)
    packages = [m for m in results[0].measures if m.category == "package" and m.applicable]

    if len(packages) > 0:
        for p in packages:
            assert p.constituent_upgrade_ids is not None, (
                f"Package {p.upgrade_id} missing constituent_upgrade_ids"
            )
            assert len(p.constituent_upgrade_ids) > 0


def test_individual_measures_no_constituent_ids(office_input):
    """Individual (non-package) measures should have constituent_upgrade_ids = None."""
    from app.services.assessment import assess_buildings
    from app.inference.model_manager import ModelManager
    from app.services.cost_calculator import CostCalculator
    from app.inference.imputation_service import ImputationService

    mm = ModelManager()
    cc = CostCalculator()
    imp = ImputationService()
    results = assess_buildings([office_input], mm, cc, imp)
    individuals = [m for m in results[0].measures if m.category != "package"]

    for m in individuals:
        assert m.constituent_upgrade_ids is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_integration_pipeline.py::test_measure_result_has_savings_by_fuel -v`
Expected: FAIL — `savings_by_fuel` is None

- [ ] **Step 3: Populate savings_by_fuel in assessment.py**

In `backend/app/services/assessment.py`, in the `MeasureResult` constructor call (around line 413), add `savings_by_fuel` built from the already-computed `savings_kwh` dict. Add this import at the top if not already present:

```python
from app.inference.applicability import PACKAGE_CONSTITUENTS
```

Then in the upgrade loop, after `other_savings_kbtu` is computed (around line 406), add:

```python
        # Per-fuel savings in kBtu/sf for client-side projected EUI computation
        savings_fuel_breakdown = FuelBreakdown(
            electricity=round(savings_kwh.get("electricity", 0.0) * KWH_TO_KBTU, 4),
            natural_gas=round(savings_kwh.get("natural_gas", 0.0) * KWH_TO_KBTU, 4),
            fuel_oil=round(savings_kwh.get("fuel_oil", 0.0) * KWH_TO_KBTU, 4),
            propane=round(savings_kwh.get("propane", 0.0) * KWH_TO_KBTU, 4),
            district_heating=round(savings_kwh.get("district_heating", 0.0) * KWH_TO_KBTU, 4),
        )

        # Package constituent IDs (only for ComStock packages)
        pkg_constituents = PACKAGE_CONSTITUENTS.get(uid)
```

Then in the `MeasureResult(...)` constructor, add the two new fields:

```python
                savings_by_fuel=savings_fuel_breakdown,
                constituent_upgrade_ids=pkg_constituents,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_integration_pipeline.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd backend && pytest --timeout=120 -x -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/assessment.py backend/tests/test_integration_pipeline.py
git commit -m "feat: populate savings_by_fuel and constituent_upgrade_ids in assessment pipeline"
```

---

## Task 4: Add `measure_selections` table and CRUD functions to database.py

**Files:**
- Modify: `backend/app/services/database.py`
- Test: `backend/tests/test_database.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_database.py`, add:

```python
def test_save_selections(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5, 8])
    result = db.get_selections(building_id=1)
    assert result is not None
    assert result["selected_upgrade_ids"] == [3, 5, 8]
    assert result["projected_espm"] is None
    assert result["updated_at"] is not None


def test_save_selections_upsert(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    db.save_selections(building_id=1, upgrade_ids=[3, 5, 8, 10])
    result = db.get_selections(building_id=1)
    assert result["selected_upgrade_ids"] == [3, 5, 8, 10]


def test_get_selections_empty(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    result = db.get_selections(building_id=1)
    assert result is not None
    assert result["selected_upgrade_ids"] == []
    assert result["projected_espm"] is None
    assert result["updated_at"] is None


def test_save_projected_espm(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    espm = {"score": 72, "eligible": True, "espm_property_type": "Office"}
    db.save_projected_espm(building_id=1, espm_result=espm)
    result = db.get_selections(building_id=1)
    assert result["projected_espm"]["score"] == 72


def test_clear_projected_espm(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    db.save_projected_espm(building_id=1, espm_result={"score": 72})
    db.clear_projected_espm(building_id=1)
    result = db.get_selections(building_id=1)
    assert result["projected_espm"] is None
    assert result["selected_upgrade_ids"] == [3, 5]  # preserved


def test_clear_projected_espm_on_reassessment(db):
    """Saving a new assessment should clear projected ESPM."""
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    db.save_projected_espm(building_id=1, espm_result={"score": 72})
    db.save_assessment(building_id=1, result={"baseline": {}}, calibrated=False)
    result = db.get_selections(building_id=1)
    assert result["projected_espm"] is None
    assert result["selected_upgrade_ids"] == [3, 5]


def test_selections_cascade_delete(db):
    """Deleting a building should cascade-delete its selections."""
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3])
    db.delete_project(1)
    result = db.get_selections(building_id=1)
    assert result["selected_upgrade_ids"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_database.py::test_save_selections -v`
Expected: FAIL — `save_selections` not found

- [ ] **Step 3: Add table creation to init()**

In `backend/app/services/database.py`, in the `init()` method's `executescript()` call, add after the `assessments` table:

```sql
CREATE TABLE IF NOT EXISTS measure_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER NOT NULL UNIQUE,
    selected_upgrade_ids TEXT NOT NULL DEFAULT '[]',
    projected_espm TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE CASCADE
);
```

- [ ] **Step 4: Add CRUD functions**

In `backend/app/services/database.py`, add these methods to the `Database` class:

```python
def save_selections(self, building_id: int, upgrade_ids: list[int]) -> None:
    with self._connect() as conn:
        conn.execute(
            """INSERT INTO measure_selections (building_id, selected_upgrade_ids, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(building_id)
               DO UPDATE SET selected_upgrade_ids = excluded.selected_upgrade_ids,
                             updated_at = CURRENT_TIMESTAMP""",
            (building_id, json.dumps(upgrade_ids)),
        )

def get_selections(self, building_id: int) -> dict:
    with self._connect() as conn:
        row = conn.execute(
            "SELECT selected_upgrade_ids, projected_espm, updated_at FROM measure_selections WHERE building_id = ?",
            (building_id,),
        ).fetchone()
    if row is None:
        return {"selected_upgrade_ids": [], "projected_espm": None, "updated_at": None}
    return {
        "selected_upgrade_ids": json.loads(row[0]),
        "projected_espm": json.loads(row[1]) if row[1] else None,
        "updated_at": row[2],
    }

def save_projected_espm(self, building_id: int, espm_result: dict) -> None:
    with self._connect() as conn:
        conn.execute(
            """UPDATE measure_selections
               SET projected_espm = ?, updated_at = CURRENT_TIMESTAMP
               WHERE building_id = ?""",
            (json.dumps(espm_result), building_id),
        )

def clear_projected_espm(self, building_id: int) -> None:
    with self._connect() as conn:
        conn.execute(
            """UPDATE measure_selections
               SET projected_espm = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE building_id = ?""",
            (building_id,),
        )
```

- [ ] **Step 5: Add assessment save hook**

In `backend/app/services/database.py`, modify the existing `save_assessment()` method to also clear projected ESPM:

```python
def save_assessment(self, building_id: int, result: dict, calibrated: bool) -> dict:
    conn = self._connect()
    # ... existing INSERT logic ...
    # Clear stale projected ESPM (baseline changed)
    self.clear_projected_espm(building_id)
    return ...
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/database.py backend/tests/test_database.py
git commit -m "feat: add measure_selections table with CRUD and assessment save hook"
```

---

## Task 5: Add selections API endpoints and projected-score endpoint

**Files:**
- Modify: `backend/app/api/projects.py` — GET/PUT selections + PUT projected-espm
- Modify: `backend/app/api/routes.py` — POST projected-score
- Create: `backend/tests/test_measure_selections.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_measure_selections.py`:

```python
"""Tests for measure selection API endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """TestClient with a fresh temporary database."""
    import os
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")

    from app.main import app
    from app.services.database import Database

    db = Database(str(tmp_path / "test.db"))
    db.init()
    app.state.database = db

    with TestClient(app) as c:
        # Create a project and building for testing
        project = db.create_project("Test")
        db.create_building(
            project["id"], "123 Main St",
            {"building_type": "Office", "sqft": 50000, "num_stories": 3,
             "zipcode": "20001", "year_built": 1985},
        )
        yield c


def test_get_selections_empty(client):
    resp = client.get("/projects/1/buildings/1/selections")
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_upgrade_ids"] == []
    assert data["projected_espm"] is None


def test_put_selections(client):
    resp = client.put(
        "/projects/1/buildings/1/selections",
        json={"selected_upgrade_ids": [3, 5, 8]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_upgrade_ids"] == [3, 5, 8]


def test_put_then_get_selections(client):
    client.put(
        "/projects/1/buildings/1/selections",
        json={"selected_upgrade_ids": [3, 5]},
    )
    resp = client.get("/projects/1/buildings/1/selections")
    assert resp.status_code == 200
    assert resp.json()["selected_upgrade_ids"] == [3, 5]


def test_put_selections_upsert(client):
    client.put("/projects/1/buildings/1/selections", json={"selected_upgrade_ids": [3]})
    client.put("/projects/1/buildings/1/selections", json={"selected_upgrade_ids": [3, 5, 8]})
    resp = client.get("/projects/1/buildings/1/selections")
    assert resp.json()["selected_upgrade_ids"] == [3, 5, 8]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_measure_selections.py::test_get_selections_empty -v`
Expected: FAIL — 404 (route not defined)

- [ ] **Step 3: Add Pydantic request/response models**

In `backend/app/api/projects.py`, add at the top with other models:

```python
class SelectionsUpdate(BaseModel):
    selected_upgrade_ids: list[int]

class ProjectedEspmUpdate(BaseModel):
    projected_espm: dict
```

- [ ] **Step 4: Add selections endpoints to projects.py**

In `backend/app/api/projects.py` (which already has `prefix="/projects"`), add:

```python
@router.get("/{project_id}/buildings/{building_id}/selections")
def get_selections(project_id: int, building_id: int, request: Request):
    db = request.app.state.database
    return db.get_selections(building_id)


@router.put("/{project_id}/buildings/{building_id}/selections")
def put_selections(
    project_id: int, building_id: int, body: SelectionsUpdate, request: Request
):
    db = request.app.state.database
    db.save_selections(building_id, body.selected_upgrade_ids)
    return db.get_selections(building_id)


@router.put("/{project_id}/buildings/{building_id}/selections/projected-espm")
def put_projected_espm(
    project_id: int, building_id: int, body: ProjectedEspmUpdate, request: Request
):
    db = request.app.state.database
    db.save_projected_espm(building_id, body.projected_espm)
    return db.get_selections(building_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_measure_selections.py -v`
Expected: All PASS

- [ ] **Step 6: Add projected-score endpoint with Pydantic model and error handling**

In `backend/app/api/routes.py`, add a Pydantic request model and the endpoint:

```python
from app.schemas.response import BaselineResult, FuelBreakdown


class ProjectedScoreRequest(BaseModel):
    building: BuildingInput
    projected_eui_by_fuel: dict
    address: Optional[str] = None


@router.post("/energy-star/projected-score", response_model=EnergyStarResponse)
async def projected_energy_star_score(req: ProjectedScoreRequest):
    # Construct a synthetic BaselineResult from the projected fuel breakdown
    projected_baseline = BaselineResult(
        total_eui_kbtu_sf=sum(req.projected_eui_by_fuel.values()),
        eui_by_fuel=FuelBreakdown(**req.projected_eui_by_fuel),
    )

    service = EnergyStarService()
    try:
        return service.get_score(
            building=req.building,
            baseline=projected_baseline,
            address=req.address,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

Note: This matches the existing `/energy-star/score` pattern — inline `EnergyStarService()` instantiation and `try/except RuntimeError` with 502 error response.

- [ ] **Step 7: Run full test suite**

Run: `cd backend && pytest --timeout=120 -x -q`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/projects.py backend/app/api/routes.py backend/tests/test_measure_selections.py
git commit -m "feat: add selections API endpoints and projected ENERGY STAR score endpoint"
```

---

## Task 6: Add frontend types (`savings_by_fuel`, `constituent_upgrade_ids`, `ProjectedEui`)

**Files:**
- Modify: `frontend/src/types/assessment.ts:52-68`

- [ ] **Step 1: Add new fields and types**

In `frontend/src/types/assessment.ts`, add fields to `MeasureResult` (after `description`):

```typescript
export interface MeasureResult {
  // ... existing fields ...
  description?: string
  savings_by_fuel?: FuelBreakdown | null
  constituent_upgrade_ids?: number[] | null
}
```

Add the new `ProjectedEui` interface (after `EnergyStarResponse`):

```typescript
export interface ProjectedEui {
  total_eui_kbtu_sf: number
  eui_by_fuel: FuelBreakdown
  reduction_pct: number
}
```

- [ ] **Step 2: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS (no errors from new optional fields)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/assessment.ts
git commit -m "feat: add savings_by_fuel, constituent_upgrade_ids, and ProjectedEui types"
```

---

## Task 7: Create `useMeasureSelections` composable

**Files:**
- Create: `frontend/src/composables/useMeasureSelections.ts`

Note: `useEnergyStarScore.ts` is NOT modified. The projected score fetch logic lives entirely in the `useMeasureSelections` composable to keep it self-contained.

- [ ] **Step 1: Create useMeasureSelections composable**

Create `frontend/src/composables/useMeasureSelections.ts`:

```typescript
import { ref, computed, watch } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import type {
  MeasureResult,
  BaselineResult,
  BuildingInput,
  FuelBreakdown,
  ProjectedEui,
  EnergyStarResponse,
} from '../types/assessment'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useMeasureSelections(
  measures: Ref<MeasureResult[]>,
  baseline: Ref<BaselineResult | null>,
  building: Ref<BuildingInput | null>,
  buildingId: Ref<number | null>,
  address: Ref<string | null>,
) {
  const selectedUpgradeIds = ref<Set<number>>(new Set())
  const projectedEspm = ref<EnergyStarResponse | null>(null)
  const projectedLoading = ref(false)
  const projectedError = ref<string | null>(null)
  const initialized = ref(false)

  // --- Package constituent map (derived from measures data) ---
  const packageConstituentMap = computed<Map<number, number[]>>(() => {
    const map = new Map<number, number[]>()
    for (const m of measures.value) {
      if (m.constituent_upgrade_ids && m.constituent_upgrade_ids.length > 0) {
        map.set(m.upgrade_id, m.constituent_upgrade_ids)
      }
    }
    return map
  })

  // --- Disabled individual measure IDs (locked out by selected packages) ---
  const disabledByPackage = computed<Map<number, string>>(() => {
    const map = new Map<number, string>()
    for (const [pkgId, constituents] of packageConstituentMap.value) {
      if (selectedUpgradeIds.value.has(pkgId)) {
        const pkgName = measures.value.find(m => m.upgrade_id === pkgId)?.name ?? 'a package'
        for (const cid of constituents) {
          map.set(cid, pkgName)
        }
      }
    }
    return map
  })

  // --- Projected EUI (computed client-side) ---
  const projectedEui = computed<ProjectedEui | null>(() => {
    if (!baseline.value || selectedUpgradeIds.value.size === 0) return null

    const baseByFuel = baseline.value.eui_by_fuel
    let elec = baseByFuel.electricity
    let gas = baseByFuel.natural_gas
    let oil = baseByFuel.fuel_oil
    let propane = baseByFuel.propane
    let district = baseByFuel.district_heating

    for (const uid of selectedUpgradeIds.value) {
      const m = measures.value.find(m => m.upgrade_id === uid)
      if (!m?.savings_by_fuel) continue
      elec -= m.savings_by_fuel.electricity
      gas -= m.savings_by_fuel.natural_gas
      oil -= m.savings_by_fuel.fuel_oil
      propane -= m.savings_by_fuel.propane
      district -= m.savings_by_fuel.district_heating
    }

    // Floor at zero
    elec = Math.max(0, elec)
    gas = Math.max(0, gas)
    oil = Math.max(0, oil)
    propane = Math.max(0, propane)
    district = Math.max(0, district)

    const total = elec + gas + oil + propane + district
    const baseTotal = baseline.value.total_eui_kbtu_sf
    const reductionPct = baseTotal > 0 ? ((baseTotal - total) / baseTotal) * 100 : 0

    return {
      total_eui_kbtu_sf: total,
      eui_by_fuel: { electricity: elec, natural_gas: gas, fuel_oil: oil, propane, district_heating: district },
      reduction_pct: reductionPct,
    }
  })

  // --- Toggle measure selection ---
  function toggleMeasure(upgradeId: number): { action: 'selected' | 'deselected' | 'replace'; replaced?: number[] } | null {
    // Don't allow selecting disabled measures
    if (disabledByPackage.value.has(upgradeId)) return null

    const newSet = new Set(selectedUpgradeIds.value)

    if (newSet.has(upgradeId)) {
      // Deselect
      newSet.delete(upgradeId)
      selectedUpgradeIds.value = newSet
      // Clear projected score (selections changed)
      projectedEspm.value = null
      _saveSelections()
      // If deselecting empties the set, clear projected ESPM from DB too
      if (newSet.size === 0) {
        _clearProjectedEspm()
      }
      return { action: 'deselected' }
    }

    // Check if this is a package that conflicts with selected individuals
    const constituents = packageConstituentMap.value.get(upgradeId)
    if (constituents) {
      const overlapping = constituents.filter(cid => newSet.has(cid))
      if (overlapping.length > 0) {
        // Auto-replace: remove overlapping individuals, add package
        for (const cid of overlapping) {
          newSet.delete(cid)
        }
        newSet.add(upgradeId)
        selectedUpgradeIds.value = newSet
        projectedEspm.value = null
        _saveSelections()
        return { action: 'replace', replaced: overlapping }
      }
    }

    // Normal select
    newSet.add(upgradeId)
    selectedUpgradeIds.value = newSet
    projectedEspm.value = null
    _saveSelections()
    return { action: 'selected' }
  }

  // --- Persistence ---
  async function _saveSelections() {
    if (!buildingId.value) return
    try {
      await fetch(
        `${API_BASE}/projects/0/buildings/${buildingId.value}/selections`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            selected_upgrade_ids: Array.from(selectedUpgradeIds.value),
          }),
        },
      )
    } catch {
      // Optimistic update — selection already applied in UI.
      // On failure, we could revert, but for now just log.
      console.error('Failed to save selections')
    }
  }

  async function _clearProjectedEspm() {
    if (!buildingId.value) return
    try {
      await fetch(
        `${API_BASE}/projects/0/buildings/${buildingId.value}/selections/projected-espm`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ projected_espm: null }),
        },
      )
    } catch {
      console.error('Failed to clear projected ESPM')
    }
  }

  async function loadSelections() {
    if (!buildingId.value) return
    try {
      const resp = await fetch(
        `${API_BASE}/projects/0/buildings/${buildingId.value}/selections`,
      )
      if (resp.ok) {
        const data = await resp.json()
        selectedUpgradeIds.value = new Set(data.selected_upgrade_ids ?? [])
        projectedEspm.value = data.projected_espm ?? null
        initialized.value = true
      }
    } catch {
      console.error('Failed to load selections')
    }
  }

  // --- Reconcile stale selections ---
  function reconcileSelections() {
    const validIds = new Set(
      measures.value.filter(m => m.applicable).map(m => m.upgrade_id)
    )
    const current = selectedUpgradeIds.value
    const reconciled = new Set<number>()
    let changed = false
    for (const id of current) {
      if (validIds.has(id)) {
        reconciled.add(id)
      } else {
        changed = true
      }
    }
    if (changed) {
      selectedUpgradeIds.value = reconciled
      _saveSelections()
    }
  }

  // --- Calculate projected ENERGY STAR score ---
  async function calculateProjectedScore() {
    if (!building.value || !projectedEui.value) return
    projectedLoading.value = true
    projectedError.value = null
    try {
      const resp = await fetch(`${API_BASE}/energy-star/projected-score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          building: building.value,
          projected_eui_by_fuel: projectedEui.value.eui_by_fuel,
          address: address.value,
        }),
      })
      if (!resp.ok) {
        const detail = await resp.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${resp.status}`)
      }
      const espmResult = await resp.json()
      projectedEspm.value = espmResult
      // Save projected score to DB via dedicated endpoint
      if (buildingId.value) {
        await fetch(
          `${API_BASE}/projects/0/buildings/${buildingId.value}/selections/projected-espm`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ projected_espm: espmResult }),
          },
        )
      }
    } catch (e) {
      projectedError.value = (e as Error).message
    } finally {
      projectedLoading.value = false
    }
  }

  return {
    selectedUpgradeIds,
    packageConstituentMap,
    disabledByPackage,
    projectedEui,
    projectedEspm,
    projectedLoading,
    projectedError,
    toggleMeasure,
    loadSelections,
    reconcileSelections,
    calculateProjectedScore,
    initialized,
  }
}
```

- [ ] **Step 3: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useMeasureSelections.ts
git commit -m "feat: add useMeasureSelections composable with selection state and projected score"
```

---

## Task 8: Add checkbox column to MeasuresTable.vue

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue`

This task adds the selection checkbox as the first sticky column, with package lockout and disabled state. The auto-replace confirmation is handled by the composable — the table just calls `toggleMeasure` and reacts to the return value.

- [ ] **Step 1: Add new props and emit**

In `MeasuresTable.vue` `<script setup>`, update the props and add emit:

```typescript
import { PCheckbox } from '@partnerdevops/partner-components'  // add to imports

const props = defineProps<{
  measures: MeasureResult[]
  sqft: number
  selectedUpgradeIds?: Set<number>
  disabledByPackage?: Map<number, string>
}>()

const emit = defineEmits<{
  'toggle-measure': [upgradeId: number]
}>()
```

- [ ] **Step 2: Add checkbox column to Individual Measures table header**

In the Individual Measures `<PTableHeader>`, add a new `<PTableHead>` as the first column:

```html
<PTableHead class="measures-th measures-th--checkbox">
  <!-- Empty header for checkbox column -->
</PTableHead>
```

- [ ] **Step 3: Add checkbox cell to Individual Measures rows**

In the Individual Measures `<PTableRow v-for>`, add as the first cell:

```html
<PTableCell class="measures-cell measures-cell--checkbox">
  <PCheckbox
    v-if="!disabledByPackage?.has(m.upgrade_id)"
    :model-value="selectedUpgradeIds?.has(m.upgrade_id) ?? false"
    @update:model-value="emit('toggle-measure', m.upgrade_id)"
    size="small"
  />
  <PTooltip v-else direction="top">
    <template #tooltip-trigger>
      <PCheckbox :model-value="false" disabled size="small" />
    </template>
    <template #tooltip-content>
      Included in {{ disabledByPackage?.get(m.upgrade_id) }}
    </template>
  </PTooltip>
</PTableCell>
```

- [ ] **Step 4: Add checkbox column to Packages table**

Same pattern as Individual Measures — add checkbox header and cells to the Packages table section. No disabled state needed for packages.

- [ ] **Step 5: Add sticky CSS for checkbox column**

Update sticky column offsets. The checkbox column is first (left: 0), Measure name shifts to ~40px, Category shifts accordingly:

```css
.measures-th--checkbox,
.measures-cell--checkbox {
  width: 40px;
  min-width: 40px;
  max-width: 40px;
  position: sticky;
  left: 0;
  z-index: 11;
  background-color: inherit;
  text-align: center;
}

/* Shift existing sticky columns right by checkbox width */
.measures-th--name,
.measures-cell--name {
  left: 40px;  /* was 0 */
}

.measures-th--category,
.measures-cell--category {
  left: 260px;  /* was 220px */
}
```

- [ ] **Step 6: Add one empty cell to non-applicable rows**

Non-applicable rows need an extra empty cell at the start to keep column alignment:

```html
<PTableCell class="measures-cell measures-cell--checkbox" />
```

- [ ] **Step 7: Run type check and dev server**

Run: `cd frontend && npm run type-check`
Run: `cd frontend && npm run dev` (visually verify checkbox column appears)
Expected: PASS, checkboxes visible and sticky

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add selection checkboxes to measures table with package lockout"
```

---

## Task 9: Expand EnergyStarScore.vue to four-state split layout

**Files:**
- Modify: `frontend/src/components/EnergyStarScore.vue`

This is the largest UI change. The component transitions from a single trigger/result card to a full-width split layout with four states.

- [ ] **Step 1: Update props**

```typescript
const props = defineProps<{
  building: BuildingInput
  baseline: BaselineResult
  address?: string | null
  selectedCount?: number
  projectedEui?: ProjectedEui | null
  projectedEspm?: EnergyStarResponse | null
  projectedLoading?: boolean
  projectedError?: string | null
}>()

const emit = defineEmits<{
  'calculate-projected': []
}>()
```

- [ ] **Step 2: Add computed state detection**

```typescript
type ScoreState = 'trigger' | 'baseline-only' | 'measures-selected' | 'projected'

const scoreState = computed<ScoreState>(() => {
  if (!result.value) return 'trigger'
  if (props.projectedEspm) return 'projected'
  if ((props.selectedCount ?? 0) > 0) return 'measures-selected'
  return 'baseline-only'
})
```

- [ ] **Step 3: Add score color function using Partner tokens**

Replace the existing hardcoded colors with Partner design system tokens:

```typescript
function scoreColor(score: number | null): string {
  if (score == null) return 'var(--partner-gray-5)'
  if (score >= 75) return 'var(--partner-green-7)'
  if (score >= 50) return 'var(--partner-yellow-7)'
  return 'var(--partner-orange-7)'
}

function scoreDasharray(score: number | null): string {
  if (score == null) return '0 314'
  return `${(score / 100) * 314} 314`
}
```

- [ ] **Step 4: Rewrite template for four states**

Replace the entire `<template>` section. The key structure:

```html
<template>
  <div class="es-section">
    <!-- State 1: Trigger (no baseline score) -->
    <button v-if="scoreState === 'trigger'" class="es-trigger" @click="handleClick">
      <!-- existing trigger button markup -->
    </button>

    <!-- Loading state for baseline -->
    <div v-else-if="loading" class="es-card es-card--loading">...</div>

    <!-- Error state for baseline -->
    <div v-else-if="error" class="es-card es-card--error">...</div>

    <!-- States 2-4: Split layout -->
    <div v-else-if="result" class="es-card es-split">
      <!-- LEFT HALF: Baseline -->
      <div class="es-half">
        <div class="es-gauge"><!-- baseline gauge SVG --></div>
        <div class="es-metrics"><!-- baseline metrics --></div>
      </div>

      <!-- DIVIDER (with arrow in state 4) -->
      <div v-if="scoreState === 'projected'" class="es-arrow-divider">...</div>
      <div v-else class="es-divider"></div>

      <!-- RIGHT HALF: depends on state -->
      <!-- State 2: empty -->
      <div v-if="scoreState === 'baseline-only'" class="es-empty">
        <p>Select upgrades below to calculate your post-retrofit ENERGY STAR score</p>
      </div>

      <!-- State 3: measures selected -->
      <div v-else-if="scoreState === 'measures-selected'" class="es-ready">
        <p>{{ selectedCount }} upgrades selected</p>
        <p>Projected EUI: {{ projectedEui?.total_eui_kbtu_sf?.toFixed(1) }} kBtu/sf (-{{ projectedEui?.reduction_pct?.toFixed(1) }}%)</p>
        <button @click="emit('calculate-projected')">Calculate Projected Score</button>
      </div>

      <!-- State 3 loading -->
      <div v-else-if="projectedLoading" class="es-ready">
        <div class="es-loading-spinner">...</div>
        <p>Calculating projected score...</p>
      </div>

      <!-- State 3 error -->
      <div v-else-if="projectedError" class="es-ready">
        <p class="es-error-text">{{ projectedError }}</p>
        <button @click="emit('calculate-projected')">Retry</button>
      </div>

      <!-- State 4: projected score -->
      <div v-else-if="scoreState === 'projected'" class="es-half es-half--projected">
        <div class="es-gauge"><!-- projected gauge SVG --></div>
        <div class="es-metrics"><!-- projected metrics --></div>
        <button @click="emit('calculate-projected')">Recalculate</button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 5: Add split layout CSS**

Add the CSS from the mockup using Partner design tokens. Key classes: `.es-split`, `.es-half`, `.es-divider`, `.es-arrow-divider`, `.es-empty`, `.es-ready`, `.es-half--projected`, `.es-gauge` (with proper centering). Use `var(--radius)` for border-radius, Partner color vars for all colors.

- [ ] **Step 6: Update baseline gauge label**

The baseline gauge caption changes based on state:
- States 1-2: "ENERGY STAR Score"
- States 3-4: "Baseline Score"

```typescript
const baselineLabel = computed(() =>
  scoreState.value === 'trigger' || scoreState.value === 'baseline-only'
    ? 'ENERGY STAR\u00AE Score'
    : 'Baseline Score'
)
```

- [ ] **Step 7: Run type check and visual verification**

Run: `cd frontend && npm run type-check`
Run: `cd frontend && npm run dev` (check all four states render correctly)
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/EnergyStarScore.vue
git commit -m "feat: expand ENERGY STAR card to four-state split layout with projected score"
```

---

## Task 10: Wire up parent components (AssessmentView + SavedAssessmentView)

**Files:**
- Modify: `frontend/src/views/AssessmentView.vue`
- Modify: `frontend/src/components/SavedAssessmentView.vue`

- [ ] **Step 1: Wire up AssessmentView.vue**

Import and instantiate `useMeasureSelections`:

```typescript
import { useMeasureSelections } from '../composables/useMeasureSelections'

// After existing refs, add:
const measuresRef = computed(() => result.value?.measures ?? [])
const baselineRef = computed(() => result.value?.baseline ?? null)
const buildingIdRef = ref<number | null>(null)  // set after building is created/saved
const addressRef = computed(() => lastAddress.value || null)

const {
  selectedUpgradeIds,
  disabledByPackage,
  projectedEui,
  projectedEspm,
  projectedLoading,
  projectedError,
  toggleMeasure,
  loadSelections,
  reconcileSelections,
  calculateProjectedScore,
} = useMeasureSelections(measuresRef, baselineRef, lastBuilding, buildingIdRef, addressRef)
```

Pass new props to `EnergyStarScore` and `MeasuresTable`:

```html
<EnergyStarScore
  :building="lastBuilding"
  :baseline="result.baseline"
  :address="lastAddress"
  :selected-count="selectedUpgradeIds.size"
  :projected-eui="projectedEui"
  :projected-espm="projectedEspm"
  :projected-loading="projectedLoading"
  :projected-error="projectedError"
  @calculate-projected="calculateProjectedScore"
/>

<MeasuresTable
  :measures="result.measures"
  :sqft="lastSqft"
  :selected-upgrade-ids="selectedUpgradeIds"
  :disabled-by-package="disabledByPackage"
  @toggle-measure="toggleMeasure"
/>
```

- [ ] **Step 2: Wire up SavedAssessmentView.vue**

Same pattern — import composable, create refs from props, pass to child components. The `buildingId` comes from `props.building.id`.

- [ ] **Step 3: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 4: Run dev server and test full flow**

Run: `cd frontend && npm run dev`
Test manually:
1. Run an assessment
2. Calculate baseline ENERGY STAR score → split layout appears
3. Select measures via checkboxes → right half shows projected EUI
4. Click "Calculate Projected Score" → projected gauge appears
5. Select a package → constituent individual measures gray out
6. Deselect all → reverts to instructional text

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/AssessmentView.vue frontend/src/components/SavedAssessmentView.vue
git commit -m "feat: wire up measure selections to parent views"
```

---

## Task 11: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `cd backend && pytest --timeout=120 -q`
Expected: All PASS

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git commit -m "chore: cleanup after measure selection feature integration"
```
