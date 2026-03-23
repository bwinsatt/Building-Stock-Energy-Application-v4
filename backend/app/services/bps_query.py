"""BPS benchmarking query service — address matching and availability checks."""
from __future__ import annotations

import csv
import logging
import os
import re

import httpx
from rapidfuzz import fuzz

from app.constants import KWH_TO_KBTU, KWH_PER_GALLON_FUEL_OIL
from app.services.bps_config import BPS_CONFIGS, FIELD_MAPPINGS, ZIPCODE_CITY_OVERRIDES

logger = logging.getLogger(__name__)

# Minimum fuzzy-match confidence (0–1 scale) to accept an address match.
_FUZZY_THRESHOLD = 0.88
_KBTU_PER_THERM = 100.0

_ADDRESS_ABBREVIATIONS = {
    "St": "Street", "Ave": "Avenue", "Blvd": "Boulevard", "Dr": "Drive",
    "Rd": "Road", "Ln": "Lane", "Ter": "Terrace", "Ct": "Court",
    "Cir": "Circle", "Pl": "Place", "Sq": "Square", "Wy": "Way",
    "Pkwy": "Parkway", "NW": "Northwest", "NE": "Northeast",
    "SW": "Southwest", "SE": "Southeast", "N": "North", "S": "South",
    "E": "East", "W": "West",
}

# Normalize spelled-out ordinals to numeric form so "Fifth" and "5th" match.
_ORDINAL_WORDS = {
    "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th",
    "fifth": "5th", "sixth": "6th", "seventh": "7th", "eighth": "8th",
    "ninth": "9th", "tenth": "10th", "eleventh": "11th", "twelfth": "12th",
}

# Pre-compile the building-number regex.
_BUILDING_NUMBER_RE = re.compile(r"^\d+(-\d+)?")


def _extract_building_number(address: str) -> str | None:
    """Return the leading building number (e.g. '123' or '45-18'), or None.

    Strips leading zeros so '0801' and '801' are treated as equivalent.
    """
    m = _BUILDING_NUMBER_RE.match(address.strip())
    if not m:
        return None
    return m.group(0).lstrip("0") or "0"


def _normalize_address(address: str) -> str:
    """Lowercase, expand abbreviations, and normalize ordinals."""
    parts = address.split()
    expanded = []
    for part in parts:
        # Strip trailing period (e.g. "St." -> "St") before lookup.
        clean = part.rstrip(".")
        replacement = _ADDRESS_ABBREVIATIONS.get(clean)
        if replacement is None:
            replacement = _ADDRESS_ABBREVIATIONS.get(clean.title())
        expanded.append(replacement if replacement else part)
    result = " ".join(expanded).lower()
    # Normalize spelled-out ordinals → numeric (e.g. "fifth" → "5th")
    for word, numeric in _ORDINAL_WORDS.items():
        result = result.replace(word, numeric)
    return result


def _extract_street(address: str) -> str:
    """Strip city/state/zip suffix from a full address.

    User-typed:  "350 Fifth Avenue, New York, NY 10118" -> "350 Fifth Avenue"
    Nominatim:   "Empire State Building, 350, 5th Avenue, Koreatown, ..." -> "350 5th Avenue"

    BPS API records typically store only the street portion, so we need
    to match against just the street part of the user's full address.
    """
    parts = [p.strip() for p in address.split(",")]

    # If the first part already starts with a building number, it's a
    # simple "350 Fifth Avenue, City, State" format.
    if _BUILDING_NUMBER_RE.match(parts[0]):
        return parts[0]

    # Nominatim format: "Building Name, 350, 5th Avenue, Neighborhood, ..."
    # Find the part that looks like a building number, then combine with
    # the next part (street name).
    for i, part in enumerate(parts):
        if _BUILDING_NUMBER_RE.match(part) and i + 1 < len(parts):
            return f"{part} {parts[i + 1]}"

    # Fallback: return the first part as-is.
    return parts[0]


def _match_address(
    records: list[dict],
    address: str,
    address_field: str,
    alt_address_field: str | None = None,
) -> dict | None:
    """Find the best-matching record by address.

    Checks ``address_field`` first, then ``alt_address_field`` (if provided)
    so that owner-reported addresses (e.g. DC's REPORTEDADDRESS) are also
    considered when the tax-lot address doesn't match.

    Returns ``{"record": <dict>, "confidence": <float>}`` or ``None``.
    """
    fields_to_check = [address_field]
    if alt_address_field:
        fields_to_check.append(alt_address_field)

    # Match against just the street portion — API records typically omit city/state/zip
    street = _extract_street(address)
    normalized_query = _normalize_address(street)
    query_bldg_num = _extract_building_number(address)

    best_score = 0.0
    best_record = None

    for field in fields_to_check:
        # 1. Try direct (exact, case-insensitive) match first.
        for record in records:
            raw = record.get(field, "")
            if raw and _normalize_address(str(raw)) == normalized_query:
                return {"record": record, "confidence": 1.0}

        # 2. Fuzzy matching — only consider records whose building number matches
        #    (when the query has one) to avoid false positives on different buildings.
        for record in records:
            raw = record.get(field, "")
            if not raw:
                continue
            raw_str = str(raw)

            # If the query has a building number, skip records with a different one.
            if query_bldg_num is not None:
                rec_bldg_num = _extract_building_number(raw_str)
                if rec_bldg_num != query_bldg_num:
                    continue

            score = fuzz.ratio(_normalize_address(raw_str), normalized_query) / 100.0
            if score > best_score:
                best_score = score
                best_record = record

    if best_record is not None and best_score >= _FUZZY_THRESHOLD:
        return {"record": best_record, "confidence": best_score}

    return None


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def check_bps_availability(
    city: str,
    state: str,
    county: str | None,
    zipcode: str | None = None,
) -> dict | None:
    """Check whether a BPS/benchmarking ordinance covers the given location.

    Lookup hierarchy (most specific wins): city -> county -> state.

    Returns a dict with ``ordinance_name``, ``config_key``, and ``tier``,
    or ``None`` if no ordinance applies.
    """
    city_lower = city.strip().lower()
    state_lower = state.strip().lower()

    # Apply zipcode overrides (e.g. Brooklyn 11201 -> "new york").
    if zipcode and zipcode in ZIPCODE_CITY_OVERRIDES:
        city_lower = ZIPCODE_CITY_OVERRIDES[zipcode]

    # 1. City tier — key is "{city}, {state}"
    city_key = f"{city_lower}, {state_lower}"
    if city_key in BPS_CONFIGS["city"]:
        cfg = BPS_CONFIGS["city"][city_key]
        return {
            "ordinance_name": cfg["ordinance_name"],
            "config_key": city_key,
            "tier": "city",
        }

    # 2. County tier — key is "{county}, {state}"
    if county:
        county_key = f"{county.strip().lower()}, {state_lower}"
        if county_key in BPS_CONFIGS["county"]:
            cfg = BPS_CONFIGS["county"][county_key]
            return {
                "ordinance_name": cfg["ordinance_name"],
                "config_key": county_key,
                "tier": "county",
            }

    # 3. State tier — key is state name
    if state_lower in BPS_CONFIGS["state"]:
        cfg = BPS_CONFIGS["state"][state_lower]
        return {
            "ordinance_name": cfg["ordinance_name"],
            "config_key": state_lower,
            "tier": "state",
        }

    return None


# ---------------------------------------------------------------------------
# Async API handlers
# ---------------------------------------------------------------------------

_BPS_TIMEOUT = 15.0  # seconds


async def _query_socrata(
    address: str, config: dict, client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query Socrata/SODA API. Returns raw records (most recent year only)."""
    building_number = _extract_building_number(address)
    if not building_number:
        return []

    from app.services.bps_config import BPS_SOCRATA_TOKEN

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

                # Also try zero-padded building numbers (e.g. "0801")
                padded = building_number.zfill(4)
                clauses = [
                    f"LOWER({addr_field}) LIKE '{building_number} %'",
                    f"LOWER({addr_field}) LIKE '{building_number}-%'",
                ]
                if padded != building_number:
                    clauses.append(f"LOWER({addr_field}) LIKE '{padded} %'")
                    clauses.append(f"LOWER({addr_field}) LIKE '{padded}-%'")
                params = {"$where": " OR ".join(clauses)}
                headers = {"X-App-Token": BPS_SOCRATA_TOKEN} if BPS_SOCRATA_TOKEN else {}

                try:
                    resp = await client.get(endpoint, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data:
                            return data
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
                # Some datasets (e.g. DC GIS) zero-pad building numbers
                # ("0801" instead of "801"), so search both forms.
                # Also search alt_address_field if configured (e.g. DC's
                # REPORTEDADDRESS which is the owner-reported street address
                # vs ADDRESSOFRECORD which is the tax lot address).
                padded = building_number.zfill(4)
                search_fields = [addr_field]
                alt_field = config.get("alt_address_field")
                if alt_field:
                    search_fields.append(alt_field)
                clauses = []
                for field in search_fields:
                    clauses.append(f"LOWER({field}) LIKE '{building_number} %'")
                    clauses.append(f"LOWER({field}) LIKE '{building_number}-%'")
                    if padded != building_number:
                        clauses.append(f"LOWER({field}) LIKE '{padded} %'")
                        clauses.append(f"LOWER({field}) LIKE '{padded}-%'")
                params = {
                    "where": " OR ".join(clauses),
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


# ---------------------------------------------------------------------------
# CSV handler (with caching for large files)
# ---------------------------------------------------------------------------

_BPS_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "bps")

# Cache: file_path → {building_number → [rows]}
_csv_cache: dict[str, dict[str, list[dict]]] = {}


def _load_csv_indexed(file_path: str, addr_field: str) -> dict[str, list[dict]]:
    """Load a CSV file and index rows by leading building number.

    Returns a dict mapping building number → list of matching rows.
    Cached after first load so the 55MB CA AB802 file is only read once.
    """
    if file_path in _csv_cache:
        return _csv_cache[file_path]

    if not os.path.exists(file_path):
        logger.warning("BPS CSV file not found: %s", file_path)
        return {}

    index: dict[str, list[dict]] = {}
    try:
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get(addr_field, "")
                bldg_num = _extract_building_number(addr)
                if bldg_num:
                    index.setdefault(bldg_num, []).append(row)
    except Exception as e:
        logger.warning("BPS CSV read failed for %s: %s", file_path, e)
        return {}

    _csv_cache[file_path] = index
    logger.info("BPS CSV cached: %s (%d building numbers)", file_path, len(index))
    return index


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
            if os.path.isabs(csv_filename):
                file_path = csv_filename
            else:
                file_path = os.path.join(_BPS_DATA_DIR, csv_filename)

            index = _load_csv_indexed(file_path, addr_field)
            matches = index.get(building_number, [])
            if matches:
                return matches

    return []


# ---------------------------------------------------------------------------
# Result transformation
# ---------------------------------------------------------------------------


def _transform_result(record: dict, field_mapping: dict) -> dict:
    """Transform API record to standardized BPS result schema."""
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
        "district_heating_kbtu": None,
        "energy_star_score": None,
        "has_per_fuel_data": False,
    }

    # Fields that must be numeric for downstream unit conversions
    _NUMERIC_FIELDS = {
        "site_eui_kbtu_sf", "site_eui_kwh_sf", "electricity_kbtu", "electricity_kwh",
        "natural_gas_kbtu", "natural_gas_therms", "fuel_oil_kbtu", "fuel_oil_gallons",
        "district_steam_kbtu", "district_hot_water_kbtu", "district_heating_kbtu",
        "energy_star_score",
    }

    for api_field, std_field in field_mapping.items():
        value = record.get(api_field)
        if value is not None and value != "":
            try:
                value = float(value)
            except (ValueError, TypeError):
                # Non-numeric value — keep as string for text fields,
                # but set to None for fields that need arithmetic.
                if std_field in _NUMERIC_FIELDS:
                    value = None
            if value is not None:
                if std_field in result:
                    result[std_field] = value
                else:
                    result[std_field] = value

    # Convert intermediate fields to standard units
    # Austin ECAD reports EUI in kWh/sqft — convert to kBtu/sqft
    if result.get("site_eui_kwh_sf") is not None:
        result["site_eui_kbtu_sf"] = result.pop("site_eui_kwh_sf") * KWH_TO_KBTU
    elif "site_eui_kwh_sf" in result:
        del result["site_eui_kwh_sf"]

    if result.get("electricity_kbtu") is not None:
        result["electricity_kwh"] = result.pop("electricity_kbtu") / KWH_TO_KBTU
    elif "electricity_kbtu" in result:
        del result["electricity_kbtu"]

    if result.get("natural_gas_kbtu") is not None:
        result["natural_gas_therms"] = result.pop("natural_gas_kbtu") / _KBTU_PER_THERM
    elif "natural_gas_kbtu" in result:
        del result["natural_gas_kbtu"]

    # Convert fuel oil kBtu to gallons (138.5 kBtu/gallon)
    if result.get("fuel_oil_kbtu") is not None:
        result["fuel_oil_gallons"] = result.pop("fuel_oil_kbtu") / (KWH_PER_GALLON_FUEL_OIL * KWH_TO_KBTU)
    elif "fuel_oil_kbtu" in result:
        del result["fuel_oil_kbtu"]

    # District steam/heating: aggregate all district sources into district_heating_kbtu
    district_total = 0.0
    has_district = False
    for key in ("district_steam_kbtu", "district_hot_water_kbtu"):
        val = result.pop(key, None)
        if val is not None:
            district_total += val
            has_district = True
    if has_district:
        result["district_heating_kbtu"] = district_total

    result["has_per_fuel_data"] = (
        result.get("electricity_kwh") is not None
        or result.get("natural_gas_therms") is not None
        or result.get("district_heating_kbtu") is not None
    )

    return result


# ---------------------------------------------------------------------------
# Query orchestrator
# ---------------------------------------------------------------------------


async def _query_socrata_by_bbl(
    bbl: str, config: dict, client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query NYC LL84 Socrata API by BBL (Borough-Block-Lot).

    Tries both raw (1012710071) and hyphenated (1-01271-0071) BBL formats
    since the dataset contains both.
    """
    from app.services.bps_config import BPS_SOCRATA_TOKEN

    bbl_field = "nyc_borough_block_and_lot"
    raw_bbl = bbl.replace("-", "")
    # Format as hyphenated: B-BBBBB-LLLL
    if "-" not in bbl and len(raw_bbl) == 10:
        hyphenated_bbl = f"{raw_bbl[0]}-{raw_bbl[1:6]}-{raw_bbl[6:]}"
    else:
        hyphenated_bbl = bbl

    clauses = [f"{bbl_field}='{raw_bbl}'"]
    if hyphenated_bbl != raw_bbl:
        clauses.append(f"{bbl_field}='{hyphenated_bbl}'")

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_BPS_TIMEOUT)

    try:
        years = sorted(config["endpoints"].keys(), reverse=True)
        for year in years:
            datasets = config["endpoints"][year]
            if isinstance(datasets, str):
                datasets = {"Benchmarking": datasets}

            for dataset_name, endpoint in datasets.items():
                if not endpoint.startswith("http"):
                    continue
                params = {"$where": " OR ".join(clauses)}
                headers = {"X-App-Token": BPS_SOCRATA_TOKEN} if BPS_SOCRATA_TOKEN else {}

                try:
                    resp = await client.get(endpoint, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data:
                            return data
                except (httpx.TimeoutException, httpx.HTTPError) as e:
                    logger.warning("BPS BBL query failed for %s %s: %s", year, dataset_name, e)
                    continue

        return []
    finally:
        if should_close:
            await client.aclose()


def _build_result(record: dict, ordinance_name: str, config: dict, confidence: float) -> dict:
    """Build a standardized BPS result from a matched record."""
    field_mapping = FIELD_MAPPINGS.get(ordinance_name, {})
    result = _transform_result(record, field_mapping)
    result["ordinance_name"] = ordinance_name
    result["match_confidence"] = confidence

    record_year = record.get("report_year") or record.get("calendar_year") or record.get("year")
    if record_year:
        try:
            result["reporting_year"] = int(record_year)
        except (ValueError, TypeError):
            result["reporting_year"] = None
    else:
        years = sorted(config["endpoints"].keys(), reverse=True)
        result["reporting_year"] = int(years[0]) if years else None

    return result


async def query_bps(
    address: str,
    city: str,
    state: str,
    county: str | None,
    zipcode: str | None = None,
    bbl: str | None = None,
) -> dict | None:
    """Search BPS benchmarking databases for a building."""
    availability = check_bps_availability(city, state, county, zipcode)
    if availability is None:
        return None

    config_key = availability["config_key"]
    tier = availability["tier"]
    config = BPS_CONFIGS[tier][config_key]
    ordinance_name = config["ordinance_name"]
    api_type = config["api_type"]

    # NYC BBL-based lookup — deterministic match, no fuzzy matching needed.
    if bbl and ordinance_name == "NYC LL84":
        records = await _query_socrata_by_bbl(bbl, config)
        if records:
            # Take most recent year
            _YEAR_FIELDS = ("report_year", "calendar_year", "year")
            for yf in _YEAR_FIELDS:
                if records[0].get(yf) is not None:
                    records.sort(key=lambda r: str(r.get(yf, "")), reverse=True)
                    break
            return _build_result(records[0], ordinance_name, config, confidence=1.0)
        logger.info("BBL %s not found in LL84 data, falling back to address matching", bbl)

    # Normalize to street-only before querying and matching — Nominatim
    # addresses include building names, neighborhoods, etc. that break
    # building-number extraction and fuzzy matching.
    street = _extract_street(address)

    if api_type == "socrata":
        records = await _query_socrata(street, config)
    elif api_type == "arcgis":
        records = await _query_arcgis(street, config)
    elif api_type == "ckan":
        records = await _query_ckan(street, config)
    elif api_type == "csv":
        records = _query_csv(street, config)
    else:
        logger.error("Unknown BPS API type: %s", api_type)
        return None

    if not records:
        return None

    # Prefer the most recent reporting year — multi-year datasets return
    # records across all years; sort so the matcher encounters newest first.
    _YEAR_FIELDS = ("report_year", "calendar_year", "year")
    for yf in _YEAR_FIELDS:
        if records[0].get(yf) is not None:
            records.sort(key=lambda r: str(r.get(yf, "")), reverse=True)
            break

    # Narrow results by zipcode when available — addresses like
    # "350 5th Avenue" exist in multiple boroughs/neighborhoods.
    if zipcode and len(records) > 1:
        _ZIP_FIELDS = ("postal_code", "zip", "zipcode", "zip_code", "postcode")
        for zf in _ZIP_FIELDS:
            filtered = [r for r in records if str(r.get(zf, "")).startswith(zipcode)]
            if filtered:
                records = filtered
                break

    match = _match_address(
        records, street, config["address_field"],
        alt_address_field=config.get("alt_address_field"),
    )
    if match is None:
        return None

    return _build_result(match["record"], ordinance_name, config, match["confidence"])
