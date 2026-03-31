# BuildingStock Energy Estimation — Technical Reference

## Overview

This application predicts building **Energy Use Intensity (EUI)** and recommends energy efficiency upgrades with cost/savings estimates and payback periods. It is designed for single-building energy assessments of commercial and multi-family residential buildings across the United States.

The tool uses **XGBoost machine learning models** trained on NREL's building energy simulation datasets:

- **ComStock 2025 Release 3** — Commercial buildings (13 building types)
- **ResStock 2025 Release 1** — Residential buildings (multi-family 4+ units)

---

## Data Sources

### NREL ComStock

ComStock is a model of the U.S. commercial building stock that simulates energy consumption for ~350,000 representative buildings across all U.S. counties, climate zones, and building types.

- **Technical Reference**: https://www.nlr.gov/buildings/comstock.html
- **Documentation Hub**: https://natlabrockies.github.io/ComStock.github.io/
- **2025 R3 Datasets**: https://comstock.nlr.gov/page/datasets
- **Upgrade Measures**: https://natlabrockies.github.io/ComStock.github.io/docs/upgrade_measures/upgrade_measures.html
- **Data Viewer**: https://comstock.nlr.gov/
- **Dataset on OEDI**: https://data.openei.org/submissions/4520
- **GitHub Repository**: https://github.com/NREL/ComStock

ComStock covers 13 building type groups: Education, Food Sales, Food Service, Healthcare, Lodging, Mercantile/Retail, Mixed Use, Office, Other, Public Assembly, Religious Worship, Warehouse and Storage, and Unassigned.

### NREL ResStock

ResStock models the U.S. residential building stock with ~550,000 representative dwelling units. This application uses the **multi-family 4+ unit** subset only.

- **Technical Reference**: https://www.nlr.gov/buildings/resstock
- **Documentation Hub**: https://natlabrockies.github.io/ResStock.github.io/
- **2025 R1 Datasets**: https://resstock.nlr.gov/datasets
- **2025 R1 README (PDF)**: https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/resstock_amy2018_release_1/README_resstock_20251.pdf
- **Upgrade Measures**: https://natlabrockies.github.io/ResStock.github.io/docs/upgrade_measures.html
- **Data Viewer**: https://resstock.nlr.gov/
- **Dataset on OEDI**: https://data.openei.org/submissions/5959
- **GitHub Repository**: https://github.com/NREL/resstock

---

## Assessment Pipeline

The application processes a building assessment through the following steps:

```
1. USER INPUT
   Building type, square footage, stories, zipcode, year built,
   heating fuel, HVAC system type, and optional fields

2. PREPROCESSING (preprocessor.py)
   - Validate inputs (ranges, valid types, zipcode format)
   - Determine dataset: ComStock (commercial) or ResStock (multi-family)
   - Derive location data from zipcode: state, climate zone, HDD/CDD, eGRID region
   - Impute missing optional fields using ML models or building-type defaults
   - Map user-facing values to training-data values
   - Derive features: floor_plate_sqft, energy codes, HVAC sub-features

3. BASELINE PREDICTION (model_manager.py)
   - XGBoost ensemble (XGB + LightGBM + CatBoost, equal-weight blend)
   - Predicts EUI (kWh/ft²) per fuel type:
     • Electricity, Natural Gas, Fuel Oil, Propane (both datasets)
     • District Heating (ComStock only)

4. UPGRADE SAVINGS PREDICTION (per applicable upgrade, parallelized)
   - Applicability check: rule-based eligibility per upgrade
   - Delta model predicts energy SAVINGS per fuel type (not absolute post-upgrade EUI)
   - Per-fuel savings clamped ≥ 0 (upgrade cannot increase consumption)
   - Post-upgrade EUI = baseline EUI - predicted savings

5. COST ESTIMATION
   - XGBoost sizing models predict equipment capacity (kBtu/h) or area (ft²)
   - Installed cost = predicted capacity/area × unit cost from lookup table
   - Regional adjustment applied by state (RSMeans-based multipliers)

6. UTILITY BILL SAVINGS
   - XGBoost rate models predict effective utility rates ($/kWh, $/therm)
   - Annual bill savings = energy savings × predicted rates
   - Payback = installed cost / annual bill savings

7. EMISSIONS CALCULATION
   - Electricity: region-specific eGRID emission factors (kg CO2e/kWh)
   - Fossil fuels: fixed emission factors (kg CO2e/kBtu)
   - Emissions reduction % = (baseline emissions - post-upgrade emissions) / baseline

8. RESPONSE
   - Measures sorted: applicable (descending by savings %) then non-applicable
   - Includes per-fuel breakdowns, costs, payback, emissions, useful life
```

---

## Machine Learning Models

### Model Architecture

All models use **XGBoost** with native categorical feature support. An ensemble infrastructure exists for blending XGBoost + LightGBM + CatBoost predictions with equal weights.

### Delta/Savings Approach

A key design decision: **upgrade models predict energy savings directly**, not absolute post-upgrade EUI.

**Why?** When baseline and upgrade models are trained independently, compounding prediction noise can produce "negative savings" (where the model predicts an upgrade increases energy use). By training on the delta (`baseline_EUI - upgrade_EUI`), the model learns the relationship directly — e.g., "duct sealing saves X kBtu/ft² in climate zone Y with a gas furnace."

Reference: `docs/plans/2026-03-08-delta-savings-models.md`

### Training Data

Models are trained on paired baseline/upgrade simulations from NREL datasets:

| Dataset | Buildings | Upgrades | Fuel Types | Models |
|---------|-----------|----------|------------|--------|
| ComStock 2025 R3 | ~18,000-40,000 paired samples | 65 individual + packages | 5 (elec, gas, oil, propane, district) | ~330 upgrade models |
| ResStock 2025 R1 | ~67,000-75,000 paired samples | 32 individual + packages | 4 (elec, gas, oil, propane) | ~128 upgrade models |

### Model Accuracy

#### ComStock (Test Set Performance)

| Fuel Type | Mean MAE (kBtu/ft²) | Mean R² |
|-----------|---------------------|---------|
| Electricity | 12.04 | 0.817 |
| Natural Gas | 9.93 | 0.662 |
| Fuel Oil | 0.60 | 0.832 |
| Propane | 0.72 | 0.891 |
| District Heating | 0.24 | 0.836 |

#### ResStock (Test Set Performance)

| Fuel Type | Mean MAE (kBtu/ft²) | Mean R² |
|-----------|---------------------|---------|
| Electricity | 1.45 | 0.733 |
| Natural Gas | 0.58 | 0.761 |
| Fuel Oil | 0.06 | 0.918 |
| Propane | 0.02 | 0.796 |

Note: Minor fuel types (fuel oil, propane, district heating) show higher R² due to less variability in consumption patterns. ResStock MAE is lower in absolute terms because residential buildings have lower EUI than commercial.

### Feature Engineering

Models use 37-41 features covering:

- **Building characteristics**: type, square footage, stories, vintage, aspect ratio
- **Climate/location**: ASHRAE climate zone, geographic cluster, HDD/CDD (heating/cooling degree days)
- **HVAC systems**: heating/cooling type, fuel, efficiency, ventilation, category
- **Building envelope**: wall construction, window type, insulation, airtightness, window-to-wall ratio
- **Operations**: thermostat setpoints/setbacks, operating hours, lighting type
- **Baseline energy**: pre-computed baseline EUI per fuel (conditions savings predictions on baseline)
- **Energy codes** (ComStock): code followed during last HVAC/roof/wall/water heater replacement

See the **ComStock_ResStock_Model_Features.xlsx** workbook for the full feature list, descriptions, valid values, and excluded column rationale.

### Hyperparameter Tuning

Models are tuned using **Optuna** (50 trials, 5-fold cross-validation) with tune groups — representative upgrades are tuned first, and optimal parameters are applied to similar measures within each group:

**ComStock Tune Groups**: baseline, hvac (1-31), demand_flex (32-42), lighting (43-44), other (45-47), envelope (48-53), packages (54-65)

**ResStock Tune Groups**: baseline, hvac (1-8), water_heating (9-10), envelope (11-17, 29-30), packages (18, 31-32), ev (19-23), demand_flex (24-28)

---

## Cost Data Methodology

Installed costs are sourced from a hierarchy of references, normalized to **2023 dollars** using BLS CPI-U data:

### Primary Sources

| Source | Coverage | Notes |
|--------|----------|-------|
| **NREL Scout ECM Definitions** | ~97 commercial + ~112 residential measures | Machine-readable JSON with full citations; includes installed cost, cost units, product lifetime |
| **NREL REMDB 2024** | 142 residential measures | Regression models for Low/Mid/High cost by performance level |
| **RSMeans City Cost Indices (via Scout)** | 50 states + DC | State-level regional adjustment multipliers, separate for residential vs. commercial |
| **BLS CPI-U** | 1947-present | Dollar-year normalization to 2023 |

### Underlying Research Sources

| Source | What It Covers | Year |
|--------|---------------|------|
| EIA Updated Buildings Sector Equipment Costs | HVAC, water heating, lighting, cooking, refrigeration | 2023 |
| NREL Annual Technology Baseline (ATB) | Residential/commercial HVAC, water heating, PV/battery | 2023 |
| RSMeans 2022 | Envelope (windows, walls, roofs) | 2022 |
| PNNL ASHRAE 90.1 Studies | Lighting, envelope, HVAC by building type | 2020 |
| DOE BTO Technology Roadmaps | Advanced envelope (windows, walls, air sealing) | 2022 |

### Cost Basis Units (vary by measure type)

- **HVAC equipment**: $/kBtu/h (heating or cooling capacity)
- **Envelope/lighting**: $/ft² (floor area or component area)
- **Solar PV**: $/Watt DC
- **Controls/demand flexibility**: $/ft² floor area

### Confidence Levels

Each cost estimate includes a confidence rating:

- **High**: Directly sourced from Scout ECM with well-cited primary data
- **Medium**: REMDB regression model or adapted from closely related Scout ECM
- **Low**: Gap-filled using industry estimates, EIA reports, or PNNL studies

### Gap-Filled Measures

~36 of 97 total upgrades required supplementary sources beyond Scout:
- VRF systems (ComStock 12-13): EIA Equipment Costs
- DOAS + Minisplits (ComStock 14): EIA report
- HVAC Controls (ComStock 19-26): PNNL ASHRAE 90.1 studies
- Demand Flexibility (ComStock 32-42): Thermostat/BMS programming estimates
- PV/Battery (ComStock 46-47): NREL ATB 2024
- EV Charging (ResStock 19-23): REMDB EV charger data
- Ideal Loads (ComStock 27): Excluded — theoretical benchmark only

See **Upgrade_Cost_Data.xlsx** for the full cost table with per-upgrade sources and confidence levels.

Reference: `docs/cost-data-research-plan.md`, `scripts/build_cost_lookup.py`

---

## Upgrade Measure References

### ComStock Upgrades (65 measures)

Individual NREL ComStock measure write-ups are available at:
https://natlabrockies.github.io/ComStock.github.io/docs/upgrade_measures/upgrade_measures.html

Key measure categories:
- **HVAC Heat Pumps** (1-10): HP-RTU variants replacing packaged rooftop units
- **Advanced RTU** (11): High-efficiency rooftop unit controls
- **VRF** (12-13): Variable refrigerant flow systems
- **DOAS + Minisplits** (14): Dedicated outdoor air + ductless heat pumps
- **Boiler Upgrades** (15-18): Condensing boilers, HP boilers, electric boilers
- **HVAC Controls** (19-26): Economizers, DCV, energy recovery, fan control, setbacks, VFD pumps
- **Ideal Loads** (27): Theoretical benchmark (excluded from cost analysis)
- **Ground Source Heat Pumps** (28-30): Hydronic, packaged, and console GHP variants
- **Chiller Replacement** (31): High-efficiency chiller upgrade
- **Demand Flexibility** (32-42): Load shifting, GEB strategies
- **Lighting** (43-44): LED upgrades
- **Electric Kitchen** (45): Induction cooking equipment
- **PV/Battery** (46-47): Solar photovoltaics and battery storage
- **Envelope** (48-53): Wall insulation, roof insulation, windows, window film
- **Packages** (54-65): Bundled combinations of individual measures

### ResStock Upgrades (32 measures)

Key measure categories:
- **Furnace Upgrades** (1-2): 95% AFUE gas and propane/oil furnaces
- **Heat Pumps** (3-8): ASHP, cold-climate ASHP, dual fuel, GSHP variants
- **Water Heating** (9-10): Heat pump water heater, gas tankless
- **Envelope** (11-17): Air sealing, attic insulation, duct sealing, wall insulation, windows
- **Packages** (18, 31-32): Bundled envelope + HVAC measures
- **EV Charging** (19-23): Electric vehicle charging infrastructure
- **Demand Flexibility** (24-28): Smart thermostats, load management
- **Additional Envelope** (29-30): Crawlspace/basement insulation

See **Applicability_Rules.xlsx** for which upgrades apply to which building configurations.

---

## Emissions Methodology

### Electricity Emissions

Electricity emission factors are **region-specific**, sourced from the EPA's **eGRID** (Emissions & Generation Resource Integrated Database). Each building's zipcode maps to an eGRID subregion, which determines the kg CO2e per kWh of electricity consumed.

These factors vary significantly by region (reflecting the local grid's fuel mix):
- Clean grids (e.g., Pacific Northwest): ~0.10-0.25 kg CO2e/kWh
- Coal-heavy grids (e.g., parts of Midwest): ~0.50-0.80 kg CO2e/kWh

### Fossil Fuel Emissions

Fixed national emission factors (kg CO2e per kBtu):

| Fuel | kg CO2e/kBtu | Source |
|------|-------------|--------|
| Natural Gas | 0.05311 | EPA GHG Emission Factors Hub |
| Propane | 0.06195 | EPA GHG Emission Factors Hub |
| Fuel Oil (#2) | 0.07421 | EPA GHG Emission Factors Hub |
| District Heating | 0.06640 | EPA GHG Emission Factors Hub |

See **Emissions_and_Constants.xlsx** for energy conversion constants and a sample of eGRID emission factors by state.

---

## Key Design Decisions

The following design decisions were documented in planning documents during development:

### 1. Delta/Savings Models (not independent baseline + upgrade models)
Training models to predict `baseline_EUI - upgrade_EUI` directly eliminates compounding noise from two independent predictions. This produces more reliable savings estimates and naturally avoids negative savings.
> Reference: `docs/plans/2026-03-08-delta-savings-models.md`

### 2. Baseline EUI as a Model Feature
Baseline EUI per fuel type is included as an input feature for upgrade models. This teaches the model that savings magnitude depends on how much energy the building uses at baseline — a building with high gas consumption will save more from a furnace upgrade.
> Reference: `docs/superpowers/plans/2026-03-19-ensemble-and-feature-engineering.md`

### 3. Cost Estimation via XGBoost Sizing Models (not lookup tables)
Rather than using fixed cost-per-sqft lookup tables, the app uses XGBoost models to predict equipment capacity (kBtu/h) or component area (ft²), then multiplies by unit costs. This accounts for climate, building size, and system type in cost estimation.
> Reference: `docs/plans/2026-03-08-app-architecture-design.md`

### 4. Rule-Based Applicability (aligned with NREL measure definitions)
Upgrade eligibility is determined by hard rules matching NREL's own applicability logic — e.g., HP-RTU requires Small Packaged Unit HVAC category, boiler upgrades require an existing boiler, LED upgrades excluded if already LED.
> Reference: `docs/plans/2026-03-09-comstock-applicability-rules.md`

### 5. Geographic Clustering (not per-county models)
Rather than using county-level identifiers (which would create ~3,000 sparse categories), buildings are grouped into ~6-7 regional clusters. This reduces overfitting while preserving meaningful geographic variation.

### 6. HDD/CDD from Lookup Tables (not simulation outputs)
Heating and Cooling Degree Days are derived from cluster-level climate data, not from individual simulation weather files. This is more stable and practical for user-facing predictions.
> Reference: `docs/superpowers/plans/2026-03-19-ensemble-and-feature-engineering.md`

### 7. Per-Fuel-Type Models (not multi-target)
Each fuel type has its own model because electricity savings and gas savings for the same upgrade can behave very differently. This allows independent optimization and better interpretability for utility program analysis.

### 8. ML-Based Imputation for Missing Fields
When users don't provide optional fields (HVAC type, wall construction, etc.), XGBoost classifier models predict likely values based on building type, climate zone, vintage, and other known characteristics — rather than using static defaults.
> Reference: `docs/plans/2026-03-09-imputation-integration-and-assumptions-panel.md`

---

## Companion Workbooks

| File | Contents |
|------|----------|
| **ComStock_ResStock_Model_Features.xlsx** | All model input features (selected + excluded), field mappings, imputation defaults |
| **Upgrade_Cost_Data.xlsx** | Full cost table with sources, confidence levels, useful life |
| **Applicability_Rules.xlsx** | Which upgrades apply to which building configurations |
| **Emissions_and_Constants.xlsx** | Energy conversion constants, emission factors, model accuracy metrics |

---

## Questions or Feedback

If you have questions about the data, methodology, or model assumptions, or if you spot something that doesn't match your domain expertise, please flag it. This tool is designed to be validated by energy professionals — your review is the point.
