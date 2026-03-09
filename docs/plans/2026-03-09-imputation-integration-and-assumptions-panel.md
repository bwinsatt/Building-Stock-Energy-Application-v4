# Imputation Integration & Assumptions Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace static default imputation with ML-based imputation (XGBoost classifiers), make `year_built` required, and surface imputed values + confidence to users in a collapsible "Assumptions" panel.

**Architecture:** The `ImputationService` is already loaded at startup (`app.state.imputation_service`) but not wired into the assessment pipeline. We integrate it into the preprocessor, enrich `InputSummary` with imputed values+confidence, and add a frontend component to display them. The imputation models use building_type, climate_zone, vintage, sqft, num_stories, and state to predict 7 categorical fields (lighting_type, heating_fuel, etc.) with confidence scores.

**Tech Stack:** Python/FastAPI backend, XGBoost classifiers (already trained), Vue 3 + TypeScript + Tailwind CSS frontend, Partner Components UI library.

---

## Task 1: Make `year_built` Required

The imputation models depend heavily on vintage. Making it required ensures accurate predictions.

**Files:**
- Modify: `backend/app/schemas/request.py:9` (change year_built from Optional to required)
- Modify: `backend/app/services/preprocessor.py:689` (remove year_built from optional_fields list)
- Modify: `frontend/src/types/assessment.ts:6` (change year_built from optional to required)
- Modify: `frontend/src/components/BuildingForm.vue:25-30` (add year_built to initial form state)
- Test: `backend/tests/test_preprocessor.py`

**Step 1: Write failing test — year_built required**

Add to `backend/tests/test_preprocessor.py`:

```python
def test_year_built_required():
    """year_built is now required; omitting it should fail Pydantic validation."""
    with pytest.raises(Exception):
        BuildingInput(
            building_type="Office",
            sqft=10000,
            num_stories=2,
            zipcode="90210",
        )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_preprocessor.py::test_year_built_required -v`
Expected: FAIL — BuildingInput still accepts None for year_built.

**Step 3: Update the schema**

In `backend/app/schemas/request.py`, change:
```python
year_built: Optional[int] = None
```
to:
```python
year_built: int = Field(..., ge=1800, le=2030, description="Year the building was constructed")
```

**Step 4: Remove year_built from optional imputation list**

In `backend/app/services/preprocessor.py`, remove `"year_built"` from the `optional_fields` list (line ~689). Year built is now always provided and never imputed.

**Step 5: Fix existing tests that omit year_built**

Update `conftest.py` fixtures and any test that creates a `BuildingInput` without `year_built`:

- `minimal_input` fixture in `conftest.py`: add `year_built=1990`
- `mf_input` fixture in `conftest.py`: add `year_built=1985`
- `test_climate_zone_derivation`: add `year_built=1990`
- `test_state_derivation`: add `year_built=1990`
- `test_invalid_building_type`: add `year_built=1990`
- `test_invalid_zipcode_letters`: add `year_built=1990`
- Any other test creating BuildingInput without year_built — search for `BuildingInput(` across `backend/tests/`

**Step 6: Update frontend types and form**

In `frontend/src/types/assessment.ts`:
```typescript
year_built: number  // remove the ?
```

In `frontend/src/components/BuildingForm.vue`, update the form reactive:
```typescript
const form = reactive<BuildingInput>({
  building_type: '',
  sqft: 0,
  num_stories: 1,
  zipcode: '',
  year_built: undefined as unknown as number,  // required but starts empty for UX
})
```

Mark the Year Built field as required in the template (move it to the required section alongside building_type/sqft/stories/zipcode, add the red asterisk).

**Step 7: Run all backend tests**

Run: `cd backend && pytest`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add backend/app/schemas/request.py backend/app/services/preprocessor.py backend/tests/ frontend/src/types/assessment.ts frontend/src/components/BuildingForm.vue
git commit -m "feat: make year_built required for accurate imputation"
```

---

## Task 2: Enrich InputSummary with Imputed Details

Add the imputed values and confidence scores to the API response.

**Files:**
- Modify: `backend/app/schemas/response.py:42-47` (add imputed_details to InputSummary)
- Modify: `backend/app/services/preprocessor.py` (return imputed values, not just field names)
- Modify: `backend/app/services/assessment.py:254` (pass imputed_details to InputSummary)
- Test: `backend/tests/test_preprocessor.py`

**Step 1: Write failing test — preprocessor returns imputed values**

Add to `backend/tests/test_preprocessor.py`:

```python
def test_preprocess_returns_imputed_details():
    """Preprocessor should return dict of imputed field details, not just names."""
    inp = BuildingInput(
        building_type="Office",
        sqft=10000,
        num_stories=2,
        zipcode="90210",
        year_built=1990,
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(inp)
    # imputed_details is now a dict, not a list
    assert isinstance(imputed_details, dict)
    assert "heating_fuel" in imputed_details
    assert "value" in imputed_details["heating_fuel"]
    assert "label" in imputed_details["heating_fuel"]
    assert "source" in imputed_details["heating_fuel"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_preprocessor.py::test_preprocess_returns_imputed_details -v`
Expected: FAIL — preprocess returns a list, not a dict.

**Step 3: Add ImputedField to response schema**

In `backend/app/schemas/response.py`, add:

```python
class ImputedField(BaseModel):
    value: str
    label: str
    source: str  # "model" or "default"
    confidence: Optional[float] = None  # 0.0-1.0, only when source="model"
```

Update `InputSummary`:
```python
class InputSummary(BaseModel):
    climate_zone: str
    cluster_name: str
    state: str
    vintage_bucket: str
    imputed_fields: list[str]  # keep for backward compat
    imputed_details: dict[str, ImputedField]
```

**Step 4: Update preprocessor to accept and use imputation_service**

Change the `preprocess` function signature to optionally accept the imputation service:

```python
def preprocess(
    building_input: BuildingInput,
    imputation_service=None,
) -> tuple[dict, dict, str, str, str]:
```

Where the second return value changes from `list[str]` to `dict[str, dict]`.

Human-friendly labels for display:
```python
FIELD_LABELS = {
    "heating_fuel": "Heating Fuel",
    "dhw_fuel": "Domestic Hot Water Fuel",
    "hvac_system_type": "HVAC System Type",
    "wall_construction": "Wall Construction",
    "window_type": "Window Type",
    "window_to_wall_ratio": "Window-to-Wall Ratio",
    "lighting_type": "Lighting Type",
    "operating_hours": "Operating Hours (hrs/week)",
}
```

In the imputation loop (where `value is None`), instead of just appending field names:

```python
if imputation_service is not None and field in imputation_service.models:
    known = {
        "building_type": building_input.building_type,
        "climate_zone": climate_zone,
        "year_built": building_input.year_built,
        "sqft": building_input.sqft,
        "num_stories": building_input.num_stories,
        "state": state,
    }
    prediction = imputation_service.predict(known, fields_to_predict=[field])
    if prediction.get(field, {}).get("value") is not None:
        pred = prediction[field]
        resolved[field] = pred["value"]
        imputed_details[field] = {
            "value": str(pred["value"]),
            "label": FIELD_LABELS.get(field, field),
            "source": "model",
            "confidence": pred.get("confidence"),
        }
    else:
        # Fallback to static default
        default_val = bt_defaults.get(field, DEFAULT_FALLBACK.get(field))
        resolved[field] = default_val
        imputed_details[field] = {
            "value": str(default_val),
            "label": FIELD_LABELS.get(field, field),
            "source": "default",
            "confidence": None,
        }
else:
    # No imputation service or no model for this field — static default
    default_val = bt_defaults.get(field, DEFAULT_FALLBACK.get(field))
    resolved[field] = default_val
    imputed_details[field] = {
        "value": str(default_val),
        "label": FIELD_LABELS.get(field, field),
        "source": "default",
        "confidence": None,
    }
```

Return `imputed_details` dict instead of `imputed_fields` list.

**Step 5: Handle imputation model output → preprocessor value mapping**

Important: the imputation models predict values in **training-data format** (e.g., `"gen4_led"` for lighting). But the preprocessor's value mapping expects **user-facing values** (e.g., `"LED"`). We need a reverse map for display and to feed the correct value into `resolved[field]`.

Add reverse display maps:
```python
# Reverse map: training-data value → user-friendly display value
_COMSTOCK_DISPLAY_MAP = {
    "lighting_type": {
        "gen1_t12_incandescent": "T12",
        "gen2_t8_halogen": "T8",
        "gen3_t5_cfl": "CFL",
        "gen4_led": "LED",
        "gen5_led": "LED",
    },
    # For other fields the training values are close enough to display as-is
}
```

When the imputation model returns `"gen4_led"`, store the display value `"LED"` in `imputed_details[field]["value"]` and the user-facing value `"LED"` in `resolved[field]` (so the existing value mapping in step 6 of preprocess handles the rest).

For fields where training values match user-facing values (heating_fuel, wall_construction, etc.), no reverse mapping needed.

**Step 6: Update assessment.py to pass imputation_service**

In `backend/app/services/assessment.py`, update `_assess_single`:

```python
def _assess_single(
    building: BuildingInput,
    index: int,
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service=None,
) -> BuildingResult:
```

Pass it through to preprocess:
```python
features, imputed_details, dataset, climate_zone, state = preprocess(
    building, imputation_service=imputation_service
)
```

Update the InputSummary construction:
```python
input_summary=InputSummary(
    climate_zone=climate_zone,
    cluster_name=features.get("cluster_name", "Unknown"),
    state=state,
    vintage_bucket=features.get(
        "in.vintage",
        year_to_vintage(building.year_built, dataset)
    ),
    imputed_fields=list(imputed_details.keys()),
    imputed_details={
        k: ImputedField(**v) for k, v in imputed_details.items()
    },
)
```

Update `assess_buildings` and the route to pass `imputation_service`:
```python
def assess_buildings(
    buildings: list[BuildingInput],
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service=None,
) -> list[BuildingResult]:
```

In `backend/app/api/routes.py`, update the `/assess` endpoint:
```python
imputation_service = getattr(req.app.state, "imputation_service", None)
results = assess_buildings(
    request.buildings, model_manager, cost_calculator, imputation_service
)
```

**Step 7: Fix all existing tests that unpack preprocess()**

Any test doing `features, imputed_fields, dataset, ...` now gets a dict instead of a list for `imputed_fields`. Update:

- `test_valid_office_input`: imputed_fields is now a dict
- `test_valid_mf_input`: same
- `test_imputation_fills_missing`: check dict keys instead of list membership
- `test_no_imputation_when_all_provided`: check `imputed_details == {}`

**Step 8: Run all backend tests**

Run: `cd backend && pytest`
Expected: ALL PASS

**Step 9: Commit**

```bash
git add backend/app/schemas/response.py backend/app/services/preprocessor.py backend/app/services/assessment.py backend/app/api/routes.py backend/tests/
git commit -m "feat: integrate ML imputation into preprocessor and enrich response with imputed details"
```

---

## Task 3: Fix Applicability LED Check

While reviewing the code, I noticed the LED applicability check compares against `"LED"` but after value mapping the feature is `"gen4_led"`. This needs fixing so the LED upgrade exclusion actually works.

**Files:**
- Modify: `backend/app/inference/applicability.py:123`
- Test: `backend/tests/test_applicability.py` (create if needed)

**Step 1: Write failing test**

Create or add to `backend/tests/test_applicability.py`:

```python
from app.inference.applicability import check_applicability

def test_led_upgrade_skipped_when_gen4_led():
    """LED upgrades (43, 44) should be skipped when lighting is gen4_led (mapped value)."""
    features = {"in.interior_lighting_generation": "gen4_led"}
    assert check_applicability(43, "comstock", features, {43}) is False
    assert check_applicability(44, "comstock", features, {44}) is False

def test_led_upgrade_allowed_when_older_lighting():
    """LED upgrades should apply when lighting is T8/T12/CFL."""
    features = {"in.interior_lighting_generation": "gen2_t8_halogen"}
    assert check_applicability(43, "comstock", features, {43}) is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_applicability.py::test_led_upgrade_skipped_when_gen4_led -v`
Expected: FAIL — `"gen4_led" == "LED"` is False, so the check doesn't filter.

**Step 3: Fix the check**

In `backend/app/inference/applicability.py`, change line ~123:

```python
# Before:
if upgrade_id in _COMSTOCK_LED_UPGRADES and lighting == "LED":

# After:
_LED_VALUES = {"LED", "gen4_led", "gen5_led"}
if upgrade_id in _COMSTOCK_LED_UPGRADES and lighting in _LED_VALUES:
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: LED applicability check matches mapped feature values (gen4_led)"
```

---

## Task 4: Frontend TypeScript Types Update

Update the frontend types to match the new response schema.

**Files:**
- Modify: `frontend/src/types/assessment.ts:54-59`

**Step 1: Update types**

```typescript
export interface ImputedField {
  value: string
  label: string
  source: 'model' | 'default'
  confidence: number | null
}

export interface InputSummary {
  climate_zone: string
  cluster_name: string
  state: string
  vintage_bucket: string
  imputed_fields: string[]
  imputed_details: Record<string, ImputedField>
}
```

**Step 2: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS (the new fields are additive)

**Step 3: Commit**

```bash
git add frontend/src/types/assessment.ts
git commit -m "feat: add ImputedField type and update InputSummary for assumptions panel"
```

---

## Task 5: Build the Assumptions Panel Component

Create a collapsible panel that shows imputed values with confidence indicators.

**Files:**
- Create: `frontend/src/components/AssumptionsPanel.vue`
- Modify: `frontend/src/views/AssessmentView.vue` (add the component to the results section)

**Step 1: Create the component**

Create `frontend/src/components/AssumptionsPanel.vue`:

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { PTypography, PBadge, PButton, PTooltip } from '@partnerdevops/partner-components'
import type { InputSummary } from '../types/assessment'

const props = defineProps<{
  summary: InputSummary
}>()

const expanded = ref(false)

const hasImputedFields = computed(() =>
  Object.keys(props.summary.imputed_details).length > 0
)

const derivedFields = computed(() => [
  { label: 'Climate Zone', value: props.summary.climate_zone, source: 'zipcode' },
  { label: 'Region', value: props.summary.cluster_name, source: 'zipcode' },
  { label: 'State', value: props.summary.state, source: 'zipcode' },
  { label: 'Vintage Bucket', value: props.summary.vintage_bucket, source: 'year_built' },
])

function confidenceLabel(confidence: number | null): string {
  if (confidence == null) return 'default'
  if (confidence >= 0.7) return 'high'
  if (confidence >= 0.4) return 'medium'
  return 'low'
}

function confidencePercent(confidence: number | null): string {
  if (confidence == null) return ''
  return `${Math.round(confidence * 100)}%`
}
</script>

<template>
  <div class="assumptions-panel">
    <button
      class="assumptions-toggle"
      type="button"
      @click="expanded = !expanded"
    >
      <span class="assumptions-toggle__icon" :class="{ 'assumptions-toggle__icon--open': expanded }">
        &#9662;
      </span>
      <PTypography variant="subhead" component="span" class="assumptions-toggle__label">
        Assumptions Used
      </PTypography>
      <span v-if="hasImputedFields" class="assumptions-toggle__count">
        {{ Object.keys(summary.imputed_details).length }} imputed
      </span>
    </button>

    <div v-if="expanded" class="assumptions-content">
      <!-- Derived fields (always shown) -->
      <div class="assumptions-section">
        <div class="assumptions-section__title">Derived from Input</div>
        <div class="assumptions-grid">
          <div
            v-for="field in derivedFields"
            :key="field.label"
            class="assumptions-item"
          >
            <span class="assumptions-item__label">{{ field.label }}</span>
            <span class="assumptions-item__value">{{ field.value }}</span>
            <PBadge variant="primary" appearance="standard" size="small">
              {{ field.source }}
            </PBadge>
          </div>
        </div>
      </div>

      <!-- Imputed fields -->
      <div v-if="hasImputedFields" class="assumptions-section">
        <div class="assumptions-section__title">Estimated Values</div>
        <p class="assumptions-section__desc">
          These fields were not provided and were estimated using an ML model or building-type defaults.
        </p>
        <div class="assumptions-grid">
          <div
            v-for="(field, key) in summary.imputed_details"
            :key="key"
            class="assumptions-item"
          >
            <span class="assumptions-item__label">{{ field.label }}</span>
            <span class="assumptions-item__value">{{ field.value }}</span>
            <PTooltip v-if="field.confidence != null" direction="top">
              <template #tooltip-trigger>
                <PBadge
                  :variant="confidenceLabel(field.confidence) === 'high' ? 'success' : confidenceLabel(field.confidence) === 'medium' ? 'warning' : 'error'"
                  appearance="standard"
                  size="small"
                >
                  {{ confidencePercent(field.confidence) }} confidence
                </PBadge>
              </template>
              <template #tooltip-content>
                ML model prediction ({{ field.source }})
              </template>
            </PTooltip>
            <PBadge v-else variant="neutral" appearance="standard" size="small">
              default
            </PBadge>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.assumptions-panel {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  overflow: hidden;
}

.assumptions-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.75rem 1.25rem;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
}

.assumptions-toggle:hover {
  background: rgba(0, 0, 0, 0.02);
}

.assumptions-toggle__icon {
  display: inline-block;
  font-size: 0.625rem;
  color: #64748b;
  transition: transform 0.2s ease;
}

.assumptions-toggle__icon--open {
  transform: rotate(180deg);
}

.assumptions-toggle__label {
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
  color: #475569;
}

.assumptions-toggle__count {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  color: #94a3b8;
  margin-left: auto;
}

.assumptions-content {
  padding: 0 1.25rem 1.25rem;
}

.assumptions-section {
  padding-top: 0.75rem;
}

.assumptions-section + .assumptions-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.assumptions-section__title {
  font-family: var(--font-display);
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #8b95a1;
  margin-bottom: 0.5rem;
}

.assumptions-section__desc {
  font-size: 0.75rem;
  color: #94a3b8;
  margin: 0 0 0.75rem;
}

.assumptions-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
}

@media (min-width: 640px) {
  .assumptions-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.assumptions-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  background: var(--app-surface);
  border-radius: 4px;
}

.assumptions-item__label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: #64748b;
  min-width: 0;
  flex-shrink: 0;
}

.assumptions-item__value {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--partner-text-primary, #333e47);
  flex: 1;
  text-align: right;
}
</style>
```

**Step 2: Wire into AssessmentView**

In `frontend/src/views/AssessmentView.vue`:

Import:
```typescript
import AssumptionsPanel from '../components/AssumptionsPanel.vue'
```

Replace the existing `profile-card` section (lines ~77-101) with:
```html
<AssumptionsPanel :summary="result.input_summary" />
```

**Step 3: Run type check and dev server**

Run: `cd frontend && npm run type-check`
Expected: PASS

Start dev server: `cd frontend && npm run dev`
Visually verify the panel appears in results and collapses/expands.

**Step 4: Commit**

```bash
git add frontend/src/components/AssumptionsPanel.vue frontend/src/views/AssessmentView.vue
git commit -m "feat: add collapsible Assumptions panel showing imputed values with confidence"
```

---

## Task 6: Integration Test — Full Pipeline with Imputation

Verify the complete pipeline returns imputed_details in the API response.

**Files:**
- Modify: `backend/tests/test_api_integration.py`

**Step 1: Write integration test**

Add to `backend/tests/test_api_integration.py`:

```python
def test_assess_returns_imputed_details(app_client):
    """POST /assess with missing optional fields returns imputed_details."""
    payload = {
        "buildings": [{
            "building_type": "Office",
            "sqft": 50000,
            "num_stories": 3,
            "zipcode": "60610",
            "year_built": 2014,
            "heating_fuel": "NaturalGas",
        }]
    }
    resp = app_client.post("/assess", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    summary = data["results"][0]["input_summary"]

    # Should have imputed_details dict
    assert "imputed_details" in summary
    assert isinstance(summary["imputed_details"], dict)

    # lighting_type was not provided, should be imputed
    assert "lighting_type" in summary["imputed_details"]
    detail = summary["imputed_details"]["lighting_type"]
    assert "value" in detail
    assert "label" in detail
    assert detail["label"] == "Lighting Type"
    assert detail["source"] in ("model", "default")

    # vintage_bucket should be present
    assert "vintage_bucket" in summary

    # heating_fuel was provided, should NOT be imputed
    assert "heating_fuel" not in summary["imputed_details"]
```

**Step 2: Run the test**

Run: `cd backend && pytest tests/test_api_integration.py::test_assess_returns_imputed_details -v`
Expected: PASS (if Tasks 1-2 are complete)

**Step 3: Commit**

```bash
git add backend/tests/test_api_integration.py
git commit -m "test: add integration test for imputed_details in assessment response"
```

---

## Summary of Changes

| Layer | What Changes | Why |
|-------|-------------|-----|
| `request.py` | `year_built` becomes required | Critical input for imputation accuracy |
| `preprocessor.py` | Uses `ImputationService` when available; returns `dict` of imputed details | ML-based imputation replaces static defaults |
| `response.py` | New `ImputedField` model; `InputSummary` gains `imputed_details` + `vintage_bucket` | Surfaces assumptions to API consumers |
| `assessment.py` | Passes `imputation_service` through pipeline | Wires service into orchestrator |
| `routes.py` | Passes `imputation_service` from `app.state` to `assess_buildings` | Connects startup-loaded service to endpoint |
| `applicability.py` | LED check matches `gen4_led`/`gen5_led` | Bug fix — check was comparing wrong values |
| `assessment.ts` | New `ImputedField` interface; updated `InputSummary` | Type safety for new response fields |
| `AssumptionsPanel.vue` | New collapsible component | User-facing display of imputed assumptions |
| `AssessmentView.vue` | Replaces profile chips with `AssumptionsPanel` | Integrates new component |
| `BuildingForm.vue` | Year built becomes required field | UX change to match schema |
