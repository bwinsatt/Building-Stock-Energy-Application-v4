# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack energy audit tool that predicts building energy use intensity (EUI) and recommends efficiency upgrades with cost/savings estimates. Uses XGBoost models trained on NREL's ComStock 2025 R3 and ResStock 2025 R1 datasets.

## Commands

### Backend
```bash
# Install dependencies
cd backend && pip install -r requirements.txt

# Run API server
cd backend && uvicorn app.main:app --reload

# Run all tests
cd backend && pytest

# Run single test file
cd backend && pytest tests/test_preprocessor.py

# Run single test
cd backend && pytest tests/test_preprocessor.py::test_function_name -v

# Run e2e tests (hit live external APIs)
cd backend && pytest --run-e2e
```

### Frontend
```bash
# Install dependencies
cd frontend && npm install

# Dev server
cd frontend && npm run dev

# Build
cd frontend && npm run build

# Type check
cd frontend && npm run type-check
```

### Partner Components (custom UI library)
```bash
cd frontend/partner-components
npm install
npm run storybook    # Component docs
npm run test         # Vitest tests
npm run lint         # ESLint
npm run format       # Prettier
```

## Architecture

### Assessment Pipeline Flow
```
BuildingInput → Preprocessor (validate, impute, map features, determine dataset)
  → ModelManager.predict_baseline() → BaselineResult (EUI by fuel)
  → For each applicable upgrade (parallelized via ThreadPoolExecutor, 8 workers):
      predict_delta() → per-fuel savings (clamped ≥ 0)
      post_upgrade_eui = baseline - savings (derived)
      predict_sizing() → CostCalculator → installed cost
      predict_rate() → utility bill savings & payback
  → Emissions calculation (CO2e reduction from per-fuel consumption)
  → AssessmentResponse (measures sorted: applicable desc by savings %, then non-applicable)
```

### Backend (`backend/app/`)
- **`api/routes.py`** — Six endpoints:
  - `POST /assess` — Main assessment
  - `GET /metadata` — Building types, fuel types, HVAC systems, etc.
  - `GET /health` — Health check
  - `GET /lookup` — Address geocoding + OSM footprint + derived building fields
  - `GET /autocomplete` — Address autocomplete via Photon/OSM
  - `POST /offload` — Manual memory management to free cached upgrade models
- **`schemas/`** — Pydantic v2 request/response models (`BuildingInput`, `AssessmentResponse`)
- **`services/preprocessor.py`** — Input validation, zipcode lookup, feature mapping, imputation. Determines ComStock vs ResStock from building_type.
- **`services/assessment.py`** — Orchestrator wiring preprocessor → inference → costs → response. Handles geometric sizing (wall/roof/window areas from sqft + stories + WWR).
- **`services/cost_calculator.py`** — Cost lookup with regional adjustment factors by state
- **`services/emissions.py`** — CO2e calculation using eGRID electricity factors (region-specific via zipcode) + fixed fossil fuel factors
- **`services/address_lookup.py`** — Geocoding via Nominatim, building footprints via Overpass API, NYC-specific municipal APIs (Building Footprints & PLUTO)
- **`inference/model_manager.py`** — Loads/manages XGBoost models organized by (dataset, category, target). Upgrade models are **delta/savings models** that predict energy savings directly (not absolute post-upgrade EUI).
- **`inference/applicability.py`** — Rule-based upgrade eligibility checker
- **`inference/imputation_service.py`** — Pre-trained imputation models for missing value handling

### Model Loading Strategy
- **Startup**: Indexes model paths only — no heavy loading
- **First dataset request**: Eagerly loads baseline + sizing + rate models (~11 small models)
- **Upgrade models**: Loaded on-demand with LRU cache (cap: 400 bundles per dataset)
- **Auto-offload**: 20-minute inactivity timer evicts upgrade models from memory
- Models stored in `app.state.model_manager` and `app.state.cost_calculator`

### Frontend (`frontend/src/`)
- **Vue 3 Composition API** + TypeScript + Vite + Tailwind CSS 4 (via `@tailwindcss/vite`)
- **`composables/useAssessment.ts`** — API state management (no Pinia/Vuex)
- **`types/assessment.ts`** — TypeScript interfaces mirroring backend Pydantic models
- **`config/dropdowns.ts`** — Dropdown option constants for form fields
- **`components/BuildingMapViewer.vue`** — 3D building visualization using MapLibre GL (45° pitch, nearby buildings in gray, target in blue)
- **`partner-components/`** — Custom component library built on Reka UI (headless), published to GitHub npm registry

### Data & Models
- **`XGB_Models/`** — ~462 trained XGBoost `.pkl` files organized as `{Dataset}_{Category}/XGB_{target}.pkl`. Upgrade models predict per-fuel savings (delta); baseline models predict absolute EUI.
- **`XGB_Models/Imputation/`** — Pre-trained imputation models for missing value inference
- **Training scripts**: `scripts/train_comstock_deltas.py` and `scripts/train_resstock_deltas.py` train upgrade models on delta targets (baseline - upgrade EUI). Baseline models (upgrade 0) predict absolute EUI.
- **`backend/app/data/zipcode_lookup.json`** — Zipcode → climate zone, cluster, state, eGRID electricity emission factor
- **`backend/app/data/upgrade_cost_lookup.json`** — Pre-built cost data with confidence levels and NREL measure descriptions

## Key Conventions

- **Python imports**: Always use absolute `app.xxx` style (`from app.schemas.request import BuildingInput`), never relative imports
- **Dataset separation**: ComStock and ResStock have different building types, features, and upgrade measures. The preprocessor determines which dataset to use based on `building_type`.
- **TypeScript strict mode** is enabled (`noUnusedLocals`, `noUnusedParameters`)
- **API base URL**: Configured via `VITE_API_URL` env var, defaults to `http://localhost:8000`
- **Constants** (`app/constants.py`): Energy conversions (`KWH_TO_KBTU`, `KWH_TO_THERMS`, `TONS_TO_KBTUH`), area conversions, geometric defaults (`STORY_HEIGHT_COMMERCIAL`, `STORY_HEIGHT_RESIDENTIAL`, `ASPECT_RATIO`), and fossil fuel emission factors. All shared numeric constants live here.
- **ResStock per-unit handling**: Multi-family costs convert from per-unit to $/sqft

## Test Fixtures (backend/tests/conftest.py)
- `office_input` — 50k sqft, 3 stories, DC zipcode, 1985, NaturalGas
- `mf_input` — 25k sqft, 5 stories, NY zipcode (ResStock)
- `minimal_input` — Only required fields
- E2e tests are skipped by default; use `--run-e2e` to run (hits live Nominatim, Overpass, NYC Open Data APIs)

## Docker
- Backend: port 8001, Frontend: port 80 (mapped from 3000)
- Models volume-mounted via `MODEL_DIR` env var
- Railway startup runs `backend/download_models.py` before Uvicorn starts
- Optional Railway env var `MODEL_BUNDLE_VERSION` controls manual model cache invalidation:
  bump the value after uploading new blobs to force a full re-download on next startup
- Versioned downloads compare `MODEL_BUNDLE_VERSION` against local volume file
  `.models_version`; matching values skip download, changed values clear the cached
  model files and download the bucket contents again

## SiteLynx Integration Notes

This app will eventually be ported into the SiteLynx platform: the Python backend merges into the KIP/QIP service (DocuEngine-style FastAPI module), and the Vue frontend becomes a new scope/page in SL_Heaven (following the Carbon Performance pattern). Keep these guidelines in mind during development:

### Backend (Python)
- **Absolute imports only**: Always use `from app.xxx` style — never relative imports. This makes the module easy to relocate into a larger service.
- **Keep the service layer decoupled from FastAPI**: Business logic (preprocessor, assessment, cost_calculator, model_manager, emissions) should not depend on FastAPI request/response objects. Pass plain data or Pydantic models into service functions so they can be called from any entry point.
- **Stay stateless**: Don't add database dependencies unless truly needed. The current stateless design (no DB, no persistent sessions) makes integration simpler — KIP will handle persistence if assessment results need to be stored.
- **Keep API contracts simple**: The single `POST /assess` endpoint is clean. Avoid adding complexity that would be hard to translate through a Rails proxy or KIP compatibility layer.
- **No Rails-specific assumptions**: The Python backend should remain framework-agnostic on the consumer side.

### Frontend (Vue)
- **Avoid Vue Router dependencies**: SL_Heaven uses Rails routing, not client-side routing. Structure multi-view flows as separate components that can each be mounted independently via `data-app` attributes, not as Vue Router routes.
- **No global state management libraries**: SL_Heaven doesn't use Pinia/Vuex. Keep state management local to components via composables (current pattern is correct).
- **Partner Components library**: Currently copied into the project directory, but will eventually be an npm package imported into SL_Heaven. Treat it as an external dependency — don't tightly couple app logic to its internals.
- **API base URL must be configurable**: Keep using the `VITE_API_URL` env var pattern. In SL_Heaven, API calls will route to KIP's `/energy-assessment/` prefix instead of `localhost:8000`.
