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
        mock_location.raw = {"address": {"postcode": "60606"}}
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        result = geocode_address("210 N Wells St, Chicago, IL 60606")
        assert result["lat"] == pytest.approx(41.886)
        assert result["lon"] == pytest.approx(-87.634)
        assert "60606" in result["address"]
        assert result["zipcode"] == "60606"

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
        mock_location.raw = {"address": {"postcode": "60606"}}
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
        assert result is not None


# --- Area computation tests ---

class TestComputeSqft:
    def test_computes_sqft_from_polygon(self):
        poly = Polygon([
            (-87.6340, 41.8860), (-87.6336, 41.8860),
            (-87.6336, 41.8863), (-87.6340, 41.8863),
            (-87.6340, 41.8860),
        ])
        sqft = compute_sqft_from_polygon(poly, num_stories=1)
        assert 5000 < sqft < 20000

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
        mock_location = MagicMock()
        mock_location.latitude = 41.886
        mock_location.longitude = -87.634
        mock_location.address = "210 N Wells St, The Loop, Chicago, Cook County, IL, 60606, USA"
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

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
