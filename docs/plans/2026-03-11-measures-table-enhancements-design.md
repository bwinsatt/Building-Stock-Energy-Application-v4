# Measures Table Enhancements Design

## Overview

Expand the upgrade measures table from 6 columns to 12 columns, adding per-fuel energy savings, emissions reduction, useful life, and NREL descriptions. Implement a new emissions calculation module and consolidate unit conversion constants.

## Table Column Layout

Horizontal scroll, all columns visible. Priority columns on the left, new columns on the right.

| # | Column | Status | Source | Notes |
|---|--------|--------|--------|-------|
| 1 | Measure | existing | — | No change |
| 2 | Category | existing | — | Clean up to friendly display names |
| 3 | Savings % | existing | — | No change |
| 4 | Annual Bill Savings ($) | existing | — | Add $ to column header |
| 5 | Installed Cost | existing | — | No change |
| 6 | Payback (yrs) | existing | — | No change |
| 7 | Electricity Savings (kWh) | **new** | backend | Dash for zero/n/a |
| 8 | Gas Savings (therms) | **new** | backend | Dash for zero/n/a |
| 9 | Other Fuel Savings (kBtu) | **new** | backend | Dash for zero/n/a |
| 10 | Emissions Reduction (%) | **new** | backend | Calculated from energy savings x emission factors |
| 11 | Useful Life (yrs) | **new** | CostEstimate | Already in schema, just display |
| 12 | Description | **new** | cost lookup | Official NREL text; packages include component details |

### Category Display Mapping

| Raw value(s) | Display name |
|-------------|-------------|
| `hvac_hp_rtu`, `hvac_furnace`, `hvac_ashp`, `hvac_gshp`, etc. | HVAC |
| `envelope_roof`, `envelope_wall`, `envelope_window_*`, `envelope_air_sealing`, `envelope_code` | Envelope |
| `lighting_led`, `lighting_controls` | Lighting |
| `demand_flexibility` | Demand Flex |
| `water_heating` | Water Heating |
| `kitchen_electric` | Kitchen |
| `package`, `hvac_hp_rtu_plus_envelope` | Package |

## Backend Changes

### 1. Constants File — `backend/app/constants.py` (new)

Consolidate all unit conversion constants currently scattered across modules:

```python
# Energy unit conversions
KWH_TO_KBTU = 3.412
KWH_TO_THERMS = 0.03412
TONS_TO_KBTUH = 12.0

# Area conversions
SQFT_PER_M2 = 10.7639
M2_PER_SQFT = 1 / SQFT_PER_M2  # 0.0929

# Fossil fuel emission factors (kg CO2e per kBtu)
# Source: archive/old_scripts/XGB_EnergyEstimation_v2.py
FOSSIL_FUEL_EMISSION_FACTORS = {
    "natural_gas": 0.05311,
    "propane": 0.06195,
    "fuel_oil": 0.07421,
    "district_heating": 0.0664,
}
```

Update existing imports in `assessment.py`, `address_lookup.py`, and `cost_calculator.py` to use this file.

### 2. Emissions Module — `backend/app/services/emissions.py` (new)

Standalone module for calculating carbon emissions from energy consumption.

**Design principles:**
- Reusable for both upgrade emissions reduction (this round) and baseline emissions (future fast-follow)
- Takes energy values + zipcode, returns emissions in kg CO2e/sf

**Function signature:**
```python
def calculate_emissions(energy_by_fuel_kwh: dict, zipcode_prefix: str) -> float:
    """Calculate total emissions in kg CO2e/sf from per-fuel energy consumption.

    Args:
        energy_by_fuel_kwh: dict of fuel -> energy in kWh/sf
        zipcode_prefix: 3-digit zipcode prefix for electricity emission factor lookup

    Returns:
        Total emissions in kg CO2e/sf
    """
```

**Unit chain:**
| Fuel | Input | Conversion | Factor | Result |
|------|-------|-----------|--------|--------|
| Electricity | kWh/sf | none | kg CO2e/kWh (from eGRID via zipcode lookup) | kg CO2e/sf |
| Natural Gas | kWh/sf | × 3.412 → kBtu/sf | 0.05311 kg CO2e/kBtu | kg CO2e/sf |
| Propane | kWh/sf | × 3.412 → kBtu/sf | 0.06195 kg CO2e/kBtu | kg CO2e/sf |
| Fuel Oil | kWh/sf | × 3.412 → kBtu/sf | 0.07421 kg CO2e/kBtu | kg CO2e/sf |
| District Heating | kWh/sf | × 3.412 → kBtu/sf | 0.0664 kg CO2e/kBtu | kg CO2e/sf |

**Emissions reduction calculation in `assessment.py`:**
```
baseline_emissions = calculate_emissions(baseline_eui, zipcode_prefix)
post_upgrade_emissions = calculate_emissions(post_upgrade_eui, zipcode_prefix)
emissions_reduction_pct = (baseline_emissions - post_upgrade_emissions) / baseline_emissions * 100
```

### 3. Response Schema — `backend/app/schemas/response.py`

Add three flat fields to `MeasureResult`:

```python
electricity_savings_kwh: Optional[float] = None
gas_savings_therms: Optional[float] = None
other_fuel_savings_kbtu: Optional[float] = None
```

Unit conversion happens in the backend (in `assessment.py`):
- Electricity: already in kWh (model output)
- Natural Gas: kWh × 0.03412 → therms
- Other fuels (fuel oil, propane, district heating): kWh × 3.412 → kBtu

### 4. Assessment Service — `backend/app/services/assessment.py`

- Import constants from `constants.py`
- After computing per-fuel savings, convert to display units and populate the three new flat fields
- Call `emissions.calculate_emissions()` twice (baseline, post-upgrade) to compute `emissions_reduction_pct`
- Verify `useful_life_years` from CostEstimate is already passed through (it is — just needs frontend display)

### 5. Zipcode Lookup — `backend/app/data/zipcode_lookup.json`

Add two fields to each entry:

```json
"005": {
    "state": "NY",
    "climate_zone": "4A",
    "cluster_name": "the Greater New York City Area",
    "egrid_subregion": "NYCW",
    "electricity_emission_factor_kg_co2e_per_kwh": 0.000312
}
```

**Source:** Convert `Resources/Zipcode to Emission Factor, kgCO2e.xlsx` and merge by zipcode prefix.

### 6. Cost Lookup — `backend/app/data/upgrade_cost_lookup.json`

Add `description` field to each entry:
- Individual measures: official NREL descriptions from ComStock/ResStock documentation
- Package measures: description includes component details (sub-measure list)

Example:
```json
{
    "upgrade_id": 43,
    "upgrade_name": "LED Lighting",
    "description": "Replaces all non-LED interior lighting with LED systems; applicable to ~65% of stock floor area.",
    ...
}
```

## Frontend Changes

### MeasuresTable.vue

- Add 6 new columns (7-12) to the right of existing columns
- Per-fuel savings columns: show "—" for zero or null values
- Category column: map raw values to friendly display names (HVAC, Envelope, etc.)
- Update "Annual Bill Savings" header to include $
- Description column: render full text, packages show component details inline
- Horizontal scroll for the wider table (scroll wrapper already exists)

### TypeScript Types — `src/types/assessment.ts`

Update `MeasureResult` interface to include new fields:
```typescript
electricity_savings_kwh?: number
gas_savings_therms?: number
other_fuel_savings_kbtu?: number
```

## Data Pipeline (One-Time Tasks)

1. **eGRID merge:** Parse `Resources/Zipcode to Emission Factor, kgCO2e.xlsx`, extract zipcode → (eGRID subregion, emission factor), merge into `zipcode_lookup.json` by prefix
2. **NREL descriptions:** Add official descriptions to each entry in `upgrade_cost_lookup.json` — ComStock measures from NREL documentation site, ResStock measures from state factsheets

## Future Fast-Follow (Not In Scope)

- **Baseline carbon emissions** (kg CO2e/sf) — emissions module is designed to support this, just needs a call with baseline energy values
- **Hide/show columns** — if horizontal scroll proves unwieldy
- **Unit toggling** — user selects preferred units (would become an API parameter)
- **eGRID subregion display** — data stored in zipcode lookup, ready to surface
