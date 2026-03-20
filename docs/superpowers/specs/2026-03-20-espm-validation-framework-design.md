# ESPM/CBECS Validation Framework Design

## Purpose

A diagnostic script that runs real-building assessments through the assessment pipeline and outputs structured results for manual review. Validates baseline EUI predictions, upgrade measure savings, costs, and payback periods across diverse building types, climates, and sizes.

## Data Sources

### ESPM Spreadsheet (`Validation/ESPM Properties Testing_MetaAnalysis.xlsx`)
- 78 real properties from ENERGY STAR Portfolio Manager
- Fields: building type, sqft, zipcode, climate zone, heating fuel, DHW fuel, HVAC type, story bin, year bin, ENERGY STAR score, total EUI (kBtu/sf)
- **No per-fuel EUI breakdown** — used for uncalibrated baseline validation only
- Already contains predictions from prior model versions (RF v0/v1, XGB v0/v1/v2) for comparison context

### CBECS Mapped CSV (`Validation/CBECS/cbecs2018_mapped_for_xgb.csv`)
- 6,436 commercial building survey records mapped to XGB model feature format
- Fields: building type, sqft, stories, year_built, heating fuel, DHW fuel, HVAC category, climate zone, HDD/CDD, plus **per-fuel EUI** (electricity, natural gas, district heating, other)
- Per-fuel data enables **calibration testing** by converting EUI to utility bill inputs

## Building Selection

~12-15 buildings selected for diversity:

### From ESPM (~8 buildings)
Selected to cover all 5 building types (Multi-Family, MediumOffice, Warehouse, LargeHotel, SmallHotel), a range of climate zones (1A through 6A), sizes (14k to 1M+ sqft), and vintages (<1946 through >2010). Includes edge cases like very low EUI warehouses and high EUI hotels.

ESPM buildings have zipcodes directly in the spreadsheet. Building types map to `BuildingInput` types as follows:
- Multi-Family → "Multi-Family" (routes to ResStock)
- MediumOffice → "Office" (routes to ComStock)
- Warehouse → "Warehouse and Storage" (routes to ComStock)
- LargeHotel / SmallHotel → "Lodging" (routes to ComStock)

### From CBECS (~5 buildings)
Selected for diversity of building type and fuel mix, specifically chosen because they have per-fuel EUI data needed for calibration testing. Includes buildings with district heating, natural gas, electricity-only, and mixed fuel profiles. Avoid selecting buildings where `other_fuel_eui` is a significant fraction of `total_site_eui` since CBECS aggregates propane/fuel oil and we cannot map them to specific fuel types.

**CBECS has no zipcode.** Use a census-division-to-representative-zipcode mapping (from existing `cbecs_run_validation.py`):

| CENDIV | Representative Zipcode | Region |
|--------|----------------------|--------|
| 1 | 02101 (Boston) | New England |
| 2 | 10001 (New York) | Middle Atlantic |
| 3 | 60601 (Chicago) | East North Central |
| 4 | 55401 (Minneapolis) | West North Central |
| 5 | 20001 (Washington DC) | South Atlantic |
| 6 | 37201 (Nashville) | East South Central |
| 7 | 75201 (Dallas) | West South Central |
| 8 | 80201 (Denver) | Mountain |
| 9 | 90001 (Los Angeles) | Pacific |

**CBECS building type mapping** (from existing `cbecs_run_validation.py`):

| CBECS `in.building_type` | `BuildingInput.building_type` |
|--------------------------|-------------------------------|
| LargeOffice, MediumOffice, SmallOffice | Office |
| Hospital, Outpatient | Healthcare |
| LargeHotel, SmallHotel | Lodging |
| PrimarySchool, SecondarySchool | Education |
| FullServiceRestaurant, QuickServiceRestaurant | Food Service |
| RetailStandalone, RetailStripmall | Mercantile |
| Warehouse | Warehouse and Storage |

## Bin-to-Numeric Mapping

Applies to both ESPM and CBECS data, which both use the same bin formats.

### Stories
| Bin | num_stories |
|-----|-------------|
| 1-3 | 2 |
| 4-7 | 5 |
| 8+ | 10 |

### Year Built
| Bin | year_built |
|-----|------------|
| <1946 | 1930 |
| 1946-1959 | 1953 |
| 1960-1979 | 1970 |
| 1980-1999 | 1990 |
| 2000-2009 | 2005 |
| >2010 | 2015 |

## Calibration Conversion (CBECS per-fuel EUI to utility bills)

```
annual_electricity_kwh = electricity_eui_kbtu_sf * sqft / 3.412
annual_natural_gas_therms = natural_gas_eui_kbtu_sf * sqft / 100
annual_district_heating_kbtu = district_heating_eui_kbtu_sf * sqft
```

Other fuel EUI is noted but not currently mapped to a specific fuel type (propane vs fuel oil) since CBECS aggregates them. This means CBECS buildings with significant `other_fuel_eui` will have that consumption silently dropped from calibration. Selected CBECS buildings should have minimal other-fuel consumption.

## Script: `scripts/validate_espm_buildings.py`

### Phase 1: Parse
- Read ESPM spreadsheet via openpyxl, extract building profiles for selected subset
- Read CBECS CSV via csv module, extract selected building profiles
- Map story/year bins to numeric values
- Build `BuildingInput` dicts for each building

### Phase 2: Assess

**Initialization:** Create `ModelManager` (call `index_all()`), `CostCalculatorService`, and `ImputationService` instances. These are the same services the API creates at startup.

For each building:
1. Construct `BuildingInput` from profile data
2. Run `_assess_single()` **uncalibrated** — baseline + all measures
3. If per-fuel EUI available (CBECS buildings):
   - Convert per-fuel EUI to utility bill fields
   - Run `_assess_single()` **calibrated** — baseline + all measures with real consumption data
4. Collect: baseline EUI (predicted vs actual), all measures with savings/costs/payback

**Error handling:** If `_assess_single()` fails for a building, log the error and continue to the next building.

### Phase 3: Output
Write CSV to `scripts/validation_results/espm_validation_YYYYMMDD_HHMMSS.csv`

**CSV Schema — one row per building x measure x calibration_mode:**

| Column | Description |
|--------|-------------|
| `source` | "ESPM" or "CBECS" |
| `building_name` | Property name or CBECS PUBID |
| `building_type` | ComStock building type |
| `sqft` | Square footage |
| `climate_zone` | ASHRAE climate zone |
| `zipcode` | Zipcode |
| `heating_fuel` | Primary heating fuel |
| `calibrated` | True/False |
| `baseline_predicted_eui_kbtu` | Model-predicted total EUI (kBtu/sf) |
| `baseline_actual_eui_kbtu` | ESPM or CBECS actual total EUI (kBtu/sf) |
| `baseline_pct_error` | (predicted - actual) / actual |
| `measure_name` | Upgrade name |
| `upgrade_id` | Numeric upgrade ID |
| `applicable` | True/False |
| `savings_pct` | Total savings % |
| `savings_kbtu_sf` | Savings in kBtu/sf |
| `electricity_savings_kwh` | Per-sf electricity savings |
| `gas_savings_therms` | Per-sf gas savings |
| `other_fuel_savings_kbtu` | Per-sf other fuel savings |
| `installed_cost_total` | Total installed cost ($) |
| `installed_cost_per_sf` | Cost per sqft |
| `payback_years` | Simple payback period |
| `emissions_reduction_pct` | CO2e reduction % |

Plus a **summary row per building** (measure columns blank) showing only baseline comparison.

### Console Output
Prints anomaly flags:
- Baseline prediction error > 30%
- Measure savings < 0.5% or > 60%
- Payback > 100 years or < 0.5 years
- Calibration dramatically shifts results (>50% change in savings for same measure)
- Electricity savings near-zero when gas savings are significant (or vice versa) for measures where this is unexpected

### CLI Flags
- Default: runs entirely offline using embedded/parsed ESPM/CBECS data

## Output Location

`scripts/validation_results/espm_validation_YYYYMMDD_HHMMSS.csv`

Timestamped filenames allow accumulating runs across model retraining cycles for comparison.

## Prior Art

- `Validation/CBECS/cbecs_run_validation.py` — Existing baseline-only CBECS validation script. Calls `model_manager.predict_baseline()` directly (bypasses `BuildingInput`/preprocessor). Contains mappings (`BT_TO_GROUP`, `CENDIV_TO_CLUSTER`, `HVAC_DETAIL`, `DEFAULT_FEATURES`) reused in this design. The new script supersedes this by going through the full `_assess_single()` pipeline and adding upgrade measure validation.

## What This Does NOT Do

- No automated pass/fail assertions (this is a diagnostic tool, not a test suite)
- No BPS API queries (uses pre-collected ESPM/CBECS data)
- No model retraining or modification
- No frontend changes
