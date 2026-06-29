# Carbon Performance Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Export button to the REAC measures results that downloads a filled SiteLynx Carbon Performance import workbook.

**Architecture:** A new backend endpoint re-runs the single-building assessment (to access per-fuel utility rates), fills the `.xlsx` template with openpyxl, and streams it back. The frontend `MeasuresTable` emits an `export` event; `AssessmentView` posts the request and triggers a browser download. No public API schema changes; only scalar cell values are written so the template's reference-table named ranges stay intact.

**Tech Stack:** FastAPI, Pydantic v2, openpyxl, pytest (backend); Vue 3 Composition API, partner-components, Vite (frontend).

## Global Constraints

- Branch `feat/carbon-performance-export` off **`main`** (post azure-migration merge). Create it before the first edit.
- Do not modify the template's structure, formulas, named ranges, or helper columns (AM/AN). Write scalar values only.
- Backend service layer stays FastAPI-decoupled (no Request/Response objects in services); absolute `app.xxx` imports only.
- Measure rows start at row 6, max 30 rows. Baseline metric values go in column AJ.
- Frontend additions use partner-components (`PButton`, `PIcon` with Carbon icon `download`). No raw HTML buttons or non-library icons.
- Energy unit constants live in `app/constants.py`: `KWH_TO_KBTU = 3.412`, `KWH_PER_THERM = 29.31`.
- AJ32 value is exactly `"NREL Cambium, 2022"`.

---

### Task 1: Energy constant + eGRID subregion lookup

**Files:**
- Modify: `backend/app/constants.py`
- Modify: `backend/app/services/preprocessor.py` (`_ZipcodeLookup` class ~959, module functions ~990)
- Test: `backend/tests/test_preprocessor.py`

**Interfaces:**
- Produces: `app.constants.KBTU_PER_THERM` (float, 100.0); `app.services.preprocessor.get_egrid_subregion(zipcode: str) -> str | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_preprocessor.py  (add)
from app.services.preprocessor import get_egrid_subregion
from app.constants import KBTU_PER_THERM


def test_kbtu_per_therm_constant():
    assert KBTU_PER_THERM == 100.0


def test_get_egrid_subregion_known_zip():
    # prefix 005 -> NYLI in zipcode_lookup.json
    assert get_egrid_subregion("00501") == "NYLI"


def test_get_egrid_subregion_unknown_zip():
    assert get_egrid_subregion("99999") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_preprocessor.py::test_get_egrid_subregion_known_zip -v`
Expected: FAIL with `ImportError: cannot import name 'get_egrid_subregion'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/constants.py  (add near KWH_PER_THERM)
KBTU_PER_THERM = 100.0          # 1 therm = 100 kBtu (= KWH_PER_THERM * KWH_TO_KBTU)
```

```python
# backend/app/services/preprocessor.py
# Add method inside _ZipcodeLookup (after get_emission_factor):
    def get_egrid_subregion(self, zipcode: str) -> str | None:
        """Return the eGRID subregion code (e.g. 'NYLI') for a zipcode, or None."""
        if self._prefixes is None:
            self._load()
        assert self._prefixes is not None
        entry = self._prefixes.get(zipcode[:3])
        if entry is not None:
            return entry.get("egrid_subregion")
        return None

# Add module-level function (after get_electricity_emission_factor):
def get_egrid_subregion(zipcode: str) -> str | None:
    """Return the eGRID subregion code for a zipcode."""
    return _zip_lookup.get_egrid_subregion(zipcode)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_preprocessor.py -k "egrid or kbtu_per_therm" -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/constants.py backend/app/services/preprocessor.py backend/tests/test_preprocessor.py
git commit -m "feat: add KBTU_PER_THERM constant and eGRID subregion lookup"
```

---

### Task 2: Expose utility rates from the assessment pipeline

**Files:**
- Modify: `backend/app/services/assessment.py` (`_assess_single` ~271-582, `assess_buildings` ~589-602)
- Test: `backend/tests/test_assessment.py` (create if absent)

**Interfaces:**
- Consumes: existing `_assess_single(building, index, model_manager, cost_calculator, imputation_service=None)`.
- Produces: `_assess_single(...) -> tuple[BuildingResult, dict]` (result, per-fuel rates `$/kWh`); new public `assess_building_for_export(building, model_manager, cost_calculator, imputation_service=None) -> tuple[BuildingResult, dict]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_assessment.py
from app.services.assessment import assess_building_for_export


def test_assess_building_for_export_returns_result_and_rates(
    office_input, model_manager, cost_calculator
):
    result, rates = assess_building_for_export(
        office_input, model_manager, cost_calculator
    )
    assert result.baseline.eui_by_fuel.electricity > 0
    assert isinstance(rates, dict)
    assert rates.get("electricity", 0) > 0
```

(If `model_manager` / `cost_calculator` fixtures do not exist in `conftest.py`, add them mirroring how `app.state` builds them in `backend/app/main.py`; reuse the same constructor calls.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_assessment.py::test_assess_building_for_export_returns_result_and_rates -v`
Expected: FAIL with `ImportError: cannot import name 'assess_building_for_export'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/assessment.py
# 1. Change _assess_single signature/return:
def _assess_single(
    building: BuildingInput,
    index: int,
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service=None,
) -> tuple[BuildingResult, dict]:
    """Run the full assessment pipeline for one building. Returns (result, rates)."""
    ...  # body unchanged through the existing `return BuildingResult(...)`

# 2. Replace the final `return BuildingResult(...)` (~line 552) with:
    result = BuildingResult(
        ...  # unchanged kwargs
    )
    return result, rates

# 3. Update assess_buildings (~line 598) to unpack:
        result, _rates = _assess_single(
            building, i, model_manager, cost_calculator, imputation_service
        )
        results.append(result)

# 4. Add public wrapper after assess_buildings:
def assess_building_for_export(
    building: BuildingInput,
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service=None,
) -> tuple[BuildingResult, dict]:
    """Assess a single building and also return the per-fuel utility rates ($/kWh)."""
    return _assess_single(building, 0, model_manager, cost_calculator, imputation_service)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_assessment.py -v && pytest tests/ -k assess -q`
Expected: PASS, and the existing `/assess` tests still pass (regression check on the unpack change).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assessment.py backend/tests/test_assessment.py backend/tests/conftest.py
git commit -m "feat: expose per-fuel utility rates via assess_building_for_export"
```

---

### Task 3: Export service + template asset + dependency

**Files:**
- Create: `backend/app/data/templates/sitelynx_carbon_performance_import.xlsx` (copy of the workbook)
- Create: `backend/app/services/export_service.py`
- Modify: `backend/requirements.txt` (add `openpyxl`)
- Test: `backend/tests/test_export_service.py`

**Interfaces:**
- Consumes: `assess_building_for_export` (Task 2); `get_egrid_subregion`, `KBTU_PER_THERM` (Task 1); `KWH_TO_KBTU`, `KWH_PER_THERM`.
- Produces: `build_carbon_performance_workbook(building, selected_upgrade_ids, model_manager, cost_calculator, imputation_service=None, espm_property_type=None) -> bytes`.

- [ ] **Step 1: Copy the template asset**

```bash
mkdir -p "backend/app/data/templates"
cp "sitelynx_carbon_performance_import.xlsx" "backend/app/data/templates/sitelynx_carbon_performance_import.xlsx"
```

- [ ] **Step 2: Add the dependency**

Add `openpyxl` to `backend/requirements.txt`, then `cd backend && pip install -r requirements.txt`.

- [ ] **Step 3: Write the failing test**

```python
# backend/tests/test_export_service.py
import io
import openpyxl
from app.schemas.response import (
    BuildingResult, BaselineResult, FuelBreakdown, MeasureResult,
    CostEstimate, InputSummary,
)
from app.services import export_service


def _fake_result():
    baseline = BaselineResult(
        total_eui_kbtu_sf=100.0,
        eui_by_fuel=FuelBreakdown(
            electricity=34.12, natural_gas=50.0, fuel_oil=0.0, propane=0.0,
        ),
    )
    measure = MeasureResult(
        upgrade_id=7, name="LED Lighting", category="lighting", applicable=True,
        cost=CostEstimate(
            installed_cost_per_sf=2.0, installed_cost_total=100000.0,
            cost_range={"low": 90000.0, "high": 110000.0}, useful_life_years=15,
            regional_factor=1.0, confidence="high",
        ),
        electricity_savings_kwh=1.0,      # kWh/sf
        gas_savings_therms=0.1,           # therms/sf
        savings_by_fuel=FuelBreakdown(
            electricity=3.412, natural_gas=2.931, fuel_oil=0.0, propane=0.0,
        ),
    )
    summary = InputSummary(
        climate_zone="4A", cluster_name="x", state="NY",
        vintage_bucket="<1946", imputed_fields=[],
    )
    result = BuildingResult(building_index=0, baseline=baseline, measures=[measure], input_summary=summary)
    rates = {"electricity": 0.20, "natural_gas": 0.05}
    return result, rates


def test_build_workbook_fills_expected_cells(monkeypatch):
    from app.schemas.request import BuildingInput
    building = BuildingInput(building_type="Office", sqft=1000, num_stories=3, zipcode="00501", year_built=1985)
    monkeypatch.setattr(export_service, "assess_building_for_export", lambda *a, **k: _fake_result())
    monkeypatch.setattr(export_service, "get_egrid_subregion", lambda z: "NYLI")

    data = export_service.build_carbon_performance_workbook(
        building, [7], model_manager=None, cost_calculator=None, espm_property_type="Office",
    )
    ws = openpyxl.load_workbook(io.BytesIO(data))["Export BlueLynx"]

    # Measure row 6
    assert ws["C6"].value == "LED Lighting"
    assert ws["D6"].value == 100000.0
    assert ws["L6"].value == 1000           # 1.0 kWh/sf * 1000 sf
    assert ws["H6"].value == 200.0          # 1000 kWh * $0.20
    assert ws["M6"].value == 100.0          # 0.1 therms/sf * 1000 sf
    # I6 = 100 therms * 29.31 kWh/therm * $0.05
    assert round(ws["I6"].value, 0) == 147

    # Baseline metrics
    assert ws["AJ8"].value == "00501"
    assert ws["AJ9"].value == "Office"
    assert ws["AJ11"].value == "NY"
    assert ws["AJ14"].value == "NYLI"
    assert ws["AJ15"].value == "4A"
    assert ws["AJ16"].value == 10000        # 34.12/3.412*1000
    assert ws["AJ17"].value == 2000.0       # 10000 kWh * $0.20
    assert ws["AJ20"].value == 500.0        # 50.0/100*1000
    assert ws["AJ24"].value == 1000
    assert ws["AJ32"].value == "NREL Cambium, 2022"


def test_named_ranges_survive(monkeypatch):
    from app.schemas.request import BuildingInput
    building = BuildingInput(building_type="Office", sqft=1000, num_stories=3, zipcode="00501", year_built=1985)
    monkeypatch.setattr(export_service, "assess_building_for_export", lambda *a, **k: _fake_result())
    monkeypatch.setattr(export_service, "get_egrid_subregion", lambda z: "NYLI")
    data = export_service.build_carbon_performance_workbook(
        building, [7], model_manager=None, cost_calculator=None,
    )
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert "Export BlueLynx" in wb.sheetnames
    assert "ESPM_Prop_Types" in wb.defined_names      # reference-table range preserved


def test_fallback_to_applicable_when_no_selection(monkeypatch):
    from app.schemas.request import BuildingInput
    building = BuildingInput(building_type="Office", sqft=1000, num_stories=3, zipcode="00501", year_built=1985)
    monkeypatch.setattr(export_service, "assess_building_for_export", lambda *a, **k: _fake_result())
    monkeypatch.setattr(export_service, "get_egrid_subregion", lambda z: "NYLI")
    data = export_service.build_carbon_performance_workbook(
        building, [], model_manager=None, cost_calculator=None,
    )
    ws = openpyxl.load_workbook(io.BytesIO(data))["Export BlueLynx"]
    assert ws["C6"].value == "LED Lighting"   # applicable measure used as fallback
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_export_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.export_service'`

- [ ] **Step 5: Write minimal implementation**

```python
# backend/app/services/export_service.py
import io
from pathlib import Path

import openpyxl

from app.constants import KWH_TO_KBTU, KWH_PER_THERM, KBTU_PER_THERM
from app.schemas.request import BuildingInput
from app.services.assessment import assess_building_for_export
from app.services.preprocessor import get_egrid_subregion

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "templates"
    / "sitelynx_carbon_performance_import.xlsx"
)
SHEET_NAME = "Export BlueLynx"
FIRST_MEASURE_ROW = 6
MAX_MEASURE_ROWS = 30
GRID_DECARB_MODEL = "NREL Cambium, 2022"


def _select_measures(measures, selected_upgrade_ids):
    """Checked measures, else fall back to applicable individual measures. Capped at 30."""
    selected_ids = set(selected_upgrade_ids or [])
    selected = [m for m in measures if m.upgrade_id in selected_ids]
    if not selected:
        selected = [m for m in measures if m.applicable and m.category != "package"]
    return selected[:MAX_MEASURE_ROWS]


def build_carbon_performance_workbook(
    building: BuildingInput,
    selected_upgrade_ids,
    model_manager,
    cost_calculator,
    imputation_service=None,
    espm_property_type=None,
) -> bytes:
    result, rates = assess_building_for_export(
        building, model_manager, cost_calculator, imputation_service
    )
    sqft = building.sqft
    rate_elec = rates.get("electricity", 0.0) or 0.0
    rate_gas = rates.get("natural_gas", 0.0) or 0.0

    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    ws = wb[SHEET_NAME]

    # --- Measure rows ---
    for i, m in enumerate(_select_measures(result.measures, selected_upgrade_ids)):
        r = FIRST_MEASURE_ROW + i
        ws[f"C{r}"] = m.name
        if m.cost is not None:
            ws[f"D{r}"] = m.cost.installed_cost_total
        if m.electricity_savings_kwh is not None:
            elec_kwh = m.electricity_savings_kwh * sqft
            ws[f"L{r}"] = round(elec_kwh, 0)
            if rate_elec:
                ws[f"H{r}"] = round(elec_kwh * rate_elec, 2)
        if m.gas_savings_therms is not None:
            gas_therms = m.gas_savings_therms * sqft
            ws[f"M{r}"] = round(gas_therms, 1)
            if rate_gas:
                ws[f"I{r}"] = round(gas_therms * KWH_PER_THERM * rate_gas, 2)

    # --- Baseline metrics (column AJ) ---
    ws["AJ8"] = building.zipcode
    if espm_property_type:
        ws["AJ9"] = espm_property_type
    ws["AJ11"] = result.input_summary.state
    egrid = get_egrid_subregion(building.zipcode)
    if egrid:
        ws["AJ14"] = egrid
    ws["AJ15"] = result.input_summary.climate_zone

    elec_kbtu_sf = result.baseline.eui_by_fuel.electricity
    gas_kbtu_sf = result.baseline.eui_by_fuel.natural_gas
    base_elec_kwh = elec_kbtu_sf / KWH_TO_KBTU * sqft
    base_gas_therms = gas_kbtu_sf / KBTU_PER_THERM * sqft

    ws["AJ16"] = round(base_elec_kwh, 0)
    if rate_elec:
        ws["AJ17"] = round(base_elec_kwh * rate_elec, 2)
    ws["AJ20"] = round(base_gas_therms, 1)
    if rate_gas:
        base_gas_kwh = gas_kbtu_sf / KWH_TO_KBTU * sqft
        ws["AJ21"] = round(base_gas_kwh * rate_gas, 2)
    ws["AJ24"] = sqft
    ws["AJ32"] = GRID_DECARB_MODEL

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_export_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/export_service.py backend/app/data/templates/ backend/requirements.txt backend/tests/test_export_service.py
git commit -m "feat: add carbon performance workbook export service"
```

---

### Task 4: Export API endpoint

**Files:**
- Modify: `backend/app/api/routes.py` (imports ~1-18, add endpoint near `/assess`)
- Test: `backend/tests/test_routes_export.py`

**Interfaces:**
- Consumes: `build_carbon_performance_workbook` (Task 3); `app.state.model_manager`, `app.state.cost_calculator`, optional `app.state.imputation_service`.
- Produces: `POST /export/carbon-performance` with body `{building, selected_upgrade_ids, espm_property_type}` returning an `.xlsx` attachment.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes_export.py
from fastapi.testclient import TestClient
from app.main import app
from app.api import routes


def test_export_endpoint_returns_xlsx(monkeypatch):
    monkeypatch.setattr(routes, "build_carbon_performance_workbook", lambda *a, **k: b"PK\x03\x04fake")
    client = TestClient(app)
    payload = {
        "building": {"building_type": "Office", "sqft": 1000, "num_stories": 3,
                      "zipcode": "00501", "year_built": 1985},
        "selected_upgrade_ids": [7],
        "espm_property_type": "Office",
    }
    resp = client.post("/export/carbon-performance", json=payload)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "CarbonPerformance_00501.xlsx" in resp.headers["content-disposition"]
    assert resp.content == b"PK\x03\x04fake"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_routes_export.py -v`
Expected: FAIL (404 — route not registered)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/api/routes.py
# Add to imports:
from fastapi import APIRouter, Request, HTTPException, Response
from app.services.export_service import build_carbon_performance_workbook

# Add request model near the other BaseModel definitions:
class CarbonPerformanceExportRequest(BaseModel):
    building: BuildingInput
    selected_upgrade_ids: list[int] = []
    espm_property_type: Optional[str] = None

# Add endpoint after the /assess route:
@router.post("/export/carbon-performance")
async def export_carbon_performance(request: CarbonPerformanceExportRequest, req: Request):
    model_manager = req.app.state.model_manager
    cost_calculator = req.app.state.cost_calculator
    imputation_service = getattr(req.app.state, "imputation_service", None)
    try:
        data = build_carbon_performance_workbook(
            request.building,
            request.selected_upgrade_ids,
            model_manager,
            cost_calculator,
            imputation_service,
            espm_property_type=request.espm_property_type,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Export template not found")
    filename = f"CarbonPerformance_{request.building.zipcode}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_routes_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes.py backend/tests/test_routes_export.py
git commit -m "feat: add POST /export/carbon-performance endpoint"
```

---

### Task 5: Export button in MeasuresTable

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue` (props ~18-24, emits ~26, header ~211-231)

**Interfaces:**
- Consumes: parent passes `:exporting` (Boolean).
- Produces: emits `export` event (no payload).

- [ ] **Step 1: Add prop, emit, and button**

```javascript
// props block (add):
  exporting: { type: Boolean, default: false },

// emits (replace line 26):
const emit = defineEmits(['toggle-measure', 'export'])
```

```html
<!-- In .measures-header, after the .measures-summary div, before closing </div> -->
<PButton
  variant="primary"
  appearance="outline"
  size="small"
  icon="download"
  :loading="exporting"
  :disabled="exporting"
  class="measures-header__export"
  @click="emit('export')"
>
  Export to Carbon Performance
</PButton>
```

```css
/* add to <style scoped> */
.measures-header__export {
  margin-top: 0.5rem;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS (no new errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add export button to measures table header"
```

---

### Task 6: Surface ESPM property type from EnergyStarScore

**Files:**
- Modify: `frontend/src/components/EnergyStarScore.vue` (script setup ~1-22)

**Interfaces:**
- Consumes: existing `useEnergyStarScore()` `result` ref (has `espm_property_type`).
- Produces: emits `espm-loaded` with the property-type string when the score result arrives.

- [ ] **Step 1: Add the emit and watcher**

```javascript
// ensure `watch` is imported from 'vue'
import { computed, watch } from 'vue'

// replace the emits line:
const emit = defineEmits(['calculate-projected', 'espm-loaded'])

// after `const { loading, error, result, fetchScore } = useEnergyStarScore()`:
watch(result, (r) => {
  if (r?.espm_property_type) emit('espm-loaded', r.espm_property_type)
}, { immediate: true })
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EnergyStarScore.vue
git commit -m "feat: emit ESPM property type from EnergyStarScore"
```

---

### Task 7: Wire export in useAssessment + AssessmentView

**Files:**
- Modify: `frontend/src/composables/useAssessment.js`
- Modify: `frontend/src/views/AssessmentView.vue` (script ~14, ~17-27; template ~178-201)

**Interfaces:**
- Consumes: `POST /export/carbon-performance`; `lastBuilding`, `selectedUpgradeIds`, captured ESPM type.
- Produces: `useAssessment()` returns `exporting` (ref) and `exportCarbonPerformance(building, selectedUpgradeIds, espmPropertyType)`.

- [ ] **Step 1: Add export function to the composable**

```javascript
// frontend/src/composables/useAssessment.js
// add inside useAssessment(), alongside loading/error/result:
  const exporting = ref(false)

  async function exportCarbonPerformance(building, selectedUpgradeIds, espmPropertyType) {
    exporting.value = true
    error.value = null
    try {
      const response = await fetch(`${API_BASE}/export/carbon-performance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          building,
          selected_upgrade_ids: selectedUpgradeIds,
          espm_property_type: espmPropertyType ?? null,
        }),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CarbonPerformance_${building.zipcode}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      error.value = e.message
    } finally {
      exporting.value = false
    }
  }

// update the return statement:
  return { loading, error, result, assess, reset, exporting, exportCarbonPerformance }
```

- [ ] **Step 2: Wire AssessmentView**

```javascript
// line 14 — pull the new members:
const { loading, error, result, assess, exporting, exportCarbonPerformance } = useAssessment()

// add a ref near lastBuilding (~line 18):
const espmPropertyType = ref(null)

// add a handler (near onSubmit):
function onExport() {
  if (!lastBuilding.value) return
  exportCarbonPerformance(
    lastBuilding.value,
    [...selectedUpgradeIds.value],
    espmPropertyType.value,
  )
}
```

```html
<!-- EnergyStarScore: add the listener -->
<EnergyStarScore
  ...
  @calculate-projected="calculateProjectedScore"
  @espm-loaded="espmPropertyType = $event"
/>

<!-- MeasuresTable: add export wiring -->
<MeasuresTable
  :measures="result.measures"
  :sqft="lastSqft"
  :selected-upgrade-ids="selectedUpgradeIds"
  :disabled-by-package="disabledByPackage"
  :replace-message="replaceMessage"
  :exporting="exporting"
  @toggle-measure="handleToggleMeasure"
  @export="onExport"
/>
```

- [ ] **Step 3: Type-check and build**

Run: `cd frontend && npm run type-check && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useAssessment.js frontend/src/views/AssessmentView.vue
git commit -m "feat: wire carbon performance export download in assessment view"
```

---

### Task 8: End-to-end verification

**Files:** none (manual + full suite)

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: PASS (no regressions; new export tests green).

- [ ] **Step 2: Manual smoke test**

Run backend (`uvicorn app.main:app --reload`) and frontend (`npm run dev`). Submit a building, wait for results and the ENERGY STAR panel, check a few measures, click "Export to Carbon Performance". Confirm a `CarbonPerformance_<zip>.xlsx` downloads.

- [ ] **Step 3: Open the file and verify**

Open the downloaded workbook. Confirm: checked measures appear from row 6 (C/D/H/I/L/M), baseline metrics populated in AJ8/AJ9/AJ11/AJ14/AJ15/AJ16/AJ17/AJ20/AJ21/AJ24/AJ32, and AJ6/AJ7/AJ10 retain their pre-filled values. Paste the sheet into the real Carbon Performance calculator and confirm formulas resolve and AJ9 / AJ32 match the calculator's dropdowns (adjust the exact strings if the dropdown labels differ).

- [ ] **Step 4: Commit any string fixups**

```bash
git add -A
git commit -m "fix: align export dropdown values with carbon performance calculator"
```

---

## Self-Review

**Spec coverage:** Measure mapping (C/D/H/I/L/M) → Task 3 + verified Task 8; baseline AJ mapping → Task 3; backend openpyxl endpoint → Tasks 3-4; rates without schema change → Task 2; eGRID subregion → Task 1; button in measures header with `download` icon → Task 5; ESPM from frontend → Tasks 6-7; download UX + loading/error → Task 7; edge cases (no selection fallback, 30-cap, missing rate/fuel, zip miss, missing template) → Tasks 3-4 + tests. All spec sections map to a task.

**Placeholder scan:** No TBD/TODO; every code step contains complete code; commands have expected output.

**Type consistency:** `assess_building_for_export` returns `(BuildingResult, dict)` everywhere it appears (Tasks 2, 3); `build_carbon_performance_workbook` signature identical in Tasks 3 and 4; `exportCarbonPerformance(building, selectedUpgradeIds, espmPropertyType)` consistent across composable and AssessmentView; emit names `export` and `espm-loaded` consistent across emitter/listener.

**Note:** `SavedAssessmentView.vue` also renders `MeasuresTable`; exporting from saved assessments is out of scope for this plan and can follow the same pattern later.
