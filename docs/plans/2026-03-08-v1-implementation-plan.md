# Energy Audit Tool V1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working Energy Audit Tool with FastAPI backend serving XGBoost predictions and a Vue 3 frontend for single-building energy assessments with upgrade measure recommendations including cost/payback.

**Architecture:** FastAPI backend loads ~600 XGB models at startup (baseline EUI, sizing, rates, per-upgrade EUI). Vue 3 frontend with partner-components provides a form → sortable results table. Cost calculation multiplies unit costs by XGB-predicted building capacity/area. Bill savings = predicted rate × energy savings.

**Tech Stack:** Python 3.11+, FastAPI, XGBoost, joblib, pandas | Vue 3, TypeScript, Vite, Tailwind CSS, partner-components

**Existing code to reuse:**
- `scripts/training_utils.py` — `encode_features()`, `tune_hyperparameters()`, `train_single_model()`, `evaluate_model()`, `save_model_artifacts()`
- `scripts/train_comstock_upgrades.py` — data loading, cluster lookup, training loop pattern
- `scripts/train_resstock_upgrades.py` — MF filtering, ResStock-specific data loading
- `Resources/upgrade_cost_lookup.json` — unit costs for 97 upgrades
- `ComStock/spatial_tract_lookup_table.csv` — zipcode/county → cluster_name + climate_zone mapping

---

## Task 0: Repository Cleanup & Organization

**Goal:** Reorganize the repo — archive legacy files, fix `.gitignore`, establish clean top-level structure for the app.

**Step 1: Create archive directory and move legacy files**

```bash
mkdir -p archive/old_scripts archive/old_notebooks archive/old_data
```

Move old training/inference scripts (superseded by `scripts/`):
```bash
git mv EnergyEstimator_Meta_v0.1.py archive/old_scripts/
git mv EnergyEstimator_Meta_v1.py archive/old_scripts/
git mv PreProcessor_ECS_v2.py archive/old_scripts/
git mv PreProcessor_ECS_v3.py archive/old_scripts/
git mv XGB_Training_All_Building_types_v3_2024.2.py archive/old_scripts/
git mv XGB_Training_BuildingTypes_v2.py archive/old_scripts/
git mv XGB_Training_BuildingTypes_v3_2024.2.py archive/old_scripts/
git mv "XGB_Training_Feature Importance_v3_2024.2.py" archive/old_scripts/
git mv XGB_EnergyEstimation_v2.py archive/old_scripts/
git mv XGB_EnergyEstimation_v2_building_types.py archive/old_scripts/
git mv OutlierAnalysis.py archive/old_scripts/
git mv main.py archive/old_scripts/
git mv building_stock_model_training.py archive/old_scripts/
```

Move old notebooks:
```bash
git mv building-stock-model-training.ipynb archive/old_notebooks/
git mv BuildingStockCalibration-jupyter.ipynb archive/old_notebooks/
git mv comstock_cleanup.ipynb archive/old_notebooks/
git mv comstock_processing-jupyter.ipynb archive/old_notebooks/
git mv ResStockProcessing-jupyter.ipynb archive/old_notebooks/
git mv Untitled-1.ipynb archive/old_notebooks/
```

Move old data processing directory:
```bash
git mv "BuildingStock Data Processing" archive/old_data_processing
```

Move misc data files (keep in repo but out of root):
```bash
git mv headers_2_rows.csv archive/old_data/
git mv data_dictionary.xlsx archive/old_data/
git mv resstock_data_dictionary.xlsx archive/old_data/
git mv "ESPM Test Properties, Energy Characterization Study, v1.xlsx" archive/old_data/
```

Move old model directories (v3, v3.1 — superseded by 2025 R3 models):
```bash
git mv XGB_Models/All_Building_Types_models_v3 archive/old_models_v3/
git mv XGB_Models/All_Building_Types_models_v3.1 archive/old_models_v3.1/
git mv XGB_Models/BuildingTypes_models_v3 archive/old_models_v3_by_type/
```

**Step 2: Update `.gitignore`**

Replace the current `.gitignore` with a proper one:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
*.egg-info/
dist/
build/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Raw data (too large, download separately)
ComStock/raw_data/
ResStock/raw_data/

# Node
frontend/node_modules/
frontend/dist/
frontend/partner-components/node_modules/
frontend/partner-components/dist/

# Environment
.env
.env.local
```

Note: `.parquet`, `.pkl`, `.xlsx`, `.png` are tracked via Git LFS (see `.gitattributes`), so they don't need to be gitignored. Only the raw download directories (`raw_data/`) are excluded since they're 60+ GB and should be downloaded separately.

**Step 3: Remove venvs from git tracking (if tracked)**

```bash
git rm -r --cached .venv/ 2>/dev/null || true
git rm -r --cached venv/ 2>/dev/null || true
git rm -r --cached __pycache__/ 2>/dev/null || true
git rm -r --cached .idea/ 2>/dev/null || true
```

**Step 4: Verify clean top-level structure**

After cleanup, the root should look like:
```
BuildingStock Energy Estimation/
  archive/               # Old scripts, notebooks, models (preserved history)
  backend/               # FastAPI app (to be created)
  ComStock/              # spatial_tract_lookup_table.csv + raw_data/ (gitignored)
  docs/                  # Design docs and plans
  frontend/              # Vue 3 app (to be created)
  ResStock/              # raw_data/ (gitignored)
  Resources/             # Cost data, emission factors, imputation models
  scripts/               # Active training pipeline
  Validation/            # CBECS validation data
  XGB_Models/            # Trained models (2025 R3 + sizing + rates)
  .gitattributes         # LFS config
  .gitignore             # Updated
  requirements.txt       # Python dependencies
```

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: reorganize repo — archive legacy files, update .gitignore"
```

---

## Task 1: Train ComStock Sizing Models

**Goal:** Train 5 XGB models that predict building capacity/area from the 25 ComStock features.

**Files:**
- Modify: `scripts/train_comstock_upgrades.py` (add sizing target support)
- Create: `scripts/train_comstock_sizing.py`
- Output: `XGB_Models/ComStock_Sizing/` (5 models + encoders + meta)

**Step 1: Create the sizing training script**

Create `scripts/train_comstock_sizing.py` — a standalone script that reuses `training_utils.py` and follows the same pattern as `train_comstock_upgrades.py` but trains on baseline data only with these targets:

```python
SIZING_TARGETS = {
    'heating_capacity': 'out.params.heating_equipment..kbtu_per_hr',
    'cooling_capacity': 'out.params.cooling_equipment_capacity..tons',
    'wall_area': 'out.params.ext_wall_area..m2',
    'roof_area': 'out.params.ext_roof_area..m2',
    'window_area': 'out.params.ext_window_area..m2',
}
```

Key differences from upgrade training:
- Only uses baseline file (`upgrade0_agg.parquet`)
- No applicability filtering
- Same 25 `FEATURE_COLS` as upgrade models
- Same `LOAD_COLS` pattern but add sizing target columns
- Single tuning group (tune on heating_capacity, apply to all)
- Output dir: `XGB_Models/ComStock_Sizing/`

**Step 2: Run the script**

```bash
python3 scripts/train_comstock_sizing.py
```

Expected: 5 models saved, each with `.pkl`, `_encoders.pkl`, `_meta.json`

**Step 3: Verify outputs**

```bash
ls XGB_Models/ComStock_Sizing/
# Expected: XGB_heating_capacity.pkl, XGB_cooling_capacity.pkl, etc.
```

**Step 4: Commit**

```bash
git add scripts/train_comstock_sizing.py XGB_Models/ComStock_Sizing/
git commit -m "feat: add ComStock sizing model training (capacity + envelope area)"
```

---

## Task 2: Train ComStock Rate Models

**Goal:** Train 4 XGB models that predict effective utility rate ($/kWh) per fuel type.

**Files:**
- Create: `scripts/train_comstock_rates.py`
- Output: `XGB_Models/ComStock_Rates/` (4 models)

**Step 1: Create the rate training script**

Create `scripts/train_comstock_rates.py`. This script:
1. Loads baseline data + bill intensity columns + consumption columns
2. Derives effective rate: `bill_intensity_usd_per_ft2 / (consumption_kwh / sqft)`
3. Filters out rows where consumption is near zero (< 0.1 kWh/sf) to avoid division issues
4. Trains one XGB model per fuel type

```python
RATE_TARGETS = {
    'electricity': {
        'bill_col': 'out.utility_bills.electricity_bill_mean_intensity..usd_per_ft2',
        'consumption_col': 'out.electricity.total.energy_consumption..kwh',
    },
    'natural_gas': {
        'bill_col': 'out.utility_bills.natural_gas_bill_state_average_intensity..usd_per_ft2',
        'consumption_col': 'out.natural_gas.total.energy_consumption..kwh',
    },
    'fuel_oil': {
        'bill_col': 'out.utility_bills.fuel_oil_bill_state_average_intensity..usd_per_ft2',
        'consumption_col': 'out.fuel_oil.total.energy_consumption..kwh',
    },
    'propane': {
        'bill_col': 'out.utility_bills.propane_bill_state_average_intensity..usd_per_ft2',
        'consumption_col': 'out.propane.total.energy_consumption..kwh',
    },
}
```

Derived target per fuel: `rate = bill_col / (consumption_col / sqft)`

Key: filter to buildings where `consumption_col / sqft > 0.1` for each fuel to avoid near-zero division.

Same 25 `FEATURE_COLS`. Single tuning group (tune on electricity, apply to all).

**Step 2: Run and verify**

```bash
python3 scripts/train_comstock_rates.py
ls XGB_Models/ComStock_Rates/
```

**Step 3: Commit**

```bash
git add scripts/train_comstock_rates.py XGB_Models/ComStock_Rates/
git commit -m "feat: add ComStock utility rate model training"
```

---

## Task 3: Train ResStock Sizing + Rate Models

**Goal:** Train 5 sizing + 4 rate models for ResStock (MF 4+ occupied).

**Files:**
- Create: `scripts/train_resstock_sizing.py`
- Create: `scripts/train_resstock_rates.py`
- Output: `XGB_Models/ResStock_Sizing/`, `XGB_Models/ResStock_Rates/`

**Step 1: Create ResStock sizing script**

Same pattern as Task 1 but with ResStock columns:

```python
SIZING_TARGETS = {
    'heating_capacity': 'out.params.size_heating_system_primary..kbtu_per_hr',
    'cooling_capacity': 'out.params.size_cooling_system_primary..kbtu_per_hr',
    'wall_area': 'out.params.wall_area_above_grade_conditioned..ft2',
    'roof_area': 'out.params.roof_area..ft2',
    'window_area': 'out.params.window_area..ft2',
}
```

Uses ResStock `FEATURE_COLS` (23 features from `train_resstock_upgrades.py`). Includes `filter_mf_occupied()` from existing script.

**Step 2: Create ResStock rate script**

Same pattern as Task 2 but with ResStock bill/consumption columns. Check ResStock column names first — they differ from ComStock (e.g., `out.utility_bills.*_bill..usd` not `*_intensity`). May need to divide by sqft manually.

**Step 3: Run both, verify, commit**

```bash
python3 scripts/train_resstock_sizing.py
python3 scripts/train_resstock_rates.py
git add scripts/train_resstock_*.py XGB_Models/ResStock_Sizing/ XGB_Models/ResStock_Rates/
git commit -m "feat: add ResStock sizing and rate model training"
```

---

## Task 4: Train ComStock + ResStock Upgrade EUI Models

**Goal:** Train all upgrade models using existing scripts.

**Note:** These scripts already exist and are ready to run. This task is just execution.

**Step 1: Run ComStock upgrade training**

```bash
python3 scripts/train_comstock_upgrades.py --tune-trials 50
```

Expected: 330 models (66 upgrades × 5 fuel types) in `XGB_Models/ComStock_Upgrades_2025_R3/`

**Step 2: Run ResStock upgrade training**

```bash
python3 scripts/train_resstock_upgrades.py --tune-trials 50
```

Expected: 132 models (33 upgrades × 4 fuel types) in `XGB_Models/ResStock_Upgrades_2025_R1/`

**Step 3: Verify and commit**

Check `training_results_summary.xlsx` in each output dir for model quality metrics.

```bash
git add XGB_Models/ComStock_Upgrades_2025_R3/ XGB_Models/ResStock_Upgrades_2025_R1/
git commit -m "feat: train all ComStock + ResStock upgrade EUI models"
```

---

## Task 5: Scaffold FastAPI Backend

**Goal:** Create the backend project structure with dependencies.

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/requirements.txt`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/inference/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p backend/app/api backend/app/schemas backend/app/services backend/app/inference backend/app/data
```

**Step 2: Create `backend/requirements.txt`**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.0
xgboost>=2.0
scikit-learn>=1.4
pandas>=2.0
numpy>=1.26
joblib>=1.3
```

**Step 3: Create `backend/app/main.py`**

Minimal FastAPI app with CORS, lifespan handler that loads models at startup. Import routes from `api/routes.py`.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.inference.model_manager import ModelManager

model_manager = ModelManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    model_manager.load_all()
    app.state.model_manager = model_manager
    yield

app = FastAPI(title="Energy Audit Tool", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from app.api.routes import router
app.include_router(router)
```

**Step 4: Create empty `__init__.py` files and commit**

```bash
touch backend/app/__init__.py backend/app/api/__init__.py backend/app/schemas/__init__.py backend/app/services/__init__.py backend/app/inference/__init__.py
git add backend/
git commit -m "feat: scaffold FastAPI backend project structure"
```

---

## Task 6: Build Pydantic Schemas

**Goal:** Define request/response models matching the API contract.

**Files:**
- Create: `backend/app/schemas/request.py`
- Create: `backend/app/schemas/response.py`

**Step 1: Create `backend/app/schemas/request.py`**

```python
from pydantic import BaseModel, Field
from typing import Optional

class BuildingInput(BaseModel):
    building_type: str = Field(..., description="One of 15 building types")
    sqft: float = Field(..., gt=0)
    num_stories: int = Field(..., ge=1)
    zipcode: str = Field(..., min_length=5, max_length=5)
    year_built: Optional[int] = None
    heating_fuel: Optional[str] = None
    dhw_fuel: Optional[str] = None
    hvac_system_type: Optional[str] = None
    wall_construction: Optional[str] = None
    window_type: Optional[str] = None
    window_to_wall_ratio: Optional[str] = None
    lighting_type: Optional[str] = None
    operating_hours: Optional[float] = None

class AssessmentRequest(BaseModel):
    buildings: list[BuildingInput]
```

**Step 2: Create `backend/app/schemas/response.py`**

```python
from pydantic import BaseModel
from typing import Optional

class FuelBreakdown(BaseModel):
    electricity: float
    natural_gas: float
    fuel_oil: float
    propane: float
    district_heating: float = 0.0

class BaselineResult(BaseModel):
    total_eui_kbtu_sf: float
    eui_by_fuel: FuelBreakdown
    emissions_kg_co2e_per_sf: Optional[float] = None

class CostEstimate(BaseModel):
    installed_cost_per_sf: float
    installed_cost_total: float
    cost_range: dict  # {"low": float, "high": float}
    useful_life_years: Optional[int] = None
    regional_factor: float
    confidence: str

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

class InputSummary(BaseModel):
    climate_zone: str
    cluster_name: str
    state: str
    imputed_fields: list[str]

class BuildingResult(BaseModel):
    building_index: int
    baseline: BaselineResult
    measures: list[MeasureResult]
    input_summary: InputSummary

class AssessmentResponse(BaseModel):
    results: list[BuildingResult]
```

**Step 3: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add Pydantic request/response schemas for /assess endpoint"
```

---

## Task 7: Build Model Manager

**Goal:** Load all XGB models at startup and provide prediction methods.

**Files:**
- Create: `backend/app/inference/model_manager.py`
- Reference: `scripts/training_utils.py` (reuse `encode_features()`)

**Step 1: Create `backend/app/inference/model_manager.py`**

This is the core inference engine. It:
1. Discovers all model directories (`ComStock_Upgrades_2025_R3/`, `ResStock_Upgrades_2025_R1/`, `ComStock_Sizing/`, `ComStock_Rates/`, etc.)
2. Loads each `.pkl` model + `_encoders.pkl` + `_meta.json` into memory at startup
3. Provides `predict_baseline()`, `predict_sizing()`, `predict_rates()`, `predict_upgrade()` methods
4. Reuses `encode_features()` from `scripts/training_utils.py` — copy the function into the backend (don't import from scripts/)

Key implementation details:
- Store models in a dict: `{model_name: {"model": xgb_model, "encoders": encoders, "meta": meta}}`
- `predict_baseline(features_dict)` → runs 5 fuel-type baseline models, returns EUI per fuel
- `predict_sizing(features_dict)` → runs 5 sizing models, returns capacity/area values
- `predict_rates(features_dict)` → runs 4 rate models, returns $/kWh per fuel
- `predict_upgrade(features_dict, upgrade_id)` → runs 5 (or 4) fuel-type models for one upgrade
- All predict methods: build a single-row DataFrame from features_dict, encode with stored encoders, call `model.predict()`

Model directory paths should be configurable via environment variable or default to `../../XGB_Models/` relative to `backend/`.

**Step 2: Test manually**

```python
# Quick test in Python
from app.inference.model_manager import ModelManager
mm = ModelManager()
mm.load_all()
print(f"Loaded {mm.model_count} models")
```

**Step 3: Commit**

```bash
git add backend/app/inference/
git commit -m "feat: add ModelManager for loading and running XGB models"
```

---

## Task 8: Build Preprocessor Service

**Goal:** Validate user input, derive climate_zone/cluster from zipcode, impute missing fields.

**Files:**
- Create: `backend/app/services/preprocessor.py`
- Reference: `ComStock/spatial_tract_lookup_table.csv` for zipcode → cluster/climate mapping

**Step 1: Create `backend/app/services/preprocessor.py`**

This service:
1. Validates inputs (building_type is valid, sqft > 0, etc.)
2. Derives `climate_zone` and `cluster_name` from zipcode (via spatial lookup table)
3. Derives `state` from zipcode (for regional cost adjustment)
4. Imputes missing optional fields using defaults or building_type-based distributions
5. Maps user-facing field names to model feature column names
6. Returns a dict ready for model inference + list of imputed fields

Needs a zipcode-to-county/state mapping. Options:
- Use `ComStock/spatial_tract_lookup_table.csv` which has tract-level GISJOIN codes
- May need a separate zipcode → county FIPS mapping file (the spatial lookup has county GISJOIN, not zipcodes directly)
- For V1, could use a simpler approach: zipcode → state (first 2-3 digits heuristic or a small lookup), then state → a representative cluster

**Important:** Document which fields were imputed in the `input_summary` response.

**Step 2: Commit**

```bash
git add backend/app/services/preprocessor.py
git commit -m "feat: add preprocessor service for input validation and imputation"
```

---

## Task 9: Build Cost Calculator Service

**Goal:** Convert unit costs from `upgrade_cost_lookup.json` into $/sf using XGB-predicted capacity/area.

**Files:**
- Create: `backend/app/services/cost_calculator.py`
- Copy: `Resources/upgrade_cost_lookup.json` → `backend/app/data/upgrade_cost_lookup.json`

**Step 1: Create `backend/app/services/cost_calculator.py`**

This service:
1. Loads `upgrade_cost_lookup.json` at init
2. `calculate_cost(upgrade_id, dataset, sqft, sizing_predictions, state)` method:
   - Looks up the upgrade's `cost_basis` and `cost_mid`/`cost_low`/`cost_high`
   - Based on `cost_basis`:
     - `$/ft² floor` → `cost × sqft`
     - `$/kBtu/h heating` → `cost × sizing_predictions['heating_capacity']`
     - `$/kBtu/h cooling` → `cost × sizing_predictions['cooling_capacity'] × 12` (tons to kBtu/h)
     - `$/ft² wall` → `cost × sizing_predictions['wall_area']` (convert m² to ft² if needed)
     - `$/ft² roof` → `cost × sizing_predictions['roof_area']`
     - `$/ft² glazing` → `cost × sizing_predictions['window_area']`
     - `$/unit` → `cost_mid` (ResStock per unit)
     - `$/watt_dc` → `cost × roof_area × panel_density` (estimate ~10 W/sf)
     - `mixed` → sum component costs (look up `components` field)
   - Apply regional adjustment: `total × regional_adjustments[state]`
   - Return `CostEstimate` with per_sf, total, range, confidence

3. Loads `regional_adjustments` from the same JSON file

**Step 2: Copy data file**

```bash
cp Resources/upgrade_cost_lookup.json backend/app/data/
```

**Step 3: Commit**

```bash
git add backend/app/services/cost_calculator.py backend/app/data/
git commit -m "feat: add cost calculator service with regional adjustments"
```

---

## Task 10: Build Assessment Orchestrator

**Goal:** Wire preprocessor → model inference → cost calculation → response formatting.

**Files:**
- Create: `backend/app/services/assessment.py`

**Step 1: Create `backend/app/services/assessment.py`**

This is the main orchestration service. Method: `assess(building_input, model_manager, cost_calculator)`

Flow:
1. Call `preprocessor.preprocess(building_input)` → features_dict, imputed_fields, climate_zone, cluster, state
2. Determine dataset: `"resstock"` if building_type == "Multi-Family" else `"comstock"`
3. Call `model_manager.predict_baseline(features_dict, dataset)` → baseline EUI per fuel
4. Call `model_manager.predict_sizing(features_dict, dataset)` → capacity/area predictions
5. Call `model_manager.predict_rates(features_dict, dataset)` → $/kWh per fuel
6. Load applicability rules and check each upgrade
7. For each applicable upgrade:
   - Call `model_manager.predict_upgrade(features_dict, upgrade_id, dataset)` → post-upgrade EUI per fuel
   - Compute savings per fuel and total
   - Call `cost_calculator.calculate_cost(upgrade_id, dataset, sqft, sizing, state)` → cost estimate
   - Compute bill_savings = Σ(rate[fuel] × savings[fuel]) per fuel
   - Compute payback = cost_per_sf / bill_savings_per_sf
8. Convert all EUI values from kWh/ft² to kBtu/sf (× 3.412)
9. Sort measures by savings_pct descending
10. Return `BuildingResult`

**Step 2: Commit**

```bash
git add backend/app/services/assessment.py
git commit -m "feat: add assessment orchestrator service"
```

---

## Task 11: Build API Routes

**Goal:** Create the FastAPI endpoints.

**Files:**
- Create: `backend/app/api/routes.py`

**Step 1: Create `backend/app/api/routes.py`**

```python
from fastapi import APIRouter, Request
from app.schemas.request import AssessmentRequest
from app.schemas.response import AssessmentResponse
from app.services.assessment import assess_buildings

router = APIRouter()

@router.post("/assess", response_model=AssessmentResponse)
async def assess(request: AssessmentRequest, req: Request):
    model_manager = req.app.state.model_manager
    results = assess_buildings(request.buildings, model_manager)
    return AssessmentResponse(results=results)

@router.get("/metadata")
async def metadata():
    """Return valid dropdown values for the frontend."""
    return {
        "building_types": [...],  # 15 types
        "heating_fuels": [...],
        "dhw_fuels": [...],
        "hvac_system_types": [...],
        # etc.
    }
```

**Step 2: Test the backend**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# Test with curl:
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"buildings": [{"building_type": "Office", "sqft": 50000, "num_stories": 3, "zipcode": "20001"}]}'
```

**Step 3: Commit**

```bash
git add backend/app/api/
git commit -m "feat: add /assess and /metadata API routes"
```

---

## Task 12: Build Applicability Rules Engine

**Goal:** Determine which upgrade measures apply to a given building based on its characteristics.

**Files:**
- Create: `backend/app/inference/applicability.py`

**Step 1: Create applicability rules**

Two approaches for V1:
- **Simple:** If a model file exists for an upgrade, it's potentially applicable. Assume all non-package measures are applicable unless specific rules disqualify them.
- **Better:** Extract applicability patterns from training data — for each upgrade, compute applicability rate by building_type × HVAC_type. If rate < 5% for a given combo, mark as non-applicable.

For V1, start simple: maintain a dict of hard rules (e.g., attic insulation never applies to MF, HP-RTU only applies to certain HVAC types). Expand later.

The rules should be data-driven where possible. Consider generating them from the training data:
```python
# During training, save applicability stats per upgrade
# applicability_stats[upgrade_id][building_type] = pct_applicable
```

**Step 2: Commit**

```bash
git add backend/app/inference/applicability.py
git commit -m "feat: add applicability rules engine"
```

---

## Task 13: Copy Partner Components + Scaffold Frontend

**Goal:** Set up the Vue 3 frontend project with partner-components.

**Files:**
- Create: `frontend/` (Vue 3 project via Vite)
- Copy: partner-components into `frontend/partner-components/`

**Step 1: Scaffold Vue project**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
```

**Step 2: Copy partner-components**

```bash
cp -r "/Users/brandonwinsatt/Documents/SiteLynx_Clone/partner-components" frontend/partner-components
```

**Step 3: Add as local dependency**

In `frontend/package.json`, add:
```json
"dependencies": {
  "@partnerdevops/partner-components": "file:./partner-components"
}
```

Then install partner-components dependencies:
```bash
cd frontend
npm install
```

**Step 4: Configure Tailwind**

Set up Tailwind CSS in the frontend, importing partner-components styles. Add to `frontend/src/main.ts`:
```typescript
import '@partnerdevops/partner-components/dist/partner-components.css'
```

**Step 5: Verify it builds**

```bash
npm run build
```

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Vue 3 frontend with partner-components"
```

---

## Task 14: Build the Assessment Form Component

**Goal:** Create the building input form using partner-components.

**Files:**
- Create: `frontend/src/components/BuildingForm.vue`
- Create: `frontend/src/components/AdvancedDetails.vue`
- Create: `frontend/src/types/assessment.ts`
- Create: `frontend/src/config/dropdowns.ts`

**Step 1: Create TypeScript types**

`frontend/src/types/assessment.ts` — interfaces matching the API schemas (BuildingInput, AssessmentResponse, BaselineResult, MeasureResult, etc.)

**Step 2: Create dropdown config**

`frontend/src/config/dropdowns.ts` — hardcoded valid values for V1 (building types, fuel types, HVAC types). Will be replaced by `/metadata` endpoint call later.

**Step 3: Create BuildingForm.vue**

Uses partner-components:
- PTextInput for zipcode
- PNumericInput for sqft, stories, year_built
- Native `<select>` or PRadioGroup for building_type, heating_fuel, dhw_fuel, hvac_type (partner-components doesn't have a dropdown/select component — use shadcn Select or native)
- PButton for submit
- Emits `submit` event with `BuildingInput` payload

**Step 4: Create AdvancedDetails.vue**

Collapsible section (use a PButton text variant to toggle visibility) containing:
- Wall construction, window type, WWR, lighting type, operating hours
- Same component pattern as BuildingForm

**Step 5: Verify form renders**

```bash
npm run dev
# Open browser, check form renders with all fields
```

**Step 6: Commit**

```bash
git add frontend/src/components/ frontend/src/types/ frontend/src/config/
git commit -m "feat: add BuildingForm and AdvancedDetails components"
```

---

## Task 15: Build the Results Components

**Goal:** Create baseline summary and measures table.

**Files:**
- Create: `frontend/src/components/BaselineSummary.vue`
- Create: `frontend/src/components/MeasuresTable.vue`

**Step 1: Create BaselineSummary.vue**

Displays:
- Total baseline EUI as a large number (PTypography h1/headline)
- Fuel-type breakdown as smaller values or a simple grid
- Uses PBadge or styled spans for fuel labels

Props: `baseline: BaselineResult`

**Step 2: Create MeasuresTable.vue**

Uses partner-components PTable system:
- PTable wrapper
- PTableHeader with variant="blue-border"
- PTableHead columns: Measure Name, Category (PBadge), Savings kBtu/sf (sortable), Savings % (sortable, default sort desc), Est. Cost $/sf (sortable), Payback yrs (sortable), Confidence (PBadge)
- PTableBody with PTableRow + PTableCell for each measure
- Non-applicable measures: show in a separate section or grayed out rows
- Use PTableHead's built-in sort functionality (`sortable`, `@sortChanged`)

Props: `measures: MeasureResult[]`

Sorting logic: maintain local state for sort column + direction, computed sorted array.

**Step 3: Verify table renders with mock data**

**Step 4: Commit**

```bash
git add frontend/src/components/BaselineSummary.vue frontend/src/components/MeasuresTable.vue
git commit -m "feat: add BaselineSummary and MeasuresTable components"
```

---

## Task 16: Build API Integration + Wire Everything

**Goal:** Connect frontend to backend API.

**Files:**
- Create: `frontend/src/composables/useAssessment.ts`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/views/AssessmentView.vue`

**Step 1: Create useAssessment composable**

```typescript
// Manages: loading state, error state, response data, submit function
export function useAssessment() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const result = ref<BuildingResult | null>(null)

  async function assess(input: BuildingInput) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('http://localhost:8000/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ buildings: [input] }),
      })
      const data: AssessmentResponse = await response.json()
      result.value = data.results[0]
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  return { loading, error, result, assess }
}
```

**Step 2: Create AssessmentView.vue**

Single view that composes:
- BuildingForm (top) → on submit, calls `assess()`
- Loading indicator while waiting
- BaselineSummary + MeasuresTable (below form, shown when result exists)

**Step 3: Update App.vue**

Wrap in PLayout (header only, no side panels). Header shows Partner logo + "Energy Assessment Tool" title.

**Step 4: End-to-end test**

```bash
# Terminal 1: Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Open browser, fill form, submit, verify results appear
```

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: wire frontend to backend API, complete V1 flow"
```

---

## Task 17: Zipcode Lookup Data

**Goal:** Create a zipcode → state/county/climate_zone mapping for the preprocessor.

**Files:**
- Create: `backend/app/data/zipcode_lookup.json` or `.csv`
- Modify: `backend/app/services/preprocessor.py`

**Step 1: Build zipcode mapping**

The spatial_tract_lookup_table has county GISJOIN → cluster_name + climate_zone, but no zipcode column. We need a zipcode → county bridge.

Options:
- Use HUD USPS ZIP-County crosswalk (publicly available)
- Use a Python package like `uszipcode` or `pgeocode`
- For V1: install `pgeocode` which maps zipcode → state + lat/lon, then use lat/lon to find nearest county in the spatial lookup

Simplest V1 approach: `pgeocode` for zipcode → state, then state → most common cluster in that state (from spatial lookup). This is approximate but functional.

**Step 2: Update preprocessor to use the mapping**

**Step 3: Commit**

```bash
git add backend/app/data/ backend/app/services/preprocessor.py
git commit -m "feat: add zipcode lookup for climate zone and cluster mapping"
```

---

## Execution Order Summary

| Task | Description | Dependencies | Estimated Effort |
|------|-------------|--------------|-----------------|
| 0 | Repo cleanup & organization | None (parallel with 1-4) | git mv + .gitignore |
| 1 | Train ComStock sizing models | None (kick off first) | Script + run |
| 2 | Train ComStock rate models | None | Script + run |
| 3 | Train ResStock sizing + rate models | None | Script + run |
| 4 | Train upgrade EUI models | None (scripts exist) | Run existing scripts |
| 5 | Scaffold FastAPI backend | None | Boilerplate |
| 6 | Build Pydantic schemas | Task 5 | Data classes |
| 7 | Build Model Manager | Tasks 1-4 (models exist), Task 5 | Core logic |
| 8 | Build Preprocessor | Task 5 | Input handling |
| 9 | Build Cost Calculator | Task 5 | Cost logic |
| 10 | Build Assessment Orchestrator | Tasks 6-9 | Wiring |
| 11 | Build API Routes | Task 10 | Thin layer |
| 12 | Build Applicability Rules | Task 5 | Rules logic |
| 13 | Scaffold Vue frontend | None | Boilerplate |
| 14 | Build form components | Task 13 | UI |
| 15 | Build results components | Task 13 | UI |
| 16 | Wire frontend to backend | Tasks 11, 14, 15 | Integration |
| 17 | Zipcode lookup data | Task 8 | Data mapping |

**Parallelization:**
- **Phase A (parallel):** Tasks 1-4 (training) kick off first. Task 0 (repo cleanup) runs in parallel while training executes.
- **Phase B (sequential):** Tasks 5-12 (backend) after training + cleanup complete.
- **Phase C (parallel with B):** Tasks 13-15 (frontend) can start as soon as Task 0 is done, in parallel with backend work.
- **Phase D:** Task 16 (integration) needs both backend + frontend complete. Task 17 (zipcode lookup) can slot in alongside backend work.

**Execution order:**
```
Time →
├── Tasks 1-4 (training, long-running) ──────────────────────┐
├── Task 0 (repo cleanup, quick) ───┐                        │
│                                    ├── Tasks 13-15 (frontend)
│                                    │                        │
│                                    └────────────────────────┤
│                                                             ├── Tasks 5-12 (backend)
│                                                             ├── Task 17 (zipcode)
│                                                             └── Task 16 (integration)
```

**Total models to train:** Tasks 1-4 produce ~480 models (5+4+5+4+330+132). Training time depends on hardware — estimate 1-4 hours for upgrade models, minutes for sizing/rate models.
