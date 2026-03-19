"""BPS benchmarking query service — address matching and availability checks."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.services.bps_config import BPS_CONFIGS, ZIPCODE_CITY_OVERRIDES

# Minimum fuzzy-match confidence (0–1 scale) to accept an address match.
_FUZZY_THRESHOLD = 0.88

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
        # Try the original casing first (abbreviations are title-case keys).
        replacement = _ADDRESS_ABBREVIATIONS.get(part)
        if replacement is None:
            # Also try title-cased version for all-caps input like "NW".
            replacement = _ADDRESS_ABBREVIATIONS.get(part.title())
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
