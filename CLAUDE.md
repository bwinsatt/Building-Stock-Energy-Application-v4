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
  → For each applicable upgrade:
      predict_delta() → per-fuel savings (clamped ≥ 0)
      post_upgrade_eui = baseline - savings (derived)
      predict_sizing() → CostCalculator → installed cost
      predict_rate() → utility bill savings & payback
  → AssessmentResponse
```

### Backend (`backend/app/`)
- **`api/routes.py`** — Three endpoints: `POST /assess`, `GET /metadata`, `GET /health`
- **`schemas/`** — Pydantic v2 request/response models (`BuildingInput`, `AssessmentResponse`)
- **`services/preprocessor.py`** — Input validation, zipcode lookup, feature mapping, imputation. Determines ComStock vs ResStock from building_type.
- **`services/assessment.py`** — Orchestrator wiring preprocessor → inference → costs → response
- **`services/cost_calculator.py`** — Cost lookup with regional adjustment factors by state
- **`inference/model_manager.py`** — Loads/manages XGBoost models organized by (dataset, category, target). Models pre-loaded at startup via FastAPI lifespan. Upgrade models are **delta/savings models** that predict energy savings directly (not absolute post-upgrade EUI).
- **`inference/applicability.py`** — Rule-based upgrade eligibility checker

### Frontend (`frontend/src/`)
- **Vue 3 Composition API** + TypeScript + Vite + Tailwind CSS 4
- **`composables/useAssessment.ts`** — API state management (no Pinia/Vuex)
- **`types/assessment.ts`** — TypeScript interfaces mirroring backend Pydantic models
- **`config/dropdowns.ts`** — Dropdown option constants for form fields
- **`partner-components/`** — Custom component library built on Reka UI (headless), published to GitHub npm registry

### Data & Models
- **`XGB_Models/`** — ~462 trained XGBoost `.pkl` files organized as `{Dataset}_{Category}/XGB_{target}.pkl`. Upgrade models predict per-fuel savings (delta); baseline models predict absolute EUI.
- **Training scripts**: `scripts/train_comstock_deltas.py` and `scripts/train_resstock_deltas.py` train upgrade models on delta targets (baseline - upgrade EUI). Baseline models (upgrade 0) predict absolute EUI.
- **`backend/app/data/zipcode_lookup.json`** — Zipcode → climate zone, cluster, state
- **`backend/app/data/upgrade_cost_lookup.json`** — Pre-built cost data with confidence levels

## Key Conventions

- **Python imports**: Always use absolute `app.xxx` style (`from app.schemas.request import BuildingInput`), never relative imports
- **Dataset separation**: ComStock and ResStock have different building types, features, and upgrade measures. The preprocessor determines which dataset to use based on `building_type`.
- **TypeScript strict mode** is enabled (`noUnusedLocals`, `noUnusedParameters`)
- **API base URL**: Configured via `VITE_API_URL` env var, defaults to `http://localhost:8000`
- **Model loading**: All models loaded at startup into `app.state.model_manager` and `app.state.cost_calculator`
- **Constant**: `KWH_TO_KBTU = 3.412` used for energy unit conversion

## Test Fixtures (backend/tests/conftest.py)
- `office_input` — 50k sqft, 3 stories, DC zipcode, 1985, NaturalGas
- `mf_input` — 25k sqft, 5 stories, NY zipcode (ResStock)
- `minimal_input` — Only required fields
