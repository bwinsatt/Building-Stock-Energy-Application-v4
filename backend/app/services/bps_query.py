"""BPS benchmarking query service — address matching and availability checks."""
from __future__ import annotations

import csv
import logging
import os
import re

import httpx
from rapidfuzz import fuzz

from app.constants import KWH_TO_KBTU
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

# Pre-compile the building-number regex.
_BUILDING_NUMBER_RE = re.compile(r"^\d+(-\d+)?")


def _extract_building_number(address: str) -> str | None:
    """Return the leading building number (e.g. '123' or '45-18'), or None."""
    m = _BUILDING_NUMBER_RE.match(address.strip())
    return m.group(0) if m else None


def _normalize_address(address: str) -> str:
    """Lowercase and expand common street abbreviations."""
    parts = address.split()
    expanded = []
    for part in parts:
        # Strip trailing period (e.g. "St." -> "St") before lookup.
        clean = part.rstrip(".")
        replacement = _ADDRESS_ABBREVIATIONS.get(clean)
        if replacement is None:
            replacement = _ADDRESS_ABBREVIATIONS.get(clean.title())
        expanded.append(replacement if replacement else part)
    return " ".join(expanded).lower()


def _match_address(
    records: list[dict],
    address: str,
    address_field: str,
) -> dict | None:
    """Find the best-matching record by address.

    Returns ``{"record": <dict>, "confidence": <float>}`` or ``None``.
    """
    normalized_query = _normalize_address(address)

    # 1. Try direct (exact, case-insensitive) match first.
    for record in records:
        raw = record.get(address_field, "")
        if raw and _normalize_address(str(raw)) == normalized_query:
            return {"record": record, "confidence": 1.0}

    # 2. Fuzzy matching — only consider records whose building number matches
    #    (when the query has one) to avoid false positives on different buildings.
    query_bldg_num = _extract_building_number(address)

    best_score = 0.0
    best_record = None

    for record in records:
        raw = record.get(address_field, "")
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


# ---------------------------------------------------------------------------
# CSV handler
# ---------------------------------------------------------------------------

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
        "energy_star_score": None,
        "has_per_fuel_data": False,
    }

    for api_field, std_field in field_mapping.items():
        value = record.get(api_field)
        if value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                pass
            if std_field in result:
                result[std_field] = value
            else:
                # Allow intermediate fields (e.g. electricity_kbtu, natural_gas_kbtu)
                result[std_field] = value

    # Convert kBtu fields to user-facing units
    if result.get("electricity_kbtu") is not None:
        result["electricity_kwh"] = result.pop("electricity_kbtu") / KWH_TO_KBTU
    elif "electricity_kbtu" in result:
        del result["electricity_kbtu"]

    if result.get("natural_gas_kbtu") is not None:
        result["natural_gas_therms"] = result.pop("natural_gas_kbtu") / _KBTU_PER_THERM
    elif "natural_gas_kbtu" in result:
        del result["natural_gas_kbtu"]

    result["has_per_fuel_data"] = (
        result.get("electricity_kwh") is not None
        or result.get("natural_gas_therms") is not None
    )

    return result


# ---------------------------------------------------------------------------
# Query orchestrator
# ---------------------------------------------------------------------------


async def query_bps(
    address: str,
    city: str,
    state: str,
    county: str | None,
    zipcode: str | None = None,
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

    match = _match_address(records, address, config["address_field"])
    if match is None:
        return None

    field_mapping = FIELD_MAPPINGS.get(ordinance_name, {})
    result = _transform_result(match["record"], field_mapping)
    result["ordinance_name"] = ordinance_name
    result["match_confidence"] = match["confidence"]

    years = sorted(config["endpoints"].keys(), reverse=True)
    result["reporting_year"] = int(years[0]) if years else None

    return result
