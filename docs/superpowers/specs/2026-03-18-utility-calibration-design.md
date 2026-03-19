# Utility Data Calibration — Design Spec

**Date:** 2026-03-18
**Status:** Draft
**Approach:** Parallel Tracks (validation experiment + feature build)

## Overview

Add the ability for users to provide actual utility bill data (annual consumption per fuel) to calibrate energy savings predictions. The core hypothesis: adding baseline EUI as an input feature to the delta/savings XGBoost models will improve prediction accuracy, because buildings with different actual consumption levels have different savings potential — even when their physical characteristics are identical.

Currently, delta models predict savings from building features alone. Within the NREL training data (ComStock/ResStock), buildings with identical characteristics but different operational profiles produce different baseline EUIs and different savings. The models average across this variation. By conditioning on actual baseline consumption, we narrow predictions to buildings that behave like the user's real building.

Simple scaling (ratio-based calibration) is the contingency fallback if fine-tuning doesn't improve predictions.

**Important:** Retraining delta models with baseline EUI as a feature changes behavior for ALL assessments, not just calibrated ones. After v2 models are deployed, every `predict_delta` call receives baseline EUI — either actual (from user) or predicted (from baseline model). V1 and v2 models cannot coexist in the same directory (same filenames, different feature sets). Deployment is an atomic swap.

## 1. Validation Experiment

**Purpose:** Determine whether adding per-fuel baseline EUI as input features to delta models meaningfully improves savings predictions.

**Script:** `scripts/validate_baseline_feature.py`

**Method:**
1. Load baseline (upgrade 0) data for both ComStock and ResStock
2. For a representative sample of upgrades (5-10 high-impact ones per dataset), load upgrade data and compute deltas
3. Merge on `bldg_id` — each row has building features + baseline EUI per fuel + delta targets
4. Train two XGBoost models per (upgrade, fuel) pair:
   - **Control:** Current feature set only (25 ComStock / 23 ResStock features)
   - **Experiment:** Current features + baseline EUI per fuel (~5 extra columns)
5. Same train/test split, same hyperparameters for both
6. Compare MAE, RMSE, R² on the held-out test set

**Secondary validation — error propagation test:**
After the primary experiment, run a second pass where the experiment models receive *predicted* baseline EUI (from a baseline model trained on the same split) instead of ground truth. Compare to v1 (control) performance. If error propagation degrades predictions below v1 quality, baseline EUI as a feature should only be used when actual utility data is provided.

**Noise robustness test:**
Inject gaussian noise (+/- 10-20%) into baseline EUI features and re-evaluate. This simulates real-world utility bill data which includes measurement noise, partial-year data, and weather variation. If R² degrades significantly under noise, simple scaling may be more robust in practice.

**Output:**
- Console summary table (upgrade × fuel × control metrics vs experiment metrics)
- CSV with full results

**Success criteria:** Consistent R² improvement across upgrades and fuels, sustained under the error propagation and noise robustness tests.

## 2. Model Retraining (Conditional on Validation)

**Conditional on validation showing meaningful improvement.**

### New Training Scripts

- `scripts/train_comstock_deltas_v2.py` — copy of `train_comstock_deltas.py` with baseline EUI features added
- `scripts/train_resstock_deltas_v2.py` — copy of `train_resstock_deltas.py` with baseline EUI features added

If v2 is adopted, delete v1 scripts. If not, delete v2 scripts.

### Additional Features

ComStock (5 new columns):
- `baseline_electricity` (kWh/sqft)
- `baseline_natural_gas` (kWh/sqft)
- `baseline_fuel_oil` (kWh/sqft)
- `baseline_propane` (kWh/sqft)
- `baseline_district_heating` (kWh/sqft)

ResStock (4 new columns — no district heating):
- `baseline_electricity` (kWh/sqft)
- `baseline_natural_gas` (kWh/sqft)
- `baseline_fuel_oil` (kWh/sqft)
- `baseline_propane` (kWh/sqft)

These come from the upgrade 0 data that is already loaded and merged during training — the change is to stop dropping these columns before model fitting.

### Model Compression

Update `save_model_artifacts` in `scripts/training_utils.py`:
```python
joblib.dump(model, model_path, compress=3)
```

This typically reduces XGBoost model size by 50-70%. No load-side changes needed — joblib handles compressed files transparently. Compression can also be applied retroactively to existing v1 models (load and re-save) for immediate disk savings independent of retraining.

### Inference Changes (`model_manager.py`)

`predict_delta()` gains an optional `baseline_eui` parameter:
- `baseline_eui: Optional[dict[str, float]]` — per-fuel baseline EUI in kWh/sqft

**Feature injection mechanism:** `predict_delta` merges baseline EUI values into a *copy* of `features_dict` before passing to `_predict_single`. This keeps the concern local to the model layer — the assessment orchestrator does not need to know the model's internal feature column names. The v2 model metadata (`feature_columns`) includes the baseline columns, so `_predict_single` picks them up automatically. The per-building `enc_cache` scope is preserved — v2 upgrade models will naturally get separate cache entries since their `feature_columns` tuple (including baseline columns) differs from baseline/sizing/rates models.

**Caller contract:** `predict_delta` does NOT call `predict_baseline` internally. The caller (assessment orchestrator) always passes `baseline_eui` — either from predicted baseline output or from converted user utility data. This keeps the model layer stateless.

The baseline model itself does NOT change.

## 3. Schema & API Changes

### Request Schema (`BuildingInput`)

New optional fields:
```python
annual_electricity_kwh: Optional[float] = None
annual_natural_gas_therms: Optional[float] = None
annual_fuel_oil_gallons: Optional[float] = None
annual_propane_gallons: Optional[float] = None
annual_district_heating_kbtu: Optional[float] = None
```

Units match what users see on utility bills. Backend converts to kWh/sqft internally using the building's `sqft` and unit constants.

### New Unit Conversion Constants (`app/constants.py`)

The following constants must be added for fuel oil and propane gallon-to-kWh conversion:
```python
KWH_PER_GALLON_FUEL_OIL = 40.6    # 138,500 BTU/gallon / 3,412 BTU/kWh
KWH_PER_GALLON_PROPANE = 26.8     # 91,500 BTU/gallon / 3,412 BTU/kWh
KWH_PER_THERM = 29.31             # 1 / 0.03412 (inverse of existing KWH_TO_THERMS)
```

### Response Schema

**`BuildingResult`** — new fields:
- `calibrated: bool` — whether actual utility data was used

**`BaselineResult`** — new fields:
- `actual_eui_by_fuel: Optional[FuelBreakdown]` — per-fuel actual EUI from utility data (null if uncalibrated)
- `actual_total_eui_kbtu_sf: Optional[float]` — total actual EUI for display alongside predicted

Per-fuel breakdown enables the frontend to show side-by-side comparison per fuel (e.g., "your model predicted high gas but actual gas is low").

### No New Assessment Endpoints

`POST /assess` handles both flows. Utility fields are optional — their presence triggers the calibrated path.

## 4. Assessment Pipeline Changes (`assessment.py`)

### Data Flow — Uncalibrated (no utility data)

```
BuildingInput (no utility fields)
  -> Preprocessor -> features
  -> predict_baseline() -> predicted_baseline_eui {fuel: kwh/sqft}
  -> predict_delta(features, baseline_eui=predicted_baseline_eui) -> savings
  -> response with calibrated: false
```

### Data Flow — Calibrated (utility data provided)

```
BuildingInput (with annual_electricity_kwh, etc.)
  -> Preprocessor -> features
  -> predict_baseline() -> predicted_baseline_eui (still computed for comparison)
  -> Convert utility data -> actual_baseline_eui {fuel: kwh/sqft}
  -> predict_delta(features, baseline_eui=actual_baseline_eui) -> savings
  -> response with calibrated: true, includes both predicted and actual baseline
```

### Key Behaviors

- Baseline model always runs — even in calibrated mode, predicted vs actual comparison is shown
- **Savings clamping:** Per-fuel savings are NOT clamped at zero — negative savings are valid for fuel-switching measures (e.g., electrification increases electricity use while eliminating gas). Post-upgrade EUI per fuel is clamped at zero: `post_upgrade_eui = max(0, baseline - savings)` — a building cannot use negative energy for a given fuel. This replaces the previous `max(0.0, d)` clamp on savings which incorrectly suppressed fuel-switching effects.
- Cost calculations, rates, and emissions are unchanged — they work off savings output regardless of source

## 5. Persistence Layer (SQLite)

### Database

Single SQLite file: `backend/data/buildingstock.db`

Path must be configurable via env var (e.g., `DATABASE_PATH`) for Docker deployments where the DB should be on a persistent volume.

### Schema

```sql
CREATE TABLE projects (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE buildings (
    id              INTEGER PRIMARY KEY,
    project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    address         TEXT,
    building_input  JSON,
    utility_data    JSON,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assessments (
    id          INTEGER PRIMARY KEY,
    building_id INTEGER REFERENCES buildings(id) ON DELETE CASCADE,
    result      JSON,
    calibrated  BOOLEAN,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Design Rationale

- `building_input` and `result` stored as JSON blobs — mirrors Pydantic models directly, no ORM mapping
- Assessments are snapshots — re-running creates a new row, not an overwrite
- No ORM — plain `sqlite3` stdlib with parameterized queries
- Disposable by design — will be replaced by KIP persistence in SiteLynx
- **`updated_at` handling:** SQLite does not auto-update timestamps on `UPDATE` (unlike MySQL). Application code must explicitly set `updated_at` on update operations.
- **Concurrency:** Enable WAL mode (`PRAGMA journal_mode=WAL`) on connection init. The app uses ThreadPoolExecutor with 8 workers — WAL allows concurrent reads with serialized writes, which is sufficient for this use case.
- **Known limitation:** JSON blob storage means buildings cannot be efficiently queried by attributes (building_type, zipcode, etc.) without deserialization. Acceptable for demo/disposable persistence.

### New API Endpoints

- `GET /projects` — list all projects
- `POST /projects` — create project
- `GET /projects/{id}` — get project with its buildings
- `DELETE /projects/{id}` — delete project (cascade)
- `POST /projects/{id}/buildings` — add building to project
- `POST /projects/{id}/buildings/{id}/assessments` — save an assessment result to a building

`POST /assess` remains stateless — no persistence params. The frontend saves results separately after assessment completes, keeping the assessment endpoint clean for SiteLynx integration where KIP handles persistence independently.

## 6. Frontend Changes

### Navigation

Top-level tab navigation via reactive `currentView` variable with `v-if` conditional rendering (no Vue Router — matches SiteLynx pattern of `data-app` mounted components):
- **Energy Audit** — current assessment view (default)
- **Projects** — project management view

### Projects View

- Project list using PTable or shadcn cards
- "Create Project" action (PButton + PTextInput)
- Click project to navigate into it — shows buildings and saved assessments
- Uses partner-components: PButton, PTable, PTextInput, PLayout, PLayoutGrid, shadcn cards

### Utility Data Input

Collapsible section in the building form, below existing building characteristics. Collapsed by default with label "Have utility bills? (Optional)".

When expanded, two PNumericInput fields shown by default:
- Annual Electricity (kWh)
- Annual Natural Gas (therms)

A secondary "Add more fuel types" link/button reveals the remaining fields:
- Annual Fuel Oil (gallons)
- Annual Propane (gallons)
- Annual District Heating (kBtu) — only shown for commercial building types

All optional — users fill in only what they have. Electricity and natural gas cover ~80% of use cases, so most users never need to expand further.

### Results Indicator

When utility data was provided, show a PBadge or PChip ("Calibrated") next to the baseline summary. Display actual vs predicted baseline EUI comparison per fuel.

## 7. Work Streams

These tracks are mostly independent and can progress in parallel:

| Track | Depends On | Outcome |
|-------|-----------|---------|
| Validation experiment | Nothing | Go/no-go for model retraining |
| SQLite persistence + CRUD endpoints | Nothing | Projects/buildings/assessments storage |
| Frontend navigation + projects view | CRUD endpoints | Tab nav, project management |
| Schema changes (utility fields) | Nothing | Optional utility data in request/response |
| Model retraining (v2 scripts) | Validation results | Delta models with baseline EUI feature |
| Assessment pipeline calibration logic | Schema changes + retrained models | Calibrated vs uncalibrated branching |
| Frontend utility input section | Schema changes | Collapsible form section |
| Model compression | Nothing (can be done independently or during retraining) | Reduced storage footprint |

## 8. Contingency: Simple Scaling

If validation shows baseline EUI as a feature does not meaningfully improve delta predictions:

- Do not retrain models — keep current delta models as-is
- Apply simple scaling: `calibration_ratio = actual_EUI / predicted_EUI` per fuel
- Multiply predicted savings by calibration ratio
- All other feature work (persistence, UI, utility input) remains valuable regardless

## 9. Future Enhancement: Monthly Bill Data

If annual totals prove insufficient signal, a future iteration could accept monthly bill data (12+ months per fuel). This provides seasonal consumption patterns and richer signal for calibration. Deferred — start with annual totals (Option A) and evaluate.

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Error propagation: predicted baseline used as feature amplifies baseline model errors in uncalibrated path | Savings predictions degrade for users without utility data | Secondary validation test (Section 1); if degradation confirmed, only use baseline feature when actual data is provided |
| Noisy user utility data reduces prediction quality below uncalibrated baseline | Calibrated results worse than uncalibrated | Noise robustness test (Section 1); simple scaling fallback |
| V1/V2 model coexistence | Cannot partially deploy — all or nothing | Atomic swap of model directory; v2 model metadata includes baseline columns in `feature_columns` so `_predict_single` handles it automatically |
| District heating rare in ResStock | ResStock buildings rarely have district heating; field may be confusing for residential users | Only show district heating input field when building type is commercial (ComStock dataset) |
