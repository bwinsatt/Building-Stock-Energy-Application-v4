"""
Address lookup service: geocodes an address, fetches the building footprint
from OpenStreetMap via Overpass API, extracts building characteristics,
and computes derived fields (sqft, stories).

Ported from AutoBEM project: OSM_footprint_search.py
"""
from __future__ import annotations

import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from geopy.geocoders import Nominatim
from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon

import pgeocode

from app.inference.imputation_service import ImputationService
from app.services.bps_query import check_bps_availability

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Municipal Open Data API endpoints (free, no auth required)
# ---------------------------------------------------------------------------

MUNICIPAL_API_TIMEOUT = 5  # seconds per request

NYC_FOOTPRINTS_URL = "https://data.cityofnewyork.us/resource/5zhs-2jue.json"
NYC_PLUTO_URL = "https://data.cityofnewyork.us/resource/64uk-42ks.json"


def _fetch_nyc_building_data(bin_id: str) -> dict | None:
    """Fetch building data from NYC Open Data using a BIN (Building ID Number).

    Two-step lookup:
    1. Building Footprints API (BIN → BBL, roof height, construction year)
    2. PLUTO API (BBL → num floors, year built, building area, building class)

    Returns combined dict or None on failure. Non-critical fallback — no retries.
    """
    try:
        # Step 1: Building Footprints → get BBL and basic info
        resp = requests.get(
            NYC_FOOTPRINTS_URL,
            params={"bin": bin_id},
            timeout=MUNICIPAL_API_TIMEOUT,
        )
        if resp.status_code != 200 or not resp.json():
            return None

        footprint = resp.json()[0]
        bbl = footprint.get("base_bbl") or footprint.get("mpluto_bbl")
        result = {
            "bbl": bbl,
            "height_roof": footprint.get("heightroof") or footprint.get("height_roof"),
            "construction_year": footprint.get("cnstrct_yr") or footprint.get("construction_year"),
        }

        if not bbl:
            return result if any(result.values()) else None

        # Step 2: PLUTO → get detailed building info
        resp2 = requests.get(
            NYC_PLUTO_URL,
            params={"bbl": bbl},
            timeout=MUNICIPAL_API_TIMEOUT,
        )
        if resp2.status_code == 200 and resp2.json():
            pluto = resp2.json()[0]
            result["numfloors"] = pluto.get("numfloors")
            result["yearbuilt"] = pluto.get("yearbuilt")
            result["bldgarea"] = pluto.get("bldgarea")
            result["bldgclass"] = pluto.get("bldgclass")

        return result if any(result.values()) else None

    except (requests.RequestException, ValueError, KeyError, IndexError):
        logger.debug("NYC Open Data lookup failed for BIN %s", bin_id, exc_info=True)
        return None


def _fetch_nyc_stories_batch(bin_ids: list[str]) -> dict[str, int]:
    """Fetch floor counts for multiple NYC BINs via PLUTO in one request.

    Returns a dict mapping BIN → floor count.
    """
    if not bin_ids:
        return {}
    result: dict[str, int] = {}
    try:
        # Building Footprints API: get BIN → BBL mapping in batch
        where_clause = " OR ".join(f"bin='{bid}'" for bid in bin_ids[:50])
        resp = requests.get(
            NYC_FOOTPRINTS_URL,
            params={"$where": where_clause, "$limit": "50"},
            timeout=MUNICIPAL_API_TIMEOUT,
        )
        if resp.status_code != 200:
            return {}

        bin_to_bbl: dict[str, str] = {}
        for row in resp.json():
            bid = row.get("bin")
            bbl = row.get("base_bbl") or row.get("mpluto_bbl")
            if bid and bbl:
                bin_to_bbl[str(bid)] = str(bbl)

        if not bin_to_bbl:
            return {}

        # PLUTO API: get BBL → numfloors in batch
        bbls = list(set(bin_to_bbl.values()))
        where_clause = " OR ".join(f"bbl='{b}'" for b in bbls[:50])
        resp2 = requests.get(
            NYC_PLUTO_URL,
            params={"$where": where_clause, "$limit": "50"},
            timeout=MUNICIPAL_API_TIMEOUT,
        )
        if resp2.status_code != 200:
            return {}

        bbl_to_floors: dict[str, int] = {}
        for row in resp2.json():
            bbl = row.get("bbl")
            nf = row.get("numfloors")
            if bbl and nf:
                try:
                    bbl_to_floors[str(bbl)] = int(float(nf))
                except (ValueError, TypeError):
                    pass

        # Map back: BIN → floors
        for bid, bbl in bin_to_bbl.items():
            if bbl in bbl_to_floors:
                result[bid] = bbl_to_floors[bbl]

    except (requests.RequestException, ValueError, KeyError):
        logger.debug("NYC batch stories lookup failed", exc_info=True)

    return result


CHICAGO_BUILDINGS_URL = "https://data.cityofchicago.org/resource/syp8-uezg.json"


def _fetch_chicago_stories_batch(building_ids: list[str]) -> dict[str, int]:
    """Fetch story counts for multiple Chicago building IDs in one request.

    Returns a dict mapping building_id → story count.
    """
    if not building_ids:
        return {}
    result: dict[str, int] = {}
    try:
        where_clause = " OR ".join(f"bldg_id='{bid}'" for bid in building_ids[:50])
        resp = requests.get(
            CHICAGO_BUILDINGS_URL,
            params={"$where": where_clause, "$limit": "50"},
            timeout=MUNICIPAL_API_TIMEOUT,
        )
        if resp.status_code != 200:
            return {}

        for row in resp.json():
            bid = row.get("bldg_id")
            stories = row.get("stories")
            if bid and stories:
                try:
                    result[str(bid)] = int(float(stories))
                except (ValueError, TypeError):
                    pass

    except (requests.RequestException, ValueError, KeyError):
        logger.debug("Chicago batch stories lookup failed", exc_info=True)

    return result


def _fetch_chicago_building_data(building_id: str) -> dict | None:
    """Fetch building data from Chicago Open Data using a building ID.

    Single-step lookup via Chicago's building violations/permits dataset.
    Returns dict with keys: stories, year_built, or None on failure.
    """
    try:
        resp = requests.get(
            CHICAGO_BUILDINGS_URL,
            params={"$where": f"bldg_id='{building_id}'"},
            timeout=MUNICIPAL_API_TIMEOUT,
        )
        if resp.status_code != 200 or not resp.json():
            return None

        record = resp.json()[0]
        result = {
            "stories": record.get("stories"),
            "year_built": record.get("year_built"),
        }

        return result if any(result.values()) else None

    except (requests.RequestException, ValueError, KeyError, IndexError):
        logger.debug("Chicago Open Data lookup failed for building_id %s", building_id, exc_info=True)
        return None


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

from app.constants import SQFT_PER_M2
TYPICAL_FLOOR_HEIGHT_M = 3.4


def _is_nan(value) -> bool:
    try:
        return value != value  # NaN != NaN
    except Exception:
        return False


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


# ---------------------------------------------------------------------------
# Overpass API – multiple public endpoints with failover
# ---------------------------------------------------------------------------

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

OVERPASS_HEADERS = {"User-Agent": "BuildingStockEnergyEstimation/1.0"}


def fetch_building_footprints(
    lat: float, lon: float, radius: int = 100
) -> dict | None:
    """Fetch building footprints from OSM Overpass API within radius (meters)."""
    query = f"""
    [out:json][timeout:15];
    (
      way["building"](around:{radius},{lat},{lon});
      relation["building"](around:{radius},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    max_attempts = len(OVERPASS_ENDPOINTS)
    for attempt in range(max_attempts):
        url = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            resp = requests.post(
                url, data={"data": query}, headers=OVERPASS_HEADERS, timeout=30
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 504):
                backoff = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "Overpass %d from %s, retry %d/%d in %.1fs",
                    resp.status_code, url, attempt + 1, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            logger.error("Overpass error %d from %s", resp.status_code, url)
            return None
        except requests.RequestException:
            backoff = (2 ** attempt) + random.uniform(0, 1)
            logger.exception(
                "Overpass request to %s failed, retry %d/%d in %.1fs",
                url, attempt + 1, max_attempts, backoff,
            )
            time.sleep(backoff)
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
    nyc_data = None

    if matched:
        tags = matched["tags"]
        target_polygon = polygon_to_coords(matched["polygon"])

        # Municipal Open Data lookups: preferred source when tags are available
        nyc_data = None
        bin_id = tags.get("nycdoitt:bin")
        if bin_id:
            nyc_data = _fetch_nyc_building_data(bin_id)

        chicago_data = None
        chicago_building_id = tags.get("chicago:building_id")
        if chicago_building_id:
            chicago_data = _fetch_chicago_building_data(chicago_building_id)

        # Stories — municipal data preferred over OSM
        stories_val = None
        stories_src = None
        if nyc_data and nyc_data.get("numfloors"):
            try:
                stories_val = int(float(nyc_data["numfloors"]))
                stories_src = "nyc_opendata"
            except (ValueError, TypeError):
                pass
        if stories_val is None and chicago_data and chicago_data.get("stories"):
            try:
                stories_val = int(float(chicago_data["stories"]))
                stories_src = "chicago_opendata"
            except (ValueError, TypeError):
                pass
        if stories_val is None:
            stories_val, stories_src = _extract_stories(tags)

        building_fields["num_stories"] = {
            "value": stories_val,
            "source": stories_src,
            "confidence": (
                0.95 if stories_src in ("nyc_opendata", "chicago_opendata")
                else 1.0 if stories_src == "osm"
                else 0.7 if stories_src
                else None
            ),
        }

        # Building type
        bt_val, bt_src = _extract_building_type(tags)
        building_fields["building_type"] = {
            "value": bt_val,
            "source": bt_src,
            "confidence": 1.0 if bt_src else None,
        }

        # Sqft — prefer NYC bldgarea if available, else compute from polygon
        sqft_val = None
        sqft_src = None
        sqft_conf = None
        if nyc_data and nyc_data.get("bldgarea"):
            try:
                sqft_val = int(float(nyc_data["bldgarea"]))
                sqft_src = "nyc_opendata"
                sqft_conf = 0.95
            except (ValueError, TypeError):
                pass
        if sqft_val is None and stories_val:
            sqft_val = round(compute_sqft_from_polygon(matched["polygon"], stories_val))
            sqft_src = "computed"
            sqft_conf = 0.8
        building_fields["sqft"] = {
            "value": sqft_val,
            "source": sqft_src,
            "confidence": sqft_conf,
        }

        # Nearby buildings for map (exclude the matched one)
        # Collect municipal IDs from nearby buildings for batch lookup
        nearby_list = [b for b in buildings if b is not matched]
        nyc_bins = {
            b["tags"]["nycdoitt:bin"]: i
            for i, b in enumerate(nearby_list)
            if b["tags"].get("nycdoitt:bin")
        }
        chi_ids = {
            b["tags"]["chicago:building_id"]: i
            for i, b in enumerate(nearby_list)
            if b["tags"].get("chicago:building_id")
        }

        # Batch fetch municipal story data in parallel
        nyc_stories: dict[str, int] = {}
        chi_stories: dict[str, int] = {}
        if nyc_bins or chi_ids:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                if nyc_bins:
                    futures[executor.submit(
                        _fetch_nyc_stories_batch, list(nyc_bins.keys())
                    )] = "nyc"
                if chi_ids:
                    futures[executor.submit(
                        _fetch_chicago_stories_batch, list(chi_ids.keys())
                    )] = "chi"
                for future in as_completed(futures):
                    if futures[future] == "nyc":
                        nyc_stories = future.result()
                    else:
                        chi_stories = future.result()

        for i, b in enumerate(nearby_list):
            # Priority: municipal data → OSM tags (building:levels, height)
            levels = None
            bin_id = b["tags"].get("nycdoitt:bin")
            chi_id = b["tags"].get("chicago:building_id")
            if bin_id and bin_id in nyc_stories:
                levels = nyc_stories[bin_id]
            elif chi_id and chi_id in chi_stories:
                levels = chi_stories[chi_id]
            else:
                levels, _ = _extract_stories(b["tags"])
            nearby_buildings.append({
                "polygon": polygon_to_coords(b["polygon"]),
                "levels": levels,
            })
    else:
        # No building found — populate what we can
        building_fields["num_stories"] = {"value": None, "source": None, "confidence": None}
        building_fields["building_type"] = {"value": None, "source": None, "confidence": None}
        building_fields["sqft"] = {"value": None, "source": None, "confidence": None}

    # Year built from municipal data if not already populated
    if matched and nyc_data and nyc_data.get("yearbuilt"):
        try:
            yb = int(float(nyc_data["yearbuilt"]))
            if yb > 1800:
                building_fields["year_built"] = {
                    "value": yb,
                    "source": "nyc_opendata",
                    "confidence": 0.95,
                }
        except (ValueError, TypeError):
            pass
    if matched and "year_built" not in building_fields and chicago_data and chicago_data.get("year_built"):
        try:
            yb = int(float(chicago_data["year_built"]))
            if yb > 1800:
                building_fields["year_built"] = {
                    "value": yb,
                    "source": "chicago_opendata",
                    "confidence": 0.95,
                }
        except (ValueError, TypeError):
            pass

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

    # Step 6: Check BPS benchmarking data availability
    bps_available = False
    bps_ordinance_name = None
    city = geo.get("city")
    state_name = geo.get("state")

    if city and state_name:
        county = None
        if zipcode:
            try:
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

    # Extract BBL from NYC data if available
    bbl = nyc_data.get("bbl") if nyc_data else None

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
        "bbl": bbl,
    }
