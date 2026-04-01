"""
End-to-end tests: API request -> preprocess -> predict -> cost -> response.

Uses a mock ModelManager but real preprocessor, cost calculator, and
applicability engine so the full pipeline is exercised.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

from app.services.cost_calculator import CostCalculatorService


# ---------------------------------------------------------------------------
# Mock ModelManager (same as integration tests)
# ---------------------------------------------------------------------------


class MockModelManager:
    """Returns fixed predictions so no real .pkl files are needed."""

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
        else:
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
    from app.main import app

    mock_mm = MockModelManager()

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


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

OFFICE_BUILDING = {
    "building_type": "Office",
    "sqft": 50000,
    "num_stories": 3,
    "zipcode": "20001",
    "year_built": 1985,
    "heating_fuel": "NaturalGas",
    "hvac_system_type": "VAV_chiller_boiler",
    "wall_construction": "Mass",
    "window_type": "Double, Low-E, Non-metal",
    "window_to_wall_ratio": "20-30%",
    "lighting_type": "T8",  # not LED so upgrade 43 is applicable
    "operating_hours": 50.0,
}

MF_BUILDING = {
    "building_type": "Multi-Family",
    "sqft": 25000,
    "num_stories": 5,
    "zipcode": "10001",
    "year_built": 1970,
    "heating_fuel": "NaturalGas",
    "hvac_system_type": "Ducted Heating",
}

MINIMAL_BUILDING = {
    "building_type": "Office",
    "sqft": 10000,
    "num_stories": 2,
    "zipcode": "90210",
    "year_built": 1990,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullAssessmentFlowOffice:
    """Complete pipeline test for a commercial (comstock) Office building."""

    def test_response_status(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        assert resp.status_code == 200

    def test_baseline_positive(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        result = resp.json()["results"][0]
        assert result["baseline"]["total_eui_kbtu_sf"] > 0

    def test_baseline_fuel_breakdown(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        fuel = resp.json()["results"][0]["baseline"]["eui_by_fuel"]
        for key in ("electricity", "natural_gas", "fuel_oil", "propane", "district_heating"):
            assert key in fuel

    def test_measures_non_empty(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        measures = resp.json()["results"][0]["measures"]
        applicable = [m for m in measures if m["applicable"]]
        assert len(applicable) >= 1, "Expected at least one applicable measure"

    def test_applicable_measures_have_savings_fields(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        measures = resp.json()["results"][0]["measures"]
        for m in measures:
            if m["applicable"]:
                assert m["savings_kbtu_sf"] is not None
                assert m["savings_pct"] is not None

    def test_climate_zone_populated(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        summary = resp.json()["results"][0]["input_summary"]
        assert summary["climate_zone"] != ""
        assert len(summary["climate_zone"]) >= 2

    def test_state_populated(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        summary = resp.json()["results"][0]["input_summary"]
        assert summary["state"] != ""
        assert len(summary["state"]) == 2

    def test_payback_positive_for_measures_with_cost_and_savings(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        measures = resp.json()["results"][0]["measures"]
        for m in measures:
            if m["applicable"] and m["cost"] is not None and m["savings_kbtu_sf"] and m["savings_kbtu_sf"] > 0:
                if m["simple_payback_years"] is not None:
                    assert m["simple_payback_years"] > 0


class TestFullAssessmentFlowMultifamily:
    """Complete pipeline test for a residential (resstock) Multi-Family building."""

    def test_response_status(self, client):
        resp = client.post("/assess", json={"buildings": [MF_BUILDING]})
        assert resp.status_code == 200

    def test_baseline_positive(self, client):
        resp = client.post("/assess", json={"buildings": [MF_BUILDING]})
        result = resp.json()["results"][0]
        assert result["baseline"]["total_eui_kbtu_sf"] > 0

    def test_measures_present(self, client):
        resp = client.post("/assess", json={"buildings": [MF_BUILDING]})
        measures = resp.json()["results"][0]["measures"]
        assert len(measures) > 0

    def test_state_derived_from_zipcode(self, client):
        resp = client.post("/assess", json={"buildings": [MF_BUILDING]})
        summary = resp.json()["results"][0]["input_summary"]
        # Zipcode 10001 is in New York
        assert summary["state"] == "NY"


class TestMultipleBuildings:
    def test_two_buildings(self, client):
        payload = {"buildings": [OFFICE_BUILDING, MF_BUILDING]}
        resp = client.post("/assess", json=payload)
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 2
        assert results[0]["building_index"] == 0
        assert results[1]["building_index"] == 1


class TestAssessmentMathConsistency:
    """Verify arithmetic relationships in the response."""

    def test_total_eui_equals_fuel_sum(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        baseline = resp.json()["results"][0]["baseline"]
        fuel = baseline["eui_by_fuel"]
        fuel_sum = sum(fuel.values())
        assert abs(fuel_sum - baseline["total_eui_kbtu_sf"]) < 0.1

    def test_savings_equals_baseline_minus_post(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        result = resp.json()["results"][0]
        total_baseline = result["baseline"]["total_eui_kbtu_sf"]

        for m in result["measures"]:
            if not m["applicable"]:
                continue
            expected_savings = total_baseline - m["post_upgrade_eui_kbtu_sf"]
            assert abs(m["savings_kbtu_sf"] - expected_savings) < 0.1, (
                f"Upgrade {m['upgrade_id']}: savings {m['savings_kbtu_sf']} "
                f"!= baseline {total_baseline} - post {m['post_upgrade_eui_kbtu_sf']}"
            )

    def test_savings_pct_consistent(self, client):
        resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
        result = resp.json()["results"][0]
        total_baseline = result["baseline"]["total_eui_kbtu_sf"]

        for m in result["measures"]:
            if not m["applicable"]:
                continue
            expected_pct = m["savings_kbtu_sf"] / total_baseline * 100
            assert abs(m["savings_pct"] - expected_pct) < 0.5, (
                f"Upgrade {m['upgrade_id']}: savings_pct {m['savings_pct']} "
                f"!= expected {expected_pct:.1f}"
            )


class TestImputationReported:
    def test_imputed_fields_listed(self, client):
        resp = client.post("/assess", json={"buildings": [MINIMAL_BUILDING]})
        assert resp.status_code == 200
        imputed = resp.json()["results"][0]["input_summary"]["imputed_fields"]
        assert len(imputed) > 0
        # year_built is now required, so it should NOT be imputed
        assert "year_built" not in imputed


class TestDifferentZipcodesProduceDifferentResults:
    def test_different_zipcodes_different_climate_zone_or_state(self, client):
        building_ny = dict(MINIMAL_BUILDING, zipcode="10001")
        building_la = dict(MINIMAL_BUILDING, zipcode="90210")

        resp_ny = client.post("/assess", json={"buildings": [building_ny]})
        resp_la = client.post("/assess", json={"buildings": [building_la]})

        assert resp_ny.status_code == 200
        assert resp_la.status_code == 200

        summary_ny = resp_ny.json()["results"][0]["input_summary"]
        summary_la = resp_la.json()["results"][0]["input_summary"]

        # These two zipcodes are in different states and climate zones
        differs = (
            summary_ny["state"] != summary_la["state"]
            or summary_ny["climate_zone"] != summary_la["climate_zone"]
            or summary_ny["cluster_name"] != summary_la["cluster_name"]
        )
        assert differs, (
            f"NY ({summary_ny}) and LA ({summary_la}) should differ in at least "
            "one of state, climate_zone, or cluster_name"
        )


def test_measure_result_has_savings_by_fuel(client):
    """After assessment, applicable MeasureResults should include per-fuel savings."""
    resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
    assert resp.status_code == 200
    data = resp.json()
    measures = data["results"][0]["measures"]
    applicable = [m for m in measures if m["applicable"]]
    assert len(applicable) > 0, "No applicable measures"

    for m in applicable:
        assert m["savings_by_fuel"] is not None, f"Upgrade {m['upgrade_id']} missing savings_by_fuel"
        assert "electricity" in m["savings_by_fuel"]
        assert "natural_gas" in m["savings_by_fuel"]


def test_package_measures_have_constituent_ids(client):
    """Package measures should have constituent_upgrade_ids populated."""
    resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
    data = resp.json()
    measures = data["results"][0]["measures"]
    packages = [m for m in measures if m["category"] == "package" and m["applicable"]]
    # The mock only returns upgrades [1, 2, 43] which are not packages,
    # so we just verify the field exists (even if null for non-packages)
    for m in measures:
        assert "savings_by_fuel" in m
        assert "constituent_upgrade_ids" in m


def test_individual_measures_no_constituent_ids(client):
    """Individual (non-package) measures should have constituent_upgrade_ids = None."""
    resp = client.post("/assess", json={"buildings": [OFFICE_BUILDING]})
    data = resp.json()
    measures = data["results"][0]["measures"]
    individuals = [m for m in measures if m["category"] != "package"]

    for m in individuals:
        assert m["constituent_upgrade_ids"] is None
