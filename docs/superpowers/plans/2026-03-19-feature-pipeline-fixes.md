# Feature Pipeline Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all type mismatches and missing categorical declarations between the preprocessor, training scripts, and model inference so that every feature flows from frontend input to model prediction with the correct type and value.

**Architecture:** The preprocessor maps user inputs to model column names. Training scripts define which columns are categorical (`CAT_FEATURE_NAMES`) vs numeric. The inference layer (`model_manager.py`) uses encoders and CatBoost's `get_cat_feature_indices()` to encode features. Misalignment between any of these layers causes wrong values at inference. This plan fixes each mismatch, updates tests, and prepares training scripts for a clean retrain.

**Tech Stack:** Python, XGBoost, LightGBM, CatBoost, pandas, pytest

---

## Audit Summary

These issues were identified by tracing every input from the frontend form through `preprocessor.py` → `model_manager.py` → actual model encoders/meta. The `baseline_*` features (5 columns) are correctly injected by `predict_delta()` and are not a problem.

| # | Issue | Severity | Fix Location |
|---|---|---|---|
| 1 | `in.weekday_operating_hours..hr`: preprocessor sends `float` (hrs/week), training data is categorical `str` (hrs/day) | **High** | preprocessor.py, train_comstock_deltas.py |
| 2 | `in.building_subtype`: preprocessor sends building_type name (e.g. `"Office"`), encoder expects subtype values (e.g. `"NA"`, `"largeoffice_nodatacenter"`) | **Medium** | preprocessor.py |
| 3 | `in.number_stories` missing from ComStock `CAT_FEATURE_NAMES` | **High** | train_comstock_deltas.py (already fixed) |
| 4 | `in.aspect_ratio` missing from ComStock `CAT_FEATURE_NAMES` | **Medium** | train_comstock_deltas.py |
| 5 | ResStock `in.geometry_stories`: preprocessor sends `int`, encoder expects categorical `str` | **High** | preprocessor.py, train_resstock_deltas.py |
| 6 | ResStock thermostat columns are categorical strings (`"70F"`, `"3F"`), preprocessor sends raw `float` | **High** | preprocessor.py |
| 7 | ResStock `in.geometry_stories` + 4 thermostat cols missing from `CAT_FEATURE_NAMES` | **High** | train_resstock_deltas.py |

---

### Task 1: Fix ComStock Operating Hours — hrs/week to hrs/day Conversion

The frontend sends `operating_hours` as hours/week (0-168). The training column `in.weekday_operating_hours..hr` contains categorical string values of hours/day (5.75-18.75). The preprocessor must convert hrs/week → hrs/day (÷7), clamp to the training range, snap to the nearest 0.25 increment (matching training data granularity), and output as a string.

**Files:**
- Modify: `backend/app/services/preprocessor.py:1314-1327` (field mapping loop in `preprocess()`)
- Modify: `backend/app/services/preprocessor.py:655-811` (DEFAULTS — change from hrs/week to hrs/day)
- Modify: `backend/app/services/preprocessor.py:811` (DEFAULT_FALLBACK)
- Modify: `backend/app/services/preprocessor.py:1093` (FIELD_LABELS)
- Test: `backend/tests/test_preprocessor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_operating_hours_converted_to_daily_string(office_input):
    """Operating hours (hrs/week) should become categorical string hrs/day."""
    office_input.operating_hours = 56.0  # 56 hrs/week = 8 hrs/day
    features, _, _, _, _ = preprocess(office_input)
    assert features["in.weekday_operating_hours..hr"] == "8"
    assert isinstance(features["in.weekday_operating_hours..hr"], str)


def test_operating_hours_snaps_to_quarter(office_input):
    """Operating hours should snap to nearest 0.25 increment."""
    office_input.operating_hours = 75.0  # 75/7 = 10.714 → snap to 10.75
    features, _, _, _, _ = preprocess(office_input)
    assert features["in.weekday_operating_hours..hr"] == "10.75"


def test_operating_hours_clamped_to_range(office_input):
    """Operating hours outside 5.75-18.75 hrs/day should be clamped."""
    office_input.operating_hours = 168.0  # 24 hrs/day → clamp to 18.75
    features, _, _, _, _ = preprocess(office_input)
    assert features["in.weekday_operating_hours..hr"] == "18.75"

    office_input.operating_hours = 10.0  # 1.43 hrs/day → clamp to 5.75
    features, _, _, _, _ = preprocess(office_input)
    assert features["in.weekday_operating_hours..hr"] == "5.75"


def test_default_operating_hours_is_valid_string(office_input):
    """Default imputed operating hours should also be a valid string."""
    office_input.operating_hours = None
    features, _, _, _, _ = preprocess(office_input)
    val = features["in.weekday_operating_hours..hr"]
    assert isinstance(val, str)
    assert 5.75 <= float(val) <= 18.75
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_preprocessor.py -k "operating_hours" -v`
Expected: FAIL — currently returns `float` not `str`, value is hrs/week not hrs/day

- [ ] **Step 3: Add conversion function to preprocessor**

Add after `_comstock_number_stories()` (around line 617):

```python
def _operating_hours_weekly_to_daily(hours_per_week: float) -> str:
    """Convert weekly operating hours to ComStock daily categorical string.

    Training data uses hours/day as categorical strings in 0.25-hr increments,
    ranging from 5.75 to 18.75.
    """
    hours_per_day = hours_per_week / 7.0
    # Clamp to training data range
    hours_per_day = max(5.75, min(18.75, hours_per_day))
    # Snap to nearest 0.25, with explicit rounding to avoid float precision noise
    hours_per_day = round(round(hours_per_day * 4) / 4, 2)
    # Format: drop trailing ".0" for whole numbers (e.g. "8" not "8.0")
    if hours_per_day == int(hours_per_day):
        return str(int(hours_per_day))
    return str(hours_per_day)
```

- [ ] **Step 4: Update the field mapping loop to call the conversion**

In `preprocess()` at the field mapping loop (around line 1314-1327), add an `elif` clause **directly after the ComStock `num_stories` branch** (line 1323) and **before the `value_map` branch** (line 1325):

```python
        # Convert num_stories to categorical bin (ComStock only)
        elif user_field == "num_stories" and not is_resstock and isinstance(value, (int, float)):
            value = _comstock_number_stories(int(value))
        # Convert operating_hours (hrs/week) to daily categorical string (ComStock only)
        elif user_field == "operating_hours" and not is_resstock and isinstance(value, (int, float)):
            value = _operating_hours_weekly_to_daily(float(value))
        # Map user-facing values to training-data values
        elif user_field in value_map and isinstance(value, str):
```

- [ ] **Step 5: Update DEFAULTS to use hrs/day values**

The `DEFAULTS` dict values for `operating_hours` are currently hrs/week. They need to stay as hrs/week (they're user-facing defaults that get converted in step 4). **No change needed** — the conversion happens in the mapping loop.

However, verify the FIELD_LABELS entry at line 1093 says "hrs/week" which is correct for the user-facing label:
```python
    "operating_hours": "Operating Hours (hrs/week)",
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_preprocessor.py -k "operating_hours" -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: All pass (445+)

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/preprocessor.py backend/tests/test_preprocessor.py
git commit -m "fix: convert operating_hours from hrs/week to daily categorical string for ComStock models"
```

---

### Task 2: Fix ComStock `in.building_subtype` Value

The preprocessor sets `in.building_subtype` to the building type name (e.g. `"Office"`) at line 1332, but the encoder expects specific subtypes: `["NA", "largeoffice_datacenter", "largeoffice_nodatacenter", "mediumoffice_datacenter", "mediumoffice_nodatacenter", "strip_mall_restaurant0", ...]`. Currently `"Office"` falls back to `"NA"` via `encode_features()` — which happens to be correct for most building types. The fix is to set it to `"NA"` directly in the preprocessor instead of relying on the encoder fallback, making the intent explicit.

**Files:**
- Modify: `backend/app/services/preprocessor.py:1332`
- Test: `backend/tests/test_preprocessor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_building_subtype_is_na_for_standard_types(office_input):
    """building_subtype should be 'NA' for standard building types, not the type name."""
    features, _, _, _, _ = preprocess(office_input)
    assert features["in.building_subtype"] == "NA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_preprocessor.py::test_building_subtype_is_na_for_standard_types -v`
Expected: FAIL — currently returns `"Office"`

- [ ] **Step 3: Fix the building_subtype assignment**

At line 1332 in `preprocessor.py`, change:

```python
    # Before (wrong — sends building type name, not subtype):
    auto_impute["in.building_subtype"] = building_input.building_type

    # After (correct — "NA" is the default for all non-special subtypes):
    # building_subtype is only meaningful for LargeOffice (datacenter variants)
    # and StripMall (restaurant percentage variants). For all other types, "NA".
    auto_impute["in.building_subtype"] = "NA"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_preprocessor.py::test_building_subtype_is_na_for_standard_types -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/preprocessor.py backend/tests/test_preprocessor.py
git commit -m "fix: set ComStock building_subtype to 'NA' instead of building type name"
```

---

### Task 3: Fix ResStock `in.geometry_stories` — int to Categorical String

The preprocessor sends `num_stories` as an `int` (e.g. `5`), but the ResStock training data has `in.geometry_stories` as a categorical string column (values: `"1"` through `"35"`). The preprocessor needs to convert it to a string.

**Files:**
- Modify: `backend/app/services/preprocessor.py:1314-1327` (field mapping loop)
- Modify: `scripts/train_resstock_deltas.py:86-108` (add to `CAT_FEATURE_NAMES`)
- Test: `backend/tests/test_preprocessor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_resstock_stories_is_string(mf_input):
    """ResStock in.geometry_stories should be a string, not int."""
    features, _, _, _, _ = preprocess(mf_input)
    assert isinstance(features["in.geometry_stories"], str)
    assert features["in.geometry_stories"] == "5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_preprocessor.py::test_resstock_stories_is_string -v`
Expected: FAIL — currently `int` 5, not `str` "5"

- [ ] **Step 3: Add string conversion for ResStock stories**

In the field mapping loop in `preprocess()` (around line 1314-1327), add an `elif` **directly after the ComStock `num_stories` branch** (and after the `operating_hours` branch added in Task 1):

```python
        # Convert num_stories to categorical bin (ComStock only)
        elif user_field == "num_stories" and not is_resstock and isinstance(value, (int, float)):
            value = _comstock_number_stories(int(value))
        # Convert num_stories to string for ResStock (categorical in training data)
        elif user_field == "num_stories" and is_resstock and isinstance(value, (int, float)):
            value = str(int(value))
        # Convert operating_hours (hrs/week) to daily categorical string (ComStock only)
        elif user_field == "operating_hours" and not is_resstock and isinstance(value, (int, float)):
            value = _operating_hours_weekly_to_daily(float(value))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_preprocessor.py::test_resstock_stories_is_string -v`
Expected: PASS

- [ ] **Step 5: Add `in.geometry_stories` to ResStock `CAT_FEATURE_NAMES`**

In `scripts/train_resstock_deltas.py`, add `'in.geometry_stories'` to the `CAT_FEATURE_NAMES` list (after `'in.geometry_building_type_height'`):

```python
CAT_FEATURE_NAMES = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
    'in.geometry_stories',  # <-- ADD THIS
    'in.ashrae_iecc_climate_zone_2004',
    ...
]
```

- [ ] **Step 6: Run full test suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/preprocessor.py scripts/train_resstock_deltas.py backend/tests/test_preprocessor.py
git commit -m "fix: convert ResStock geometry_stories to categorical string, add to CAT_FEATURE_NAMES"
```

---

### Task 4: Fix ResStock Thermostat Columns — Float to Categorical String

The ResStock training data stores thermostat setpoints as categorical strings like `"70F"`, `"72F"` and setback offsets as `"0F"`, `"3F"`, `"6F"`. The preprocessor currently sends raw `float` values (e.g. `70.0`). The preprocessor must:
1. Round the float to the nearest integer
2. Append `"F"` suffix
3. For setback offsets, round to nearest category (`0F`, `3F`, `6F`, `12F` for heating; `0F`, `2F`, `5F`, `9F` for cooling)

**Files:**
- Modify: `backend/app/services/preprocessor.py:1362-1369` (advanced field map loop in `preprocess()`)
- Modify: `scripts/train_resstock_deltas.py:86-108` (add 4 thermostat cols + stories to `CAT_FEATURE_NAMES`)
- Test: `backend/tests/test_preprocessor.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_resstock_heating_setpoint_is_string_with_f(mf_input):
    """ResStock heating setpoint should be string like '70F'."""
    mf_input.thermostat_heating_setpoint = 70.0
    features, _, _, _, _ = preprocess(mf_input)
    assert features["in.heating_setpoint"] == "70F"


def test_resstock_cooling_setpoint_is_string_with_f(mf_input):
    """ResStock cooling setpoint should be string like '75F'."""
    mf_input.thermostat_cooling_setpoint = 75.0
    features, _, _, _, _ = preprocess(mf_input)
    assert features["in.cooling_setpoint"] == "75F"


def test_resstock_heating_setback_snaps_to_category(mf_input):
    """ResStock heating setback should snap to nearest category (0F/3F/6F/12F)."""
    mf_input.thermostat_heating_setback = 5.0  # nearest is 6F
    features, _, _, _, _ = preprocess(mf_input)
    assert features["in.heating_setpoint_offset_magnitude"] == "6F"


def test_resstock_cooling_setback_snaps_to_category(mf_input):
    """ResStock cooling setback should snap to nearest category (0F/2F/5F/9F)."""
    mf_input.thermostat_cooling_setback = 4.0  # nearest is 5F
    features, _, _, _, _ = preprocess(mf_input)
    assert features["in.cooling_setpoint_offset_magnitude"] == "5F"


def test_resstock_thermostat_none_is_float_nan(mf_input):
    """When thermostat not provided, value should be float NaN.

    Float NaN works for XGB/LGBM natively. For CatBoost, the inference path
    (_predict_single_catboost) converts cat columns via astype(str), which
    turns float NaN into the string "nan" — CatBoost handles this correctly.
    """
    mf_input.thermostat_heating_setpoint = None
    features, _, _, _, _ = preprocess(mf_input)
    import math
    assert math.isnan(features["in.heating_setpoint"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_preprocessor.py -k "resstock_heating_setpoint or resstock_cooling_setpoint or resstock_heating_setback or resstock_cooling_setback or resstock_thermostat_none" -v`
Expected: FAIL — currently sends raw float

- [ ] **Step 3: Add ResStock thermostat conversion functions**

Add to `preprocessor.py` after the `_operating_hours_weekly_to_daily()` function:

```python
def _resstock_setpoint_to_category(temp_f: float) -> str:
    """Convert a temperature float to ResStock categorical string (e.g. 70.0 → '70F').

    Rounds to nearest integer and appends 'F'.
    """
    return f"{round(temp_f)}F"


def _resstock_setback_to_category(delta_f: float, categories: list[float]) -> str:
    """Snap a setback delta to the nearest ResStock category and format as string.

    Args:
        delta_f: User-provided setback in °F.
        categories: Valid numeric category values (e.g. [0, 3, 6, 12]).
    """
    nearest = min(categories, key=lambda c: abs(c - delta_f))
    return f"{int(nearest)}F"


# Valid setback offset categories from ResStock training data
_HEATING_SETBACK_CATEGORIES = [0, 3, 6, 12]
_COOLING_SETBACK_CATEGORIES = [0, 2, 5, 9]
```

- [ ] **Step 4: Update the advanced field map loop for ResStock**

In `preprocess()`, the advanced field map loop (around line 1362-1369) currently does:

```python
    for user_field, model_col in advanced_map.items():
        value = getattr(building_input, user_field, None)
        if value is not None:
            features[model_col] = value
        else:
            features[model_col] = float('nan')
```

Replace with:

```python
    for user_field, model_col in advanced_map.items():
        value = getattr(building_input, user_field, None)
        if value is not None:
            # ResStock thermostat columns are categorical strings in training data
            if is_resstock:
                if user_field in ("thermostat_heating_setpoint", "thermostat_cooling_setpoint"):
                    value = _resstock_setpoint_to_category(value)
                elif user_field == "thermostat_heating_setback":
                    value = _resstock_setback_to_category(value, _HEATING_SETBACK_CATEGORIES)
                elif user_field == "thermostat_cooling_setback":
                    value = _resstock_setback_to_category(value, _COOLING_SETBACK_CATEGORIES)
            features[model_col] = value
        else:
            features[model_col] = float('nan')
```

- [ ] **Step 5: Add thermostat columns to ResStock `CAT_FEATURE_NAMES`**

In `scripts/train_resstock_deltas.py`, add the 4 thermostat columns to `CAT_FEATURE_NAMES`:

```python
CAT_FEATURE_NAMES = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
    'in.geometry_stories',
    'in.ashrae_iecc_climate_zone_2004',
    'cluster_name',
    'in.vintage',
    'in.heating_fuel',
    'in.hvac_heating_type',
    'in.hvac_heating_efficiency',
    'in.hvac_cooling_type',
    'in.hvac_cooling_efficiency',
    'in.hvac_has_shared_system',
    'in.water_heater_fuel',
    'in.water_heater_efficiency',
    'in.geometry_wall_type',
    'in.insulation_wall',
    'in.insulation_floor',
    'in.window_areas',
    'in.windows',
    'in.lighting',
    'in.infiltration',
    'in.geometry_foundation_type',
    'in.heating_setpoint',               # <-- ADD
    'in.cooling_setpoint',               # <-- ADD
    'in.heating_setpoint_offset_magnitude',  # <-- ADD
    'in.cooling_setpoint_offset_magnitude',  # <-- ADD
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_preprocessor.py -k "resstock" -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/preprocessor.py scripts/train_resstock_deltas.py backend/tests/test_preprocessor.py
git commit -m "fix: convert ResStock thermostat inputs to categorical strings, add to CAT_FEATURE_NAMES"
```

---

### Task 5: Add `in.aspect_ratio` to ComStock `CAT_FEATURE_NAMES`

The `in.aspect_ratio` column has categorical string values `["1", "2", "3", "4", "5", "6"]`. The preprocessor already sends it as a string (`"2"` from `COMSTOCK_AUTO_IMPUTE`), so no preprocessor change is needed. But it's missing from `CAT_FEATURE_NAMES` in the training script, causing CatBoost to treat it as numeric.

**Files:**
- Modify: `scripts/train_comstock_deltas.py:91-113` (add to `CAT_FEATURE_NAMES`)
- No preprocessor change needed (already sends string)
- No test change needed (type is already correct)

- [ ] **Step 1: Add `in.aspect_ratio` to ComStock `CAT_FEATURE_NAMES`**

In `scripts/train_comstock_deltas.py`, add `'in.aspect_ratio'` to the `CAT_FEATURE_NAMES` list (after `'in.building_subtype'`):

```python
    'in.building_subtype',
    'in.aspect_ratio',  # <-- ADD THIS
    'in.energy_code_followed_during_last_hvac_replacement',
```

- [ ] **Step 2: Commit**

```bash
git add scripts/train_comstock_deltas.py
git commit -m "fix: add in.aspect_ratio to ComStock CAT_FEATURE_NAMES for CatBoost"
```

---

### Task 6: Add `in.weekday_operating_hours..hr` to ComStock `CAT_FEATURE_NAMES`

> **Depends on:** Task 1 (preprocessor must send string values before CatBoost can treat this as categorical)

Same pattern as aspect_ratio — the column is categorical strings in training data but missing from `CAT_FEATURE_NAMES`. After Task 1, the preprocessor correctly sends a string value.

**Files:**
- Modify: `scripts/train_comstock_deltas.py:91-113`

- [ ] **Step 1: Add to `CAT_FEATURE_NAMES`**

Add `'in.weekday_operating_hours..hr'` to the list:

```python
    'in.interior_lighting_generation',
    'in.weekday_operating_hours..hr',  # <-- ADD THIS
    'in.building_subtype',
```

- [ ] **Step 2: Commit**

```bash
git add scripts/train_comstock_deltas.py
git commit -m "fix: add in.weekday_operating_hours to ComStock CAT_FEATURE_NAMES for CatBoost"
```

---

### Task 7: Verify CatBoost Inference Fix and Run Integration Test

The CatBoost inference fix (`_predict_single_catboost` using `model.get_cat_feature_indices()`) was already applied in the earlier debugging session. This task verifies it works end-to-end with the preprocessor fixes from Tasks 1-6.

**Files:**
- Verify: `backend/app/inference/model_manager.py:400-421`
- Test: `backend/tests/test_preprocessor.py` (or a new integration test)

- [ ] **Step 1: Write integration test**

```python
def test_full_pipeline_tall_building_no_crash(office_input):
    """A 30-story building should not crash CatBoost with 'over_25'."""
    office_input.num_stories = 30
    office_input.sqft = 500000
    features, _, dataset, _, _ = preprocess(office_input)
    # Verify the value is a string
    assert features["in.number_stories"] == "over_25"
    assert isinstance(features["in.number_stories"], str)
    # Verify operating hours is also a string
    assert isinstance(features["in.weekday_operating_hours..hr"], str)


def test_full_pipeline_resstock_types_correct(mf_input):
    """All ResStock categorical features should be strings."""
    mf_input.thermostat_heating_setpoint = 70.0
    mf_input.thermostat_cooling_setpoint = 75.0
    mf_input.thermostat_heating_setback = 5.0
    mf_input.thermostat_cooling_setback = 4.0
    features, _, dataset, _, _ = preprocess(mf_input)
    assert isinstance(features["in.geometry_stories"], str)
    assert features["in.heating_setpoint"] == "70F"
    assert features["in.cooling_setpoint"] == "75F"
    assert features["in.heating_setpoint_offset_magnitude"] == "6F"
    assert features["in.cooling_setpoint_offset_magnitude"] == "5F"
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pytest tests/test_preprocessor.py -k "full_pipeline" -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_preprocessor.py
git commit -m "test: add integration tests for feature pipeline type correctness"
```

---

## Post-Implementation: Retrain Checklist

After all tasks are complete, the following training scripts have updated `CAT_FEATURE_NAMES` and are ready for retrain:

- `scripts/train_comstock_deltas.py` — Added: `in.number_stories`, `in.aspect_ratio`, `in.weekday_operating_hours..hr`
- `scripts/train_resstock_deltas.py` — Added: `in.geometry_stories`, `in.heating_setpoint`, `in.cooling_setpoint`, `in.heating_setpoint_offset_magnitude`, `in.cooling_setpoint_offset_magnitude`

**Do NOT retrain until all 7 tasks are complete and tests pass.** The preprocessor fixes and training script fixes must be in sync.
