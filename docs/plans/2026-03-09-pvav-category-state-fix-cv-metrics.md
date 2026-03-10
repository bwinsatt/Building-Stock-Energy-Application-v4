# PVAV Category Separation, State Column Fix, and CV Metrics

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three imputation issues: (1) separate PVAV systems into their own `packaged_vav` category instead of lumping them under `central_chiller_boiler`, (2) fix the state column mismatch in the imputation service (`in.state_abbreviation` → `in.state`), and (3) add cross-validation accuracy metrics to the imputation trainer.

**Architecture:** The PVAV category change touches four mapping structures in `preprocessor.py`, the frontend dropdown config in `dropdowns.ts`, and the display map. The state fix is a one-line change in `imputation_service.py`. The CV metrics enhancement adds train/test split evaluation to `imputation_trainer.py` and stores accuracy in the saved model bundles.

**Tech Stack:** Python (backend), TypeScript/Vue 3 (frontend), XGBoost, scikit-learn

---

### Task 1: Add `packaged_vav` category to backend value map

**Files:**
- Modify: `backend/app/services/preprocessor.py:124-174` (`_COMSTOCK_VALUE_MAP["hvac_system_type"]`)

**Step 1: Add category key and update existing PVAV old-code mappings**

In `_COMSTOCK_VALUE_MAP["hvac_system_type"]`, add a new category key `packaged_vav` that maps to the default PVAV variant, and update the old PVAV backward-compat codes:

```python
# Add after "central_chiller_boiler" line (~131):
"packaged_vav": "PVAV with gas heat with electric reheat",

# Update old codes (~140-141) to point to packaged_vav's default:
"PVAV_gas_boiler": "PVAV with gas boiler reheat",    # no change needed (pass-through exists)
"PVAV_gas_heat": "PVAV with gas heat with electric reheat",  # no change needed
```

No other changes needed here — the 29 ComStock variant pass-through strings (lines 161-164) already map correctly.

**Step 2: Run tests**

Run: `cd backend && pytest tests/test_preprocessor.py -v`
Expected: All existing tests PASS (this is additive).

---

### Task 2: Update display map to map PVAV → `packaged_vav`

**Files:**
- Modify: `backend/app/services/preprocessor.py:949-979` (`_COMSTOCK_DISPLAY_MAP["hvac_system_type"]`)

**Step 1: Change PVAV mappings from `central_chiller_boiler` to `packaged_vav`**

Change lines 966-969:
```python
# BEFORE:
"PVAV with gas boiler reheat": "central_chiller_boiler",
"PVAV with gas heat with electric reheat": "central_chiller_boiler",
"PVAV with PFP boxes": "central_chiller_boiler",
"PVAV with district hot water reheat": "central_chiller_boiler",

# AFTER:
"PVAV with gas boiler reheat": "packaged_vav",
"PVAV with gas heat with electric reheat": "packaged_vav",
"PVAV with PFP boxes": "packaged_vav",
"PVAV with district hot water reheat": "packaged_vav",
```

**Step 2: Run tests**

Run: `cd backend && pytest tests/test_preprocessor.py -v`
Expected: PASS

---

### Task 3: Add `packaged_vav` to ResStock value map

**Files:**
- Modify: `backend/app/services/preprocessor.py:385-404` (`_RESSTOCK_VALUE_MAP["hvac_system_type"]`)

**Step 1: Add packaged_vav mapping**

Add after line 393 (`"residential_furnace": "Ducted Heating"`):
```python
"packaged_vav": "Ducted Heating",
```

**Step 2: Run tests**

Run: `cd backend && pytest tests/test_preprocessor.py -v`
Expected: PASS

---

### Task 4: Add `packaged_vav` to frontend dropdown config

**Files:**
- Modify: `frontend/src/config/dropdowns.ts:75-93` (HVAC_CATEGORIES array)

**Step 1: Extract PVAV variants from `central_chiller_boiler` into new `packaged_vav` category**

Remove the 4 PVAV variants from the `central_chiller_boiler` category (lines 88-91), and add a new category object after it:

The `central_chiller_boiler` category should become (VAV-only):
```typescript
{
  key: 'central_chiller_boiler',
  label: 'Central Chiller + Boiler',
  defaultVariant: 'VAV chiller with gas boiler reheat',
  datasets: ['comstock'],
  variants: [
    { value: 'VAV chiller with gas boiler reheat', label: 'VAV - Water-Cooled Chiller, Gas Boiler' },
    { value: 'VAV chiller with PFP boxes', label: 'VAV - Water-Cooled Chiller, Electric Reheat' },
    { value: 'VAV chiller with district hot water reheat', label: 'VAV - Water-Cooled Chiller, District Hot Water' },
    { value: 'VAV air-cooled chiller with gas boiler reheat', label: 'VAV - Air-Cooled Chiller, Gas Boiler' },
    { value: 'VAV air-cooled chiller with PFP boxes', label: 'VAV - Air-Cooled Chiller, Electric Reheat' },
    { value: 'VAV air-cooled chiller with district hot water reheat', label: 'VAV - Air-Cooled Chiller, District Hot Water' },
    { value: 'VAV district chilled water with district hot water reheat', label: 'VAV - District Chilled Water' },
  ],
},
```

Add the new `packaged_vav` category immediately after:
```typescript
{
  key: 'packaged_vav',
  label: 'Packaged VAV (Rooftop)',
  defaultVariant: 'PVAV with gas heat with electric reheat',
  datasets: ['comstock'],
  variants: [
    { value: 'PVAV with gas boiler reheat', label: 'PVAV - Gas Boiler Reheat' },
    { value: 'PVAV with gas heat with electric reheat', label: 'PVAV - Gas Heat, Electric Reheat' },
    { value: 'PVAV with PFP boxes', label: 'PVAV - Electric Reheat' },
    { value: 'PVAV with district hot water reheat', label: 'PVAV - District Hot Water' },
  ],
},
```

**Step 2: Update the legacy map in `getHvacCategoryForValue`**

Change lines 183-184:
```typescript
// BEFORE:
'PVAV_gas_boiler': 'central_chiller_boiler',
'PVAV_gas_heat': 'central_chiller_boiler',

// AFTER:
'PVAV_gas_boiler': 'packaged_vav',
'PVAV_gas_heat': 'packaged_vav',
```

**Step 3: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

---

### Task 5: Fix state column mismatch in imputation service

**Files:**
- Modify: `backend/app/inference/imputation_service.py:105`

**Step 1: Fix the column name**

The imputation models were trained with column name `in.state` (see `imputation_trainer.py:46`), but the service maps `state` → `in.state_abbreviation` which doesn't match any model column, causing the state to be silently encoded as 0 (Alaska).

Change line 105:
```python
# BEFORE:
"state": "in.state_abbreviation",

# AFTER:
"state": "in.state",
```

**Step 2: Write a test for the fix**

In `backend/tests/test_imputation_service.py`, add a test that verifies state is correctly mapped:

```python
def test_map_known_to_input_state_column():
    """State should map to 'in.state', not 'in.state_abbreviation'."""
    service = ImputationService.__new__(ImputationService)
    input_columns = [
        "in.comstock_building_type_group",
        "in.state",
    ]
    known = {"building_type": "Office", "state": "CA"}
    result = service._map_known_to_input(known, input_columns)
    assert result[1] == "CA", f"Expected 'CA', got {result[1]}"
```

**Step 3: Run tests**

Run: `cd backend && pytest tests/test_imputation_service.py -v`
Expected: PASS

---

### Task 6: Add cross-validation metrics to imputation trainer

**Files:**
- Modify: `backend/app/inference/imputation_trainer.py:120-148`

**Step 1: Add stratified cross-validation before final training**

After encoding target (line 118) and before training (line 121), add a 5-fold stratified CV:

```python
from sklearn.model_selection import StratifiedKFold, cross_val_predict

# --- Cross-validation for accuracy metrics ---
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_preds = cross_val_predict(
    XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        use_label_encoder=False,
        eval_metric="mlogloss",
    ),
    X, y_encoded, cv=cv, method="predict",
)
cv_accuracy = float(np.mean(cv_preds == y_encoded))
logger.info("  CV accuracy for %s: %.3f", field_name, cv_accuracy)
```

**Step 2: Store accuracy in the saved model bundle**

Add `cv_accuracy` to the `joblib.dump` dict (line 133):

```python
joblib.dump({
    "model": model,
    "feature_encoders": encoders,
    "target_encoder": target_encoder,
    "input_columns": available_inputs,
    "feature_names": FEATURE_NAMES[:len(available_inputs)],
    "cv_accuracy": cv_accuracy,
}, model_path)
```

**Step 3: Add accuracy to metadata**

Add to the metadata dict (line 142):
```python
metadata[field_name] = {
    "n_samples": len(subset),
    "n_classes": len(target_encoder.classes_),
    "classes": target_encoder.classes_.tolist(),
    "cv_accuracy": cv_accuracy,
}
```

**Step 4: Run trainer (optional — requires ComStock parquet data)**

Run: `cd backend && python -m app.inference.imputation_trainer --comstock-path ../../ComStock/raw_data/comstock.parquet --output-dir ../../XGB_Models/Imputation`
Expected: Logs should show CV accuracy for each field. Models get re-saved with accuracy metadata.

Note: This step is only needed to regenerate models with accuracy data. The code change itself can be verified structurally.

---

### Task 7: Commit all changes

**Step 1: Run full test suite**

Run: `cd backend && pytest -v`
Expected: All tests PASS

**Step 2: Run frontend type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/services/preprocessor.py backend/app/inference/imputation_service.py backend/app/inference/imputation_trainer.py frontend/src/config/dropdowns.ts backend/tests/test_imputation_service.py
git commit -m "fix: separate PVAV into packaged_vav category, fix state column mismatch, add CV metrics to imputation trainer"
```
