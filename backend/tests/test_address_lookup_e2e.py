"""
End-to-end tests for the address lookup pipeline using LIVE external APIs.

These tests hit real Nominatim and Overpass API servers — no mocks.
They verify the full geocoding -> footprint fetch -> parse -> match -> extract pipeline.

Run with:
    cd backend && pytest tests/test_address_lookup_e2e.py -v --run-e2e

Skipped by default in normal test runs (needs --run-e2e flag).

NOTE: Uses session-scoped fixtures to cache API responses. Only makes
~3 total external API call sets to respect rate limits.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

from app.services.address_lookup import lookup_address
from app.services.cost_calculator import CostCalculatorService


# Mark all tests in this module as e2e (requires network)
pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Session-scoped fixtures — cache full lookup results
# Only 2 real API call chains for the entire test session
# ---------------------------------------------------------------------------


def _lookup_with_retry(address: str, retries: int = 3, delay: float = 3.0):
    """Call lookup_address with retries and delays for rate-limited APIs."""
    for attempt in range(retries):
        if attempt > 0:
            time.sleep(delay * attempt)  # Increasing backoff
        result = lookup_address(address)
        if result is not None:
            return result
    return None


@pytest.fixture(scope="session")
def esb_result():
    """Full lookup for Empire State Building — cached for entire session."""
    time.sleep(5)  # Initial delay to avoid rate limits from previous runs
    return _lookup_with_retry(
        "Empire State Building, New York, NY",
        retries=4,
        delay=5.0,
    )


@pytest.fixture(scope="session")
def whitehouse_result():
    """Full lookup for White House — cached for entire session."""
    time.sleep(3)
    return _lookup_with_retry(
        "1600 Pennsylvania Avenue NW, Washington, DC 20500"
    )


# ---------------------------------------------------------------------------
# Full pipeline tests — Empire State Building
# ---------------------------------------------------------------------------


class TestLookupESB:
    """End-to-end tests using the Empire State Building as a known landmark."""

    def test_lookup_returns_result(self, esb_result):
        assert esb_result is not None, (
            "lookup_address returned None — Nominatim/Overpass may be rate-limiting"
        )

    def test_geocoded_coordinates(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        assert esb_result["lat"] == pytest.approx(40.748, abs=0.01)
        assert esb_result["lon"] == pytest.approx(-73.986, abs=0.01)

    def test_address_string_populated(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        assert esb_result["address"] is not None
        assert len(esb_result["address"]) > 0

    def test_zipcode_extracted(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        assert esb_result["zipcode"] is not None
        assert len(esb_result["zipcode"]) == 5

    def test_building_polygon_returned(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        poly = esb_result["target_building_polygon"]
        assert poly is not None, "No building polygon found for ESB"
        assert len(poly) >= 4, "Polygon should have at least 4 coordinate pairs"

    def test_polygon_coords_in_nyc(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        poly = esb_result["target_building_polygon"]
        if poly is None:
            pytest.skip("No polygon returned")
        for coord in poly:
            assert len(coord) == 2
            lat, lon = coord
            assert 40.0 < lat < 41.0, f"Latitude {lat} out of NYC range"
            assert -74.5 < lon < -73.0, f"Longitude {lon} out of NYC range"

    def test_nearby_buildings_found(self, esb_result):
        """Manhattan is dense — should find neighboring buildings."""
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        nearby = esb_result["nearby_buildings"]
        assert len(nearby) > 0, "Expected nearby buildings in Manhattan"
        for nb in nearby:
            assert "polygon" in nb
            assert "levels" in nb
            assert len(nb["polygon"]) >= 4

    def test_all_building_fields_present(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        expected_fields = [
            "num_stories", "building_type", "sqft",
            "year_built", "heating_fuel", "dhw_fuel", "hvac_system_type",
            "wall_construction", "window_type", "window_to_wall_ratio",
            "lighting_type",
        ]
        for field in expected_fields:
            assert field in esb_result["building_fields"], f"Missing field: {field}"
            entry = esb_result["building_fields"][field]
            assert "value" in entry, f"Field {field} missing 'value' key"
            assert "source" in entry, f"Field {field} missing 'source' key"
            assert "confidence" in entry, f"Field {field} missing 'confidence' key"

    def test_stories_from_osm(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        stories = esb_result["building_fields"]["num_stories"]
        if stories["value"] is not None:
            assert stories["value"] > 10, f"ESB should have many stories, got {stories['value']}"
            assert stories["source"] in ("osm", "computed")
            assert stories["confidence"] is not None

    def test_sqft_computed_from_polygon(self, esb_result):
        if esb_result is None:
            pytest.skip("ESB lookup failed")
        sqft = esb_result["building_fields"]["sqft"]
        if sqft["value"] is not None:
            assert sqft["value"] > 100_000, f"ESB sqft {sqft['value']} seems too small"
            assert sqft["source"] == "computed"
            assert sqft["confidence"] is not None


# ---------------------------------------------------------------------------
# Full pipeline tests — White House (different building type / location)
# ---------------------------------------------------------------------------


class TestLookupWhiteHouse:
    """End-to-end tests using the White House as a second reference point."""

    def test_lookup_returns_result(self, whitehouse_result):
        assert whitehouse_result is not None, (
            "lookup_address returned None — Nominatim/Overpass may be rate-limiting"
        )

    def test_geocoded_coordinates(self, whitehouse_result):
        if whitehouse_result is None:
            pytest.skip("White House lookup failed")
        assert whitehouse_result["lat"] == pytest.approx(38.898, abs=0.01)
        assert whitehouse_result["lon"] == pytest.approx(-77.036, abs=0.01)

    def test_zipcode_extracted(self, whitehouse_result):
        if whitehouse_result is None:
            pytest.skip("White House lookup failed")
        assert whitehouse_result["zipcode"] is not None

    def test_building_polygon_returned(self, whitehouse_result):
        if whitehouse_result is None:
            pytest.skip("White House lookup failed")
        assert whitehouse_result["target_building_polygon"] is not None

    def test_different_location_from_esb(self, esb_result, whitehouse_result):
        """Verify two different addresses produce different results."""
        if esb_result is None or whitehouse_result is None:
            pytest.skip("One or both lookups failed")
        assert abs(esb_result["lat"] - whitehouse_result["lat"]) > 1.0


# ---------------------------------------------------------------------------
# Negative test
# ---------------------------------------------------------------------------


class TestLookupBadAddress:
    def test_bad_address_returns_none(self):
        result = lookup_address("zzznotarealplace99999xyz")
        assert result is None


# ---------------------------------------------------------------------------
# API endpoint e2e test
# ---------------------------------------------------------------------------


class MockModelManager:
    """Minimal mock for assessment models — not needed for /lookup endpoint."""

    def load_all(self):
        return 0

    def predict_baseline(self, features_dict, dataset):
        return {"electricity": 0, "natural_gas": 0, "fuel_oil": 0, "propane": 0, "district_heating": 0}

    def predict_sizing(self, features_dict, dataset):
        return {}

    def predict_rates(self, features_dict, dataset):
        return {}

    def get_available_upgrades(self, dataset):
        return []

    def predict_delta(self, features_dict, upgrade_id, dataset):
        return {}


@pytest.fixture(scope="module")
def live_client():
    """TestClient that does NOT mock address lookup — uses real APIs."""
    from app.main import app

    @asynccontextmanager
    async def mock_lifespan(app_instance):
        app_instance.state.model_manager = MockModelManager()
        app_instance.state.cost_calculator = CostCalculatorService()
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.router.lifespan_context = original_lifespan


class TestLookupEndpointLive:
    """Test the /lookup API endpoint against live Nominatim and Overpass."""

    def test_endpoint_returns_200_with_valid_structure(self, live_client):
        time.sleep(3)
        resp = live_client.get(
            "/lookup",
            params={"address": "1600 Pennsylvania Avenue NW, Washington, DC 20500"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Response structure
        assert "address" in data
        assert "lat" in data
        assert "lon" in data
        assert "zipcode" in data
        assert "building_fields" in data
        assert "target_building_polygon" in data
        assert "nearby_buildings" in data

        # All field results have proper structure
        for field_name, field_data in data["building_fields"].items():
            assert "value" in field_data, f"{field_name} missing 'value'"
            assert "source" in field_data, f"{field_name} missing 'source'"
            assert "confidence" in field_data, f"{field_name} missing 'confidence'"

    def test_endpoint_404_for_bad_address(self, live_client):
        resp = live_client.get(
            "/lookup",
            params={"address": "zzznotarealplace99999xyz"},
        )
        assert resp.status_code == 404
