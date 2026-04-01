"""
Integration tests for the FastAPI API endpoints using TestClient with a
mocked ModelManager so no real .pkl model files are required.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.services.cost_calculator import CostCalculatorService


# ---------------------------------------------------------------------------
# Mock ModelManager — returns fixed, deterministic predictions
# ---------------------------------------------------------------------------


class MockModelManager:
    """Mock model manager that returns fixed predictions without real XGB models."""

    def load_all(self):
        return 10

    def predict_baseline(self, features_dict, dataset, _enc_cache=None):
        if dataset == "comstock":
            return {
                "electricity": 12.5,
                "natural_gas": 8.3,
                "fuel_oil": 0.5,
                "propane": 0.2,
                "district_heating": 0.0,
            }
        else:  # resstock
            return {
                "electricity": 6.0,
                "natural_gas": 10.0,
                "fuel_oil": 0.0,
                "propane": 0.0,
            }

    def predict_sizing(self, features_dict, dataset, _enc_cache=None):
        return {
            "heating_capacity": 500.0,
            "cooling_capacity": 100.0,
            "wall_area": 1000.0,
            "roof_area": 800.0,
            "window_area": 200.0,
        }

    def predict_rates(self, features_dict, dataset, _enc_cache=None):
        return {
            "electricity": 0.12,
            "natural_gas": 0.04,
            "fuel_oil": 0.08,
            "propane": 0.10,
        }

    def get_available_upgrades(self, dataset):
        return [1, 2, 43]

    def warm_upgrades(self, dataset, upgrade_ids):
        pass

    def predict_delta(self, features_dict, upgrade_id, dataset, baseline_eui=None, _enc_cache=None):
        baseline = self.predict_baseline(features_dict, dataset)
        return {fuel: eui * 0.1 for fuel, eui in baseline.items()}

    def predict_enduse(self, features_dict, dataset, _enc_cache=None):
        return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a TestClient with the mocked ModelManager injected."""
    from app.main import app

    mock_mm = MockModelManager()

    # Patch the lifespan so it doesn't try to load real models
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_lifespan(app_instance):
        app_instance.state.model_manager = mock_mm
        app_instance.state.cost_calculator = CostCalculatorService()
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.router.lifespan_context = original_lifespan


def _office_payload(**overrides):
    """Build a valid office assessment request payload."""
    building = {
        "building_type": "Office",
        "sqft": 50000,
        "num_stories": 3,
        "zipcode": "20001",
        "year_built": 1985,
        "heating_fuel": "NaturalGas",
        "lighting_type": "T8",
    }
    building.update(overrides)
    return {"buildings": [building]}


def _multifamily_payload(**overrides):
    """Build a valid Multi-Family assessment request payload."""
    building = {
        "building_type": "Multi-Family",
        "sqft": 25000,
        "num_stories": 5,
        "zipcode": "10001",
        "year_built": 1985,
    }
    building.update(overrides)
    return {"buildings": [building]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok"}


class TestMetadataEndpoint:
    def test_metadata_endpoint(self, client):
        resp = client.get("/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert "building_types" in data
        assert len(data["building_types"]) == 14


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


class TestAssessEndpoint:
    def test_assess_office(self, client):
        resp = client.post("/assess", json=_office_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["baseline"]["total_eui_kbtu_sf"] > 0

    def test_assess_multifamily(self, client):
        resp = client.post("/assess", json=_multifamily_payload())
        assert resp.status_code == 200
        data = resp.json()
        result = data["results"][0]
        # Multi-Family routes to resstock
        assert result["baseline"]["total_eui_kbtu_sf"] > 0

    def test_assess_minimal_input(self, client):
        """Only required fields provided — imputation should fill the rest."""
        payload = {
            "buildings": [
                {
                    "building_type": "Office",
                    "sqft": 10000,
                    "num_stories": 2,
                    "zipcode": "90210",
                    "year_built": 1990,
                }
            ]
        }
        resp = client.post("/assess", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        result = data["results"][0]
        imputed = result["input_summary"]["imputed_fields"]
        assert len(imputed) > 0, "Expected at least one field to be imputed"

    def test_assess_invalid_building_type(self, client):
        payload = {
            "buildings": [
                {
                    "building_type": "SpaceStation",
                    "sqft": 10000,
                    "num_stories": 1,
                    "zipcode": "20001",
                    "year_built": 1990,
                }
            ]
        }
        resp = client.post("/assess", json=payload)
        assert resp.status_code == 422

    def test_assess_response_structure(self, client):
        """Verify all expected top-level fields are present in the response."""
        resp = client.post("/assess", json=_office_payload())
        assert resp.status_code == 200
        result = resp.json()["results"][0]

        # Top-level keys
        assert "building_index" in result
        assert "baseline" in result
        assert "measures" in result
        assert "input_summary" in result

        # Baseline keys
        baseline = result["baseline"]
        assert "total_eui_kbtu_sf" in baseline
        assert "eui_by_fuel" in baseline

        # Fuel breakdown keys
        fuel = baseline["eui_by_fuel"]
        for key in ("electricity", "natural_gas", "fuel_oil", "propane", "district_heating"):
            assert key in fuel

        # Input summary keys
        summary = result["input_summary"]
        assert "climate_zone" in summary
        assert "state" in summary
        assert "imputed_fields" in summary
        assert "cluster_name" in summary

    def test_assess_measures_sorted(self, client):
        """Applicable measures should be sorted by savings_pct descending."""
        resp = client.post("/assess", json=_office_payload())
        data = resp.json()
        measures = data["results"][0]["measures"]

        applicable = [m for m in measures if m["applicable"]]
        if len(applicable) > 1:
            savings = [m["savings_pct"] for m in applicable]
            assert savings == sorted(savings, reverse=True), (
                "Applicable measures should be sorted by savings_pct descending"
            )

    def test_assess_measures_have_cost(self, client):
        """Applicable measures with entries in the cost lookup should have cost estimates."""
        resp = client.post("/assess", json=_office_payload())
        data = resp.json()
        measures = data["results"][0]["measures"]

        applicable_with_cost = [
            m for m in measures if m["applicable"] and m["cost"] is not None
        ]
        # At least upgrade 43 (LED) has a simple $/ft^2 floor basis and should produce a cost
        assert len(applicable_with_cost) > 0, (
            "Expected at least one applicable measure to have a cost estimate"
        )

    def test_assess_baseline_fuel_breakdown(self, client):
        """Sum of fuel breakdowns should approximately equal total_eui."""
        resp = client.post("/assess", json=_office_payload())
        data = resp.json()
        baseline = data["results"][0]["baseline"]
        fuel = baseline["eui_by_fuel"]
        fuel_sum = (
            fuel["electricity"]
            + fuel["natural_gas"]
            + fuel["fuel_oil"]
            + fuel["propane"]
            + fuel["district_heating"]
        )
        assert abs(fuel_sum - baseline["total_eui_kbtu_sf"]) < 0.1, (
            f"Fuel sum {fuel_sum} != total {baseline['total_eui_kbtu_sf']}"
        )

    def test_assess_returns_imputed_details(self, client):
        """POST /assess with missing optional fields returns imputed_details."""
        payload = {
            "buildings": [{
                "building_type": "Office",
                "sqft": 50000,
                "num_stories": 3,
                "zipcode": "60610",
                "year_built": 2014,
                "heating_fuel": "NaturalGas",
            }]
        }
        resp = client.post("/assess", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        summary = data["results"][0]["input_summary"]

        # Should have imputed_details dict
        assert "imputed_details" in summary
        assert isinstance(summary["imputed_details"], dict)

        # lighting_type was not provided, should be imputed
        assert "lighting_type" in summary["imputed_details"]
        detail = summary["imputed_details"]["lighting_type"]
        assert "value" in detail
        assert "label" in detail
        assert detail["label"] == "Lighting Type"
        assert detail["source"] in ("model", "default")

        # vintage_bucket should be present
        assert "vintage_bucket" in summary

        # heating_fuel was provided, should NOT be imputed
        assert "heating_fuel" not in summary["imputed_details"]
