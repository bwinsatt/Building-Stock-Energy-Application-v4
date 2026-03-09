# Address Lookup & Auto-Populate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users enter a building address and auto-populate form fields from OSM data + model-based imputation, with a 2.5D MapLibre building viewer.

**Architecture:** New `/lookup` endpoint calls Nominatim (geocode) → Overpass API (building footprint + tags) → imputation models (predict missing fields). Frontend adds address bar above existing form, MapLibre map viewer, and confidence badges on auto-filled fields.

**Tech Stack:** Python (geopy, shapely, pyproj, requests), XGBoost classifiers for imputation, Vue 3, MapLibre GL JS, TypeScript

**Worktree:** `.worktrees/address-lookup` on branch `feature/address-lookup`

**Reference code:** `/Users/brandonwinsatt/Documents/AutoBEM_python_project/OSM_footprint_search.py`

---

## Task 1: Backend — Address Lookup Service (Geocoding + Overpass)

**Files:**
- Create: `backend/app/services/address_lookup.py`
- Create: `backend/tests/test_address_lookup.py`
- Modify: `backend/requirements.txt`

**Step 1: Add dependencies to requirements.txt**

Add these lines to `backend/requirements.txt`:
```
geopy>=2.4
shapely>=2.0
pyproj>=3.6
requests>=2.31
```

Run: `cd backend && pip install -r requirements.txt`

**Step 2: Write failing tests for geocoding and footprint search**

Create `backend/tests/test_address_lookup.py`:

```python
"""Tests for the address lookup service.

These tests mock external APIs (Nominatim, Overpass) to avoid network calls.
"""
import pytest
from unittest.mock import patch, MagicMock
from shapely.geometry import Polygon

from app.services.address_lookup import (
    geocode_address,
    fetch_building_footprints,
    parse_osm_footprints,
    match_building,
    compute_sqft_from_polygon,
    OSM_BUILDING_TYPE_MAP,
    lookup_address,
)


# --- Geocoding tests ---

class TestGeocodeAddress:
    @patch("app.services.address_lookup.Nominatim")
    def test_geocode_returns_lat_lon_and_address(self, mock_nominatim_cls):
        mock_location = MagicMock()
        mock_location.latitude = 41.886
        mock_location.longitude = -87.634
        mock_location.address = "210 N Wells St, Chicago, IL 60606, USA"
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        result = geocode_address("210 N Wells St, Chicago, IL 60606")
        assert result["lat"] == pytest.approx(41.886)
        assert result["lon"] == pytest.approx(-87.634)
        assert "60606" in result["address"]

    @patch("app.services.address_lookup.Nominatim")
    def test_geocode_returns_none_for_bad_address(self, mock_nominatim_cls):
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = None
        mock_nominatim_cls.return_value = mock_geocoder

        result = geocode_address("not a real address xyz123")
        assert result is None


# --- Zipcode extraction ---

class TestZipcodeExtraction:
    @patch("app.services.address_lookup.Nominatim")
    def test_extracts_zipcode_from_address(self, mock_nominatim_cls):
        mock_location = MagicMock()
        mock_location.latitude = 41.886
        mock_location.longitude = -87.634
        mock_location.address = "210 N Wells St, The Loop, Chicago, Cook County, IL, 60606, USA"
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        result = geocode_address("210 N Wells St, Chicago, IL 60606")
        assert result["zipcode"] == "60606"


# --- OSM parsing tests ---

class TestParseOsmFootprints:
    def test_parses_building_ways_into_polygons(self):
        osm_data = {
            "elements": [
                {"type": "node", "id": 1, "lon": -87.634, "lat": 41.886},
                {"type": "node", "id": 2, "lon": -87.633, "lat": 41.886},
                {"type": "node", "id": 3, "lon": -87.633, "lat": 41.887},
                {"type": "node", "id": 4, "lon": -87.634, "lat": 41.887},
                {
                    "type": "way",
                    "id": 100,
                    "nodes": [1, 2, 3, 4, 1],
                    "tags": {"building": "office", "building:levels": "3"},
                },
            ]
        }
        result = parse_osm_footprints(osm_data)
        assert len(result) == 1
        assert result[0]["tags"]["building"] == "office"
        assert result[0]["tags"]["building:levels"] == "3"
        assert isinstance(result[0]["polygon"], Polygon)

    def test_returns_empty_list_when_no_buildings(self):
        osm_data = {"elements": []}
        result = parse_osm_footprints(osm_data)
        assert result == []


# --- Building matching tests ---

class TestMatchBuilding:
    def test_matches_building_containing_point(self):
        # Building polygon surrounds (41.886, -87.634)
        buildings = [
            {
                "polygon": Polygon([
                    (-87.635, 41.885), (-87.633, 41.885),
                    (-87.633, 41.887), (-87.635, 41.887),
                    (-87.635, 41.885),
                ]),
                "tags": {"building": "office"},
            }
        ]
        result = match_building(buildings, 41.886, -87.634, "210")
        assert result is not None
        assert result["tags"]["building"] == "office"

    def test_falls_back_to_nearest_when_no_containment(self):
        # Building polygon does NOT contain point, but is nearby
        buildings = [
            {
                "polygon": Polygon([
                    (-87.640, 41.890), (-87.639, 41.890),
                    (-87.639, 41.891), (-87.640, 41.891),
                    (-87.640, 41.890),
                ]),
                "tags": {"building": "yes"},
            }
        ]
        result = match_building(buildings, 41.886, -87.634, "210")
        assert result is not None  # Falls back to nearest


# --- Area computation tests ---

class TestComputeSqft:
    def test_computes_sqft_from_polygon(self):
        # Roughly 30m x 30m = ~900 m2 = ~9688 sqft
        poly = Polygon([
            (-87.6340, 41.8860), (-87.6336, 41.8860),
            (-87.6336, 41.8863), (-87.6340, 41.8863),
            (-87.6340, 41.8860),
        ])
        sqft = compute_sqft_from_polygon(poly, num_stories=1)
        assert 5000 < sqft < 20000  # Reasonable range for this polygon

    def test_multiplies_by_stories(self):
        poly = Polygon([
            (-87.6340, 41.8860), (-87.6336, 41.8860),
            (-87.6336, 41.8863), (-87.6340, 41.8863),
            (-87.6340, 41.8860),
        ])
        sqft_1 = compute_sqft_from_polygon(poly, num_stories=1)
        sqft_3 = compute_sqft_from_polygon(poly, num_stories=3)
        assert sqft_3 == pytest.approx(sqft_1 * 3, rel=0.01)


# --- Building type mapping ---

class TestBuildingTypeMapping:
    def test_office_maps_correctly(self):
        assert OSM_BUILDING_TYPE_MAP.get("office") == "Office"

    def test_apartments_maps_to_multifamily(self):
        assert OSM_BUILDING_TYPE_MAP.get("apartments") == "Multi-Family"

    def test_generic_yes_not_in_map(self):
        assert "yes" not in OSM_BUILDING_TYPE_MAP


# --- Full lookup integration test (all externals mocked) ---

class TestLookupAddress:
    @patch("app.services.address_lookup.requests.post")
    @patch("app.services.address_lookup.Nominatim")
    def test_full_lookup_returns_expected_structure(
        self, mock_nominatim_cls, mock_post
    ):
        # Mock geocoding
        mock_location = MagicMock()
        mock_location.latitude = 41.886
        mock_location.longitude = -87.634
        mock_location.address = "210 N Wells St, The Loop, Chicago, Cook County, IL, 60606, USA"
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        # Mock Overpass response
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "elements": [
                    {"type": "node", "id": 1, "lon": -87.635, "lat": 41.885},
                    {"type": "node", "id": 2, "lon": -87.633, "lat": 41.885},
                    {"type": "node", "id": 3, "lon": -87.633, "lat": 41.887},
                    {"type": "node", "id": 4, "lon": -87.635, "lat": 41.887},
                    {
                        "type": "way", "id": 100,
                        "nodes": [1, 2, 3, 4, 1],
                        "tags": {"building": "office", "building:levels": "5"},
                    },
                ]
            }),
        )

        result = lookup_address("210 N Wells St, Chicago, IL 60606")
        assert result is not None
        assert result["lat"] == pytest.approx(41.886)
        assert result["lon"] == pytest.approx(-87.634)
        assert result["zipcode"] == "60606"
        assert result["building_fields"]["num_stories"]["value"] == 5
        assert result["building_fields"]["num_stories"]["source"] == "osm"
        assert result["building_fields"]["building_type"]["value"] == "Office"
        assert "target_building_polygon" in result
        assert "nearby_buildings" in result
```

Run: `cd backend && pytest tests/test_address_lookup.py -v`
Expected: FAIL (module does not exist)

**Step 3: Implement address_lookup.py**

Create `backend/app/services/address_lookup.py`:

```python
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


def lookup_address(address: str) -> dict | None:
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

    return {
        "address": geo["address"],
        "lat": lat,
        "lon": lon,
        "zipcode": zipcode,
        "building_fields": building_fields,
        "target_building_polygon": target_polygon,
        "nearby_buildings": nearby_buildings,
    }
```

Run: `cd backend && pytest tests/test_address_lookup.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/services/address_lookup.py backend/tests/test_address_lookup.py
git commit -m "feat: add address lookup service with geocoding and OSM footprint search"
```

---

## Task 2: Backend — `/lookup` API Endpoint

**Files:**
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/schemas/request.py` (add LookupRequest)
- Create: `backend/app/schemas/lookup_response.py`
- Modify: `backend/tests/test_api_integration.py`

**Step 1: Write the response schema**

Create `backend/app/schemas/lookup_response.py`:

```python
from pydantic import BaseModel
from typing import Optional


class FieldResult(BaseModel):
    value: Optional[object] = None
    source: Optional[str] = None  # "osm", "computed", "imputed", None
    confidence: Optional[float] = None


class LookupResponse(BaseModel):
    address: str
    lat: float
    lon: float
    zipcode: Optional[str] = None
    building_fields: dict[str, FieldResult]
    target_building_polygon: Optional[list[list[float]]] = None
    nearby_buildings: list[dict] = []
```

**Step 2: Write failing test for the endpoint**

Add to `backend/tests/test_api_integration.py`:

```python
class TestLookupEndpoint:
    @patch("app.services.address_lookup.requests.post")
    @patch("app.services.address_lookup.Nominatim")
    def test_lookup_returns_building_data(self, mock_nominatim_cls, mock_post, client):
        # Mock geocoding
        mock_location = MagicMock()
        mock_location.latitude = 38.9072
        mock_location.longitude = -77.0369
        mock_location.address = "1600 Pennsylvania Ave NW, Washington, DC, 20500, USA"
        mock_location.raw = {"address": {"postcode": "20500"}}
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        # Mock Overpass
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "elements": [
                    {"type": "node", "id": 1, "lon": -77.037, "lat": 38.907},
                    {"type": "node", "id": 2, "lon": -77.036, "lat": 38.907},
                    {"type": "node", "id": 3, "lon": -77.036, "lat": 38.908},
                    {"type": "node", "id": 4, "lon": -77.037, "lat": 38.908},
                    {
                        "type": "way", "id": 100,
                        "nodes": [1, 2, 3, 4, 1],
                        "tags": {"building": "government", "building:levels": "3"},
                    },
                ]
            }),
        )

        resp = client.get("/lookup", params={"address": "1600 Pennsylvania Ave NW, Washington, DC"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["zipcode"] == "20500"
        assert data["building_fields"]["num_stories"]["value"] == 3
        assert data["target_building_polygon"] is not None

    def test_lookup_returns_404_for_bad_address(self, client):
        with patch("app.services.address_lookup.Nominatim") as mock_cls:
            mock_geocoder = MagicMock()
            mock_geocoder.geocode.return_value = None
            mock_cls.return_value = mock_geocoder

            resp = client.get("/lookup", params={"address": "xyznotreal123"})
            assert resp.status_code == 404
```

Add required imports at top of test file:
```python
from unittest.mock import patch, MagicMock
```

Run: `cd backend && pytest tests/test_api_integration.py::TestLookupEndpoint -v`
Expected: FAIL

**Step 3: Add the endpoint to routes.py**

Add to `backend/app/api/routes.py`:

```python
from app.services.address_lookup import lookup_address
from app.schemas.lookup_response import LookupResponse


@router.get("/lookup", response_model=LookupResponse)
async def lookup(address: str):
    result = lookup_address(address)
    if result is None:
        raise HTTPException(status_code=404, detail="Address not found")
    return result
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_api_integration.py::TestLookupEndpoint -v`
Expected: PASS

Run: `cd backend && pytest`
Expected: All tests PASS (existing + new)

**Step 5: Commit**

```bash
git add backend/app/api/routes.py backend/app/schemas/lookup_response.py backend/tests/test_api_integration.py
git commit -m "feat: add GET /lookup endpoint for address-based building search"
```

---

## Task 3: Backend — Imputation Model Training Script

**Files:**
- Create: `backend/app/inference/imputation_trainer.py`
- Create: `backend/tests/test_imputation.py`

This task creates a standalone training script that reads ComStock/ResStock raw data and trains one XGBoost classifier per target field. The trained models are saved to `XGB_Models/Imputation/`.

**Step 1: Write the training script**

Create `backend/app/inference/imputation_trainer.py`:

```python
"""
Train XGBoost classifiers for imputing missing building characteristics.

Usage:
    python -m app.inference.imputation_trainer \
        --comstock-path ../../ComStock/raw_data/comstock.parquet \
        --resstock-path ../../ResStock/raw_data/resstock.parquet \
        --output-dir ../../XGB_Models/Imputation

Each model predicts one target field given:
    building_type, climate_zone, year_built (vintage), sqft, num_stories, state
"""
from __future__ import annotations

import argparse
import json
import os
import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

# Target fields to train imputation models for
TARGET_FIELDS_COMSTOCK = {
    "heating_fuel": "in.heating_fuel",
    "dhw_fuel": "in.service_water_heating_fuel",
    "hvac_system_type": "in.hvac_system_type",
    "wall_construction": "in.wall_construction_type",
    "window_type": "in.window_type",
    "window_to_wall_ratio": "in.window_to_wall_ratio_category",
    "lighting_type": "in.interior_lighting_generation",
}

# Input feature columns used for prediction
INPUT_FEATURES_COMSTOCK = [
    "in.comstock_building_type_group",
    "in.as_simulated_ashrae_iecc_climate_zone_2006",
    "in.vintage",
    "in.sqft..ft2",
    "in.number_stories",
    "in.state_abbreviation",
]

# Friendly names for features (used in model metadata)
FEATURE_NAMES = [
    "building_type",
    "climate_zone",
    "vintage",
    "sqft",
    "num_stories",
    "state",
]


def train_imputation_models(
    data_path: str,
    output_dir: str,
    dataset: str = "comstock",
) -> dict[str, str]:
    """Train and save imputation models.

    Args:
        data_path: Path to raw parquet data file.
        output_dir: Directory to save trained models.
        dataset: 'comstock' or 'resstock'.

    Returns:
        Dict of {field_name: model_path} for successfully trained models.
    """
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Loading data from %s", data_path)
    df = pd.read_parquet(data_path)

    target_fields = TARGET_FIELDS_COMSTOCK  # Expand for resstock later
    input_features = INPUT_FEATURES_COMSTOCK

    # Check which columns actually exist
    available_inputs = [c for c in input_features if c in df.columns]
    if len(available_inputs) < len(input_features):
        missing = set(input_features) - set(available_inputs)
        logger.warning("Missing input columns: %s", missing)

    trained = {}
    metadata = {}

    for field_name, col_name in target_fields.items():
        if col_name not in df.columns:
            logger.warning("Target column %s not found, skipping %s", col_name, field_name)
            continue

        logger.info("Training imputation model for: %s (%s)", field_name, col_name)

        # Prepare data: drop rows where target or any input is missing
        subset = df[available_inputs + [col_name]].dropna()
        if len(subset) < 100:
            logger.warning("Too few samples for %s (%d), skipping", field_name, len(subset))
            continue

        X = subset[available_inputs].copy()
        y = subset[col_name].copy()

        # Encode categorical features
        encoders = {}
        for col in X.columns:
            if X[col].dtype == object:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                encoders[col] = le

        # Encode target
        target_encoder = LabelEncoder()
        y_encoded = target_encoder.fit_transform(y.astype(str))

        # Train XGBoost
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric="mlogloss",
        )
        model.fit(X, y_encoded)

        # Save model + encoders + metadata
        model_path = os.path.join(output_dir, f"impute_{field_name}.pkl")
        joblib.dump({
            "model": model,
            "feature_encoders": encoders,
            "target_encoder": target_encoder,
            "input_columns": available_inputs,
            "feature_names": FEATURE_NAMES[:len(available_inputs)],
        }, model_path)

        trained[field_name] = model_path
        metadata[field_name] = {
            "n_samples": len(subset),
            "n_classes": len(target_encoder.classes_),
            "classes": target_encoder.classes_.tolist(),
        }
        logger.info("  Saved %s (%d samples, %d classes)",
                     model_path, len(subset), len(target_encoder.classes_))

    # Save metadata summary
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return trained


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Train imputation models")
    parser.add_argument("--comstock-path", required=True, help="Path to ComStock parquet")
    parser.add_argument("--output-dir", default="../../XGB_Models/Imputation")
    args = parser.parse_args()

    train_imputation_models(args.comstock_path, args.output_dir, dataset="comstock")
```

**Step 2: Write tests for the imputation trainer**

Create `backend/tests/test_imputation.py`:

```python
"""Tests for imputation model training and prediction."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
import joblib

from app.inference.imputation_trainer import train_imputation_models


@pytest.fixture
def synthetic_comstock_data(tmp_path):
    """Create a small synthetic dataset mimicking ComStock structure."""
    rng = np.random.default_rng(42)
    n = 500
    df = pd.DataFrame({
        "in.comstock_building_type_group": rng.choice(
            ["Office", "Education", "Mercantile"], n
        ),
        "in.as_simulated_ashrae_iecc_climate_zone_2006": rng.choice(
            ["3A", "4A", "5A"], n
        ),
        "in.vintage": rng.choice(
            ["1980-1989", "1990-1999", "2000-2004"], n
        ),
        "in.sqft..ft2": rng.uniform(5000, 100000, n),
        "in.number_stories": rng.choice([1, 2, 3, 5], n),
        "in.state_abbreviation": rng.choice(["NY", "CA", "TX"], n),
        "in.heating_fuel": rng.choice(["NaturalGas", "Electricity"], n),
        "in.service_water_heating_fuel": rng.choice(["NaturalGas", "Electricity"], n),
        "in.hvac_system_type": rng.choice(["PSZ-AC", "VAV_chiller_boiler"], n),
        "in.wall_construction_type": rng.choice(["Mass", "SteelFrame"], n),
        "in.window_type": rng.choice(
            ["Double, Clear, Metal", "Double, Low-E, Non-metal"], n
        ),
        "in.window_to_wall_ratio_category": rng.choice(["10-20%", "20-30%"], n),
        "in.interior_lighting_generation": rng.choice(["LED", "T8"], n),
    })
    path = tmp_path / "synthetic_comstock.parquet"
    df.to_parquet(path)
    return str(path)


class TestImputationTrainer:
    def test_trains_all_target_models(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        trained = train_imputation_models(
            synthetic_comstock_data, output_dir, dataset="comstock"
        )
        assert "heating_fuel" in trained
        assert "wall_construction" in trained
        assert len(trained) == 7  # All 7 target fields

    def test_saved_models_are_loadable(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        trained = train_imputation_models(
            synthetic_comstock_data, output_dir, dataset="comstock"
        )
        for field, path in trained.items():
            bundle = joblib.load(path)
            assert "model" in bundle
            assert "target_encoder" in bundle
            assert "feature_encoders" in bundle

    def test_model_predicts_with_probabilities(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        trained = train_imputation_models(
            synthetic_comstock_data, output_dir, dataset="comstock"
        )
        bundle = joblib.load(trained["heating_fuel"])
        model = bundle["model"]
        # Single sample prediction
        sample = np.array([[0, 1, 2, 50000, 3, 0]])  # Encoded values
        proba = model.predict_proba(sample)
        assert proba.shape[1] == len(bundle["target_encoder"].classes_)
        assert abs(proba.sum() - 1.0) < 0.01

    def test_metadata_json_created(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        train_imputation_models(synthetic_comstock_data, output_dir)
        import json
        with open(os.path.join(output_dir, "metadata.json")) as f:
            meta = json.load(f)
        assert "heating_fuel" in meta
        assert "n_classes" in meta["heating_fuel"]
```

Run: `cd backend && pytest tests/test_imputation.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add backend/app/inference/imputation_trainer.py backend/tests/test_imputation.py
git commit -m "feat: add XGBoost imputation model trainer for building characteristics"
```

---

## Task 4: Backend — Imputation Service (Runtime Prediction)

**Files:**
- Create: `backend/app/inference/imputation_service.py`
- Modify: `backend/app/services/address_lookup.py` (integrate imputation into lookup)
- Modify: `backend/app/main.py` (load imputation models at startup)
- Create: `backend/tests/test_imputation_service.py`

**Step 1: Write failing tests for imputation service**

Create `backend/tests/test_imputation_service.py`:

```python
"""Tests for the runtime imputation service."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
import joblib
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder

from app.inference.imputation_service import ImputationService


@pytest.fixture
def mock_imputation_models(tmp_path):
    """Create minimal mock imputation models for testing."""
    model_dir = tmp_path / "Imputation"
    model_dir.mkdir()

    # Create a simple model for heating_fuel
    X = np.array([[0, 0, 0, 50000, 3, 0]] * 50 + [[1, 1, 1, 20000, 1, 1]] * 50)
    y = np.array(["NaturalGas"] * 50 + ["Electricity"] * 50)

    feature_cols = [
        "in.comstock_building_type_group",
        "in.as_simulated_ashrae_iecc_climate_zone_2006",
        "in.vintage",
        "in.sqft..ft2",
        "in.number_stories",
        "in.state_abbreviation",
    ]

    target_enc = LabelEncoder()
    y_enc = target_enc.fit_transform(y)

    model = XGBClassifier(n_estimators=10, random_state=42, eval_metric="mlogloss")
    model.fit(X, y_enc)

    # Save with empty feature encoders (inputs are already numeric in test)
    bundle = {
        "model": model,
        "feature_encoders": {},
        "target_encoder": target_enc,
        "input_columns": feature_cols,
        "feature_names": ["building_type", "climate_zone", "vintage", "sqft", "num_stories", "state"],
    }
    joblib.dump(bundle, str(model_dir / "impute_heating_fuel.pkl"))

    return str(model_dir)


class TestImputationService:
    def test_loads_models(self, mock_imputation_models):
        svc = ImputationService(mock_imputation_models)
        svc.load()
        assert "heating_fuel" in svc.models

    def test_predicts_with_confidence(self, mock_imputation_models):
        svc = ImputationService(mock_imputation_models)
        svc.load()

        known_fields = {
            "building_type": "Office",
            "climate_zone": "4A",
            "year_built": 1985,
            "sqft": 50000,
            "num_stories": 3,
            "state": "NY",
        }

        results = svc.predict(known_fields, fields_to_predict=["heating_fuel"])
        assert "heating_fuel" in results
        assert "value" in results["heating_fuel"]
        assert "confidence" in results["heating_fuel"]
        assert results["heating_fuel"]["source"] == "imputed"
        assert 0 <= results["heating_fuel"]["confidence"] <= 1.0

    def test_skips_fields_without_models(self, mock_imputation_models):
        svc = ImputationService(mock_imputation_models)
        svc.load()

        known_fields = {
            "building_type": "Office",
            "climate_zone": "4A",
            "sqft": 50000,
            "num_stories": 3,
            "state": "NY",
        }

        results = svc.predict(known_fields, fields_to_predict=["wall_construction"])
        # No model for wall_construction in our mock, should not error
        assert "wall_construction" not in results or results["wall_construction"]["value"] is None
```

Run: `cd backend && pytest tests/test_imputation_service.py -v`
Expected: FAIL (module does not exist)

**Step 2: Implement imputation service**

Create `backend/app/inference/imputation_service.py`:

```python
"""Runtime imputation service that predicts missing building characteristics."""
from __future__ import annotations

import logging
import os

import joblib
import numpy as np

from app.services.preprocessor import year_to_vintage

logger = logging.getLogger(__name__)


class ImputationService:
    """Loads pre-trained imputation models and predicts missing fields."""

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.models: dict[str, dict] = {}

    def load(self) -> None:
        """Load all imputation models from model_dir."""
        if not os.path.isdir(self.model_dir):
            logger.warning("Imputation model dir not found: %s", self.model_dir)
            return

        for filename in os.listdir(self.model_dir):
            if filename.startswith("impute_") and filename.endswith(".pkl"):
                field_name = filename[len("impute_"):-len(".pkl")]
                path = os.path.join(self.model_dir, filename)
                try:
                    bundle = joblib.load(path)
                    self.models[field_name] = bundle
                    logger.info("Loaded imputation model: %s", field_name)
                except Exception:
                    logger.exception("Failed to load imputation model: %s", path)

        logger.info("Loaded %d imputation models", len(self.models))

    def predict(
        self,
        known_fields: dict,
        fields_to_predict: list[str] | None = None,
    ) -> dict[str, dict]:
        """Predict missing field values with confidence.

        Args:
            known_fields: Dict with keys like building_type, climate_zone,
                year_built, sqft, num_stories, state.
            fields_to_predict: Which fields to impute. If None, predicts all
                fields that have models loaded.

        Returns:
            Dict of {field_name: {value, source, confidence}}.
        """
        if fields_to_predict is None:
            fields_to_predict = list(self.models.keys())

        results = {}

        for field in fields_to_predict:
            if field not in self.models:
                results[field] = {"value": None, "source": None, "confidence": None}
                continue

            bundle = self.models[field]
            model = bundle["model"]
            feature_encoders = bundle["feature_encoders"]
            target_encoder = bundle["target_encoder"]
            input_columns = bundle["input_columns"]

            try:
                # Build input feature vector
                raw_values = self._map_known_to_input(known_fields, input_columns)
                encoded = self._encode_features(raw_values, input_columns, feature_encoders)

                X = np.array([encoded])
                proba = model.predict_proba(X)
                pred_idx = np.argmax(proba[0])
                confidence = float(proba[0][pred_idx])
                predicted_value = target_encoder.inverse_transform([pred_idx])[0]

                results[field] = {
                    "value": predicted_value,
                    "source": "imputed",
                    "confidence": round(confidence, 3),
                }
            except Exception:
                logger.exception("Imputation failed for field: %s", field)
                results[field] = {"value": None, "source": None, "confidence": None}

        return results

    def _map_known_to_input(
        self, known_fields: dict, input_columns: list[str]
    ) -> list:
        """Map user-friendly known_fields to the model's input column order."""
        # Mapping from known_fields keys to input column names
        key_to_col = {
            "building_type": "in.comstock_building_type_group",
            "climate_zone": "in.as_simulated_ashrae_iecc_climate_zone_2006",
            "year_built": "in.vintage",
            "sqft": "in.sqft..ft2",
            "num_stories": "in.number_stories",
            "state": "in.state_abbreviation",
        }
        col_to_key = {v: k for k, v in key_to_col.items()}

        values = []
        for col in input_columns:
            key = col_to_key.get(col)
            if key is None:
                values.append(0)  # Unknown column
                continue
            val = known_fields.get(key)
            # Convert year_built to vintage string
            if key == "year_built" and isinstance(val, (int, float)):
                val = year_to_vintage(int(val))
            elif key == "year_built" and val is None:
                val = "1980-1989"  # Default vintage
            values.append(val)
        return values

    def _encode_features(
        self,
        raw_values: list,
        input_columns: list[str],
        feature_encoders: dict,
    ) -> list:
        """Encode categorical values using the saved label encoders."""
        encoded = []
        for col, val in zip(input_columns, raw_values):
            if col in feature_encoders:
                le = feature_encoders[col]
                val_str = str(val)
                if val_str in le.classes_:
                    encoded.append(le.transform([val_str])[0])
                else:
                    # Unknown category: use 0 (most common)
                    encoded.append(0)
            else:
                encoded.append(val if isinstance(val, (int, float)) else 0)
        return encoded
```

Run: `cd backend && pytest tests/test_imputation_service.py -v`
Expected: All PASS

**Step 3: Integrate imputation into address lookup**

Add to `backend/app/services/address_lookup.py`, in the `lookup_address` function, after the OSM extraction section and before the return statement:

At the top, add import:
```python
from app.inference.imputation_service import ImputationService
```

Update the `lookup_address` function signature to accept an optional imputation service:

```python
def lookup_address(address: str, imputation_service: ImputationService | None = None) -> dict | None:
```

Before the return, add imputation logic:
```python
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
```

**Step 4: Load imputation service at startup**

Modify `backend/app/main.py` to load imputation models:

```python
from app.inference.imputation_service import ImputationService
```

In the lifespan, after existing model loading:
```python
    imputation_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "XGB_Models", "Imputation"
    )
    imputation_service = ImputationService(imputation_dir)
    imputation_service.load()
    app.state.imputation_service = imputation_service
```

Add `import os` at top.

Update the `/lookup` endpoint in `routes.py` to pass the imputation service:

```python
@router.get("/lookup", response_model=LookupResponse)
async def lookup(address: str, req: Request):
    imputation_service = getattr(req.app.state, "imputation_service", None)
    result = lookup_address(address, imputation_service=imputation_service)
    if result is None:
        raise HTTPException(status_code=404, detail="Address not found")
    return result
```

**Step 5: Run all tests**

Run: `cd backend && pytest -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/app/inference/imputation_service.py backend/tests/test_imputation_service.py backend/app/services/address_lookup.py backend/app/main.py backend/app/api/routes.py
git commit -m "feat: add runtime imputation service and integrate with address lookup"
```

---

## Task 5: Frontend — Address Lookup Composable

**Files:**
- Create: `frontend/src/composables/useAddressLookup.ts`
- Create: `frontend/src/types/lookup.ts`

**Step 1: Create lookup types**

Create `frontend/src/types/lookup.ts`:

```typescript
export interface FieldResult {
  value: string | number | null
  source: 'osm' | 'computed' | 'imputed' | null
  confidence: number | null
}

export interface LookupResponse {
  address: string
  lat: number
  lon: number
  zipcode: string | null
  building_fields: Record<string, FieldResult>
  target_building_polygon: number[][] | null
  nearby_buildings: Array<{
    polygon: number[][]
    levels: number | null
  }>
}
```

**Step 2: Create the composable**

Create `frontend/src/composables/useAddressLookup.ts`:

```typescript
import { ref } from 'vue'
import type { LookupResponse } from '../types/lookup'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useAddressLookup() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lookupResult = ref<LookupResponse | null>(null)

  async function lookup(address: string) {
    loading.value = true
    error.value = null
    lookupResult.value = null
    try {
      const response = await fetch(
        `${API_BASE}/lookup?address=${encodeURIComponent(address)}`,
      )
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Address not found. Please check and try again.')
        }
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      lookupResult.value = await response.json()
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  function reset() {
    lookupResult.value = null
    error.value = null
  }

  return { loading, error, lookupResult, lookup, reset }
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/lookup.ts frontend/src/composables/useAddressLookup.ts
git commit -m "feat: add useAddressLookup composable and lookup types"
```

---

## Task 6: Frontend — Address Input Component

**Files:**
- Create: `frontend/src/components/AddressLookup.vue`
- Modify: `frontend/src/components/BuildingForm.vue` (integrate address bar)

**Step 1: Create AddressLookup component**

Create `frontend/src/components/AddressLookup.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { PTextInput, PButton } from '@partnerdevops/partner-components'

defineProps<{
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  lookup: [address: string]
}>()

const address = ref('')

function onLookup() {
  if (address.value.trim()) {
    emit('lookup', address.value.trim())
  }
}
</script>

<template>
  <div class="address-lookup">
    <div class="address-lookup__header">
      <p class="address-lookup__label">Building Address</p>
      <p class="address-lookup__desc">Enter an address to auto-populate building details</p>
    </div>
    <form class="address-lookup__form" @submit.prevent="onLookup">
      <div class="address-lookup__input-wrap">
        <PTextInput
          v-model="address"
          placeholder="e.g. 210 N Wells St, Chicago, IL 60606"
          size="medium"
          :disabled="loading"
        />
      </div>
      <PButton
        type="submit"
        variant="secondary"
        size="medium"
        :disabled="loading || !address.trim()"
      >
        {{ loading ? 'Looking up...' : 'Look Up' }}
      </PButton>
    </form>
    <p v-if="error" class="address-lookup__error">{{ error }}</p>
  </div>
</template>

<style scoped>
.address-lookup {
  background-color: var(--app-surface-raised);
  border: 1px solid #e2e6ea;
  border-radius: 6px;
  padding: 1.5rem 2rem;
  margin-bottom: 1.5rem;
}

.address-lookup__header {
  margin-bottom: 1rem;
}

.address-lookup__label {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--app-header-bg);
  margin: 0;
}

.address-lookup__desc {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  color: #6b7a8a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0.25rem 0 0;
}

.address-lookup__form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
}

.address-lookup__input-wrap {
  flex: 1;
}

.address-lookup__error {
  color: var(--partner-error-main, #dc2626);
  font-size: 0.8125rem;
  margin: 0.5rem 0 0;
}
</style>
```

**Step 2: Integrate into BuildingForm.vue**

Modify `frontend/src/components/BuildingForm.vue`:

Add imports at top of `<script setup>`:
```typescript
import { watch } from 'vue'
import AddressLookup from './AddressLookup.vue'
import { useAddressLookup } from '../composables/useAddressLookup'
import type { FieldResult } from '../types/lookup'
```

Add lookup state:
```typescript
const { loading: lookupLoading, error: lookupError, lookupResult, lookup } = useAddressLookup()

// Track which fields were auto-filled and their source
const fieldSources = ref<Record<string, FieldResult>>({})

function onAddressLookup(address: string) {
  lookup(address)
}

// When lookup completes, populate form fields
watch(lookupResult, (result) => {
  if (!result) return

  const fields = result.building_fields
  fieldSources.value = {}

  // Zipcode
  if (result.zipcode) {
    form.zipcode = result.zipcode
  }

  // Direct field mapping
  const fieldMap: Record<string, keyof typeof form> = {
    building_type: 'building_type',
    sqft: 'sqft',
    num_stories: 'num_stories',
    year_built: 'year_built',
    heating_fuel: 'heating_fuel',
    dhw_fuel: 'dhw_fuel',
    hvac_system_type: 'hvac_system_type',
  }

  for (const [lookupKey, formKey] of Object.entries(fieldMap)) {
    const field = fields[lookupKey]
    if (field?.value != null) {
      ;(form as any)[formKey] = field.value
      fieldSources.value[lookupKey] = field
    }
  }

  // Advanced fields
  const advancedMap: Record<string, string> = {
    wall_construction: 'wall_construction',
    window_type: 'window_type',
    window_to_wall_ratio: 'window_to_wall_ratio',
    lighting_type: 'lighting_type',
  }

  for (const [lookupKey, advKey] of Object.entries(advancedMap)) {
    const field = fields[lookupKey]
    if (field?.value != null) {
      advancedFields.value[advKey as keyof typeof advancedFields.value] = field.value as any
      fieldSources.value[lookupKey] = field
    }
  }
})
```

In the template, add the AddressLookup component before the form sections:

```html
<!-- Address Lookup -->
<AddressLookup
  :loading="lookupLoading"
  :error="lookupError"
  @lookup="onAddressLookup"
/>
```

Add source badges next to auto-filled fields. For each field that can be auto-filled, add a small badge:

```html
<span v-if="fieldSources['building_type']" class="field-badge" :class="'field-badge--' + fieldSources['building_type'].source">
  {{ fieldSources['building_type'].source === 'osm' ? 'public records' : 'estimated' }}
</span>
```

Add badge styles:
```css
.field-badge {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 0.125rem 0.375rem;
  border-radius: 2px;
  margin-left: 0.5rem;
  vertical-align: middle;
}

.field-badge--osm {
  background-color: #dbeafe;
  color: #1e40af;
}

.field-badge--computed {
  background-color: #e0e7ff;
  color: #3730a3;
}

.field-badge--imputed {
  background-color: #fef3c7;
  color: #92400e;
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/AddressLookup.vue frontend/src/components/BuildingForm.vue
git commit -m "feat: add address lookup UI with auto-populate and source badges"
```

---

## Task 7: Frontend — MapLibre 2.5D Building Viewer

**Files:**
- Create: `frontend/src/components/BuildingMapViewer.vue`
- Modify: `frontend/src/components/BuildingForm.vue` (add map viewer)
- Modify: `frontend/package.json` (add maplibre-gl)

**Step 1: Install MapLibre GL JS**

Run: `cd frontend && npm install maplibre-gl`

**Step 2: Create the map viewer component**

Create `frontend/src/components/BuildingMapViewer.vue`:

```vue
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const props = defineProps<{
  lat: number
  lon: number
  targetPolygon: number[][] | null
  nearbyBuildings: Array<{ polygon: number[][]; levels: number | null }>
  numStories: number
}>()

const mapContainer = ref<HTMLDivElement>()
let map: maplibregl.Map | null = null

const FLOOR_HEIGHT_M = 3.4

function initMap() {
  if (!mapContainer.value) return

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '&copy; OpenStreetMap contributors',
        },
      },
      layers: [
        {
          id: 'osm-tiles',
          type: 'raster',
          source: 'osm',
          minzoom: 0,
          maxzoom: 19,
        },
      ],
    },
    center: [props.lon, props.lat],
    zoom: 17,
    pitch: 45,
    bearing: -17,
  })

  map.addControl(new maplibregl.NavigationControl())

  map.on('load', () => {
    addBuildingLayers()
  })
}

function addBuildingLayers() {
  if (!map) return

  // Nearby buildings (flat, muted)
  if (props.nearbyBuildings.length > 0) {
    const nearbyFeatures = props.nearbyBuildings.map((b, i) => ({
      type: 'Feature' as const,
      properties: {
        height: (b.levels || 1) * FLOOR_HEIGHT_M,
      },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [b.polygon.map(([lat, lon]) => [lon, lat])],
      },
    }))

    map.addSource('nearby-buildings', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: nearbyFeatures },
    })

    map.addLayer({
      id: 'nearby-buildings-3d',
      type: 'fill-extrusion',
      source: 'nearby-buildings',
      paint: {
        'fill-extrusion-color': '#c4cdd5',
        'fill-extrusion-height': ['get', 'height'],
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.5,
      },
    })
  }

  // Target building (extruded, highlighted)
  if (props.targetPolygon) {
    const targetHeight = props.numStories * FLOOR_HEIGHT_M

    map.addSource('target-building', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: { height: targetHeight },
        geometry: {
          type: 'Polygon',
          coordinates: [props.targetPolygon.map(([lat, lon]) => [lon, lat])],
        },
      },
    })

    map.addLayer({
      id: 'target-building-3d',
      type: 'fill-extrusion',
      source: 'target-building',
      paint: {
        'fill-extrusion-color': '#3b82f6',
        'fill-extrusion-height': targetHeight,
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.8,
      },
    })

    // Outline for clarity
    map.addLayer({
      id: 'target-building-outline',
      type: 'line',
      source: 'target-building',
      paint: {
        'line-color': '#1e40af',
        'line-width': 2,
      },
    })
  }
}

onMounted(() => {
  initMap()
})

onUnmounted(() => {
  map?.remove()
})

// Re-render when data changes
watch(() => [props.targetPolygon, props.nearbyBuildings], () => {
  if (map?.loaded()) {
    // Remove old layers/sources and re-add
    for (const id of ['target-building-outline', 'target-building-3d', 'nearby-buildings-3d']) {
      if (map.getLayer(id)) map.removeLayer(id)
    }
    for (const id of ['target-building', 'nearby-buildings']) {
      if (map.getSource(id)) map.removeSource(id)
    }
    addBuildingLayers()

    // Fly to new location
    map.flyTo({ center: [props.lon, props.lat], zoom: 17, pitch: 45 })
  }
})
</script>

<template>
  <div class="map-viewer">
    <div ref="mapContainer" class="map-viewer__map" />
  </div>
</template>

<style scoped>
.map-viewer {
  border: 1px solid #e2e6ea;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.map-viewer__map {
  width: 100%;
  height: 400px;
}
</style>
```

**Step 3: Add map viewer to BuildingForm.vue**

Import and add between AddressLookup and the form fields:

```typescript
import BuildingMapViewer from './BuildingMapViewer.vue'
```

In template, after AddressLookup:
```html
<!-- Map Viewer (shown after successful lookup) -->
<BuildingMapViewer
  v-if="lookupResult?.target_building_polygon"
  :lat="lookupResult.lat"
  :lon="lookupResult.lon"
  :target-polygon="lookupResult.target_building_polygon"
  :nearby-buildings="lookupResult.nearby_buildings"
  :num-stories="lookupResult.building_fields.num_stories?.value ?? 1"
/>
```

**Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

**Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/BuildingMapViewer.vue frontend/src/components/BuildingForm.vue
git commit -m "feat: add MapLibre 2.5D building viewer with nearby context"
```

---

## Task 8: Integration Testing & Polish

**Files:**
- Modify: `backend/tests/test_api_integration.py` (add full integration test)
- Run full test suites

**Step 1: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: All tests PASS (69 existing + new tests)

**Step 2: Run frontend type check and build**

Run: `cd frontend && npm run build`
Expected: No errors

**Step 3: Manual smoke test**

Run both servers:
```bash
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

Test the lookup endpoint directly:
```bash
curl "http://localhost:8000/lookup?address=210+N+Wells+St,+Chicago,+IL+60606"
```

Expected: JSON response with building_fields, polygon data, nearby_buildings.

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: add integration tests for address lookup pipeline"
```

---

## Dependency Summary

### Backend (add to requirements.txt)
- `geopy>=2.4` — Nominatim geocoding
- `shapely>=2.0` — polygon geometry
- `pyproj>=3.6` — UTM coordinate projection
- `requests>=2.31` — Overpass API calls

### Frontend (npm install)
- `maplibre-gl` — map rendering and 3D extrusion

### New Files Created
```
backend/
  app/
    services/address_lookup.py          # Geocoding + Overpass + building matching
    inference/imputation_trainer.py     # Offline model training script
    inference/imputation_service.py     # Runtime imputation predictions
    schemas/lookup_response.py          # Pydantic response model
  tests/
    test_address_lookup.py              # Address lookup unit tests
    test_imputation.py                  # Imputation trainer tests
    test_imputation_service.py          # Runtime imputation tests
frontend/
  src/
    types/lookup.ts                     # TypeScript interfaces
    composables/useAddressLookup.ts     # API composable
    components/AddressLookup.vue        # Address input bar
    components/BuildingMapViewer.vue    # MapLibre 2.5D viewer
```

### Files Modified
```
backend/
  requirements.txt                      # New dependencies
  app/main.py                           # Load imputation service at startup
  app/api/routes.py                     # Add GET /lookup endpoint
frontend/
  package.json                          # Add maplibre-gl
  src/components/BuildingForm.vue       # Integrate address bar + map + badges
```
