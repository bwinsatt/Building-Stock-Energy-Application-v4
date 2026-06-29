"""Tests for the assessment service rates output."""

from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.services.assessment import assess_buildings


def test_assessment_result_includes_per_fuel_rates(office_input):
    # The lifespan loads the models into app.state.
    with TestClient(fastapi_app):
        mm = fastapi_app.state.model_manager
        cc = fastapi_app.state.cost_calculator
        imp = getattr(fastapi_app.state, "imputation_service", None)
        results = assess_buildings([office_input], mm, cc, imp)

    result = results[0]
    assert result.baseline.eui_by_fuel.electricity > 0
    assert result.rates is not None
    assert result.rates.electricity > 0
