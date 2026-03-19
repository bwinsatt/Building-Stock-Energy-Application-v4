# BPS Benchmarking Data Import — Design Spec

## Overview

Integrate the ability to search and import publicly available energy benchmarking data from Building Performance Standard (BPS) ordinances into the energy assessment tool. When a user looks up an address, the app detects if a benchmarking ordinance covers that location and offers to search for the building's reported energy data. Imported data populates the utility data fields, feeding into the calibration pipeline.

Ported from the standalone [BPS_Query](https://github.com/bwinsatt/BPS_Query.git) repository into an inline backend service module.

## Goals

- Auto-detect benchmarking data availability during address lookup (zero extra user effort)
- Let users import reported energy usage into utility data fields with one click
- Handle data quality issues gracefully — soft warnings for suspicious values, "estimated" labels for derived fuel splits
- Keep the integration simple and decoupled so it doesn't complicate the existing assessment pipeline

## Non-Goals

- Compliance tracking or reporting (BPS_Query's `compliance_checker` is not ported)
- Bulk/batch address queries (BPS_Query's IMT import is not ported)
- Improving address matching robustness (ported as-is, flagged for future work)
- Showing benchmarking data as a standalone comparison view

## Supported Ordinances

16 cities/jurisdictions across 9 states + 1 county, queried via 4 API types:

| API Type | Cities |
|----------|--------|
| **Socrata** (11) | NYC (LL84), Austin (ECAD), Chicago, LA (EBEWE), SF, Berkeley (BESO), Cambridge (BEUDO), Seattle, Orlando (BEWES), Montgomery County MD |
| **ArcGIS** (5) | Denver (Energize Denver), DC (BEPS), Atlanta (CBEEO), Philadelphia |
| **CKAN** (1) | Boston (BERDO) |
| **CSV/Local** (4) | California (AB802), Colorado (BPS), Miami, SF (audit compliance) |

---

## Architecture

### New Files

| File | Responsibility |
|------|---------------|
| `backend/app/services/bps_query.py` | Core query service — orchestrator, async API handlers (Socrata/ArcGIS/CKAN/CSV), address matching, result transformation |
| `backend/app/services/bps_config.py` | Config dict — city/county/state hierarchy, endpoints, API types, field mappings, zipcode overrides |
| `backend/app/data/bps/` | Directory containing 4 CSV files for local ordinances (CA AB802, CO BPS, Miami, SF audit) |
| `frontend/src/composables/useBpsSearch.ts` | BPS search state management composable |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/schemas/lookup_response.py` | Add `bps_available: bool`, `bps_ordinance_name: str \| None` |
| `backend/app/services/address_lookup.py` | Call `check_bps_availability()` after geocoding, add result to response |
| `backend/app/api/routes.py` | Add `GET /bps/search` endpoint |
| `frontend/src/components/BuildingForm.vue` | Add BPS banner UI, import-to-utility-data flow |
| `frontend/src/types/lookup.ts` | Add `bps_available`, `bps_ordinance_name` to lookup types |

### Dependencies Added

| Package | Purpose |
|---------|---------|
| `rapidfuzz` | Address fuzzy matching (88% threshold) |
| `pgeocode` | Zipcode → county resolution |

### Dependencies NOT Ported (dropped from BPS_Query)

| Package | Reason |
|---------|--------|
| `usaddress` | City/state already extracted from Nominatim geocoding |
| `chardet` | CSV files will be saved as UTF-8 |
| `openpyxl` | No file output — everything returns via API |

---

## Data Flow

### Detection (during existing `/lookup`)

```
GET /lookup?address=350 Fifth Avenue, New York, NY
  → geocode → city="New York", state="New York", zipcode="10118"
  → pgeocode(zipcode) → county="New York County"
  → zipcode override check (NYC boroughs, Boston neighborhoods)
  → check_bps_availability("new york", "new york", "new york county")
  → config match found: BPS_CONFIGS["city"]["new york, new york"]
  → LookupResponse includes:
      bps_available: true
      bps_ordinance_name: "NYC LL84"
```

**Zipcode overrides:** NYC borough names (Brooklyn, Queens, Bronx, Staten Island, Manhattan) and Boston neighborhood names (Dorchester, Roxbury, etc.) are mapped back to their parent city via a zipcode lookup table. This ensures "11201" (Brooklyn) triggers "new york, new york" → NYC LL84.

**Config lookup hierarchy:** city → county → state (same 3-tier priority as BPS_Query v2).

### Search

```
GET /bps/search?address=350 Fifth Avenue, New York, NY 10118&city=New+York&state=New+York&zipcode=10118
```

The endpoint accepts optional `city`, `state`, `zipcode`, and `county` query params. When provided (forwarded from the lookup result), the endpoint skips re-geocoding. When omitted, it falls back to Nominatim geocoding.

**Internal flow:**
1. Use provided city/state/zipcode or fall back to Nominatim geocoding; resolve county via pgeocode
2. Apply zipcode overrides
3. Look up config(s) — may match multiple (e.g., city + state level)
4. For each config, query all endpoints for most recent year
5. Extract building number from address → API filter (LIKE query)
6. Normalize address (expand abbreviations: St→Street, Blvd→Boulevard, etc.)
7. Fuzzy match results against normalized address (RapidFuzz, 88% threshold)
8. Pick highest confidence match
9. Transform API-specific fields to standard schema
10. Return standardized result

### Response Schema

```json
{
  "ordinance_name": "NYC LL84",
  "reporting_year": 2023,
  "property_name": "Empire State Building",
  "matched_address": "350 5TH AVENUE",
  "match_confidence": 0.94,
  "site_eui_kbtu_sf": 72.4,
  "electricity_kwh": 485200,
  "natural_gas_therms": 8340,
  "fuel_oil_gallons": null,
  "energy_star_score": 81,
  "has_per_fuel_data": true
}
```

When `has_per_fuel_data` is `false`, only `site_eui_kbtu_sf` is populated. The frontend uses predicted baseline fuel mix ratios to split aggregate EUI into per-fuel values.

### Import to Utility Data

On "Import to Utility Data" click:

**When `has_per_fuel_data: true`:**
- Directly populate utility fields (`annual_electricity_kwh`, `annual_natural_gas_therms`, etc.)
- Source badges show "benchmarking"

**When `has_per_fuel_data: false`:**
- **Frontend computes the fuel split** using the predicted baseline EUI (already available from a prior assessment run, or triggered on-demand). The baseline's per-fuel ratios are applied to the aggregate Site EUI to estimate per-fuel consumption.
- Convert Site EUI (kBtu/ft²) back to annual consumption units using building sqft
- Source badges show "estimated" with tooltip: "Per-fuel data not available from benchmarking. Split based on energy use of similar buildings."

**Data quality warning:**
- Compare reported Site EUI against predicted baseline EUI
- If outside **0.4x–2.5x** range, show soft warning: "Reported energy use looks unusual — reported EUI is Nx our estimate for this building type. Data may be inaccurate — review before running assessment."
- User can proceed regardless (no blocking)

---

## Backend Service Design

### `bps_query.py` (~300 lines)

```python
# Public API (sync — pure config lookup, no I/O)
def check_bps_availability(city: str, state: str, county: str | None) -> dict | None
async def query_bps(address: str, city: str, state: str, county: str | None, zipcode: str | None) -> dict | None

# Internal handlers
async def _query_socrata(address: str, config: dict) -> list[dict]
async def _query_arcgis(address: str, config: dict) -> list[dict]
async def _query_ckan(address: str, config: dict) -> list[dict]
def _query_csv(address: str, config: dict) -> list[dict]

# Address matching (ported from bps_utils.py)
def _extract_building_number(address: str) -> str | None
def _normalize_address(address: str) -> str
def _match_address(records: list[dict], address: str, address_field: str) -> dict | None

# Result transformation
def _transform_result(record: dict, config: dict) -> dict
```

**Key patterns:**
- All HTTP calls use `httpx.AsyncClient` with 15-second timeout
- Socrata app token passed via `X-App-Token` header, read from `BPS_SOCRATA_TOKEN` env var
- CSV queries are synchronous file reads (files in `app/data/bps/`)
- Address matching: extract building number → filter results → normalize → fuzzy match (88%)

### `bps_config.py` (~120 lines)

```python
BPS_CONFIGS = {
    "city": {
        "new york, new york": {
            "ordinance_name": "NYC LL84",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cityofnewyork.us/resource/..."},
                ...
            },
            "address_field": "address_1",
            "api_type": "socrata",
        },
        ...
    },
    "county": { ... },
    "state": { ... },
}

# NYC borough zipcodes → "new york", Boston neighborhood zipcodes → "boston"
ZIPCODE_CITY_OVERRIDES = { ... }

# Per-ordinance field mappings: API field name → standard field name
FIELD_MAPPINGS = { ... }
```

### Endpoint Addition

```python
# In routes.py
@router.get("/bps/search")
async def bps_search(address: str):
    """Search benchmarking databases for a building's reported energy data."""
    # Geocode to get city/state/zipcode
    # pgeocode for county
    # Apply zipcode overrides
    # query_bps(...)
    # Return standardized result or error
```

---

## Frontend Design

### `useBpsSearch.ts`

```typescript
export function useBpsSearch() {
  // State
  const loading: Ref<boolean>
  const result: Ref<BpsSearchResult | null>
  const error: Ref<string | null>

  // Actions
  async function search(address: string): Promise<void>
  function clear(): void

  return { loading, result, error, search, clear }
}
```

### BuildingForm.vue Integration

**State additions:**
- Watch `lookupResult.bps_available` — when true, show banner
- `bpsSearch` composable instance for managing search state
- `bpsDismissed` ref — user can dismiss the banner with ✕

**Banner states:**
1. **Available** (`bps_available && !searched && !dismissed`): "Benchmarking data may be available" + ordinance name + "Search Records" button
2. **Loading** (`bpsSearch.loading`): Banner shows spinner
3. **Found** (`bpsSearch.result`): Expanded preview with data + "Import to Utility Data" + dismiss
4. **Not found** (`bpsSearch.result === null && searched`): "No matching record found in {ordinance_name}"
5. **Error** (`bpsSearch.error`): "Search failed, try again later" + retry button

**Import action:**
- Populates utility data fields in the form reactive object
- Sets source badges to "benchmarking" or "estimated" depending on `has_per_fuel_data`
- If predicted baseline is available, compares against reported Site EUI and shows/hides soft warning
- Collapses the banner, expands the utility data section

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| BPS API timeout (>15s) | Return error, frontend shows "Search failed, try again later" |
| BPS API returns error | Same as timeout |
| No fuzzy match above 88% | Return `null` match, frontend shows "No matching record found" |
| Multiple matches above threshold | Pick highest confidence |
| County detection fails (pgeocode) | Skip county-level config lookup, proceed with city/state only |
| Zipcode not in override table | Normal behavior — overrides only apply to NYC/Boston |

---

## Address Matching (Ported As-Is)

The address matching logic is ported directly from BPS_Query without modification:

1. **Extract building number** — regex `^\d+(-\d+)?` (handles "123" and "45-18")
2. **API-level filter** — Socrata: `$where LOWER(addr) LIKE '123 %'`; ArcGIS: `where addr LIKE '123%'`; CKAN: `q=123`; CSV: string startswith
3. **Normalize** — expand abbreviations (St→Street, Blvd→Boulevard, Ave→Avenue, NW→Northwest, ~20 mappings)
4. **Fuzzy match** — RapidFuzz `fuzz.ratio()` on normalized addresses, 88% threshold, pick best

**Known limitations (future improvement area):**
- Doesn't handle "Fifth Avenue" vs "5th Avenue" ordinal conversion
- Building number extraction fails on addresses without leading numbers
- Fuzzy matching can false-positive on short addresses with same number
- No geocoding-based proximity fallback

---

## Integration with Calibration Pipeline

This feature feeds directly into the utility calibration pipeline (spec: `2026-03-18-utility-calibration-design.md`):

```
Address Lookup → BPS Available? → User clicks "Search Records"
  → BPS data returned → User clicks "Import to Utility Data"
  → Utility fields populated (benchmarking or estimated source)
  → User submits assessment
  → Backend: convert_utility_to_eui() → calibrated assessment
```

The imported benchmarking values are treated identically to manually entered utility data — they flow through `convert_utility_to_eui()` and into the calibration pipeline. The only difference is the source badge displayed in the UI.

---

## Operational Notes

- **`pgeocode` data download:** `pgeocode` downloads postal code data from the internet on first import for a given country (~2MB). For Docker/CI, pre-download during image build (`python -c "import pgeocode; pgeocode.Nominatim('US')"`) or bundle the cached file.

## Future Improvements

- **Address matching robustness:** Ordinal conversion (Fifth↔5th), geocoding-based proximity matching, better handling of unit/suite numbers
- **Year selector:** Let users pick which reporting year to import (currently auto-selects most recent)
- **Multi-year trending:** Show EUI trend across available years
- **Additional ordinances:** Add new cities as they publish benchmarking data via public APIs
- **Caching:** Cache BPS query results to avoid re-querying the same address
