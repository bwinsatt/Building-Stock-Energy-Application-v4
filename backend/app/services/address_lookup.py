"""
Address lookup service: geocodes an address, fetches the building footprint
from OpenStreetMap via Overpass API, extracts building characteristics,
and computes derived fields (sqft, stories).

Ported from AutoBEM project: OSM_footprint_search.py
"""
from __future__ import annotations

import logging
import re
import time

import requests
from geopy.geocoders import Nominatim
from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon

from app.inference.imputation_service import ImputationService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OSM building tag -> our building_type mapping
# ---------------------------------------------------------------------------

OSM_BUILDING_TYPE_MAP: dict[str, str] = {
    "office": "Office",
    "commercial": "Mercantile",
    "retail": "Mercantile",
    "supermarket": "Mercantile",
    "apartments": "Multi-Family",
    "residential": "Multi-Family",
    "school": "Education",
    "university": "Education",
    "college": "Education",
    "hospital": "Healthcare",
    "clinic": "Healthcare",
    "hotel": "Lodging",
    "church": "Religious Worship",
    "cathedral": "Religious Worship",
    "mosque": "Religious Worship",
    "synagogue": "Religious Worship",
    "warehouse": "Warehouse and Storage",
    "industrial": "Warehouse and Storage",
    "restaurant": "Food Service",
    "fast_food": "Food Service",
    "public": "Public Order and Safety",
    "civic": "Public Order and Safety",
    "government": "Public Order and Safety",
    "theatre": "Public Assembly",
    "stadium": "Public Assembly",
    "community_centre": "Public Assembly",
}

SQFT_PER_M2 = 10.7639
TYPICAL_FLOOR_HEIGHT_M = 3.4


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------


def geocode_address(address: str) -> dict | None:
    """Geocode an address string using Nominatim.

    Returns dict with lat, lon, address, zipcode or None if not found.
    """
    geolocator = Nominatim(user_agent="energy_audit_lookup")
    try:
        location = geolocator.geocode(address, addressdetails=True)
    except Exception:
        logger.exception("Geocoding failed for: %s", address)
        return None

    if location is None:
        return None

    # Extract zipcode from address details or raw address string
    zipcode = None
    if hasattr(location, "raw") and "address" in location.raw:
        zipcode = location.raw["address"].get("postcode")

    if zipcode is None:
        # Fallback: regex search for 5-digit zip in address string
        match = re.search(r"\b(\d{5})\b", location.address)
        if match:
            zipcode = match.group(1)

    return {
        "lat": location.latitude,
        "lon": location.longitude,
        "address": location.address,
        "zipcode": zipcode,
    }


# ---------------------------------------------------------------------------
# Overpass API
# ---------------------------------------------------------------------------

OVERPASS_URL = "http://overpass-api.de/api/interpreter"


def fetch_building_footprints(
    lat: float, lon: float, radius: int = 100
) -> dict | None:
    """Fetch building footprints from OSM Overpass API within radius (meters)."""
    query = f"""
    [out:json];
    (
      way["building"](around:{radius},{lat},{lon});
      relation["building"](around:{radius},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    for attempt in range(3):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code == 504:
                logger.warning("Overpass %d, retry %d/3", resp.status_code, attempt + 1)
                time.sleep(2)
                continue
            logger.error("Overpass error: %d", resp.status_code)
            return None
        except requests.RequestException:
            logger.exception("Overpass request failed, attempt %d/3", attempt + 1)
            time.sleep(2)
    return None


# ---------------------------------------------------------------------------
# OSM data parsing
# ---------------------------------------------------------------------------


def parse_osm_footprints(osm_data: dict) -> list[dict]:
    """Parse Overpass response into list of {polygon, tags} dicts."""
    elements = osm_data.get("elements", [])

    # Index nodes
    nodes = {
        e["id"]: (e["lon"], e["lat"])
        for e in elements
        if e["type"] == "node"
    }

    # TODO: Handle relation/multipolygon buildings (currently only processes ways)
    buildings = []
    for e in elements:
        if e["type"] != "way" or "building" not in e.get("tags", {}):
            continue
        coords = [nodes[nid] for nid in e["nodes"] if nid in nodes]
        if len(coords) >= 4 and coords[0] == coords[-1]:
            buildings.append({
                "polygon": Polygon(coords),
                "tags": e.get("tags", {}),
            })
    return buildings


# ---------------------------------------------------------------------------
# Building matching
# ---------------------------------------------------------------------------


def match_building(
    buildings: list[dict],
    lat: float,
    lon: float,
    housenumber: str | None = None,
) -> dict | None:
    """Find the building that best matches the geocoded point.

    Priority: 1) address metadata match, 2) point-in-polygon, 3) nearest.
    """
    if not buildings:
        return None

    point = Point(lon, lat)

    # Try address metadata match first
    if housenumber:
        for b in buildings:
            if b["tags"].get("addr:housenumber") == housenumber:
                return b

    # Try containment
    for b in buildings:
        if b["polygon"].contains(point):
            return b

    # Fallback: nearest boundary
    nearest = min(buildings, key=lambda b: b["polygon"].boundary.distance(point))
    return nearest


# ---------------------------------------------------------------------------
# Area computation
# ---------------------------------------------------------------------------


def _get_utm_transformer(lat: float, lon: float) -> Transformer:
    """Create a WGS84 -> UTM transformer for the given location."""
    utm_zone = int((lon + 180) // 6) + 1
    epsg = 32600 + utm_zone if lat >= 0 else 32700 + utm_zone
    return Transformer.from_crs("EPSG:4326", CRS.from_epsg(epsg), always_xy=True)


def compute_sqft_from_polygon(polygon: Polygon, num_stories: int = 1) -> float:
    """Compute total building sqft from a WGS84 polygon and story count.

    Projects to UTM for accurate area calculation, then converts m2 to sqft.
    """
    centroid = polygon.centroid
    transformer = _get_utm_transformer(centroid.y, centroid.x)

    utm_coords = [transformer.transform(x, y) for x, y in polygon.exterior.coords]
    utm_polygon = Polygon(utm_coords)
    footprint_sqft = utm_polygon.area * SQFT_PER_M2
    return footprint_sqft * num_stories


def polygon_to_coords(polygon: Polygon) -> list[list[float]]:
    """Convert Shapely polygon to [[lat, lon], ...] for frontend."""
    return [[lat, lon] for lon, lat in polygon.exterior.coords]


# ---------------------------------------------------------------------------
# Data extraction from OSM tags
# ---------------------------------------------------------------------------


def _extract_stories(tags: dict) -> tuple[int | None, str | None]:
    """Extract num_stories from OSM tags. Returns (value, source)."""
    levels = tags.get("building:levels")
    if levels is not None:
        try:
            return int(levels), "osm"
        except (ValueError, TypeError):
            pass

    height = tags.get("height")
    if height is not None:
        try:
            h = float(re.sub(r"[^\d.]", "", str(height)))
            return max(1, round(h / TYPICAL_FLOOR_HEIGHT_M)), "computed"
        except (ValueError, TypeError):
            pass

    return None, None


def _extract_building_type(tags: dict) -> tuple[str | None, str | None]:
    """Map OSM building tag to our building_type. Returns (value, source)."""
    osm_type = tags.get("building", "yes")
    mapped = OSM_BUILDING_TYPE_MAP.get(osm_type)
    if mapped:
        return mapped, "osm"
    return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lookup_address(address: str, imputation_service: ImputationService | None = None) -> dict | None:
    """Full address lookup pipeline.

    Returns a dict with all extracted building fields, polygon data,
    and nearby buildings for the map viewer. Returns None if geocoding fails.
    """
    # Step 1: Geocode
    geo = geocode_address(address)
    if geo is None:
        return None

    lat, lon = geo["lat"], geo["lon"]
    zipcode = geo["zipcode"]

    # Step 2: Fetch footprints
    osm_data = fetch_building_footprints(lat, lon, radius=100)
    buildings = parse_osm_footprints(osm_data) if osm_data else []

    # Step 3: Match building
    # Simple heuristic; may not work for all address formats
    housenumber = address.split()[0] if address else None
    matched = match_building(buildings, lat, lon, housenumber)

    # Step 4: Extract data from matched building
    building_fields: dict[str, dict] = {}
    target_polygon = None
    nearby_buildings = []

    if matched:
        tags = matched["tags"]
        target_polygon = polygon_to_coords(matched["polygon"])

        # Stories
        stories_val, stories_src = _extract_stories(tags)
        building_fields["num_stories"] = {
            "value": stories_val,
            "source": stories_src,
            "confidence": 1.0 if stories_src == "osm" else 0.7 if stories_src else None,
        }

        # Building type
        bt_val, bt_src = _extract_building_type(tags)
        building_fields["building_type"] = {
            "value": bt_val,
            "source": bt_src,
            "confidence": 1.0 if bt_src else None,
        }

        # Sqft (computed from polygon if we have stories)
        if stories_val:
            sqft = compute_sqft_from_polygon(matched["polygon"], stories_val)
            building_fields["sqft"] = {
                "value": round(sqft),
                "source": "computed",
                "confidence": 0.8,
            }
        else:
            building_fields["sqft"] = {"value": None, "source": None, "confidence": None}

        # Nearby buildings for map (exclude the matched one)
        for b in buildings:
            if b is matched:
                continue
            levels = None
            try:
                levels = int(b["tags"].get("building:levels", 0)) or None
            except (ValueError, TypeError):
                pass
            nearby_buildings.append({
                "polygon": polygon_to_coords(b["polygon"]),
                "levels": levels,
            })
    else:
        # No building found — populate what we can
        building_fields["num_stories"] = {"value": None, "source": None, "confidence": None}
        building_fields["building_type"] = {"value": None, "source": None, "confidence": None}
        building_fields["sqft"] = {"value": None, "source": None, "confidence": None}

    # Fields we can't get from OSM — placeholders for imputation model later
    for field in ["year_built", "heating_fuel", "dhw_fuel", "hvac_system_type",
                  "wall_construction", "window_type", "window_to_wall_ratio",
                  "lighting_type"]:
        if field not in building_fields:
            building_fields[field] = {"value": None, "source": None, "confidence": None}

    # Step 5: Impute missing fields if service available
    if imputation_service is not None:
        # Gather known fields for imputation input
        known = {}
        bt = building_fields.get("building_type", {}).get("value")
        if bt:
            known["building_type"] = bt
        stories = building_fields.get("num_stories", {}).get("value")
        if stories:
            known["num_stories"] = stories
        sqft_val = building_fields.get("sqft", {}).get("value")
        if sqft_val:
            known["sqft"] = sqft_val
        if zipcode:
            # Use existing zipcode lookup for climate_zone and state
            try:
                from app.services.preprocessor import _get_location_from_zipcode
                state, climate_zone, _ = _get_location_from_zipcode(zipcode)
                known["climate_zone"] = climate_zone
                known["state"] = state
            except (ValueError, Exception):
                pass

        # Only impute fields we don't already have from OSM
        fields_to_impute = [
            f for f in ["heating_fuel", "dhw_fuel", "hvac_system_type",
                        "wall_construction", "window_type",
                        "window_to_wall_ratio", "lighting_type"]
            if building_fields.get(f, {}).get("value") is None
        ]

        if known.get("building_type") and fields_to_impute:
            imputed = imputation_service.predict(known, fields_to_impute)
            for field, result in imputed.items():
                if result["value"] is not None:
                    building_fields[field] = result

    return {
        "address": geo["address"],
        "lat": lat,
        "lon": lon,
        "zipcode": zipcode,
        "building_fields": building_fields,
        "target_building_polygon": target_polygon,
        "nearby_buildings": nearby_buildings,
    }
