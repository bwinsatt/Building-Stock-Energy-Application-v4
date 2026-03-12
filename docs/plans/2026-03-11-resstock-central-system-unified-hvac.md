# ResStock Central System & Unified HVAC Categories

**Date:** 2026-03-11
**Status:** Design approved

## Motivation

ResStock hardcodes `in.hvac_has_shared_system` to `"None"`, ignoring that ~11% of the ResStock dataset (and ~41% of real MF buildings) have shared/central HVAC systems. Additionally, the HVAC category names between ComStock and ResStock are completely different, creating a disjointed user experience.

## Goals

1. Add "Central Boiler + Chiller" as a ResStock HVAC option that sets the shared system flag
2. Unify HVAC category labels so ComStock and ResStock look as similar as possible to the user
3. No model retraining — only send existing feature values the models already know

## Design

### HVAC Category Changes (`dropdowns.ts`)

**Deleted categories:**
- `residential_furnace` (ComStock) — replaced by `forced_air_furnace`
- `ducted_heating` (ResStock) — replaced by `forced_air_furnace`
- `non_ducted_heating` (ResStock) — replaced by `baseboard_wall_unit`
- `non_ducted_heat_pump` (ResStock) — replaced by `mini_split_heat_pump`

**New/modified categories:**

| Key | Label | Datasets | Variants |
|---|---|---|---|
| `forced_air_furnace` | Forced Air Furnace + AC | comstock, resstock | ComStock: `"Residential AC with residential forced air furnace"`. ResStock: `"Ducted Heating"` |
| `ducted_heat_pump` | Ducted Heat Pump | resstock | `"Ducted Heat Pump"` |
| `baseboard_wall_unit` | Baseboard / Wall Unit | resstock | `"Non-Ducted Heating"` |
| `mini_split_heat_pump` | Mini-Split Heat Pump | resstock | `"Non-Ducted Heat Pump"` |
| `central_chiller_boiler` | Central Boiler + Chiller | comstock, resstock | ComStock: existing 7 VAV variants (unchanged). ResStock: `"Fan Coil Units"`, `"Baseboards / Radiators"` |

All other ComStock categories (Packaged Rooftop, Packaged Heat Pump, Through-Wall/PTAC, PTHP, Packaged VAV, DOAS + Fan Coil) stay unchanged.

**Type change:** `HvacVariant` gets optional `dataset?: 'comstock' | 'resstock'` field for filtering variants by dataset.

### Preprocessor Mapping (`preprocessor.py`)

New variant values map to ResStock features:

| Variant value | `in.hvac_heating_type` | `in.hvac_has_shared_system` | `in.hvac_heating_efficiency` | `in.hvac_cooling_efficiency` |
|---|---|---|---|---|
| `"Ducted Heating"` | Ducted Heating | None | imputed | imputed |
| `"Ducted Heat Pump"` | Ducted Heat Pump | None | imputed | imputed |
| `"Non-Ducted Heating"` | Non-Ducted Heating | None | imputed | imputed |
| `"Non-Ducted Heat Pump"` | Non-Ducted Heat Pump | None | imputed | imputed |
| `"Fan Coil Units"` | Ducted Heating | Heating and Cooling | Shared Heating | Shared Cooling |
| `"Baseboards / Radiators"` | Non-Ducted Heating | Heating Only | Shared Heating | imputed |

### Frontend Changes (`AdvancedDetails.vue`)

- `hvacVariants` computed property filters by dataset
- When a central system variant is selected, heating/cooling efficiency dropdowns show "Shared Heating"/"Shared Cooling" as disabled
- User efficiency overrides ignored when central system variant is active (preprocessor handles override)

### Legacy Mapping

Update `legacyMap` in `getHvacCategoryForValue` so old saved values still resolve to the correct renamed categories.

## Files Modified

1. `frontend/src/config/dropdowns.ts` — category renames, new variants, variant filtering, legacy map
2. `frontend/src/components/AdvancedDetails.vue` — dataset-aware variant filtering, disabled efficiency fields
3. `backend/app/services/preprocessor.py` — central system variant mapping

## Out of Scope

- Renaming any ComStock categories other than "Residential Furnace + AC"
- Model retraining
- Adding "Cooling Only" shared system option
