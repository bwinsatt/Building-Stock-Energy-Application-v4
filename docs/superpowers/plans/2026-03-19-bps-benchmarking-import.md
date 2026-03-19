# BPS Benchmarking Data Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to search and import publicly available energy benchmarking data from 16 BPS ordinances into the utility data fields, feeding into the calibration pipeline.

**Architecture:** New backend service module (`bps_query.py` + `bps_config.py`) ported from the standalone BPS_Query repo, with async httpx handlers for Socrata/ArcGIS/CKAN APIs and sync CSV queries. Detection hooks into the existing `/lookup` endpoint; search is a new `GET /bps/search` endpoint. Frontend adds an inline banner in BuildingForm.vue with a `useBpsSearch` composable.

**Tech Stack:** Python 3, FastAPI, httpx (async), rapidfuzz, pgeocode, Vue 3 Composition API, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-19-bps-benchmarking-import-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `backend/app/services/bps_config.py` | Config dict — 16 city/county/state configs, zipcode overrides, field mappings |
| `backend/app/services/bps_query.py` | Core query service — availability check, async API handlers, address matching, result transformation |
| `backend/app/data/bps/` | Directory for CSV files (CA AB802, CO BPS, Miami, SF audit) |
| `backend/tests/test_bps_query.py` | Unit + integration tests for BPS query service |
| `frontend/src/composables/useBpsSearch.ts` | BPS search state management composable |
| `frontend/src/types/bps.ts` | TypeScript interfaces for BPS search results |

### Modified Files
| File | Changes |
|------|---------|
| `backend/requirements.txt` | Add `rapidfuzz>=3.0` and `pgeocode>=0.4` |
| `backend/app/schemas/lookup_response.py:11-18` | Add `bps_available`, `bps_ordinance_name`, `city`, `state` fields |
| `backend/app/services/address_lookup.py:250-281,682-690` | Extract city/state from Nominatim, call `check_bps_availability()`, add to response |
| `backend/app/api/routes.py:133-139` | Add `GET /bps/search` endpoint |
| `frontend/src/types/lookup.ts` | Add `bps_available`, `bps_ordinance_name` to `LookupResponse` |
| `frontend/src/components/BuildingForm.vue` | Add BPS banner UI, import-to-utility-data flow |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add rapidfuzz and pgeocode to requirements.txt**

In `backend/requirements.txt`, append after the last line:
```
rapidfuzz>=3.0
pgeocode>=0.4
pytest-asyncio>=0.23
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && pip install -r requirements.txt`
Expected: Both packages install successfully

- [ ] **Step 3: Verify imports work**

Run: `cd backend && python -c "import rapidfuzz; import pgeocode; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Pre-download pgeocode data**

Run: `cd backend && python -c "import pgeocode; pgeocode.Nominatim('US'); print('Data cached')"`
Expected: Downloads US postal data (~2MB) on first run, prints `Data cached`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add rapidfuzz and pgeocode dependencies for BPS integration"
```

---

## Task 2: BPS Config Module

**Files:**
- Create: `backend/app/services/bps_config.py`
- Test: `backend/tests/test_bps_query.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_bps_query.py`:
```python
"""Tests for BPS benchmarking query service."""
from app.services.bps_config import BPS_CONFIGS, ZIPCODE_CITY_OVERRIDES, FIELD_MAPPINGS


def test_bps_configs_has_three_tiers():
    assert "city" in BPS_CONFIGS
    assert "county" in BPS_CONFIGS
    assert "state" in BPS_CONFIGS


def test_nyc_config_exists():
    nyc = BPS_CONFIGS["city"]["new york, new york"]
    assert nyc["ordinance_name"] == "NYC LL84"
    assert nyc["api_type"] == "socrata"
    assert nyc["address_field"] == "address_1"
    assert "2023" in nyc["endpoints"]


def test_all_16_ordinances_present():
    total = (
        len(BPS_CONFIGS["city"])
        + len(BPS_CONFIGS["county"])
        + len(BPS_CONFIGS["state"])
    )
    assert total == 16


def test_zipcode_overrides_nyc():
    # Brooklyn zipcode should map to "new york"
    assert ZIPCODE_CITY_OVERRIDES.get("11201") == "new york"


def test_zipcode_overrides_boston():
    # Dorchester zipcode should map to "boston"
    assert ZIPCODE_CITY_OVERRIDES.get("02125") == "boston"


def test_field_mappings_has_nyc():
    assert "NYC LL84" in FIELD_MAPPINGS
    nyc_map = FIELD_MAPPINGS["NYC LL84"]
    assert "site_eui" in nyc_map or "site_eui_kbtu_ft" in nyc_map
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.bps_config'`

- [ ] **Step 3: Create bps_config.py**

Create `backend/app/services/bps_config.py` with the full config ported from the BPS_Query repo's `bps_config_v2.py`. This is a data-only module.

The config structure:
```python
"""BPS ordinance configuration — endpoints, field mappings, and zipcode overrides."""
import os

# Socrata app token from environment (public app token, not a secret key)
BPS_SOCRATA_TOKEN = os.environ.get("BPS_SOCRATA_TOKEN", "")

BPS_CONFIGS: dict = {
    "state": {
        "california": {
            "ordinance_name": "CA AB802",
            "endpoints": {
                "2018": {"Benchmarking": "CA_AB802_database, 2025.04.28.csv"},
            },
            "address_field": "Address",
            "api_type": "csv",
        },
        "colorado": {
            "ordinance_name": "CO BPS",
            "endpoints": {
                "2022": {"Benchmarking": "CO_BPS_2022-2025, 2025.05.07.csv"},
            },
            "address_field": "address_line_1_107",
            "api_type": "csv",
        },
    },
    "county": {
        "montgomery county, maryland": {
            "ordinance_name": "Montgomery County Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.montgomerycountymd.gov/resource/ensr-8pr2.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
    },
    "city": {
        "new york, new york": {
            "ordinance_name": "NYC LL84",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cityofnewyork.us/resource/5zyy-y8am.json"},
                "2022": {"Benchmarking": "https://data.cityofnewyork.us/resource/7x5e-2fxh.json"},
                "2021": {"Benchmarking": "https://data.cityofnewyork.us/resource/usc3-8zwd.json"},
            },
            "address_field": "address_1",
            "api_type": "socrata",
        },
        "denver, colorado": {
            "ordinance_name": "Energize Denver",
            "endpoints": {
                "2023": {"Benchmarking": "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/_2023_Final_Master_Dataset/FeatureServer/0/query"},
                "2022": {"Benchmarking": "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC__2022_Final_Master_Dataset/FeatureServer/28/query"},
            },
            "address_field": "Street",
            "api_type": "arcgis",
        },
        "washington, district of columbia": {
            "ordinance_name": "DC BEPS",
            "endpoints": {
                "2023": {"Benchmarking": "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Environment_Energy_WebMercator/MapServer/45/query"},
            },
            "address_field": "ADDRESSOFRECORD",
            "api_type": "arcgis",
        },
        "atlanta, georgia": {
            "ordinance_name": "Atlanta CBEEO",
            "endpoints": {
                "2019": {"Benchmarking": "https://services5.arcgis.com/5RxyIIJ9boPdptdo/ArcGIS/rest/services/Energy_Ratings/FeatureServer/14/query"},
            },
            "address_field": "Match_addr",
            "api_type": "arcgis",
        },
        "austin, texas": {
            "ordinance_name": "Austin ECAD",
            "endpoints": {
                "2019": {"Benchmarking": "https://data.austintexas.gov/resource/rs4a-x7f5.json"},
            },
            "address_field": "commercial_property_property_street_address",
            "api_type": "socrata",
        },
        "chicago, illinois": {
            "ordinance_name": "Chicago Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cityofchicago.org/resource/xq83-jr8c.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
        "los angeles, california": {
            "ordinance_name": "LA EBEWE",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.lacity.org/resource/9yda-i4ya.json"},
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "san francisco, california": {
            "ordinance_name": "San Francisco Benchmarking",
            "endpoints": {
                "2011": {
                    "Benchmarking": "https://data.sfgov.org/resource/96ck-qcfe.json",
                    "Audit Compliance": "SF_Audit_Compliance.csv",
                },
            },
            "address_field": "building_address",
            "api_type": "socrata",  # primary; audit compliance is CSV
        },
        "berkeley, california": {
            "ordinance_name": "Berkeley BESO",
            "endpoints": {
                "2020": {"Benchmarking": "https://data.cityofberkeley.info/resource/5vy5-rwja.json"},
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "boston, massachusetts": {
            "ordinance_name": "Boston BERDO",
            "endpoints": {
                "2024": {"Benchmarking": "87521565-7f15-4b8d-a225-ac4df9e3f309"},
                "2023": {"Benchmarking": "cb9ad2aa-eec6-4726-a308-945a215056d5"},
                "2022": {"Benchmarking": "cd2c6809-ee14-4321-9d88-e9b45a840a02"},
                "2021": {"Benchmarking": "a7b155de-10ee-48fc-bd89-fc8e31134913"},
            },
            "base_url": "https://data.boston.gov/api/3/action/datastore_search",
            "address_field": "Building Address",
            "api_type": "ckan",
        },
        "cambridge, massachusetts": {
            "ordinance_name": "Cambridge BEUDO",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cambridgema.gov/resource/72g6-j7aq.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
        "seattle, washington": {
            "ordinance_name": "Seattle Benchmarking",
            "endpoints": {
                "2015": {"Benchmarking": "https://data.seattle.gov/resource/teqw-tu6e.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
        "orlando, florida": {
            "ordinance_name": "Orlando BEWES",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cityoforlando.net/resource/f63n-kp6t.json"},
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "miami, florida": {
            "ordinance_name": "Miami Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "Miami Benchmarking, 2023 Data.csv"},
            },
            "address_field": "Property Address Street*",
            "api_type": "csv",
        },
        "philadelphia, pennsylvania": {
            "ordinance_name": "Philadelphia Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/properties_reported_2023/FeatureServer/0/query"},
                "2022": {"Benchmarking": "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Properties_Reported_2022/FeatureServer/0/query"},
                "2021": {"Benchmarking": "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Properties_Reported_2021/FeatureServer/0/query"},
            },
            "address_field": "street_address",
            "api_type": "arcgis",
        },
    },
}
```

Also include `ZIPCODE_CITY_OVERRIDES` — a flat dict of zipcode → canonical city name. These must be obtained from the original BPS_Query local working directory's `Resources/nyc-zip-codes.csv` (column `ZipCode`, ~200 entries → map to `"new york"`) and `Resources/boston-zip-codes.csv` (column `ZIP5`, ~30 entries → map to `"boston"`). These files are gitignored in BPS_Query and not in the git clone.

**To obtain the data:** Open the BPS_Query working copy on your local machine (the one with the `Resources/` directory), read both CSVs, and inline the zipcodes as a Python dict:
```python
ZIPCODE_CITY_OVERRIDES = {
    # NYC boroughs — from Resources/nyc-zip-codes.csv
    "10001": "new york", "10002": "new york", ...  # ~200 entries
    # Boston neighborhoods — from Resources/boston-zip-codes.csv
    "02101": "boston", "02102": "boston", ...  # ~30 entries
}
```

Also include `FIELD_MAPPINGS` — a dict of `ordinance_name → {api_field: standard_field}`. These must be obtained from the BPS_Query working copy's `Resources/API_Table_and_keys.csv`. The standard fields we care about:
- `site_eui_kbtu_sf` — Site EUI (kBtu/ft²)
- `electricity_kwh` — Annual electricity usage
- `natural_gas_therms` — Annual natural gas usage
- `fuel_oil_gallons` — Annual fuel oil usage
- `energy_star_score` — ENERGY STAR score
- `property_name` — Building/property name
- `matched_address` — Address as stored in the database

If the BPS_Query working copy's `Resources/` directory is unavailable, the field mappings can be bootstrapped by querying each API for a known address (e.g., `350 Fifth Avenue` for NYC) and inspecting the response fields. Start with NYC LL84 as the reference implementation — common Socrata field names for NYC include:
```python
FIELD_MAPPINGS = {
    "NYC LL84": {
        "site_eui_kbtu_ft": "site_eui_kbtu_sf",
        "electricity_use_grid_purchase_kbtu": "electricity_kbtu",
        "natural_gas_use_kbtu": "natural_gas_kbtu",
        "energy_star_score": "energy_star_score",
        "property_name": "property_name",
        "address_1": "matched_address",
    },
    # Add remaining 15 ordinances...
}
```

**Important:** The `electricity_kbtu` and `natural_gas_kbtu` values from APIs are typically in kBtu, not kWh/therms. The `_transform_result` function must convert: `electricity_kwh = electricity_kbtu / 3.412`, `natural_gas_therms = natural_gas_kbtu / 100`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bps_config.py backend/tests/test_bps_query.py
git commit -m "feat: add BPS ordinance config with 16 cities, zipcode overrides, and field mappings"
```

---

## Task 3: Address Matching Utilities

**Files:**
- Create: `backend/app/services/bps_query.py` (partial — utilities only)
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_bps_query.py`:
```python
from app.services.bps_query import (
    _extract_building_number,
    _normalize_address,
    _match_address,
)


def test_extract_building_number_simple():
    assert _extract_building_number("123 Main Street") == "123"


def test_extract_building_number_hyphenated():
    assert _extract_building_number("45-18 Court Square") == "45-18"


def test_extract_building_number_none():
    assert _extract_building_number("Main Street") is None


def test_normalize_address_abbreviations():
    result = _normalize_address("123 Main St NW")
    assert "street" in result
    assert "northwest" in result


def test_normalize_address_lowercase():
    result = _normalize_address("123 BROADWAY")
    assert result == "123 broadway"


def test_match_address_direct():
    records = [
        {"address": "123 Main Street", "eui": 50},
        {"address": "123 Oak Avenue", "eui": 60},
    ]
    result = _match_address(records, "123 Main Street", "address")
    assert result is not None
    assert result["record"]["eui"] == 50


def test_match_address_fuzzy():
    records = [
        {"address": "123 MAIN ST", "eui": 50},
        {"address": "456 Oak Ave", "eui": 60},
    ]
    result = _match_address(records, "123 Main Street", "address")
    assert result is not None
    assert result["record"]["eui"] == 50
    assert result["confidence"] >= 0.88


def test_match_address_no_match():
    records = [
        {"address": "999 Completely Different Road", "eui": 50},
    ]
    result = _match_address(records, "123 Main Street", "address")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_extract_building_number_simple -v`
Expected: FAIL — `ImportError: cannot import name '_extract_building_number'`

- [ ] **Step 3: Create bps_query.py with address utilities**

Create `backend/app/services/bps_query.py`:
```python
"""BPS benchmarking data query service.

Searches public energy benchmarking databases for building energy usage data.
Ported from https://github.com/bwinsatt/BPS_Query.git
"""
import logging
import re

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Address abbreviation expansions (ported from BPS_Query address_normalizer.py)
_ADDRESS_ABBREVIATIONS = {
    "St": "Street", "Ave": "Avenue", "Blvd": "Boulevard", "Dr": "Drive",
    "Rd": "Road", "Ln": "Lane", "Ter": "Terrace", "Ct": "Court",
    "Cir": "Circle", "Pl": "Place", "Sq": "Square", "Wy": "Way",
    "Pkwy": "Parkway", "NW": "Northwest", "NE": "Northeast",
    "SW": "Southwest", "SE": "Southeast", "N": "North", "S": "South",
    "E": "East", "W": "West",
}


def _extract_building_number(address: str) -> str | None:
    """Extract building number from address, including hyphenated (e.g., '45-18')."""
    match = re.match(r"^\d+(-\d+)?", address.strip())
    return match.group(0) if match else None


def _normalize_address(address: str) -> str:
    """Normalize address by expanding abbreviations and lowercasing."""
    for abbr, full in _ADDRESS_ABBREVIATIONS.items():
        address = re.sub(rf"\b{abbr}\b\.?", full, address, flags=re.IGNORECASE)
    return address.lower().strip()


def _match_address(
    records: list[dict], address: str, address_field: str,
) -> dict | None:
    """Match address against records using direct then fuzzy matching.

    Returns dict with 'record' and 'confidence' (0.0-1.0), or None.
    """
    normalized_search = _normalize_address(address)

    # Direct match first
    for record in records:
        record_addr = record.get(address_field, "")
        if _normalize_address(record_addr) == normalized_search:
            return {"record": record, "confidence": 1.0}

    # Fuzzy match fallback
    best_match = None
    best_score = 0.0
    for record in records:
        record_addr = record.get(address_field, "")
        score = fuzz.ratio(_normalize_address(record_addr), normalized_search)
        if score > best_score:
            best_score = score
            best_match = record

    if best_match and best_score >= 88:
        return {"record": best_match, "confidence": best_score / 100.0}

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bps_query.py backend/tests/test_bps_query.py
git commit -m "feat: add BPS address matching utilities (building number extraction, normalization, fuzzy match)"
```

---

## Task 4: Availability Check

**Files:**
- Modify: `backend/app/services/bps_query.py`
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_bps_query.py`:
```python
from app.services.bps_query import check_bps_availability


def test_check_availability_nyc():
    result = check_bps_availability("new york", "new york", None)
    assert result is not None
    assert result["ordinance_name"] == "NYC LL84"


def test_check_availability_county():
    result = check_bps_availability("silver spring", "maryland", "montgomery county")
    assert result is not None
    assert result["ordinance_name"] == "Montgomery County Benchmarking"


def test_check_availability_state():
    result = check_bps_availability("sacramento", "california", None)
    assert result is not None
    assert result["ordinance_name"] == "CA AB802"


def test_check_availability_city_over_state():
    """City-level config should take priority over state-level."""
    result = check_bps_availability("los angeles", "california", None)
    assert result is not None
    assert result["ordinance_name"] == "LA EBEWE"


def test_check_availability_not_found():
    result = check_bps_availability("dallas", "texas", None)
    assert result is None


def test_check_availability_zipcode_override_brooklyn():
    result = check_bps_availability("brooklyn", "new york", None, zipcode="11201")
    assert result is not None
    assert result["ordinance_name"] == "NYC LL84"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_check_availability_nyc -v`
Expected: FAIL — `ImportError: cannot import name 'check_bps_availability'`

- [ ] **Step 3: Implement check_bps_availability**

Add to `backend/app/services/bps_query.py`:
```python
from app.services.bps_config import BPS_CONFIGS, ZIPCODE_CITY_OVERRIDES


def check_bps_availability(
    city: str, state: str, county: str | None, zipcode: str | None = None,
) -> dict | None:
    """Check if a BPS ordinance covers this location.

    Pure config lookup — no I/O. Returns dict with ordinance_name or None.
    Lookup hierarchy: city → county → state (most specific wins).
    """
    # Apply zipcode override (NYC boroughs, Boston neighborhoods)
    effective_city = city
    if zipcode and zipcode in ZIPCODE_CITY_OVERRIDES:
        effective_city = ZIPCODE_CITY_OVERRIDES[zipcode]

    city_key = f"{effective_city.lower()}, {state.lower()}"
    config = BPS_CONFIGS["city"].get(city_key)
    if config:
        return {"ordinance_name": config["ordinance_name"], "config_key": city_key, "tier": "city"}

    if county:
        county_key = f"{county.lower()}, {state.lower()}"
        config = BPS_CONFIGS["county"].get(county_key)
        if config:
            return {"ordinance_name": config["ordinance_name"], "config_key": county_key, "tier": "county"}

    state_key = state.lower()
    config = BPS_CONFIGS["state"].get(state_key)
    if config:
        return {"ordinance_name": config["ordinance_name"], "config_key": state_key, "tier": "state"}

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bps_query.py backend/tests/test_bps_query.py
git commit -m "feat: add BPS availability check with city/county/state hierarchy and zipcode overrides"
```

---

## Task 5: Async API Handlers

**Files:**
- Modify: `backend/app/services/bps_query.py`
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_bps_query.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

from app.services.bps_query import _query_socrata, _query_arcgis, _query_ckan


@pytest.mark.asyncio
async def test_query_socrata_returns_records():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"address_1": "350 5TH AVENUE", "site_eui_kbtu_ft": "72.4"},
        {"address_1": "123 OTHER ST", "site_eui_kbtu_ft": "50.0"},
    ]
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    config = {
        "endpoints": {"2023": {"Benchmarking": "https://example.com/resource/abc.json"}},
        "address_field": "address_1",
        "api_type": "socrata",
    }
    records = await _query_socrata("350 Fifth Avenue", config, client=mock_client)
    assert len(records) == 2
    assert records[0]["address_1"] == "350 5TH AVENUE"


@pytest.mark.asyncio
async def test_query_arcgis_returns_records():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "features": [
            {"attributes": {"Street": "350 5TH AVE", "site_eui": "72.4"}},
        ]
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    config = {
        "endpoints": {"2023": {"Benchmarking": "https://example.com/query"}},
        "address_field": "Street",
        "api_type": "arcgis",
    }
    records = await _query_arcgis("350 Fifth Avenue", config, client=mock_client)
    assert len(records) == 1
    assert records[0]["Street"] == "350 5TH AVE"


@pytest.mark.asyncio
async def test_query_ckan_returns_records():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {"records": [{"Building Address": "100 MAIN ST", "eui": 50}]}
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    config = {
        "endpoints": {"2024": {"Benchmarking": "resource-id-abc"}},
        "base_url": "https://data.boston.gov/api/3/action/datastore_search",
        "address_field": "Building Address",
        "api_type": "ckan",
    }
    records = await _query_ckan("100 Main Street", config, client=mock_client)
    assert len(records) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_query_socrata_returns_records -v`
Expected: FAIL — `ImportError: cannot import name '_query_socrata'`

- [ ] **Step 3: Implement async handlers**

Add to `backend/app/services/bps_query.py`:
```python
import httpx

_BPS_TIMEOUT = 15.0  # seconds


async def _query_socrata(
    address: str, config: dict, client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query Socrata/SODA API. Returns raw records (most recent year only)."""
    building_number = _extract_building_number(address)
    if not building_number:
        return []

    from app.services.bps_config import BPS_SOCRATA_TOKEN

    # Get most recent year's endpoint
    years = sorted(config["endpoints"].keys(), reverse=True)
    addr_field = config["address_field"]

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_BPS_TIMEOUT)

    try:
        for year in years:
            datasets = config["endpoints"][year]
            if isinstance(datasets, str):
                datasets = {"Benchmarking": datasets}

            for dataset_name, endpoint in datasets.items():
                if not endpoint.startswith("http"):
                    continue  # Skip CSV endpoints

                params = {
                    "$where": (
                        f"LOWER({addr_field}) LIKE '{building_number} %' OR "
                        f"LOWER({addr_field}) LIKE '{building_number}-%'"
                    ),
                }
                headers = {"X-App-Token": BPS_SOCRATA_TOKEN} if BPS_SOCRATA_TOKEN else {}

                try:
                    resp = await client.get(endpoint, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data:
                            return data  # Return first year with results
                except (httpx.TimeoutException, httpx.HTTPError) as e:
                    logger.warning("BPS Socrata query failed for %s %s: %s", year, dataset_name, e)
                    continue

        return []
    finally:
        if should_close:
            await client.aclose()


async def _query_arcgis(
    address: str, config: dict, client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query ArcGIS FeatureServer API. Returns raw records (most recent year only)."""
    building_number = _extract_building_number(address)
    if not building_number:
        return []

    addr_field = config["address_field"]
    years = sorted(config["endpoints"].keys(), reverse=True)

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_BPS_TIMEOUT)

    try:
        for year in years:
            datasets = config["endpoints"][year]
            if isinstance(datasets, str):
                datasets = {"Benchmarking": datasets}

            for dataset_name, endpoint in datasets.items():
                params = {
                    "where": (
                        f"LOWER({addr_field}) LIKE '{building_number} %' "
                        f"OR LOWER({addr_field}) LIKE '{building_number}-%'"
                    ),
                    "outFields": "*",
                    "f": "json",
                }
                try:
                    resp = await client.get(endpoint, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data and "features" in data and data["features"]:
                            return [f["attributes"] for f in data["features"]]
                except (httpx.TimeoutException, httpx.HTTPError) as e:
                    logger.warning("BPS ArcGIS query failed for %s %s: %s", year, dataset_name, e)
                    continue

        return []
    finally:
        if should_close:
            await client.aclose()


async def _query_ckan(
    address: str, config: dict, client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query CKAN Datastore API (Boston). Returns raw records (most recent year only)."""
    building_number = _extract_building_number(address)
    if not building_number:
        return []

    base_url = config["base_url"]
    years = sorted(config["endpoints"].keys(), reverse=True)

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_BPS_TIMEOUT)

    try:
        for year in years:
            datasets = config["endpoints"][year]
            if isinstance(datasets, str):
                datasets = {"Benchmarking": datasets}

            for dataset_name, resource_id in datasets.items():
                params = {"resource_id": resource_id, "q": building_number}
                try:
                    resp = await client.get(base_url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        records = data.get("result", {}).get("records", [])
                        if records:
                            return records
                except (httpx.TimeoutException, httpx.HTTPError) as e:
                    logger.warning("BPS CKAN query failed for %s %s: %s", year, dataset_name, e)
                    continue

        return []
    finally:
        if should_close:
            await client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bps_query.py backend/tests/test_bps_query.py
git commit -m "feat: add async BPS API handlers for Socrata, ArcGIS, and CKAN"
```

---

## Task 6: CSV Handler + Data Files

**Files:**
- Modify: `backend/app/services/bps_query.py`
- Create: `backend/app/data/bps/` directory + CSV files
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_bps_query.py`:
```python
from app.services.bps_query import _query_csv


def test_query_csv_returns_records(tmp_path):
    # Create a test CSV
    csv_content = "Address,Site EUI\n123 Main Street,72.4\n456 Oak Ave,50.0\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    config = {
        "endpoints": {"2023": {"Benchmarking": str(csv_file)}},
        "address_field": "Address",
        "api_type": "csv",
    }
    records = _query_csv("123 Main Street", config)
    assert len(records) >= 1
    assert records[0]["Address"] == "123 Main Street"


def test_query_csv_no_match(tmp_path):
    csv_content = "Address,Site EUI\n999 Other Road,72.4\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    config = {
        "endpoints": {"2023": {"Benchmarking": str(csv_file)}},
        "address_field": "Address",
        "api_type": "csv",
    }
    records = _query_csv("123 Main Street", config)
    assert records == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_query_csv_returns_records -v`
Expected: FAIL — `ImportError: cannot import name '_query_csv'`

- [ ] **Step 3: Implement CSV handler**

Add to `backend/app/services/bps_query.py`:
```python
import csv
import os

_BPS_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "bps")


def _query_csv(address: str, config: dict) -> list[dict]:
    """Query local CSV files. Returns raw records filtered by building number."""
    building_number = _extract_building_number(address)
    if not building_number:
        return []

    addr_field = config["address_field"]
    years = sorted(config["endpoints"].keys(), reverse=True)

    for year in years:
        datasets = config["endpoints"][year]
        if isinstance(datasets, str):
            datasets = {"Benchmarking": datasets}

        for dataset_name, csv_filename in datasets.items():
            # Resolve path: absolute paths used as-is (for testing), relative resolved from data dir
            if os.path.isabs(csv_filename):
                file_path = csv_filename
            else:
                file_path = os.path.join(_BPS_DATA_DIR, csv_filename)

            if not os.path.exists(file_path):
                logger.warning("BPS CSV file not found: %s", file_path)
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    filtered = [
                        row for row in reader
                        if row.get(addr_field, "").lower().startswith(f"{building_number} ")
                    ]
                    if filtered:
                        return filtered
            except Exception as e:
                logger.warning("BPS CSV read failed for %s: %s", csv_filename, e)
                continue

    return []
```

- [ ] **Step 4: Create data directory and copy CSV files**

```bash
mkdir -p backend/app/data/bps
```

Copy the 4 CSV files from the BPS_Query local working directory's `Local Databases/` folder into `backend/app/data/bps/`:
- `CA_AB802_database, 2025.04.28.csv`
- `CO_BPS_2022-2025, 2025.05.07.csv`
- `Miami Benchmarking, 2023 Data.csv`
- `SF_Audit_Compliance.csv` (if available)

**Note:** These files are gitignored in BPS_Query. If unavailable, create empty placeholder CSVs and document that they need to be populated. The API-based ordinances (12 of 16) will work without them.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/bps_query.py backend/app/data/bps/ backend/tests/test_bps_query.py
git commit -m "feat: add BPS CSV query handler and data directory"
```

---

## Task 7: Query Orchestrator + Result Transformation

**Files:**
- Modify: `backend/app/services/bps_query.py`
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_bps_query.py`:
```python
from app.services.bps_query import _transform_result, query_bps


def test_transform_result_with_per_fuel_data():
    record = {
        "address_1": "350 5TH AVE",
        "property_name": "Empire State Building",
        "site_eui_kbtu_ft": "72.4",
        "electricity_use_grid_purchase_kbtu": "485200",
        "natural_gas_use_kbtu": "834000",
        "energy_star_score": "81",
    }
    field_mapping = {
        "site_eui_kbtu_ft": "site_eui_kbtu_sf",
        "electricity_use_grid_purchase_kbtu": "electricity_kbtu",
        "natural_gas_use_kbtu": "natural_gas_kbtu",
        "energy_star_score": "energy_star_score",
        "property_name": "property_name",
        "address_1": "matched_address",
    }
    result = _transform_result(record, field_mapping)
    assert result["matched_address"] == "350 5TH AVE"
    assert result["site_eui_kbtu_sf"] == 72.4
    assert result["has_per_fuel_data"] is True


def test_transform_result_without_per_fuel_data():
    record = {
        "address": "123 MAIN ST",
        "site_eui": "60.0",
    }
    field_mapping = {
        "site_eui": "site_eui_kbtu_sf",
        "address": "matched_address",
    }
    result = _transform_result(record, field_mapping)
    assert result["site_eui_kbtu_sf"] == 60.0
    assert result["has_per_fuel_data"] is False
    assert result["electricity_kwh"] is None


@pytest.mark.asyncio
async def test_query_bps_with_mock():
    """Integration test: query_bps routes to correct handler and transforms results."""
    mock_records = [{"address_1": "350 5TH AVENUE", "site_eui_kbtu_ft": "72.4"}]

    with patch("app.services.bps_query._query_socrata", new_callable=AsyncMock) as mock_socrata:
        mock_socrata.return_value = mock_records

        result = await query_bps(
            address="350 Fifth Avenue",
            city="new york",
            state="new york",
            county=None,
            zipcode="10118",
        )
        mock_socrata.assert_called_once()
        assert result is not None
        assert result["ordinance_name"] == "NYC LL84"
        assert result["match_confidence"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_transform_result_with_per_fuel_data -v`
Expected: FAIL — `ImportError: cannot import name '_transform_result'`

- [ ] **Step 3: Implement transformation and orchestrator**

Add to `backend/app/services/bps_query.py`:
```python
from app.services.bps_config import FIELD_MAPPINGS


def _transform_result(record: dict, field_mapping: dict) -> dict:
    """Transform API record to standardized BPS result schema.

    Maps API field names to standard names, converts numeric strings,
    and determines if per-fuel data is available.
    """
    result = {
        "ordinance_name": None,
        "reporting_year": None,
        "property_name": None,
        "matched_address": None,
        "match_confidence": None,
        "site_eui_kbtu_sf": None,
        "electricity_kwh": None,
        "natural_gas_therms": None,
        "fuel_oil_gallons": None,
        "energy_star_score": None,
        "has_per_fuel_data": False,
    }

    for api_field, std_field in field_mapping.items():
        value = record.get(api_field)
        if value is not None and std_field in result:
            # Try numeric conversion
            try:
                value = float(value)
            except (ValueError, TypeError):
                pass
            result[std_field] = value

    # Determine if per-fuel data is present
    result["has_per_fuel_data"] = (
        result.get("electricity_kwh") is not None
        or result.get("natural_gas_therms") is not None
    )

    return result


async def query_bps(
    address: str,
    city: str,
    state: str,
    county: str | None,
    zipcode: str | None = None,
) -> dict | None:
    """Search BPS benchmarking databases for a building.

    Returns standardized result dict or None if not found.
    """
    availability = check_bps_availability(city, state, county, zipcode)
    if availability is None:
        return None

    config_key = availability["config_key"]
    tier = availability["tier"]
    config = BPS_CONFIGS[tier][config_key]
    ordinance_name = config["ordinance_name"]
    api_type = config["api_type"]

    # Route to correct handler
    if api_type == "socrata":
        records = await _query_socrata(address, config)
    elif api_type == "arcgis":
        records = await _query_arcgis(address, config)
    elif api_type == "ckan":
        records = await _query_ckan(address, config)
    elif api_type == "csv":
        records = _query_csv(address, config)
    else:
        logger.error("Unknown BPS API type: %s", api_type)
        return None

    if not records:
        return None

    # Match address
    match = _match_address(records, address, config["address_field"])
    if match is None:
        return None

    # Transform result
    field_mapping = FIELD_MAPPINGS.get(ordinance_name, {})
    result = _transform_result(match["record"], field_mapping)
    result["ordinance_name"] = ordinance_name
    result["match_confidence"] = match["confidence"]

    # Get reporting year from the most recent endpoint key
    years = sorted(config["endpoints"].keys(), reverse=True)
    result["reporting_year"] = int(years[0]) if years else None

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bps_query.py backend/tests/test_bps_query.py
git commit -m "feat: add BPS query orchestrator with result transformation"
```

---

## Task 8: Lookup Response Schema + Address Lookup Integration

**Files:**
- Modify: `backend/app/schemas/lookup_response.py:11-18`
- Modify: `backend/app/services/address_lookup.py:250-281,682-690`
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_bps_query.py`:
```python
from app.schemas.lookup_response import LookupResponse


def test_lookup_response_has_bps_fields():
    resp = LookupResponse(
        address="350 Fifth Avenue, New York, NY",
        lat=40.748,
        lon=-73.985,
        zipcode="10118",
        building_fields={},
        bps_available=True,
        bps_ordinance_name="NYC LL84",
        city="New York",
        state="New York",
    )
    assert resp.bps_available is True
    assert resp.bps_ordinance_name == "NYC LL84"
    assert resp.city == "New York"


def test_lookup_response_bps_defaults():
    resp = LookupResponse(
        address="123 Main St",
        lat=0,
        lon=0,
        building_fields={},
    )
    assert resp.bps_available is False
    assert resp.bps_ordinance_name is None
    assert resp.city is None
    assert resp.state is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_lookup_response_has_bps_fields -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'bps_available'`

- [ ] **Step 3: Update LookupResponse schema**

In `backend/app/schemas/lookup_response.py`, add to the `LookupResponse` class:
```python
    bps_available: bool = False
    bps_ordinance_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
```

- [ ] **Step 4: Update geocode_address to extract city/state**

In `backend/app/services/address_lookup.py`, update `geocode_address()` (around line 276) to also extract city and state from the Nominatim response:

Change the return dict from:
```python
    return {
        "lat": location.latitude,
        "lon": location.longitude,
        "address": location.address,
        "zipcode": zipcode,
    }
```

To:
```python
    # Extract city and state from Nominatim address details
    addr_details = location.raw.get("address", {})
    city = addr_details.get("city") or addr_details.get("town") or addr_details.get("village")
    state = addr_details.get("state")

    return {
        "lat": location.latitude,
        "lon": location.longitude,
        "address": location.address,
        "zipcode": zipcode,
        "city": city,
        "state": state,
    }
```

- [ ] **Step 5: Add BPS availability check to lookup_address**

In `backend/app/services/address_lookup.py`, at the top add the import:
```python
from app.services.bps_query import check_bps_availability
```

Then in `lookup_address()`, before the return statement (around line 682), add:
```python
    # Step 6: Check BPS benchmarking data availability
    bps_available = False
    bps_ordinance_name = None
    city = geo.get("city")
    state_name = geo.get("state")

    if city and state_name:
        # Resolve county from zipcode for county-level config lookup
        county = None
        if zipcode:
            try:
                import pgeocode
                nomi = pgeocode.Nominatim("US")
                result = nomi.query_postal_code(zipcode)
                if hasattr(result, "county_name") and not _is_nan(result.county_name):
                    county = result.county_name
            except Exception:
                pass

        bps_check = check_bps_availability(city, state_name, county, zipcode)
        if bps_check is not None:
            bps_available = True
            bps_ordinance_name = bps_check["ordinance_name"]
```

Add a small helper (or inline) for NaN checking since pgeocode returns numpy NaN:
```python
def _is_nan(value) -> bool:
    try:
        return value != value  # NaN != NaN
    except Exception:
        return False
```

Update the return dict to include BPS fields:
```python
    return {
        "address": geo["address"],
        "lat": lat,
        "lon": lon,
        "zipcode": zipcode,
        "building_fields": building_fields,
        "target_building_polygon": target_polygon,
        "nearby_buildings": nearby_buildings,
        "bps_available": bps_available,
        "bps_ordinance_name": bps_ordinance_name,
        "city": city,
        "state": state_name,
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py -v`
Expected: All tests pass

- [ ] **Step 7: Run full backend test suite**

Run: `cd backend && pytest`
Expected: All existing tests still pass (new fields have defaults)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/lookup_response.py backend/app/services/address_lookup.py backend/tests/test_bps_query.py
git commit -m "feat: add BPS availability detection to address lookup response"
```

---

## Task 9: BPS Search Endpoint

**Files:**
- Modify: `backend/app/api/routes.py:133-139`
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_bps_query.py`:
```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_bps_search_endpoint_live(app_client):
    """E2E: hit live NYC LL84 API for a known address."""
    resp = app_client.get(
        "/bps/search",
        params={
            "address": "350 Fifth Avenue, New York, NY 10118",
            "city": "New York",
            "state": "New York",
            "zipcode": "10118",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ordinance_name"] == "NYC LL84"
    assert data["site_eui_kbtu_sf"] is not None


def test_bps_search_endpoint_no_ordinance(app_client):
    """Non-BPS city should return 404."""
    resp = app_client.get(
        "/bps/search",
        params={
            "address": "123 Main St, Dallas, TX",
            "city": "Dallas",
            "state": "Texas",
        },
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_bps_query.py::test_bps_search_endpoint_no_ordinance -v`
Expected: FAIL — 404 or no route matched

- [ ] **Step 3: Add BPS search endpoint to routes.py**

In `backend/app/api/routes.py`, add the import at the top:
```python
from app.services.bps_query import query_bps, check_bps_availability
```

Add the endpoint after the `/lookup` endpoint (around line 139):
```python
@router.get("/bps/search")
async def bps_search(
    address: str,
    city: str | None = None,
    state: str | None = None,
    zipcode: str | None = None,
    county: str | None = None,
):
    """Search BPS benchmarking databases for a building's energy data."""
    # If city/state not provided, fall back to geocoding
    if not city or not state:
        from app.services.address_lookup import geocode_address
        geo = geocode_address(address)
        if geo is None:
            raise HTTPException(status_code=404, detail="Could not geocode address")
        city = city or geo.get("city")
        state = state or geo.get("state")
        zipcode = zipcode or geo.get("zipcode")

    if not city or not state:
        raise HTTPException(status_code=400, detail="Could not determine city/state")

    # Resolve county if not provided
    if not county and zipcode:
        try:
            import pgeocode
            nomi = pgeocode.Nominatim("US")
            result = nomi.query_postal_code(zipcode)
            if hasattr(result, "county_name"):
                county_val = result.county_name
                if county_val == county_val:  # NaN check
                    county = county_val
        except Exception:
            pass

    result = await query_bps(address, city, state, county, zipcode)
    if result is None:
        raise HTTPException(status_code=404, detail="No benchmarking data found for this address")

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_bps_query.py::test_bps_search_endpoint_no_ordinance -v`
Expected: PASS

- [ ] **Step 5: Run full backend test suite**

Run: `cd backend && pytest`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes.py backend/tests/test_bps_query.py
git commit -m "feat: add GET /bps/search endpoint for benchmarking data queries"
```

---

## Task 10: Frontend BPS Types

**Files:**
- Create: `frontend/src/types/bps.ts`
- Modify: `frontend/src/types/lookup.ts`

- [ ] **Step 1: Create BPS types**

Create `frontend/src/types/bps.ts`:
```typescript
export interface BpsSearchResult {
  ordinance_name: string
  reporting_year: number | null
  property_name: string | null
  matched_address: string | null
  match_confidence: number | null
  site_eui_kbtu_sf: number | null
  electricity_kwh: number | null
  natural_gas_therms: number | null
  fuel_oil_gallons: number | null
  energy_star_score: number | null
  has_per_fuel_data: boolean
}
```

- [ ] **Step 2: Update lookup types**

In `frontend/src/types/lookup.ts`, add to the `LookupResponse` interface:
```typescript
  bps_available: boolean
  bps_ordinance_name: string | null
  city: string | null
  state: string | null
```

- [ ] **Step 3: Type check**

Run: `cd frontend && npm run type-check`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/bps.ts frontend/src/types/lookup.ts
git commit -m "feat: add BPS search result types and BPS fields to lookup response"
```

---

## Task 11: Frontend BPS Search Composable

**Files:**
- Create: `frontend/src/composables/useBpsSearch.ts`

- [ ] **Step 1: Create useBpsSearch composable**

Create `frontend/src/composables/useBpsSearch.ts`:
```typescript
import { ref } from 'vue'
import type { BpsSearchResult } from '@/types/bps'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useBpsSearch() {
  const loading = ref(false)
  const result = ref<BpsSearchResult | null>(null)
  const error = ref<string | null>(null)
  const searched = ref(false)

  async function search(
    address: string,
    city?: string | null,
    state?: string | null,
    zipcode?: string | null,
  ): Promise<void> {
    loading.value = true
    error.value = null
    result.value = null
    searched.value = true

    const params = new URLSearchParams({ address })
    if (city) params.set('city', city)
    if (state) params.set('state', state)
    if (zipcode) params.set('zipcode', zipcode)

    try {
      const resp = await fetch(`${API_BASE}/bps/search?${params}`)
      if (resp.status === 404) {
        // No match found — not an error, just no data
        result.value = null
        return
      }
      if (!resp.ok) {
        throw new Error('Search failed')
      }
      result.value = await resp.json()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Search failed'
    } finally {
      loading.value = false
    }
  }

  function clear() {
    loading.value = false
    result.value = null
    error.value = null
    searched.value = false
  }

  return { loading, result, error, searched, search, clear }
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useBpsSearch.ts
git commit -m "feat: add useBpsSearch composable for BPS benchmarking data queries"
```

---

## Task 12: Frontend BPS Banner in BuildingForm

**Files:**
- Modify: `frontend/src/components/BuildingForm.vue`

This is the largest frontend task. It adds the BPS banner UI with 5 states (available, loading, found, not found, error) and the import-to-utility-data flow.

- [ ] **Step 1: Add imports and state**

In `BuildingForm.vue` `<script setup>`, add:
```typescript
import { useBpsSearch } from '@/composables/useBpsSearch'
import type { BpsSearchResult } from '@/types/bps'

const bpsSearch = useBpsSearch()
const bpsDismissed = ref(false)

// Reset BPS state when address changes
watch(() => lookupResult.value, () => {
  bpsSearch.clear()
  bpsDismissed.value = false
})
```

- [ ] **Step 2: Add BPS banner template**

In the `<template>`, add the banner below the address lookup component (after the AddressLookup component, before the form fields). The banner should follow the mockup from the brainstorming session:

**State 1 — Available:** Shown when `lookupResult?.bps_available && !bpsSearch.searched.value && !bpsDismissed`. Shows ordinance name and "Search Records" button.

**State 2 — Loading:** Shown when `bpsSearch.loading.value`. Shows spinner.

**State 3 — Found:** Shown when `bpsSearch.result.value`. Shows data preview (Site EUI, electricity, gas) with "Import to Utility Data" and dismiss buttons.

**State 4 — Not found:** Shown when `bpsSearch.searched.value && !bpsSearch.result.value && !bpsSearch.error.value && !bpsSearch.loading.value`. Shows "No matching record found."

**State 5 — Error:** Shown when `bpsSearch.error.value`. Shows error message with retry button.

Use the existing styling patterns from BuildingForm.vue. The banner should be a subtle inline element, not a modal or popup. Match the color scheme from the brainstorm mockups (teal/blue gradient for available, green for found, amber for warnings).

- [ ] **Step 3: Add import-to-utility-data handler**

Add a function that handles the "Import to Utility Data" button click:
```typescript
function importBpsData(bpsResult: BpsSearchResult) {
  if (bpsResult.has_per_fuel_data) {
    // Direct import
    if (bpsResult.electricity_kwh != null) {
      utilityData.annual_electricity_kwh = bpsResult.electricity_kwh
      fieldSources.value['annual_electricity_kwh'] = { value: bpsResult.electricity_kwh, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
    if (bpsResult.natural_gas_therms != null) {
      utilityData.annual_natural_gas_therms = bpsResult.natural_gas_therms
      fieldSources.value['annual_natural_gas_therms'] = { value: bpsResult.natural_gas_therms, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
    if (bpsResult.fuel_oil_gallons != null) {
      utilityData.annual_fuel_oil_gallons = bpsResult.fuel_oil_gallons
      fieldSources.value['annual_fuel_oil_gallons'] = { value: bpsResult.fuel_oil_gallons, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
  } else if (bpsResult.site_eui_kbtu_sf != null) {
    // Fuel split from predicted baseline ratios
    // Use the assessment's baseline EUI fuel breakdown if available,
    // otherwise just import the aggregate and tag as estimated
    // This is computed in the frontend using predicted baseline ratios
    // (implementation depends on whether a baseline prediction is available)
    fieldSources.value['annual_electricity_kwh'] = { value: null, source: 'estimated', confidence: null }
    fieldSources.value['annual_natural_gas_therms'] = { value: null, source: 'estimated', confidence: null }
  }

  // Expand utility data section
  showUtilityData.value = true
  // Collapse the BPS banner
  bpsDismissed.value = true
}
```

- [ ] **Step 4: Add soft warning for suspicious data**

The data quality warning compares reported Site EUI against the predicted baseline. `BuildingForm.vue` does not currently have access to `assessmentResult` — it lives in the parent component. To implement the warning:

**Option A (recommended):** Accept an optional `predictedBaselineEui` prop from the parent. The parent passes it down after an assessment is run. When null (no assessment run yet), the warning is not shown.

**Option B:** Import `useAssessment` composable directly into BuildingForm. This adds coupling but is simpler if the assessment composable uses shared state.

Using Option A, add the prop and computed:
```typescript
const props = defineProps<{
  predictedBaselineEui?: number | null
}>()

const bpsWarning = computed(() => {
  if (!bpsSearch.result.value?.site_eui_kbtu_sf) return null
  if (!props.predictedBaselineEui) return null

  const reported = bpsSearch.result.value.site_eui_kbtu_sf
  const ratio = reported / props.predictedBaselineEui
  if (ratio < 0.4 || ratio > 2.5) {
    return `Reported Site EUI (${reported.toFixed(1)} kBtu/ft²) is ${ratio.toFixed(1)}x our estimate (${props.predictedBaselineEui.toFixed(1)} kBtu/ft²) for this building type. The data may be inaccurate — review before running assessment.`
  }
  return null
})
```

**Note:** If no assessment has been run yet (prop is null), the warning simply won't show. This is acceptable — the user can still import the data and will see the warning after running an assessment if the EUI deviates.

Display this warning in the banner when `bpsWarning.value` is truthy — use amber styling matching the mockup.

- [ ] **Step 5: Update sourceLabel for new source types**

The existing `sourceLabel` function uses a Set-based check:
```typescript
const PUBLIC_RECORD_SOURCES = new Set(['osm', 'nyc_opendata', 'chicago_opendata'])
function sourceLabel(source: string | null): string {
  return source && PUBLIC_RECORD_SOURCES.has(source) ? 'public records' : 'estimated'
}
```

Update it to handle the new `'benchmarking'` source:
```typescript
const PUBLIC_RECORD_SOURCES = new Set(['osm', 'nyc_opendata', 'chicago_opendata'])
function sourceLabel(source: string | null): string {
  if (source === 'benchmarking') return 'benchmarking'
  return source && PUBLIC_RECORD_SOURCES.has(source) ? 'public records' : 'estimated'
}
```

And add the corresponding CSS class:
```css
.field-badge--benchmarking {
  background: #d1fae5;
  color: #065f46;
}
```

- [ ] **Step 6: Type check and verify**

Run: `cd frontend && npm run type-check && npm run dev`
Navigate to the app, look up a NYC address. Verify:
- BPS banner appears after lookup
- "Search Records" triggers the search
- Results display correctly
- "Import to Utility Data" populates utility fields

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/BuildingForm.vue
git commit -m "feat: add BPS benchmarking banner with search, preview, and import-to-utility flow"
```

---

## Task 13: E2E Test

**Files:**
- Test: `backend/tests/test_bps_query.py`

- [ ] **Step 1: Add comprehensive e2e test**

Append to `backend/tests/test_bps_query.py`:
```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_bps_full_flow_nyc():
    """E2E: full BPS query flow for a known NYC building."""
    result = await query_bps(
        address="350 Fifth Avenue, New York, NY 10118",
        city="New York",
        state="New York",
        county=None,
        zipcode="10118",
    )
    assert result is not None
    assert result["ordinance_name"] == "NYC LL84"
    assert result["site_eui_kbtu_sf"] is not None
    assert isinstance(result["site_eui_kbtu_sf"], float)
    assert result["match_confidence"] >= 0.88


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_bps_full_flow_chicago():
    """E2E: full BPS query flow for a known Chicago building."""
    result = await query_bps(
        address="233 S Wacker Dr, Chicago, IL 60606",
        city="Chicago",
        state="Illinois",
        county=None,
        zipcode="60606",
    )
    assert result is not None
    assert result["ordinance_name"] == "Chicago Benchmarking"
```

- [ ] **Step 2: Run e2e tests**

Run: `cd backend && pytest tests/test_bps_query.py -v --run-e2e`
Expected: E2E tests pass (hits live APIs — may take 5-15 seconds each)

- [ ] **Step 3: Run full test suite (excluding e2e)**

Run: `cd backend && pytest`
Expected: All non-e2e tests pass, e2e tests skipped

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_bps_query.py
git commit -m "test: add BPS e2e tests for NYC and Chicago live API queries"
```

---

## Execution Order

Tasks are sequential — each builds on the previous:

```
Task 1:  Dependencies
Task 2:  Config module
Task 3:  Address matching utilities
Task 4:  Availability check
Task 5:  Async API handlers (Socrata/ArcGIS/CKAN)
Task 6:  CSV handler + data files
Task 7:  Query orchestrator + result transformation
Task 8:  Lookup response schema + address_lookup integration
Task 9:  BPS search endpoint
Task 10: Frontend BPS types
Task 11: Frontend BPS search composable
Task 12: Frontend BPS banner in BuildingForm
Task 13: E2E test
```

**Tasks 10-11 can run in parallel with Tasks 5-9** (frontend types and composable don't depend on backend being complete).
