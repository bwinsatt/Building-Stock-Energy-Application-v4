# Energy Audit Tool - Design Document

**Date:** 2026-03-07
**Status:** In Progress - Phase 1 (Data Science & Model Training)

---

## 1. Project Overview

### What Exists Today
A Python desktop pipeline that predicts baseline Energy Use Intensity (EUI) for commercial buildings using XGBoost models trained on NREL's ComStock and ResStock 2024.2 datasets.

**Current flow:** User uploads Excel with building portfolio data -> PreProcessor cleans/bins/imputes -> XGBoost models predict EUI by fuel type -> Carbon emissions calculated -> Output Excel.

**Current model inputs (9 features, all categorical):**
- `in.building_type` (15 types: SmallOffice, RetailStripmall, Multi-Family, etc.)
- `floor_area` (binned: <25,000 | 25,000-200,000 | >200,000)
- `climate_zone_ashrae_2006` (15 zones)
- `in.heating_fuel` (5: Electricity, NaturalGas, Propane, FuelOil, DistrictHeating)
- `in.water_heater_fuel` (5 types)
- `in.hvac_category` (2: Central Plant, Unitary/Split/DX)
- `num_of_stories` (binned: 1-3 | 4-7 | 8+)
- `year_built` (binned: <1946 | 1946-1959 | 1960-1979 | 1980-1999 | 2000-2009 | >2010)
- `cluster_name` (97 geographic clusters derived from zipcode)

**Current model outputs:** EUI (kBtu/sf) per fuel type (electricity, natural gas, district heating, other fuel); total site EUI = sum of fuel-type EUIs. Optionally 25th/75th percentile quantiles.

### What We're Building
An "energy audit light" web application that:
1. Predicts baseline energy usage for a single building (enhancing the current capability)
2. Predicts energy savings for each of ComStock's 65 upgrade measures and ResStock's 32 measures
3. Shows which measures are applicable and ranks them by impact
4. Eventually serves as an API consumed by a Ruby on Rails application

### Target Users
- **V1:** Energy consultants doing quick assessments for clients
- **Future:** Client self-service (must be simple enough for non-technical users)

---

## 2. Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single vs bulk | API accepts array (1 or many buildings); v1 UI is single-building only | Backend handles both from day one; bulk UI is fast follow |
| Savings prediction approach | Train new XGBoost models on ComStock/ResStock upgrade results | Most accurate; datasets provide the training data directly |
| Model architecture | **One model per upgrade per fuel type** (330 ComStock + 132 ResStock = 462 models) | Per-measure models outperform multi-measure; per-fuel-type ensures parts sum to total |
| ComStock vs ResStock | **Separate model sets** - ComStock for commercial, ResStock for multi-family (4+ units) | Different measures, features, energy representation, and fuel types |
| Measure selection UX | Pre-built packages + individual mix-and-match, with recommendations by impact | Analyze all applicable measures, rank by savings |
| Training weights | **Unweighted training** (deduplicate by bldg_id, discard weights) | Validated: unweighted MAE=1.28% vs weighted MAE=1.39% for per-building prediction |
| Dataset | ComStock 2025 Release 3 (65 measures) + ResStock 2025 Release 1 (32 measures) | Latest releases, most measures available |
| Frontend | Vue 3 + partner-components (copied into repo) | Brand-consistent throwaway; eventually replaced by Rails frontend. See `docs/plans/2026-03-08-app-architecture-design.md` |
| Cost estimation | XGB models predict building capacity/area; multiply by unit costs | Lookup tables had CV=0.59+ within cells; HVAC system type drives 3× variance |
| Utility bill savings | XGB models predict effective $/kWh rate per fuel; multiply by energy savings | Captures demand charges, tiered rates from ComStock simulations; rate is 90% geographic (within-state CV=0.17) |
| Backend | FastAPI, designed as a proper API from day one | Will be consumed by Rails app in future |
| Data source | National aggregate datasets | Same building-level granularity as state-level, single download |
| Output units | **kBtu/sf** (US standard) | Train in kWh/ft² (native to ComStock), convert at output: kBtu/sf = kWh/ft² × 3.412 |
| Cost data source | **NREL Scout ECMs + REMDB** (primary), with gap-filling from EIA/TRMs | Scout covers ~70/97 upgrades with structured JSON cost data; REMDB adds regression-based residential costs; state-level regional adjustment via RSMeans multipliers |
| Cost data approach | Pre-built lookup table (`Resources/upgrade_cost_lookup.json`) populated from Scout + REMDB, applied at inference time | Avoids embedding cost assumptions in models; costs are transparent and updatable independently of energy models |

---

## 3. Data Sources

### ComStock 2025 Release 3 (Downloaded)
- **Location:** `ComStock/raw_data/`
- **Files:** 66 parquet files (upgrade0 = baseline, upgrade1-65 = measures)
- **Size:** ~39 GB total, ~500-680 MB per file
- **Raw rows:** 149,272 per file → **91,464 unique buildings** after deduplication (duplicates have same features/EUI, different weights for geographic representation)
- **Columns:** 1,306 per file (66 input "in." columns, ~1,240 output/applicability columns)
- **S3 path:** `s3://oedi-data-lake/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/comstock_amy2018_release_3/metadata_and_annual_results_aggregates/national/full/parquet/`

### ResStock 2025 Release 1 (Downloaded & Explored)
- **Location:** `ResStock/raw_data/`
- **Files:** 33 parquet files (upgrade0 = baseline, upgrade1-32 = measures)
- **Size:** ~23 GB total, 771 columns per file
- **Raw rows:** 549,971 per file (all unique bldg_ids — no deduplication needed, unlike ComStock)
- **S3 path:** `s3://oedi-data-lake/.../2025/resstock_amy2018_release_1/metadata_and_annual_results/national/full/parquet/`
- Filtered to **multi-family only** (`in.geometry_building_number_units_mf >= 4`): **117,815 units**
- After excluding vacant units: **101,185 occupied units** available for training
- **Per-unit energy data:** Each row represents one dwelling unit, not a whole building. EUI is the same at unit or building level (energy/sqft scales proportionally). Total building energy = unit energy × number of units. Total building GFA = unit sqft × number of units (existing cleanup script already does this).
- **Cluster mapping:** `in.county` column uses GISJOIN format (e.g., `G0600370`) — 3,107 of 3,139 counties match `nhgis_county_gisjoin` in `ComStock/spatial_tract_lookup_table.csv`. The 32 non-matching counties are all Alaska/Hawaii using "state, name" format (e.g., "HI, Honolulu County") — need manual mapping or fallback.
- **No simulation failures:** All 549,971 rows have `completed_status = Success` across all upgrade files.
- **Mean EUI (MF occupied):** 41.5 kBtu/sf (vs ComStock commercial mean of 116 kBtu/sf)

### CBECS 2018 Validation Dataset
- **Location:** `Validation/CBECS/`
- **Source:** CBECS 2018 Public Use Microdata (EIA survey of real US commercial buildings)
- **Files:**
  - `cbecs2018_final_public.csv` — Raw CBECS microdata (6,436 buildings)
  - `cbecs2018_mapped_for_xgb.csv` — Mapped to XGB model input features
  - `cbecs_to_xgb_mapping.py` — Mapping script with detailed logic
  - `2018microdata_codebook.xlsx` — Variable definitions
- **Purpose:** Validation only (NOT for training). Closest approximation to real-world building energy data for testing baseline EUI predictions.
- **Mapped features:** building_type, floor_area (binned), climate_zone, heating_fuel, water_heater_fuel, num_of_stories (binned), year_built (binned), hvac_category, cluster_name
- **Actual EUI columns:** electricity_eui, natural_gas_eui, district_heating_eui, other_fuel_eui, total_site_eui (all in kBtu/sf)
- **Limitations:** No Multi-Family buildings (CBECS is commercial only). No zipcode (CENDIV is finest geography). Cluster_name must be approximated from census division. Mappings are approximate (e.g., PBA→building_type uses heuristics for office size splits).

### ComStock Upgrade Measures (65 total)
See `ComStock/raw_data/upgrades_lookup.json` for full list. Key categories:

**HVAC (upgrades 1-31):**
- Heat Pump RTU variants (1-10)
- Advanced RTU (11)
- VRF systems (12-13)
- DOAS HP Minisplits (14)
- HP Boilers (15-16), Condensing Gas Boilers (17), Electric Resistance Boilers (18)
- HVAC Controls: Economizers (19), DCV (20), Energy Recovery (21), RTU Controls (22), Unoccupied Controls (23), Fan Reset (24), Setbacks (25), VFD Pumps (26)
- Geothermal Heat Pumps (28-30)
- Chiller Replacement (31)

**Demand Flexibility (upgrades 32-42):**
- Thermostat, lighting, and plug load controls for peak reduction

**Lighting (upgrades 43-44):**
- LED Lighting (43), Lighting Controls (44)

**Other (upgrades 45-47):**
- Electric Kitchen Equipment (45)
- Photovoltaics (46), PV + Battery (47)

**Envelope (upgrades 48-53):**
- Wall Insulation (48), Roof Insulation (49)
- Secondary Windows (50), Window Film (51), New Windows (52)
- Code Envelope (53)

**Packages (upgrades 54-65):**
- Pre-built combinations of individual measures

### ResStock Upgrade Measures (32 total)
See `ResStock/raw_data/upgrades_lookup.json` for full list:

**HVAC (upgrades 1-8):**
- Gas/Propane Furnace 95% AFUE (1-2), Min Efficiency circa 2025 (3)
- Cold Climate Ducted ASHP (4), Dual Fuel (5)
- Geothermal HP: single/dual/variable speed (6-8)

**Water Heating (upgrades 9-10):**
- HPWH (9), HE Gas Tankless (10)

**Envelope (upgrades 11-17):**
- Air Sealing (11), Attic Insulation (12), Duct Sealing (13), Drill-and-Fill Wall Insulation (14)
- Combo packages (15-16), EnergyStar Windows (17)

**Packages (upgrade 18, 29-32):**
- Geothermal + envelope combos

**EV Charging (upgrades 19-23):**
- Level 1/2 charging, with/without demand flexibility

**Demand Flexibility (upgrades 24-28):**
- Thermostat load shed/shift variants

---

## 4. Data Structure & Key Columns

### Data Cleaning & Exclusions

#### ComStock
- **Deduplication:** 149,272 raw rows → 91,464 unique `bldg_id` values. Duplicates have identical features/EUI but different `weight` values (geographic representation). Deduplicate by `bldg_id`, discard weights.
- **Failed simulations:** Filter out `completed_status == 'Fail'` in upgrade files. Only 11,607 failures across ~5.9M total upgrade simulations (0.2%). Failures are concentrated in geothermal packages (upgrades 59/63/64 account for ~7,300). Baseline has zero failures.
- **Invalid status:** `completed_status == 'Invalid'` rows are NOT errors — they are non-applicable buildings with EUI identical to baseline (verified: 0.000000 mean absolute difference). Already excluded by `applicability == True` filter.
- **No vacancy column** in ComStock. No EUI-based outlier filtering needed — extreme EUIs are legitimate (Food Service median 331 kBtu/sf, Warehouse median 26 kBtu/sf).

#### ResStock
- **No deduplication needed:** 549,971 rows = 549,971 unique bldg_ids.
- **Multi-family filter:** Keep only `in.geometry_building_number_units_mf >= 4` (117,815 units).
- **Vacancy exclusion:** Remove `in.vacancy_status == 'Vacant'` (16,630 units, 14.1%). Vacant units have artificially low EUI (mean 14.2 kBtu/sf vs 41.5 occupied). 95.9% of buildings ≤10 kBtu/sf are vacant.
- **No simulation failures** across any upgrade file.
- **Constant columns to drop** (always same value for MF occupied):
  - `in.corridor` — always "Double-Loaded Interior"
  - `in.geometry_attic_type` — always "None"
  - `in.insulation_ceiling` — always "None" (no attic in MF)
  - `in.mechanical_ventilation` — always "None"

#### Legitimate Edge Cases (Keep)
- ResStock `in.heating_fuel = 'None'` (1.7%) — warm-climate buildings (Hawaii, SoCal) with no heating system
- ResStock `in.hvac_cooling_type = 'None'` (13.7%) — older buildings without AC (CA, NY, WA)
- ComStock `in.tstat_*_sp_f = '999'` (26%) — zone-level control buildings (Warehouse, Lodging, Healthcare), not missing data
- ResStock `in.hvac_heating_efficiency = 'Shared Heating'` (36% of MF occupied) — valid categorical for shared building systems

### ComStock Feature Columns

All features are included at training time. If a user doesn't provide a value, it is imputed based on building type + vintage. The model handles missing/imputed values the same as user-provided values.

| Column | Category | User Provides? |
|--------|----------|---------------|
| `in.comstock_building_type_group` | Core | Required |
| `in.sqft..ft2` | Core | Required |
| `in.number_stories` | Core | Required |
| `in.as_simulated_ashrae_iecc_climate_zone_2006` | Core | Derived from zipcode |
| `cluster_name` | Core | Derived from zipcode via `spatial_tract_lookup_table.csv` |
| `in.vintage` | Core | Optional (imputed if missing) |
| `in.heating_fuel` | HVAC | Optional (imputed) |
| `in.service_water_heating_fuel` | HVAC | Optional (imputed) |
| `in.hvac_category` | HVAC | Optional (imputed) |
| `in.hvac_cool_type` | HVAC Detail | Optional (imputed) |
| `in.hvac_heat_type` | HVAC Detail | Optional (imputed) |
| `in.hvac_system_type` | HVAC Detail | Optional (imputed) |
| `in.hvac_vent_type` | HVAC Detail | Optional (imputed) |
| `in.wall_construction_type` | Envelope | Optional (imputed) |
| `in.window_type` | Envelope | Optional (imputed) |
| `in.window_to_wall_ratio_category` | Envelope | Optional (imputed) |
| `in.airtightness..m3_per_m2_h` | Envelope | Optional (imputed) |
| `in.interior_lighting_generation` | Lighting | Optional (imputed) |
| `in.weekday_operating_hours..hr` | Operations | Optional (imputed) |
| `in.building_subtype` | Detail | Optional (imputed) |
| `in.aspect_ratio` | Detail | Optional (imputed) |
| `in.energy_code_followed_during_last_hvac_replacement` | Code History | Optional (imputed*) |
| `in.energy_code_followed_during_last_roof_replacement` | Code History | Optional (imputed*) |
| `in.energy_code_followed_during_last_walls_replacement` | Code History | Optional (imputed*) |
| `in.energy_code_followed_during_last_svc_water_htg_replacement` | Code History | Optional (imputed*) |

*Energy code history columns: Imputed from vintage for now. In the future, these could reflect recent renovations (e.g., user indicates "HVAC replaced in 2024" which would assign a modern energy code, improving savings predictions even for older buildings).

### ResStock Feature Columns (Multi-Family)

| ResStock Column | Maps to ComStock | User Provides? |
|----------------|-----------------|---------------|
| `in.geometry_building_type_recs` | `in.comstock_building_type_group` | Required (always MF) |
| `in.sqft..ft2` | `in.sqft..ft2` | Required (per-unit sqft) |
| `in.geometry_stories` | `in.number_stories` | Required |
| `in.ashrae_iecc_climate_zone_2004` | `in.as_simulated_ashrae_iecc_climate_zone_2006` | Derived from zipcode |
| `cluster_name` (via county lookup) | `cluster_name` | Derived from zipcode |
| `in.vintage` | `in.vintage` | Optional (imputed) |
| `in.heating_fuel` | `in.heating_fuel` | Optional (imputed) |
| `in.hvac_heating_type` | `in.hvac_heat_type` | Optional (imputed) |
| `in.hvac_heating_efficiency` | — | Optional (imputed) |
| `in.hvac_cooling_type` | `in.hvac_cool_type` | Optional (imputed) |
| `in.hvac_cooling_efficiency` | — | Optional (imputed) |
| `in.hvac_has_shared_system` | — | Optional (imputed) |
| `in.water_heater_fuel` | `in.service_water_heating_fuel` | Optional (imputed) |
| `in.water_heater_efficiency` | — | Optional (imputed) |
| `in.geometry_wall_type` | `in.wall_construction_type` | Optional (imputed) |
| `in.insulation_wall` | — | Optional (imputed) |
| `in.insulation_floor` | — | Optional (imputed) |
| `in.window_areas` | `in.window_to_wall_ratio_category` | Not exposed (future: aerial/street view data) |
| `in.windows` | `in.window_type` | Not exposed |
| `in.lighting` | `in.interior_lighting_generation` | Optional (imputed) |
| `in.infiltration` | `in.airtightness..m3_per_m2_h` | Optional (imputed) |
| `in.geometry_building_type_height` | — | Derived from stories + type |
| `in.geometry_foundation_type` | — | Optional (imputed) |

**ResStock-specific notes:**
- `in.hvac_has_shared_system` — 41% of MF have shared heating/cooling. Important differentiator.
- `in.geometry_building_type_height` — encodes MF height category (1-3 stories, 4-7, 8+). Derived feature.
- `in.window_areas` — directional format "F12 B12 L12 R12" (front/back/left/right percentages), not a single ratio.

### Energy Output Columns

**Approach: Predict by fuel type, sum for total.** Each upgrade model predicts EUI for each fuel type individually. Total site EUI = sum of fuel-type EUIs. This ensures the parts always sum to the whole — predicting total independently would create inconsistencies.

**ComStock EUI target columns (5 fuel types):**

| Column | Fuel Type |
|--------|-----------|
| `out.electricity.total.energy_consumption_intensity..kwh_per_ft2` | Electricity |
| `out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2` | Natural Gas |
| `out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2` | Fuel Oil |
| `out.propane.total.energy_consumption_intensity..kwh_per_ft2` | Propane |
| `out.district_heating.total.energy_consumption_intensity..kwh_per_ft2` | District Heating |

**ResStock EUI target columns (4 fuel types):**

| Column | Fuel Type |
|--------|-----------|
| `out.electricity.total.energy_consumption_intensity..kwh_per_ft2` | Electricity |
| `out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2` | Natural Gas |
| `out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2` | Fuel Oil |
| `out.propane.total.energy_consumption_intensity..kwh_per_ft2` | Propane |

**Models per upgrade:** Each upgrade gets one model per fuel type (5 for ComStock, 4 for ResStock). Total models: ComStock 66×5 = 330, ResStock 33×4 = 132.

**Other output columns (reference only):**

| Column Pattern | Description |
|---------------|-------------|
| `out.[fuel].total.energy_consumption..kwh` | Annual energy by fuel type (absolute) |
| `out.[fuel].total.energy_savings..kwh` | Savings vs baseline (upgrade files only) |
| `out.utility_bills.*_bill_mean..usd` | Utility cost estimates |
| `out.utility_bills.*_bill_savings_mean_intensity..usd_per_ft2` | Cost savings |

### Applicability Flags
- 38 boolean columns (`applicability.*`) indicate which measures can apply to each building
- The main `applicability` column is True/False per upgrade file
- Non-applicable buildings show zero savings in upgrade files
- Applicability rates vary widely: Roof Insulation applies to 100% of buildings, HP-RTU applies to only 37%

### Cost Data

#### Utility Bill Savings (In Dataset)
Both datasets include utility bill savings columns that provide the annual dollar savings per building per upgrade:
- **ComStock (152 bill columns):** `out.utility_bills.total_bill_savings_mean_intensity..usd_per_ft2` — annual $/ft² savings, with min/max/mean/median across rate scenarios, plus component breakdowns (energy charge, demand charge, fixed charge)
- **ResStock (18 bill columns):** `out.utility_bills.total_bill_savings..usd` — annual $ savings per dwelling unit, single rate scenario

Note: The "cost" substring appearing in ~80-96 column names per dataset refers to emissions factor scenario names (e.g., `lrmer_high_re_cost`), NOT financial costs.

#### Upgrade Installation Costs (External Sources — Resolved)
Neither dataset includes first costs (installation/material costs for upgrades). Three structured sources have been identified:

| Source | Location | Coverage | Format |
|--------|----------|----------|--------|
| **NREL Scout ECM Definitions** | `Resources/scout/ecm_definitions/` | 97 commercial + 112 residential measures | 185 JSON files with `installed_cost`, `cost_units`, `product_lifetime`, full source citations |
| **NREL REMDB** | `Resources/REMDB_2024.xlsx` | 142 residential measures | Excel with regression-based cost models (Low/Mid/High bands, performance metric inputs) |
| **Scout Regional Adjustments** | `Resources/scout/scout/supporting_data/convert_data/loc_cost_adj.csv` | 50 states + DC | State-level cost multipliers from RSMeans (e.g., NY=1.36, FL=0.81) |

**Scout ECM cost schema per measure:**
- `installed_cost` — absolute cost (can be flat, `{new: X, existing: Y}`, or per-building-type dict)
- `cost_units` — includes dollar year (e.g., `2023$/kBtu/h heating`, `2022$/ft² glazing`, `2020$/ft² floor`)
- `product_lifetime` — useful life in years
- `installed_cost_source` — full citation (title, author, year, pages, URL)

**Scout's underlying data sources:**
- EIA "Updated Buildings Sector Appliance and Equipment Costs and Efficiencies" (March 2023) — HVAC, water heating, lighting, cooking
- NREL Buildings Annual Technology Baseline (2023$) — HVAC, water heating (some entries marked "forthcoming")
- RSMeans 2022 Building Construction Data — envelope (windows, walls, roofs)
- PNNL ASHRAE 90.1 Cost-Effectiveness Studies (2020$) — commercial code compliance costs
- DOE BTO R&D Roadmaps (2022$) — advanced envelope technology costs

**Coverage assessment:** ~70 of 97 upgrades map directly to Scout ECMs or REMDB. ~15 are trivial estimates (demand flex = thermostat cost, packages = sum of components). Only ~13 need additional research (HVAC controls like DCV/economizers/ERV, VRF, minisplits, PV/battery).

**Regional cost adjustment:** Both datasets have `in.state` which maps 1:1 to Scout's `loc_cost_adj.csv`. At prediction time: `adjusted_cost = national_cost × loc_cost_adj[state].{commercial|residential}`.

See `docs/cost-data-research-plan.md` for the full implementation plan, upgrade-to-source mapping, and gap-filling strategy.

---

## 5. Architecture

### Phase 1: Data Science & Model Training (In Progress)
- [x] Download ComStock 2025 R3 national data (39 GB, 66 files)
- [x] Download ResStock 2025 R1 national data (23 GB, 33 files)
- [x] Exploratory analysis on ComStock upgrade data
- [x] Validate model architecture (per-measure models beat multi-measure)
- [x] Validate weighted vs unweighted training (unweighted wins)
- [x] Identify key features driving savings predictions
- [x] Explore ResStock data (column mapping, MF filter, outlier analysis)
- [x] Data quality audit (exclusions: vacancy, failed sims, constant columns)
- [x] Create CBECS 2018 validation dataset mapping
- [x] Research cost data sources for upgrade measures (Scout ECMs, REMDB, regional adjustments)
- [ ] Build upgrade cost lookup table from Scout + REMDB (`Resources/upgrade_cost_lookup.json`)
- [ ] Finalize feature sets and training pipeline design
- [ ] Train baseline + 65 ComStock upgrade models (with hyperparameter tuning)
- [ ] Train baseline + 32 ResStock upgrade models
- [ ] Validate baseline predictions against CBECS 2018 validation set

### Phase 2: FastAPI Backend + Vue Frontend

See `docs/plans/2026-03-08-app-architecture-design.md` for full architecture, API contract, and inference flow.

**Backend:** FastAPI with two endpoints (`POST /assess`, `GET /metadata`). Models loaded at startup. Cost calculation via XGB-predicted capacity/area × unit costs × regional adjustment. Bill savings via XGB-predicted effective rates × energy savings.

**Frontend:** Vue 3 + partner-components (brand-consistent throwaway). Single-page: form → sortable results table. V2 adds charts, export, detail panels.

**Model inventory (~605 total):**
- 5 baseline EUI models (per fuel type)
- 5 building sizing models (heating cap, cooling cap, wall/roof/window area)
- 4 effective utility rate models (per fuel type)
- 325 ComStock post-upgrade EUI models (65 upgrades × 5 fuel types)
- 128 ResStock post-upgrade EUI models (32 upgrades × 4 fuel types)
- ResStock baseline sizing + rate models (9 additional)
- ~129 additional ResStock upgrade EUI models

### Future: Rails Integration
- FastAPI backend deployed as standalone API service
- Rails app consumes the API
- Same endpoints, Vue frontend discarded

---

## 6. User Input Strategy

### Minimal Required Inputs (Basic Mode)
The goal is to minimize what the user must enter. Required fields:

1. **Building Type** - dropdown (15 options)
2. **Building Square Footage** - number input
3. **Number of Stories** - number input
4. **Zipcode** - text input (derives climate zone AND cluster)

That's it for the minimum. From zipcode alone we can derive climate zone and geographic cluster. HVAC fuel, DHW fuel, HVAC type, and year built can all be imputed or defaulted.

### Optional Detail Fields
If the user knows more, they can provide:

5. **Year Built** - number input
6. **HVAC Heating Fuel** - dropdown
7. **DHW Fuel** - dropdown
8. **HVAC System Type** - dropdown

### Future "Detailed Mode" Fields
For more accurate savings predictions (especially envelope/lighting measures):

9. **Wall Construction Type** - dropdown (4 options)
10. **Window Type** - dropdown (12 options)
11. **Window-to-Wall Ratio** - dropdown (6 bins)
12. **Current Lighting Type** - dropdown (5 generations)
13. **Operating Hours** - number input

---

## 7. Model Training Approach

### Separate Model Sets for ComStock and ResStock

ComStock and ResStock are trained as **completely separate model sets** because:
- Different upgrade measures (65 commercial vs 32 residential)
- Different building characteristics and column names
- Different energy representation (whole-building vs per-unit)
- Different fuel type enumerations

**Routing logic at inference:** If `building_type == "Multi-Family"`, use ResStock models; otherwise, use ComStock models.

### One Model Per Upgrade Measure (Validated)

Based on Phase 1 exploratory analysis, we train **one separate XGBoost model per upgrade** rather than a single model with upgrade_id as a feature:

- **Per-measure model (LED):** MAE=1.28%, R²=0.81
- **Multi-measure model (LED subset):** MAE=1.51%, R²=0.76

The multi-measure model introduced noise - `upgrade_id` only had 0.22 feature importance, meaning the model wasn't fully differentiating between measures. Different measures have fundamentally different physics drivers (LED savings depend on lighting generation; HP-RTU savings depend on HVAC system type), so specialized models perform better.

**Total models:**
- ComStock: 66 upgrades × 5 fuel types = **330 models**
- ResStock: 33 upgrades × 4 fuel types = **132 models**
- **462 models total** (each ~1-5 MB, fast to train)
- Hyperparameters tuned once per upgrade group, shared across fuel types within the same upgrade

### ComStock Models

**Training data per model:** 91,464 buildings filtered to applicable only (varies by measure: 37-100% applicability)

| Component | Detail |
|-----------|--------|
| Features | 25 building characteristics (see Section 4) |
| Targets | 5 fuel-type EUI columns (one model per fuel type per upgrade): `out.electricity.total.energy_consumption_intensity..kwh_per_ft2`, `out.natural_gas.total...`, `out.fuel_oil.total...`, `out.propane.total...`, `out.district_heating.total...` |
| Models per upgrade | 5 (one per fuel type) → 66 upgrades × 5 = **330 models total** |
| Deduplication | By `bldg_id` (149,272 raw → 91,464 unique) |
| Weights | Not used (unweighted outperforms weighted for per-building prediction) |
| Applicability filter | Train only on `applicability == True` rows |

**Inference flow:**
1. Run 5 baseline models (upgrade 0) → baseline EUI per fuel type
2. Sum fuel-type EUIs → baseline total EUI
3. Check applicability flags for each of 65 measures
4. For each applicable upgrade, run 5 fuel-type models → post-upgrade EUI per fuel type
5. Sum fuel-type EUIs → post-upgrade total EUI
6. Savings per fuel type = baseline fuel EUI - post-upgrade fuel EUI
7. Total savings = sum of fuel-type savings (guaranteed consistent)
8. Convert kWh/ft² to kBtu/sf (× 3.412)

### ResStock Models

**Training data:** 101,185 occupied MF 4+ dwelling units, per measure

| Component | Detail |
|-----------|--------|
| Features | ~23 ResStock building characteristics (see Section 4) |
| Targets | 4 fuel-type EUI columns (one model per fuel type per upgrade): `out.electricity.total.energy_consumption_intensity..kwh_per_ft2`, `out.natural_gas.total...`, `out.fuel_oil.total...`, `out.propane.total...` |
| Models per upgrade | 4 (one per fuel type) → 33 upgrades × 4 = **132 models total** |
| Filter | `in.geometry_building_number_units_mf >= 4` AND `in.vacancy_status == 'Occupied'` |
| Exclusions | Vacant units (16,630), constant columns (corridor, attic_type, insulation_ceiling, mechanical_ventilation) |
| Cluster mapping | `in.county` (GISJOIN format) → `nhgis_county_gisjoin` → `cluster_name` via `spatial_tract_lookup_table.csv` |
| GFA scaling | Building GFA = unit sqft × number of units (for total energy output, not for EUI) |
| Applicability | Some upgrades have 0% MF applicability (e.g., upgrade 12 attic insulation). Skip these. |

**ResStock applicability rates for MF (notable):**
- 100%: Windows (17)
- 96-99%: Air sealing (11,14,15,16), HPWH (9), demand flex (24-28)
- 45%: HVAC replacements (3-8, 18) — only applicable to ducted systems
- 8%: Duct sealing (13) — few MF have accessible ducts
- 0%: Attic insulation (12) — MF buildings have no attic

### Fuel Type Harmonization

Both datasets have electricity, natural gas, propane, and fuel oil. Column naming differs:
- ComStock: `in.heating_fuel` values = `Electricity`, `NaturalGas`, `Propane`, `FuelOil`, `DistrictHeating`
- ResStock: `in.heating_fuel` values = `Electricity`, `Natural Gas`, `Propane`, `Fuel Oil`, `Other Fuel`, `None`, `Wood`
- ComStock has `DistrictHeating` which ResStock does not
- ResStock has `None` (1.7%, warm-climate no-heating) and `Wood` (negligible)
- Need a common fuel type mapping for the API response

### Key Consideration: Applicability
The model should NOT predict savings for non-applicable measures. Applicability is deterministic based on building characteristics, so we:
- Train only on applicable buildings (where `applicability=True`)
- Use the applicability flags as a pre-filter at inference time
- Rules-based applicability determination (no separate classifier needed)

### Energy Code History as Renovation Proxy (Future)
The `in.energy_code_followed_during_last_*_replacement` columns are imputed from vintage for now. In the future, if a user indicates "HVAC replaced in 2024", we'd assign the corresponding modern energy code to that column, which would improve savings predictions for older buildings that have been partially renovated. Phase 1 analysis confirmed `energy_code_followed_during_last_hvac_replacement` is a significant predictor for HP-RTU savings (eta²=0.056, 3rd most important feature).

---

## 8. Phase 1 Exploratory Findings

### Savings Analysis by Measure (ComStock, 91,464 unique buildings)

| Measure | Applicable % | Mean Savings | Median Savings |
|---------|-------------|-------------|----------------|
| HP-RTU (upgrade 1) | 37.1% | 28.1% | 27.8% |
| LED Lighting (upgrade 43) | 63.8% | 4.9% | 3.7% |
| Wall Insulation (upgrade 48) | 98.9% | 4.8% | 3.3% |
| Roof Insulation (upgrade 49) | 100.0% | 3.3% | 2.6% |
| Package 2: LED + HP-RTU/Boilers (upgrade 55) | 83.3% | 20.8% | 18.5% |

### Feature Importance (Eta-squared variance analysis)

**For LED Lighting savings:**
1. `in.comstock_building_type` (0.22) - building type is top driver
2. `in.interior_lighting_generation` (0.22) - current lighting type is equally important
3. `in.hvac_system_type` (0.12) - indirect HVAC interaction effects

**For HP-RTU savings:**
1. `in.comstock_building_type` (0.45) - building type dominates
2. `in.energy_code_followed_during_last_hvac_replacement` (0.06) - validates renovation proxy
3. `in.sqft..ft2` (0.05) - building size matters
4. `in.as_simulated_ashrae_iecc_climate_zone_2006` (0.05) - climate matters

**Key insight:** Different measures are driven by different features, confirming that per-measure models are the right approach.

### Weighted vs Unweighted Training (LED Lighting test)

| Metric | Unweighted | Weighted |
|--------|-----------|---------|
| MAE (unweighted eval) | **1.28%** | 1.39% |
| R² (unweighted eval) | **0.8103** | 0.7810 |
| MAE (weighted eval) | 1.11 | **1.10** |

Unweighted wins on per-building accuracy (our use case). Weighted only marginally better on weighted evaluation (stock-level analysis, not our use case).

### Multi-Measure vs Per-Measure Models

| Approach | LED MAE | LED R² |
|----------|---------|--------|
| Per-measure model (LED only) | **1.28%** | **0.81** |
| Multi-measure model (LED subset) | 1.51% | 0.76 |

Per-measure models are more accurate. The multi-measure model's `upgrade_id` feature importance was only 0.22, meaning it couldn't fully specialize for each measure's unique physics.

### ResStock Data Exploration

**Dataset overview (MF 4+ units):**

| Metric | Value |
|--------|-------|
| Total MF 4+ rows | 117,815 |
| Occupied (for training) | 101,185 (86%) |
| Vacant (excluded) | 16,630 (14%) |
| Mean EUI (occupied) | 41.5 kBtu/sf |
| Median EUI (occupied) | 36.3 kBtu/sf |
| Unique bldg_ids | All unique (no dedup needed) |

**Outlier analysis:**
- 7,651 buildings (6.5%) had EUI ≤ 10 kBtu/sf — **95.9% were vacant units**
- Only 316 occupied buildings below 10 kBtu/sf — mostly warm-climate (3B, 1A, 2A), legitimate
- High-end outliers minimal: only 32 buildings (0.03%) above 200 kBtu/sf

**Key ResStock characteristics (MF occupied):**
- 86% are "5+ Units", 14% are "2-4 Units" (which have 4 units to pass our filter)
- 59% electric heating, 36% natural gas
- 36% have shared heating systems
- 88% renter-occupied, 12% owner-occupied
- 52% have no ducts (non-ducted systems dominate MF)

---

## 9. Open Questions

1. ~~**Cost data source**~~ **RESOLVED** — Three structured sources identified: NREL Scout ECM definitions (185 JSON files, commercial + residential), NREL REMDB (142 residential measures, regression-based), and Scout regional cost adjustments (state-level RSMeans multipliers). ~70/97 upgrades map directly; ~13 need additional research (HVAC controls, VRF, PV/battery). See `docs/cost-data-research-plan.md` for implementation plan.

2. **Model validation** - CBECS 2018 mapped dataset exists (`Validation/CBECS/cbecs2018_mapped_for_xgb.csv`, 6,436 buildings). Will be used for baseline EUI validation only. Note: CBECS has no Multi-Family buildings — need RECS or ESPM data for ResStock validation. Existing `ESPM Test Properties, Energy Characterization Study, v1.xlsx` may provide supplementary validation.

3. **HVAC category mapping** - ComStock 2025 R3 has 4 HVAC categories (Small Packaged Unit, Multizone CAV/VAV, Zone-by-Zone, Residential) vs our current models which use 2 (Central Plant, Unitary/Split/DX). Need a mapping strategy.

4. **Measure interactions** - When a user selects multiple measures (packages), how do we handle interactive effects? ComStock already provides package results (upgrades 54-65) but custom combinations would need a strategy.

5. **Applicability determination at inference** - How do we determine which measures apply to a user's building when we only have a subset of the full ComStock feature set? May need a simplified rules engine based on available inputs.

6. **Alaska/Hawaii cluster mapping** - 32 ResStock counties use "state, name" format instead of GISJOIN codes. Need manual mapping or climate-zone-based fallback for cluster assignment.

---

## 10. File & Directory Structure

```
BuildingStock Energy Estimation/
  ComStock/
    raw_data/                    # Downloaded ComStock 2025 R3 (39 GB)
      upgrade0_agg.parquet       # Baseline (91,464 unique buildings)
      upgrade1_agg.parquet       # ...through upgrade65_agg.parquet
      upgrades_lookup.json       # Measure ID -> name mapping
      measure_name_crosswalk.csv # Cross-release measure mapping
    spatial_tract_lookup_table.csv  # County GISJOIN -> cluster_name + climate_zone mapping
  ResStock/
    raw_data/                    # Downloaded ResStock 2025 R1 (23 GB)
      upgrade0.parquet           # Baseline (549,971 units, 117,815 MF 4+)
      upgrade1.parquet           # ...through upgrade32.parquet
      upgrades_lookup.json       # Measure ID -> name mapping
  Validation/
    CBECS/
      cbecs2018_final_public.csv       # Raw CBECS 2018 microdata (6,436 buildings)
      cbecs2018_mapped_for_xgb.csv     # Mapped to model features + actual EUI
      cbecs_to_xgb_mapping.py          # Mapping logic (PBA→building_type, etc.)
      2018microdata_codebook.xlsx      # Variable definitions
  Resources/                     # Existing resources (emission factors, imputation models)
    REMDB_2024.xlsx              # NREL Residential Efficiency Measures Database (142 measures, regression costs)
    upgrade_cost_lookup.json     # Final cost lookup table (planned — all 97 upgrades)
    scout/                       # NREL Scout repo clone (ECM cost data + supporting data)
      ecm_definitions/           # 185 ECM JSON files with installed_cost, lifetime, citations
      scout/supporting_data/convert_data/
        loc_cost_adj.csv         # State-level cost multipliers (RSMeans)
        cpi.csv                  # CPI data for dollar-year normalization
  XGB_Models/                    # Existing baseline models (v3, v3.1)
  docs/                          # Design documents
  scripts/                       # Data processing & model training scripts
    comstock_exploratory_analysis.py  # Phase 1 analysis (completed)
  BuildingStock Data Processing/
    buildingstock_cleanup.py     # Existing cleaning scripts (reference for ResStock processing)
  backend/                       # Phase 2: FastAPI application (planned)
    app/
      main.py                    # FastAPI app, CORS, model loading at startup
      api/routes.py              # POST /assess, GET /metadata
      services/                  # assessment.py, preprocessor.py, cost_calculator.py
      inference/                 # model_manager.py, applicability.py
      schemas/                   # Pydantic request/response models
      data/                      # upgrade_cost_lookup.json, regional_adjustments.json
  frontend/                      # Phase 2: Vue 3 throwaway UI
    partner-components/          # Copied from SiteLynx_Clone (local dependency)
    src/
      views/AssessmentView.vue   # Single-page form → results
      components/                # BuildingForm, MeasuresTable, BaselineSummary
      composables/               # useAssessment.ts (API integration)
      types/                     # TypeScript interfaces matching API schemas
```

---

## 11. Next Steps

1. [x] ~~Exploratory analysis on ComStock 2025 R3 upgrade data~~
2. [x] ~~Download ResStock 2025 R1 upgrade data~~
3. [x] ~~Explore ResStock data (column mapping, MF filter, outlier/exclusion analysis)~~
4. [x] ~~Create CBECS validation dataset mapping~~
5. [x] ~~Research cost data sources (Scout ECMs, REMDB, regional adjustments)~~
6. [ ] **Build upgrade cost lookup table** — parse Scout ECMs, map to our 97 upgrades, gap-fill from REMDB/EIA/TRMs, normalize dollar years, add regional multipliers → `Resources/upgrade_cost_lookup.json` (see `docs/cost-data-research-plan.md`)
7. [ ] **Design model training pipeline** — finalize feature encoding, hyperparameter tuning strategy, cross-validation approach, target variable (post-upgrade EUI vs savings %)
8. [ ] Train ComStock models: 5 baseline EUI + 5 sizing + 4 rate + 325 upgrade EUI (65 × 5 fuels)
9. [ ] Train ResStock models: 4 baseline EUI + 5 sizing + 4 rate + 128 upgrade EUI (32 × 4 fuels)
10. [ ] Validate baseline predictions against CBECS 2018 (6,436 real commercial buildings)
11. [ ] Build FastAPI backend with `/assess` + `/metadata` endpoints (see `docs/plans/2026-03-08-app-architecture-design.md`)
12. [ ] Copy partner-components into repo, scaffold Vue 3 frontend
13. [ ] Build V1 frontend: form → sortable results table with cost/payback
14. [ ] V2: Add charts (fuel breakdown, top measures), Excel export, measure detail panel
