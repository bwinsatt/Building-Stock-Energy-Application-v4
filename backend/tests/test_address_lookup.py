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
    _fetch_nyc_building_data,
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


# --- NYC Open Data fallback tests ---

class TestNycOpenDataFallback:
    """Tests for the NYC Open Data BIN→BBL→PLUTO fallback lookup."""

    @patch("app.services.address_lookup.requests.get")
    def test_successful_two_step_lookup(self, mock_get):
        """BIN → Footprints API → PLUTO API returns combined data."""
        footprint_resp = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "base_bbl": "1012345678",
                "heightroof": "500",
                "cnstrct_yr": "1970",
            }]),
        )
        pluto_resp = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "numfloors": "40",
                "yearbuilt": "1970",
                "bldgarea": "800000",
                "bldgclass": "O4",
            }]),
        )
        mock_get.side_effect = [footprint_resp, pluto_resp]

        result = _fetch_nyc_building_data("1234567")
        assert result is not None
        assert result["numfloors"] == "40"
        assert result["yearbuilt"] == "1970"
        assert result["bldgarea"] == "800000"
        assert result["height_roof"] == "500"

    @patch("app.services.address_lookup.requests.get")
    def test_returns_none_when_api_unavailable(self, mock_get):
        """Gracefully returns None when NYC API fails."""
        import requests as req
        mock_get.side_effect = req.ConnectionError("Connection refused")
        result = _fetch_nyc_building_data("1234567")
        assert result is None

    @patch("app.services.address_lookup.requests.get")
    def test_returns_none_for_empty_response(self, mock_get):
        """Returns None when BIN not found in footprints API."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[]),
        )
        result = _fetch_nyc_building_data("0000000")
        assert result is None

    @patch("app.services.address_lookup.requests.get")
    def test_returns_partial_data_without_bbl(self, mock_get):
        """Returns footprint data even when BBL is missing (no PLUTO call)."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "heightroof": "500",
                "cnstrct_yr": "1970",
            }]),
        )
        result = _fetch_nyc_building_data("1234567")
        assert result is not None
        assert result["height_roof"] == "500"
        assert "numfloors" not in result
        mock_get.assert_called_once()  # Only one call — no PLUTO lookup

    @patch("app.services.address_lookup.requests.post")
    @patch("app.services.address_lookup.requests.get")
    @patch("app.services.address_lookup.Nominatim")
    def test_nyc_data_preferred_over_osm_levels(
        self, mock_nominatim_cls, mock_get, mock_post
    ):
        """NYC data is used even when building:levels exists in OSM."""
        mock_location = MagicMock()
        mock_location.latitude = 40.762
        mock_location.longitude = -73.979
        mock_location.address = "1155 6th Ave, New York, NY 10036, USA"
        mock_location.raw = {"address": {"postcode": "10036"}}
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "elements": [
                    {"type": "node", "id": 1, "lon": -73.980, "lat": 40.761},
                    {"type": "node", "id": 2, "lon": -73.978, "lat": 40.761},
                    {"type": "node", "id": 3, "lon": -73.978, "lat": 40.763},
                    {"type": "node", "id": 4, "lon": -73.980, "lat": 40.763},
                    {
                        "type": "way", "id": 100,
                        "nodes": [1, 2, 3, 4, 1],
                        "tags": {
                            "building": "office",
                            "building:levels": "38",
                            "nycdoitt:bin": "1234567",
                        },
                    },
                ]
            }),
        )

        footprint_resp = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "base_bbl": "1012345678",
                "heightroof": "500",
                "cnstrct_yr": "1970",
            }]),
        )
        pluto_resp = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "numfloors": "40",
                "yearbuilt": "1970",
                "bldgarea": "800000",
                "bldgclass": "O4",
            }]),
        )
        mock_get.side_effect = [footprint_resp, pluto_resp]

        result = lookup_address("1155 6th Ave, New York, NY 10036")
        # NYC data (40 floors) should win over OSM levels (38)
        assert result["building_fields"]["num_stories"]["value"] == 40
        assert result["building_fields"]["num_stories"]["source"] == "nyc_opendata"
        mock_get.assert_called()  # NYC API was called despite OSM levels existing

    @patch("app.services.address_lookup.requests.post")
    @patch("app.services.address_lookup.requests.get")
    @patch("app.services.address_lookup.Nominatim")
    def test_falls_back_to_osm_when_nyc_api_fails(
        self, mock_nominatim_cls, mock_get, mock_post
    ):
        """Falls back to OSM building:levels when NYC API is unavailable."""
        mock_location = MagicMock()
        mock_location.latitude = 40.762
        mock_location.longitude = -73.979
        mock_location.address = "1155 6th Ave, New York, NY 10036, USA"
        mock_location.raw = {"address": {"postcode": "10036"}}
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "elements": [
                    {"type": "node", "id": 1, "lon": -73.980, "lat": 40.761},
                    {"type": "node", "id": 2, "lon": -73.978, "lat": 40.761},
                    {"type": "node", "id": 3, "lon": -73.978, "lat": 40.763},
                    {"type": "node", "id": 4, "lon": -73.980, "lat": 40.763},
                    {
                        "type": "way", "id": 100,
                        "nodes": [1, 2, 3, 4, 1],
                        "tags": {
                            "building": "office",
                            "building:levels": "38",
                            "nycdoitt:bin": "1234567",
                        },
                    },
                ]
            }),
        )

        import requests as req
        mock_get.side_effect = req.ConnectionError("Connection refused")

        result = lookup_address("1155 6th Ave, New York, NY 10036")
        # Should fall back to OSM levels
        assert result["building_fields"]["num_stories"]["value"] == 38
        assert result["building_fields"]["num_stories"]["source"] == "osm"

    @patch("app.services.address_lookup.requests.post")
    @patch("app.services.address_lookup.requests.get")
    @patch("app.services.address_lookup.Nominatim")
    def test_nyc_fallback_populates_stories_and_sqft(
        self, mock_nominatim_cls, mock_get, mock_post
    ):
        """NYC fallback fills in stories, sqft, and year_built when OSM lacks levels."""
        mock_location = MagicMock()
        mock_location.latitude = 40.762
        mock_location.longitude = -73.979
        mock_location.address = "1155 6th Ave, New York, NY 10036, USA"
        mock_location.raw = {"address": {"postcode": "10036"}}
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = mock_location
        mock_nominatim_cls.return_value = mock_geocoder

        # OSM building has BIN but no levels or height
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "elements": [
                    {"type": "node", "id": 1, "lon": -73.980, "lat": 40.761},
                    {"type": "node", "id": 2, "lon": -73.978, "lat": 40.761},
                    {"type": "node", "id": 3, "lon": -73.978, "lat": 40.763},
                    {"type": "node", "id": 4, "lon": -73.980, "lat": 40.763},
                    {
                        "type": "way", "id": 100,
                        "nodes": [1, 2, 3, 4, 1],
                        "tags": {
                            "building": "office",
                            "nycdoitt:bin": "1086382",
                        },
                    },
                ]
            }),
        )

        # NYC API responses
        footprint_resp = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "base_bbl": "1012345678",
                "heightroof": "500",
                "cnstrct_yr": "1970",
            }]),
        )
        pluto_resp = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{
                "numfloors": "40",
                "yearbuilt": "1970",
                "bldgarea": "800000",
                "bldgclass": "O4",
            }]),
        )
        mock_get.side_effect = [footprint_resp, pluto_resp]

        result = lookup_address("1155 6th Ave, New York, NY 10036")
        bf = result["building_fields"]
        assert bf["num_stories"]["value"] == 40
        assert bf["num_stories"]["source"] == "nyc_opendata"
        assert bf["num_stories"]["confidence"] == 0.95
        assert bf["sqft"]["value"] == 800000
        assert bf["sqft"]["source"] == "nyc_opendata"
        assert bf["year_built"]["value"] == 1970
        assert bf["year_built"]["source"] == "nyc_opendata"
