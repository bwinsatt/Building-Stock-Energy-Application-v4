# Upgrade Measure Cost Data — Implementation Plan

## Objective

Produce `Resources/upgrade_cost_lookup.json` mapping all 65 ComStock and 32 ResStock upgrade measures to installed cost data (Low/Mid/High range, units, lifetime, source citations), enabling simple payback and ROI calculations.

**Payback formula:** `payback_years = installed_cost / annual_bill_savings`

---

## What We Already Have

### Savings Data (In Our Parquet Files)
- ComStock: `out.utility_bills.total_bill_savings_mean_intensity..usd_per_ft2` — annual $/ft² savings per upgrade
- ResStock: `out.utility_bills.total_bill_savings..usd` — annual $ savings per upgrade

### Cost Data Sources (Downloaded)

| Source | Location | Coverage | Format |
|--------|----------|----------|--------|
| **NREL Scout ECMs** | `Resources/scout/ecm_definitions/` | 97 commercial + 112 residential measures | 185 JSON files with installed_cost, cost_units, lifetime, full citations |
| **NREL REMDB** | `Resources/REMDB_2024.xlsx` | 142 residential measures | Excel with regression-based cost models (Low/Mid/High) |
| **Scout Regional Adjustments** | `Resources/scout/scout/supporting_data/convert_data/loc_cost_adj.csv` | All 50 states + DC | State-level cost multipliers (from RSMeans) |
| **Scout CPI Data** | `Resources/scout/scout/supporting_data/convert_data/cpi.csv` | 1947–present | For dollar-year normalization |

---

## Primary Source: NREL Scout ECM Definitions

Scout is the best source because it covers **both commercial and residential** buildings with structured, machine-readable JSON files. Each ECM contains:

```
installed_cost      → absolute installed cost ($/unit, $/kBtu/h, $/ft² floor, $/ft² glazing, etc.)
cost_units          → unit basis with dollar year (e.g., "2023$/kBtu/h heating")
product_lifetime    → useful life in years
installed_cost_source → full citation (title, author, year, pages, URL)
```

### Scout's Underlying Data Sources (What It Cites)

| Source | What It Provides | Year | Access |
|--------|-----------------|------|--------|
| **EIA "Updated Buildings Sector Appliance and Equipment Costs and Efficiencies"** | HVAC, water heating, lighting, cooking, refrigeration costs for residential + commercial | March 2023 | Free PDF: `eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf` |
| **NREL Buildings Annual Technology Baseline (ATB)** | Residential + commercial HVAC, water heating | 2023$ (some entries marked "forthcoming") | Referenced via Google Sheets in Scout JSONs |
| **RSMeans 2022 Building Construction Data** | Envelope (windows, walls, roofs) installation costs | 2022$ | Paid database, but Scout has extracted key values into its JSONs |
| **PNNL ASHRAE 90.1 Cost-Effectiveness Studies** | Commercial lighting, envelope, HVAC by building type | 2020$ | Free: PNNL technical reports |
| **DOE BTO R&D Roadmaps** | Future/advanced envelope technology costs (windows, walls, air sealing) | 2022$ | Free: DOE reports |

### Scout ECM Inventory (Relevant to Our Upgrades)

**Commercial (97 ECMs, prefix `(C)`):**
- HP fuel switch variants (RTU, boiler, furnace) — `2023$/kBtu/h heating`, lifetime 15-21 yrs
- GSHP reference case — `2023$/kBtu/h heating`, lifetime 15 yrs
- HP water heater — `2022$/kBtu/h water heating`, lifetime 15 yrs
- Lighting (90.1 compliance) — `2020$/ft² floor`, lifetime 10 yrs
- Windows (90.1 + BTO RDO) — `2022$/ft² glazing`, lifetime 25 yrs
- Walls & air sealing — `2022$/ft² wall`, lifetime 100 yrs
- Roofs — `2022$/ft² roof`, lifetime 30 yrs
- Cooking (induction range) — `2022$/kBtu/h cooking`, lifetime 12 yrs
- Refrigeration — `2022$/kBtu/h refrigeration`, lifetime 10 yrs

**Residential (112 ECMs, prefix `(R)`):**
- ASHP variants (ENERGY STAR, Best, Min. Efficiency, Breakthrough) — `2023$/unit`, lifetime 15 yrs
- GSHP — `2023$/unit`, lifetime 15 yrs
- HP water heater — `2023$/unit`, lifetime 15 yrs
- Gas furnace & AC — `2023$/unit`, lifetime 21 yrs (furnace) / 18 yrs (AC)
- Windows (ENERGY STAR, BTO RDO) — `2022$/ft² glazing`, lifetime 30 yrs
- Walls, air sealing, roofs, foundations — `2022$/ft² wall|roof|footprint`, lifetime 25-100 yrs
- LED lighting — `2023$/unit`, lifetime 22.8 yrs

### Secondary Source: REMDB (ResStock Residential Detail)

REMDB provides **regression-based cost models** with performance metric inputs:
```
Installed_Cost = (Coeff × Metric + Intercept) × Install_Multiplier_Retrofit + Install_Adder
```
With Low/Mid/High bands. Useful for computing costs at specific performance levels (e.g., AFUE=0.95, SEER=21, R-49).

---

## Implementation Steps

### Step 1: Parse All Scout ECMs → Structured Database

**Script:** `scripts/parse_scout_ecm_costs.py`

```
Input:  Resources/scout/ecm_definitions/*.json (185 files)
Output: Resources/scout_ecm_costs.json (flat structure with all cost fields)
```

For each ECM JSON, extract:
- `name`, `installed_cost`, `cost_units`, `product_lifetime`, `product_lifetime_units`
- `installed_cost_source` (citations)
- `bldg_type`, `end_use`, `technology`, `fuel_switch_to`
- `energy_efficiency`, `energy_efficiency_units`

Handle edge cases:
- Cost can be a flat number, a `{new: X, existing: Y}` dict, or a `{bldg_type: cost}` dict
- Some files contain arrays of ECMs (package definitions that reference component ECMs)
- Cost units embed the dollar year (parse "2023$/kBtu/h heating" → year=2023, basis="$/kBtu/h heating")
- Lifetimes can be dicts by technology sub-type

### Step 2: Map ComStock/ResStock Upgrades → Scout ECMs

**Script:** `scripts/map_upgrades_to_scout.py`

Manual mapping table (the core intellectual work). For each of our 97 upgrades, identify the best-matching Scout ECM(s):

**ComStock Upgrade → Scout ECM Mapping (Key Examples):**

| ComStock Upgrade | Scout ECM(s) | Cost Field to Use |
|-----------------|-------------|-------------------|
| 1-10: HP RTU variants | `(C) Best HP FS (RTU, NG Heat)`, `(C) ESTAR HP FS (RTU, NG Heat)`, `(C) Min. Efficiency HP FS (RTU, NG Heat)` | `installed_cost.existing` in `2023$/kBtu/h heating` |
| 11: Advanced RTU | `(C) Ref. Case RTU, NG Heat` (baseline) → compute incremental | Incremental = upgrade ECM cost - ref case cost |
| 12-13: VRF | No direct Scout ECM → **gap, use EIA report** | |
| 14: DOAS HP Minisplits | No direct Scout ECM → **gap, use EIA report** | |
| 15-16: HP Boiler | `(C) Best HP FS (NG Boiler)` | `installed_cost.existing` |
| 17: Condensing Gas Boiler | `(C) Best NG Boiler & Chiller` | `installed_cost.existing` |
| 19-26: HVAC Controls | **Gap** — DCV, economizers, ERV, setbacks not in Scout | Manual research needed |
| 28-30: Geothermal | `(C) Ref. Case GSHP` | `installed_cost.existing` |
| 43: LED Lighting | `(C) 90.1 Lighting` | Per building type costs |
| 45: Electric Kitchen | `(C) Induction Range FS` | `installed_cost` |
| 46-47: PV/Battery | **Gap** — not in Scout → use NREL ATB | |
| 48: Wall Insulation | `(C) 90.1-2022 Walls & Air Sealing` or `(C) BTO RDO Walls` | `installed_cost` |
| 49: Roof Insulation | `(C) BTO RDO Roofs` | `installed_cost` |
| 50-52: Windows | `(C) 90.1-2022 Windows` or `(C) BTO RDO Windows` | `installed_cost` |

**ResStock Upgrade → Scout ECM Mapping (Key Examples):**

| ResStock Upgrade | Scout ECM(s) | Cost Field to Use |
|-----------------|-------------|-------------------|
| 1: NG Furnace 95% AFUE | `(R) Best NG Furnace & AC` | `installed_cost` in `2023$/unit` |
| 4: Cold Climate ASHP | `(R) Best HP FS (NG Furnace)` or `(R) ESTAR HP FS (NG Furnace)` | `installed_cost` |
| 6-8: GSHP | `(R) ESTAR GSHP (NG Furnace)` | `installed_cost` |
| 9: HP Water Heater | `(R) Best HPWH FS` or `(R) ESTAR 240V HPWH FS` | `installed_cost` |
| 11, 29: Air Sealing | `(R) BTO RDO Air Sealing` | `installed_cost` in `2022$/ft² wall` |
| 12: Attic Insulation | Use REMDB regression (more granular) | `2023$/sqft` at target R-value |
| 17: EnergyStar Windows | `(R) ENERGY STAR Windows` | `installed_cost` in `2022$/ft² glazing` |

**Known Gaps (Not in Scout):**
- ComStock VRF (12-13) — use EIA equipment cost report
- ComStock DOAS Minisplits (14) — use EIA report
- ComStock HVAC controls (19-26): DCV, economizers, ERV, fan static pressure reset, setbacks, VFD pumps — use state TRMs or PNNL 90.1 studies
- ComStock PV/Battery (46-47) — use NREL ATB
- ComStock Window Film (51) — use industry estimates
- ComStock Demand Flexibility (32-42) — controls-only, estimate $0.50-2.00/sqft
- ResStock EV measures (19-23) — EV charger from REMDB, vehicle cost out of scope
- ResStock Demand Flexibility (24-28) — smart thermostat cost from REMDB

### Step 3: Extract Cost Data → Lookup Table

**Script:** `scripts/build_cost_lookup.py`

```
Input:  Resources/scout_ecm_costs.json + mapping table from Step 2
        Resources/REMDB_2024.xlsx (for ResStock gap-filling)
Output: Resources/upgrade_cost_lookup.json
```

Per upgrade, produce:

```json
{
  "upgrade_id": 1,
  "dataset": "comstock",
  "upgrade_name": "Variable Speed HP RTU, Electric Backup",
  "measure_category": "hvac_hp_rtu",
  "cost_low": null,
  "cost_mid": 220.0,
  "cost_high": null,
  "cost_units": "$/kBtu_hr_heating",
  "cost_units_display": "$/kBtu/h heating capacity",
  "useful_life_years": 21,
  "cost_year_dollars": 2023,
  "cost_type": "full_replacement",
  "scout_ecm_name": "(C) Best HP FS (RTU, NG Heat)",
  "sources": [
    {
      "name": "NREL Scout / EIA Equipment Costs 2023",
      "citation": "U.S. EIA, Updated Buildings Sector Appliance and Equipment Costs and Efficiencies, March 2023",
      "url": "https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf"
    }
  ],
  "confidence": "high",
  "notes": "Covers all RTU sizes. Cost is for existing building replacement."
}
```

**Low/Mid/High ranges:**
- Scout ECMs with `{new: X, existing: Y}` → use `existing` as mid, compute range from new/existing spread
- Scout ECMs with per-building-type costs → use weighted average as mid, min/max as low/high
- REMDB measures → use Low/Mid/High intercepts directly

### Step 4: Regional Cost Adjustment (State-Level)

**Feasible — both datasets have `in.state` which maps to Scout's `loc_cost_adj.csv`.**

Scout's `loc_cost_adj.csv` has 51 rows (50 states + DC), with columns:
```
state, city, residential, commercial
AL, Huntsville, 0.83, 0.85
NY, New York, 1.36, 1.32
...
```

Implementation:
- For ComStock buildings: `adjusted_cost = national_cost × loc_cost_adj[state].commercial`
- For ResStock buildings: `adjusted_cost = national_cost × loc_cost_adj[state].residential`
- Join key: `in.state` (2-letter abbreviation) in both ComStock and ResStock parquet files matches `state` column in `loc_cost_adj.csv`

Store the adjustment factors in the lookup JSON under a `regional_adjustments` key, and apply at prediction time.

### Step 5: Dollar-Year Normalization

Scout ECMs use mixed dollar years (2020$, 2022$, 2023$). Normalize all to a single year using `cpi.csv`.

```
normalized_cost = original_cost × (CPI_target_year / CPI_source_year)
```

Target year: **2023$** (most common in Scout, most recent).

The CPI file has annual values — straightforward computation.

---

## Gap-Filling Strategy for Measures Not in Scout

| Gap | Count | Strategy |
|-----|-------|----------|
| ComStock VRF (12-13) | 2 | EIA Equipment Costs report Table 5-X (commercial HP systems) |
| ComStock Minisplits (14) | 1 | EIA Equipment Costs report + residential REMDB ASHP ductless as proxy |
| ComStock HVAC Controls (19-26) | 8 | PNNL ASHRAE 90.1 cost studies, state TRMs (IL TRM has DCV, economizer, ERV costs). Deep research target. |
| ComStock PV/Battery (46-47) | 2 | NREL ATB 2024 — commercial rooftop PV $/Watt, battery $/kWh |
| ComStock Window Film (51) | 1 | Industry estimate ~$8-15/ft² glazing installed |
| ComStock Demand Flex (32-42) | 11 | Controls-only cost: smart thermostat ($150-300) + BMS programming ($0.50-2.00/sqft) |
| ResStock EV (19-23) | 5 | REMDB EV Charger for L1/L2 hardware; vehicle cost excluded (not a building upgrade) |
| ResStock Demand Flex (24-28) | 5 | REMDB Thermostat Smart ($150-300/unit) |
| ComStock Ideal Loads (27) | 1 | **Exclude** — theoretical benchmark, not a real measure |

**Total gaps: ~36 upgrades** needing non-Scout sources, but most are trivial (demand flex = thermostat cost, packages = sum of components, EV = charger cost). Only **~10 truly need deep research** (VRF, minisplits, 8 HVAC controls).

---

## Output Deliverables

| Deliverable | Path | Description |
|-------------|------|-------------|
| Scout ECM parser | `scripts/parse_scout_ecm_costs.py` | Parses all 185 ECM JSONs into flat structure |
| Upgrade mapping | `scripts/map_upgrades_to_scout.py` | Maps 97 upgrades to Scout ECMs + gap-fill sources |
| Cost lookup builder | `scripts/build_cost_lookup.py` | Produces final lookup JSON |
| **Cost lookup table** | `Resources/upgrade_cost_lookup.json` | Final deliverable — all 97 upgrades with costs, sources, confidence |
| Regional adjustments | Included in lookup JSON | State-level multipliers from Scout/RSMeans |

---

## Scope Summary (Revised)

| Item | Count | Source | Effort |
|------|-------|--------|--------|
| ComStock HVAC equipment | 18 | Scout ECMs (direct match) | **Scripted** |
| ComStock envelope | 6 | Scout ECMs (direct match) | **Scripted** |
| ComStock lighting | 2 | Scout ECMs (direct match) | **Scripted** |
| ComStock kitchen | 1 | Scout ECMs (direct match) | **Scripted** |
| ComStock geothermal | 3 | Scout ECMs (direct match) | **Scripted** |
| ResStock HVAC | 8 | Scout ECMs + REMDB | **Scripted** |
| ResStock water heating | 2 | Scout ECMs + REMDB | **Scripted** |
| ResStock envelope | 8 | Scout ECMs + REMDB | **Scripted** |
| ResStock windows | 1 | Scout ECMs | **Scripted** |
| ComStock demand flex | 11 | Thermostat/BMS estimate | **Trivial** |
| ResStock demand flex | 5 | REMDB thermostat | **Trivial** |
| ResStock EV | 5 | REMDB EV charger | **Trivial** |
| All packages | 20 | Sum of components | **Trivial** |
| ComStock HVAC controls | 8 | TRMs, PNNL studies | **Deep research needed** |
| ComStock VRF/minisplits | 3 | EIA report | **Moderate research** |
| ComStock PV/battery | 2 | NREL ATB | **Low research** |
| ComStock window film | 1 | Industry estimate | **Trivial** |
| ComStock ideal loads | 1 | Excluded | N/A |
| Regional adjustments | 51 states | Scout `loc_cost_adj.csv` | **Scripted** |
| Dollar-year normalization | all | Scout `cpi.csv` | **Scripted** |

**Bottom line: ~70 of 97 upgrades can be scripted from Scout + REMDB. ~15 are trivial estimates. Only ~10 HVAC controls + 3 VRF/minisplit measures need manual research.**
