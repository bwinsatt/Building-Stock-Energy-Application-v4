# Energy Audit Tool — App Architecture Design

**Date:** 2026-03-08
**Status:** Approved
**Parent:** `docs/2026-03-07-energy-audit-tool-design.md`

---

## 1. Overview

Web application architecture for the Energy Audit Tool: a FastAPI backend serving XGBoost model predictions, consumed by a Vue 3 frontend using the Partner design component library.

**Key architectural decisions made in this session:**
- Cost calculation uses XGB models (not lookup tables) for capacity/area estimation
- Utility bill savings derived from XGB-predicted effective rates × energy savings
- Frontend uses Vue 3 + partner-components (copied into repo) — throwaway, eventually replaced by Rails
- V1 is a single-page form → sortable table; V2 adds charts, export, detail panels

---

## 2. Model Inventory (152 Total)

### Baseline Models (14 models, run once per assessment)

| Purpose | Target Columns | Count | Source |
|---------|---------------|-------|--------|
| Baseline EUI by fuel | `out.{fuel}.total.energy_consumption_intensity..kwh_per_ft2` | 5 | ComStock baseline |
| Building sizing | heating_cap, cooling_cap, wall_area, roof_area, window_area | 5 | ComStock baseline `out.params.*` |
| Effective utility rates | $/kWh by fuel (derived: `bill_intensity / consumption_intensity`) | 4 | ComStock baseline bills |

**Why XGB models for sizing instead of lookup tables:**
- Heating capacity per sf has CV of 0.59 even within building_type × climate × size bins (excluding zeros)
- 30% of buildings have zero heating capacity (electric-only, heat pumps) — lookups fail on mixed cells
- HVAC system type drives 3× variation (residential forced air = 0.15 kBtu/h/sf vs VAV chiller = 0.03)
- XGB captures all 25 feature interactions; lookup tables can't handle HVAC type dimension without extreme sparsity

**Why XGB models for rates instead of rate tables:**
- Within-state CV is only 0.17 — rates are 90% geographic
- But cluster_name (97 clusters) is already a model feature, capturing regional rate variation
- Models also capture demand charge effects that ComStock simulated but a flat $/kWh table would miss
- Cheap to train (baseline-only, 4 models)

### Upgrade Models (per-upgrade, run per applicable measure)

| Purpose | Target | Count |
|---------|--------|-------|
| ComStock post-upgrade EUI | EUI by fuel type (5 fuels × 65 upgrades) | 325 |
| ResStock post-upgrade EUI | EUI by fuel type (4 fuels × 32 upgrades) | 128 |

**Note:** ResStock needs its own set of baseline sizing + rate models (9 additional models). Total across both datasets: ~152 baseline + auxiliary models, ~453 upgrade models ≈ **~605 total models** when counting per-fuel-type upgrade models.

**Correction to earlier estimate:** The 152 count assumed 1 model per upgrade. With 5 fuel types per ComStock upgrade and 4 per ResStock upgrade, the real count is higher. Each model is small (~1-5 MB) and trains fast.

---

## 3. Inference Flow

```
User Input (building characteristics + zipcode)
  │
  ▼
1. PREPROCESS
   ├── Validate inputs
   ├── Derive climate_zone + cluster_name from zipcode
   ├── Derive state from zipcode (for regional cost adjustment)
   ├── Impute missing optional fields (from building_type + vintage distributions)
   └── Encode features (label encoding for XGBoost)
  │
  ▼
2. BASELINE PREDICTION (run once)
   ├── 5 baseline EUI models → electricity, gas, fuel_oil, propane, district_heating (kWh/ft²)
   ├── 5 sizing models → heating_cap, cooling_cap, wall_area, roof_area, window_area
   └── 4 rate models → effective $/kWh per fuel type
  │
  ▼
3. UPGRADE PREDICTION (per applicable measure)
   ├── Check applicability rules for all 65/32 measures
   ├── For each applicable upgrade:
   │   ├── Run 5 (or 4) fuel-type EUI models → post-upgrade EUI by fuel
   │   ├── Savings by fuel = baseline_fuel_eui - post_upgrade_fuel_eui
   │   └── Total savings = sum of fuel-type savings
  │
  ▼
4. COST CALCULATION (per applicable measure)
   ├── Look up unit cost from upgrade_cost_lookup.json
   ├── Based on cost_basis:
   │   ├── $/ft² floor    → cost_mid × sqft
   │   ├── $/kBtu/h heat  → cost_mid × predicted_heating_capacity
   │   ├── $/kBtu/h cool  → cost_mid × predicted_cooling_capacity × 12 (tons→kBtu/h)
   │   ├── $/ft² wall     → cost_mid × predicted_wall_area
   │   ├── $/ft² roof     → cost_mid × predicted_roof_area
   │   ├── $/ft² glazing  → cost_mid × predicted_window_area
   │   ├── $/unit          → cost_mid (ResStock per dwelling unit)
   │   ├── $/watt_dc      → cost_mid × predicted_roof_area × panel_density
   │   └── mixed           → sum of component upgrade costs
   ├── Apply regional adjustment: total × regional_adjustments[state]
   └── Compute $/sf = total / sqft
  │
  ▼
5. BILL SAVINGS & PAYBACK
   ├── Bill savings = Σ(predicted_rate[fuel] × energy_savings[fuel]) per upgrade
   ├── Simple payback = installed_cost_per_sf / bill_savings_per_sf
   └── Emissions reduction from fuel-type savings × emission factors
  │
  ▼
6. FORMAT RESPONSE
   └── Sort measures by savings_pct descending, include non-applicable with null savings
```

---

## 4. API Contract

### `POST /assess`

```json
// Request
{
  "buildings": [{
    "building_type": "Office",
    "sqft": 50000,
    "num_stories": 3,
    "zipcode": "20001",
    "year_built": 1985,
    "heating_fuel": "NaturalGas",
    "dhw_fuel": "NaturalGas",
    "hvac_system_type": "VAV_chiller_boiler",
    "wall_construction": null,
    "window_type": null,
    "lighting_type": null
  }]
}

// Response
{
  "results": [{
    "building_index": 0,
    "baseline": {
      "total_eui_kbtu_sf": 85.2,
      "eui_by_fuel": {
        "electricity": 42.1,
        "natural_gas": 38.5,
        "district_heating": 0.0,
        "other_fuel": 4.6
      },
      "emissions_kg_co2e_per_sf": 12.3
    },
    "measures": [{
      "upgrade_id": 1,
      "name": "Variable Speed HP RTU, Electric Backup",
      "category": "hvac_hp_rtu",
      "applicable": true,
      "post_upgrade_eui_kbtu_sf": 61.4,
      "savings_kbtu_sf": 23.8,
      "savings_pct": 27.9,
      "cost": {
        "installed_cost_per_sf": 8.80,
        "installed_cost_total": 440000,
        "cost_range": { "low": 8.48, "high": 8.80 },
        "useful_life_years": 21,
        "regional_factor": 1.08,
        "confidence": "high"
      },
      "utility_bill_savings_per_sf": 1.42,
      "simple_payback_years": 6.2,
      "emissions_reduction_pct": 31.5
    }],
    "input_summary": {
      "climate_zone": "4A",
      "cluster_name": "Mid-Atlantic Urban",
      "state": "DC",
      "imputed_fields": ["dhw_fuel", "hvac_system_type"]
    }
  }]
}
```

### `GET /metadata`

Returns valid dropdown values for the frontend (building types, fuel types, HVAC system types, etc.).

---

## 5. Backend Structure

```
backend/
  app/
    main.py                     # FastAPI app, CORS, load models at startup
    api/
      routes.py                 # POST /assess, GET /metadata
    schemas/
      request.py                # BuildingInput pydantic model
      response.py               # AssessmentResult pydantic model
    services/
      assessment.py             # Orchestrator: preprocess → predict → cost → format
      preprocessor.py           # Input validation, imputation, feature encoding
      cost_calculator.py        # Unit cost × predicted capacity/area → $/sf
    inference/
      model_manager.py          # Load/cache XGB models at startup, run predictions
      applicability.py          # Rules engine: which measures apply
    data/
      upgrade_cost_lookup.json  # Unit costs by upgrade
      regional_adjustments.json # State-level RSMeans multipliers
```

**Key design decisions:**
- Two endpoints only: `/assess` (main) and `/metadata` (dropdowns)
- Models loaded once at startup, held in memory (~1-5 MB each)
- Cost calculation is a separate service — costs updatable without retraining energy models
- Preprocessor reuses existing feature encoding logic from training pipeline

---

## 6. Frontend Structure

```
frontend/
  partner-components/           # Copied from SiteLynx_Clone repo (local dependency)
  src/
    App.vue                     # Root — PLayout wrapper
    main.ts                     # Vue app setup, import partner styles
    views/
      AssessmentView.vue        # Single view for V1
    components/
      BuildingForm.vue          # Required + optional fields
      AdvancedDetails.vue       # Collapsible detailed fields
      BaselineSummary.vue       # EUI headline numbers + fuel breakdown
      MeasuresTable.vue         # Sortable PTable of upgrade results
    composables/
      useAssessment.ts          # API call, loading/error state, response data
    types/
      assessment.ts             # TypeScript interfaces matching API schemas
    config/
      dropdowns.ts              # Valid values for form selects (from GET /metadata)
```

**Tech stack:** Vue 3 + TypeScript + Vite + Tailwind CSS
**Component library:** `@partnerdevops/partner-components` (copied into repo as `frontend/partner-components/`, referenced via local file dependency)
**No router needed for V1** — single view

### Partner Components Used

| UI Element | Partner Component |
|-----------|-------------------|
| Page layout | PLayout (header only, no side panels) |
| Text fields (zipcode, etc.) | PTextInput |
| Number fields (sqft, stories, year) | PNumericInput |
| Fuel type selection | PRadioGroup |
| Submit button | PButton |
| Results table | PTable + PTableHead (sortable) + PTableRow + PTableCell |
| Category badges | PBadge (color-coded by category) |
| Confidence indicator | PBadge (green/yellow/orange) |
| Advanced section toggle | PButton (text variant) |

---

## 7. User Input Fields

### Always Visible (Required + Common Optional)

| Field | Component | Required? | Notes |
|-------|-----------|-----------|-------|
| Building Type | Dropdown (15 options) | Required | Routes to ComStock vs ResStock |
| Square Footage | PNumericInput | Required | |
| Number of Stories | PNumericInput | Required | |
| Zipcode | PTextInput | Required | Derives climate_zone, cluster_name, state |
| Year Built | PNumericInput | Optional | Imputed from building_type distribution |
| Heating Fuel | Dropdown | Optional | Imputed |
| DHW Fuel | Dropdown | Optional | Imputed |
| HVAC System Type | Dropdown | Optional | Imputed |

### Collapsible "Advanced Details"

| Field | Component | Notes |
|-------|-----------|-------|
| Wall Construction Type | Dropdown (4 options) | Imputed |
| Window Type | Dropdown (12 options) | Imputed |
| Window-to-Wall Ratio | Dropdown (6 bins) | Imputed |
| Lighting Type | Dropdown (5 generations) | Imputed |
| Operating Hours | PNumericInput | Imputed |

---

## 8. V1 Results Table Columns

| Column | Sortable | Notes |
|--------|----------|-------|
| Measure Name | No | Text |
| Category | No | PBadge, color-coded |
| Savings (kBtu/sf) | Yes | Baseline - post-upgrade |
| Savings (%) | Yes | Default sort descending |
| Est. Cost ($/sf) | Yes | From cost calculator |
| Payback (yrs) | Yes | cost / bill_savings |
| Confidence | No | PBadge (high/medium/low) |

Non-applicable measures included with `applicable: false` and grayed out — visible but clearly marked.

---

## 9. Version Roadmap

### V1 — Minimal Assessment Tool
- Single-page: form → sortable results table
- 8 visible input fields + 5 collapsible advanced fields
- Baseline EUI summary above table
- Sortable measures table with cost/payback
- Non-applicable measures shown as grayed out

### V2 — Visual Context & Actionability
- **Fuel-type EUI breakdown chart** — stacked/grouped bar: baseline vs post-upgrade by fuel, updates on measure row click
- **End use breakdown chart** - pie chart showing the baseline energy usage disaggregrated by end-use (heating, cooling, lighting, etc). may require new inference models
- **Top measures comparison chart** — horizontal bar: top 10 by savings, secondary axis for payback
- **Export to Excel** — table data + baseline summary as formatted .xlsx
- **Measure detail panel** — click row → expandable section with full cost breakdown, fuel-type savings, data sources
- **Input validation feedback** — real-time: "Zipcode → Climate Zone 4A, DC metro" + warnings for edge cases

### V3 — Full-Featured (Future)
- Bulk upload (multiple buildings)
- Measure packages / custom combinations
- Side-by-side building comparison
- PDF report generation
- User accounts / saved assessments
- Rails frontend replaces Vue app

---

## 10. Cost Calculation Details

### Cost Basis Resolution

The `upgrade_cost_lookup.json` has 11 different cost bases across 97 upgrades:

| Cost Basis | Count | Resolution Method |
|-----------|-------|-------------------|
| `$/ft² floor` | 21 | `cost × sqft` (trivial) |
| `$/unit` | 20 | Per dwelling unit (ResStock) |
| `$/kBtu/h heating` | 19 | `cost × XGB_predicted_heating_capacity` |
| `mixed` | 18 | Sum of component upgrade costs |
| `$/ft² wall` | 5 | `cost × XGB_predicted_wall_area` |
| `$/ft² glazing` | 4 | `cost × XGB_predicted_window_area` |
| `$/kBtu/h cooling` | 3 | `cost × XGB_predicted_cooling_capacity × 12` |
| `$/ft² roof` | 2 | `cost × XGB_predicted_roof_area` |
| `$/watt_dc` | 2 | `cost × predicted_roof_area × panel_density_w_per_sf` |
| `$/ft² duct` | 1 | `cost × estimated_duct_area` (from sqft heuristic) |
| `$/kBtu/h cooking` | 1 | `cost × cooking_capacity` (building_type heuristic) |

### Sizing Model Training Data (ComStock Baseline)

| Target | Column | Unit | Coverage |
|--------|--------|------|----------|
| Heating capacity | `out.params.heating_equipment..kbtu_per_hr` | kBtu/hr | 100% (30% are zero — electric/HP) |
| Cooling capacity | `out.params.cooling_equipment_capacity..tons` | tons | 100% |
| Wall area | `out.params.ext_wall_area..m2` | m² → ft² | 100% |
| Roof area | `out.params.ext_roof_area..m2` | m² → ft² | 100% |
| Window area | `out.params.ext_window_area..m2` | m² → ft² | 100% |

ResStock equivalents: `out.params.size_heating_system_primary..kbtu_per_hr`, `out.params.size_cooling_system_primary..kbtu_per_hr`, `out.params.wall_area_above_grade_conditioned..ft2`, `out.params.roof_area..ft2`, `out.params.window_area..ft2`

### Rate Model Training Data

| Target | Derived from | Median | Range |
|--------|-------------|--------|-------|
| Electricity rate | `electricity_bill_mean_intensity / (electricity_consumption / sqft)` | $0.108/kWh | $0.015 – $0.67 |
| Natural gas rate | `gas_bill_state_avg_intensity / (gas_consumption / sqft)` | $0.038/kWh | $0.024 – $0.16 |
| Fuel oil rate | Same pattern | TBD | TBD |
| Propane rate | Same pattern | TBD | TBD |

**Important:** Use `_intensity..usd_per_ft2` bill columns (per-building values), NOT the non-intensity columns (which are stock-weighted and inflated by geographic representation weights).

### Regional Cost Adjustment

Applied at inference time: `adjusted_cost = national_cost × regional_adjustments[state]`

Source: `Resources/scout/scout/supporting_data/convert_data/loc_cost_adj.csv` (51 entries, RSMeans-derived)
Range: 0.81 (FL) to 1.36 (NY) for commercial; 0.83 (AL) to 1.17 (AK) for residential

---

## 11. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Vue 3 Frontend                       │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────┐  │
│  │ Building  │───▶│  useAssessment │───▶│  Measures    │  │
│  │ Form      │    │  composable   │    │  Table +     │  │
│  │           │    │  (API call)   │    │  Summary     │  │
│  └──────────┘    └───────┬───────┘    └──────────────┘  │
└──────────────────────────┼──────────────────────────────┘
                           │ POST /assess
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                        │
│                                                         │
│  routes.py → assessment.py (orchestrator)                │
│                    │                                    │
│         ┌──────────┼──────────┐                         │
│         ▼          ▼          ▼                         │
│   preprocessor  model_mgr  cost_calc                   │
│   (validate,    (load/run   (unit cost ×               │
│    impute,      XGB models)  predicted                  │
│    encode)                   capacity)                  │
│                                                         │
│  Model groups loaded at startup:                        │
│  ├── 5 baseline EUI models                             │
│  ├── 5 sizing models (capacity, areas)                 │
│  ├── 4 rate models ($/kWh by fuel)                     │
│  ├── 325 ComStock upgrade EUI models (65 × 5 fuels)   │
│  └── 128 ResStock upgrade EUI models (32 × 4 fuels)   │
│                                                         │
│  Static data:                                           │
│  ├── upgrade_cost_lookup.json (unit costs)              │
│  └── regional_adjustments.json (state multipliers)      │
└─────────────────────────────────────────────────────────┘
```
