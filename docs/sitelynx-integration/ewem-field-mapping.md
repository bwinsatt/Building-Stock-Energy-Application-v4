# EWEM Field Mapping — Energy Audit Assessment Results

> **Status:** Reference document (2026-03-23)
> **Purpose:** Map Energy Audit Lite's `MeasureResult` / `BaselineResult` output to SL_Heaven's `ewems` and `energy_efficiency_measures` tables for Carbon Performance integration.

---

## Table of Contents

1. [Measure Result → EWEM Row](#measure-result--ewem-row)
2. [Baseline Result → Baseline Metrics Row](#baseline-result--baseline-metrics-row)
3. [Category → System Type / Subcomponent Mapping](#category--system-type--subcomponent-mapping)
4. [Unit Conversions Required](#unit-conversions-required)
5. [Fields That Need Attention](#fields-that-need-attention)
6. [Example Mapped Record](#example-mapped-record)
7. [EnergyEfficiencyMeasure Bridge Record](#energyefficiencymeasure-bridge-record)

---

## Measure Result → EWEM Row

Each applicable `MeasureResult` from our assessment becomes one EWEM record. Non-applicable measures are not stored.

### Direct Mappings

| Assessment Field | EWEM Column | Transform | Notes |
|-----------------|-------------|-----------|-------|
| `name` | `description` | Direct copy | EWEM has no separate "name" column — `description` is the primary label |
| `category` | `system_type` + `subcomponent` | Lookup table (see [Category Mapping](#category--system-type--subcomponent-mapping)) | Two-level classification |
| `description` | `additional_notes` | Direct copy | NREL measure description text |
| `cost.installed_cost_total` | `installed_cost` | Direct copy | Total installed cost in dollars |
| `cost.installed_cost_total` | `premium_cost` | Direct copy | Use same value as installed_cost initially |
| `cost.confidence` | `cost_certainty` | Map: "high"→"Opinion of Cost", "medium"→"Opinion of Cost", "low"→"Soft Bid" | EWEM options: "Actual", "Opinion of Cost", "Hard Bid", "Soft Bid" |
| `electricity_savings_kwh` | `annual_site_energy_savings_total_electricity` | **Multiply by sqft** (`value * sqft`) — API returns per-sf, EWEM needs absolute | decimal 13,2 |
| `gas_savings_therms` | `annual_site_energy_savings_total_gas` | **Multiply by sqft** (`value * sqft`) — API returns per-sf, EWEM needs absolute | decimal 13,2 |
| `simple_payback_years` | `gross_payback` | Direct copy | Years |
| `emissions_reduction_pct` | *(no direct column)* | Store in `additional_notes` or skip | Carbon Performance recalculates emissions |

### Computed Mappings (require calculation in Rails proxy)

| Assessment Field(s) | EWEM Column | Computation | Notes |
|---------------------|-------------|-------------|-------|
| `utility_bill_savings_per_sf` × `sqft` × electricity fraction | `annual_cost_savings_total_electricity` | `bill_savings_total * (elec_savings_kbtu / total_savings_kbtu)` | Split total bill savings by fuel proportion |
| `utility_bill_savings_per_sf` × `sqft` × gas fraction | `annual_cost_savings_total_gas` | `bill_savings_total * (gas_savings_kbtu / total_savings_kbtu)` | Split total bill savings by fuel proportion |
| `cost.installed_cost_total` - `standard_cost` - `rebate` | `net_payback` | `(premium - standard - rebate) / annual_cost_savings` | Currently we don't separate standard_cost; set to 0 |
| `savings_pct` | `priority` | Map: >15% → "High", 5-15% → "Medium", <5% → "Low" | Suggested heuristic |

### Fixed/Default Values

| EWEM Column | Value | Rationale |
|-------------|-------|-----------|
| `source` | `"Energy Audit"` | Accepted EWEM source option |
| `project_type` | `"Energy Efficiency"` | Default; override to `"Electrification"` for heat pump / electric measures |
| `status` | `"Identified"` | Standard initial status |
| `cost_category` | `"Immediate"` | Default; user can reclassify later |
| `include_in_carbon_performance` | `true` | Enables Carbon Performance integration |
| `deprecated` | `false` | Active record |
| `scenario_0` | `true` | Include in default scenario |
| `standard_cost` | `0` | We don't separate base replacement cost |
| `rebate` | `0` | We don't calculate incentives (future enhancement) |
| `fuel_switching` | `true` for electrification measures | Set based on category (see mapping below) |
| `scope` | `"Ewem"` | Default value |

### Fields We Don't Populate

| EWEM Column | Reason |
|-------------|--------|
| `annual_site_savings_water` | We don't model water savings |
| `annual_cost_savings_water` | We don't model water savings |
| `o_m_savings` | Not modeled separately (included in bill savings) |
| `base_installed_cost` | No incremental cost analysis |
| `completion_date` | User sets this in Asset Planner |
| `install_date` | User sets this |
| `due_date` | User sets this |
| `rul_year` | Not modeled |
| `year_installed` | Not applicable at assessment time |
| `notes` | User-entered field |

---

## Baseline Result → Baseline Metrics Row

The `BaselineResult` maps to SL_Heaven's `baseline_metrics` table, which Carbon Performance uses as its foundation.

| Assessment Field | Baseline Metrics Column | Transform |
|-----------------|------------------------|-----------|
| `baseline.eui_by_fuel.electricity` | `baseline_electric_usage` | kBtu/sf → kWh total: `(val / 3.412) * sqft` |
| `baseline.eui_by_fuel.natural_gas` | `baseline_usage_therms` | kBtu/sf → therms total: `(val / 100) * sqft` |
| `baseline.total_eui_kbtu_sf` | *(derived)* | `baseline_site_eui()` method calculates from electric + gas |
| `input_summary.state` | *(used for)* `egrid_subregion_id` | Lookup eGRID subregion from state |
| `building_input.sqft` | `building_area` | Direct copy |
| `building_input.year_built` | *(informational)* | Not a baseline_metrics column |

**Note:** Creating a `baseline_metrics` record is optional for EWEM storage but required for full Carbon Performance integration. Without it, measures appear in Asset Planner but Carbon Performance can't generate decarbonization projections.

---

## Category → System Type / Subcomponent Mapping

Our `measure_category` values (from `upgrade_cost_lookup.json`) need to map to SL_Heaven's two-level classification: `system_type` + `subcomponent`.

### ComStock Categories

| Our Category | EWEM `system_type` | EWEM `subcomponent` | `project_type` | `fuel_switching` |
|-------------|--------------------|--------------------|----------------|------------------|
| `hvac_controls_dcv` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_economizer` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_erv` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_fan` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_rtu` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_setback` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_unoccupied` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_controls_vfd` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_chiller` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_condensing_boiler` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_hp_rtu` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_hp_boiler` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_electric_boiler` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_geothermal` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_minisplit` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_vrf` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_rtu_controls` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_hp_rtu_plus_envelope` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `lighting_led` | Interior Elements | Lighting | Energy Efficiency | false |
| `lighting_controls` | Interior Elements | Lighting | Energy Efficiency | false |
| `envelope_code` | Structural Frame And Building Envelope | Exterior Walls | Energy Efficiency | false |
| `envelope_wall` | Structural Frame And Building Envelope | Exterior Walls | Energy Efficiency | false |
| `envelope_roof` | Structural Frame And Building Envelope | Roofing Materials | Energy Efficiency | false |
| `envelope_window_new` | Structural Frame And Building Envelope | Windows | Energy Efficiency | false |
| `envelope_window_film` | Structural Frame And Building Envelope | Windows | Energy Efficiency | false |
| `envelope_window_secondary` | Structural Frame And Building Envelope | Windows | Energy Efficiency | false |
| `kitchen_electric` | Mechanical, Electrical, Plumbing, FLS | Other Systems | Electrification | true |
| `solar_pv` | Mechanical, Electrical, Plumbing, FLS | Electrical | Renewables | false |
| `solar_pv_battery` | Mechanical, Electrical, Plumbing, FLS | Electrical | Renewables | false |
| `demand_flexibility` | Mechanical, Electrical, Plumbing, FLS | Other Systems | Energy Efficiency | false |
| `theoretical_benchmark` | *(skip)* | *(skip)* | *(skip)* | — |
| `package` | *(use constituents)* | *(use constituents)* | Energy Efficiency | varies |

### ResStock Categories

| Our Category | EWEM `system_type` | EWEM `subcomponent` | `project_type` | `fuel_switching` |
|-------------|--------------------|--------------------|----------------|------------------|
| `hvac_ashp` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_dual_fuel` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_furnace` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `hvac_gshp` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Electrification | true |
| `hvac_min_efficiency` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `water_heater_hp` | Mechanical, Electrical, Plumbing, FLS | Plumbing, Domestic Hot Water, And Sewer Systems | Electrification | true |
| `water_heater_gas` | Mechanical, Electrical, Plumbing, FLS | Plumbing, Domestic Hot Water, And Sewer Systems | Energy Efficiency | false |
| `envelope_air_sealing` | Structural Frame And Building Envelope | Exterior Walls | Energy Efficiency | false |
| `envelope_attic_insulation` | Structural Frame And Building Envelope | Roofing Materials | Energy Efficiency | false |
| `envelope_duct` | Mechanical, Electrical, Plumbing, FLS | Heating, Ventilation, And Air Conditioning (Hvac) | Energy Efficiency | false |
| `envelope_wall_insulation` | Structural Frame And Building Envelope | Exterior Walls | Energy Efficiency | false |
| `envelope_windows` | Structural Frame And Building Envelope | Windows | Energy Efficiency | false |
| `ev_charging` | Mechanical, Electrical, Plumbing, FLS | Electrical | Renewables | false |
| `ev_charging_demand_flex` | Mechanical, Electrical, Plumbing, FLS | Electrical | Renewables | false |
| `demand_flexibility` | Mechanical, Electrical, Plumbing, FLS | Other Systems | Energy Efficiency | false |
| `package` | *(use constituents)* | *(use constituents)* | Energy Efficiency | varies |

### Package Measures

Package measures (category = `package`) contain multiple constituent upgrades. When creating EWEMs:
- Create one **parent EWEM** with the package totals (set `parent_ewem_id = nil`)
- Optionally create **child EWEMs** for each constituent (set `parent_ewem_id` to parent's ID)
- The assessment response includes `constituent_upgrade_ids` for package measures

---

## Unit Conversions Required

Our assessment returns values in per-square-foot or specific fuel units. EWEMs expect **absolute annual values**.

| Our Value | Our Unit | EWEM Unit | Conversion |
|-----------|----------|-----------|------------|
| `electricity_savings_kwh` | kWh/sf (annual) | kWh (annual total) | `value * sqft` |
| `gas_savings_therms` | therms/sf (annual) | therms (annual total) | `value * sqft` |
| `utility_bill_savings_per_sf` | $/sf (annual) | $ (annual total) | `value * sqft` |
| `cost.installed_cost_total` | $ (total) | $ (total) | Direct — already absolute |
| `cost.installed_cost_per_sf` | $/sf | *(not stored directly)* | Use `installed_cost_total` instead |
| `savings_kbtu_sf` | kBtu/sf | *(not stored directly)* | Used for priority heuristic only |

**Confirmed:** `electricity_savings_kwh` and `gas_savings_therms` in the API response are **per-sf** values. The frontend already multiplies by `sqft` for display (`MeasuresTable.vue:389,395`). The Rails proxy must do the same when writing to EWEMs: `value * sqft` → absolute annual savings.

---

## Fields That Need Attention

### 1. Bill Savings Split by Fuel

Our assessment returns `utility_bill_savings_per_sf` as a **single total** (electricity + gas + other). EWEMs need it split into:
- `annual_cost_savings_total_electricity`
- `annual_cost_savings_total_gas`

**Approach:** Use the savings_by_fuel breakdown to proportionally split bill savings:
```
elec_fraction = savings_by_fuel.electricity / total_savings_kbtu
gas_fraction = savings_by_fuel.natural_gas / total_savings_kbtu
annual_cost_savings_electricity = bill_savings_total * elec_fraction
annual_cost_savings_gas = bill_savings_total * gas_fraction
```

### 2. Measure Name vs Description

Our `MeasureResult` has:
- `name` — Short label (e.g., "HP RTU with Economizer")
- `description` — Longer NREL description text

EWEM has:
- `description` — The primary field shown in Asset Planner table (used as the "name")
- `additional_notes` — Secondary text field

**Decision:** Put `name` in `description`, put `description` in `additional_notes`.

### 3. Electrification Identification

Measures that switch from fossil fuel to electric need `fuel_switching = true` and `project_type = "Electrification"`. Our category names contain hints:
- `hvac_hp_*` (heat pump) → Electrification
- `hvac_electric_*` → Electrification
- `hvac_ashp` / `hvac_gshp` → Electrification
- `water_heater_hp` → Electrification
- `kitchen_electric` → Electrification

See the full mapping table above for all classifications.

### 4. Package Measures and Parent/Child Structure

EWEM supports parent/child hierarchy via `parent_ewem_id`. For package measures:
- The package itself becomes the parent (aggregated totals)
- Individual constituent measures become children
- Carbon Performance typically reads parent-level totals

### 5. Renewable Energy Measures

Solar PV and battery measures should set:
- `project_type = "Renewables"`
- In the `energy_efficiency_measure` bridge record: `bool_renewable_energy = true`
- Carbon Performance handles renewable generation separately from EE savings

---

## Example Mapped Record

Given this assessment MeasureResult:
```json
{
  "upgrade_id": 5,
  "name": "HP RTU with Economizer",
  "category": "hvac_hp_rtu",
  "applicable": true,
  "post_upgrade_eui_kbtu_sf": 42.5,
  "savings_kbtu_sf": 12.3,
  "savings_pct": 22.4,
  "cost": {
    "installed_cost_per_sf": 8.50,
    "installed_cost_total": 425000.00,
    "cost_range": { "low": 340000, "high": 510000 },
    "useful_life_years": 20,
    "regional_factor": 1.05,
    "confidence": "medium"
  },
  "utility_bill_savings_per_sf": 0.85,
  "simple_payback_years": 10.0,
  "electricity_savings_kwh": -2.5,
  "gas_savings_therms": 0.08,
  "emissions_reduction_pct": 18.5,
  "description": "Replace existing rooftop units with high-efficiency heat pump RTUs...",
  "savings_by_fuel": {
    "electricity": -8.53,
    "natural_gas": 23.5,
    "fuel_oil": 0,
    "propane": 0,
    "district_heating": 0
  }
}
```

For a 50,000 sqft building, the EWEM record would be:

```ruby
{
  # Identity
  project_id: 123,
  description: "HP RTU with Economizer",
  additional_notes: "Replace existing rooftop units with high-efficiency heat pump RTUs...",

  # Classification
  source: "Energy Audit",
  project_type: "Electrification",
  system_type: "Mechanical, Electrical, Plumbing, FLS",
  subcomponent: "Heating, Ventilation, And Air Conditioning (Hvac)",
  status: "Identified",
  cost_category: "Immediate",
  priority: "High",           # savings_pct 22.4% > 15%
  fuel_switching: true,       # heat pump = electrification

  # Cost
  installed_cost: 425000.00,
  premium_cost: 425000.00,
  standard_cost: 0,
  rebate: 0,
  cost_certainty: "Opinion of Cost",

  # Energy savings (API returns per-sf; multiply by sqft for absolute values)
  annual_site_energy_savings_total_electricity: -125000.0,  # -2.5 kWh/sf × 50,000 sqft (negative = increased electric use from electrification)
  annual_site_energy_savings_total_gas: 4000.0,             # 0.08 therms/sf × 50,000 sqft

  # Cost savings (bill_savings_per_sf × sqft, split by fuel proportion)
  # total bill savings = 0.85 × 50000 = $42,500
  # gas_kbtu_fraction = 23.5 / (23.5 - 8.53) = ~1.57 (gas dominates savings)
  # Note: negative electricity savings means all bill savings come from gas reduction
  annual_cost_savings_total_electricity: 0,
  annual_cost_savings_total_gas: 42500.00,

  # Payback
  gross_payback: 10.0,
  net_payback: 10.0,          # same as gross when standard_cost = 0 and rebate = 0

  # Carbon Performance flags
  include_in_carbon_performance: true,
  scenario_0: true,
  deprecated: false,
  scope: "Ewem"
}
```

---

## EnergyEfficiencyMeasure Bridge Record

When an EWEM with `include_in_carbon_performance: true` is created, SL_Heaven auto-creates an `energy_efficiency_measure` record. This is what Carbon Performance actually reads.

| Bridge Column | Source | Notes |
|---------------|--------|-------|
| `ewem_id` | EWEM.id | FK, auto-set |
| `cost` | `installed_cost` | Copied from EWEM |
| `net_installed_cost` | `premium_cost - standard_cost - rebate` | Calculated |
| `cost_savings` | `annual_cost_savings_electricity + gas + o_m_savings` | Summed |
| `kwh_savings` | `annual_site_energy_savings_total_electricity` | Copied |
| `therm_savings` | `annual_site_energy_savings_total_gas` | Copied |
| `year_implemented` | 0 (default) | User sets in Carbon Performance |
| `spread_years` | 1 (default) | User can adjust |
| `degradation` | 0 (default) | Applies to renewables only |
| `partial_measure` | 100 (default) | 100% of measure applied |
| `bool_active` | true | Active in default scenario |
| `bool_renewable_energy` | true for solar_pv* categories | false for all others |
| `payback` | `gross_payback` | Copied from EWEM |

**Important:** The `energy_efficiency_measure` record is typically created by SL_Heaven's `Ewem.create_with_default_values` method. We should use that method (or replicate its logic) rather than inserting bridge records directly, to ensure all callbacks and defaults are applied correctly.

---

## Data Flow Summary

```
Python API /assess response
    │
    ├─ BaselineResult ──→ baseline_metrics record (optional, enables Carbon Performance)
    │
    └─ MeasureResult[] ──→ For each applicable measure:
         │
         ├─ Map category → system_type + subcomponent (lookup table above)
         ├─ Convert per-sf values → absolute values (× sqft)
         ├─ Split bill savings by fuel proportion
         ├─ Set fixed defaults (source, status, include_in_carbon_performance)
         │
         └─ Create EWEM record via Ewem.create_with_default_values
              └─ Auto-creates energy_efficiency_measure bridge record
                   └─ Carbon Performance reads this for projections
```
