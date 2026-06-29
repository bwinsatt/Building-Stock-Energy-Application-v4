"""Tests for the assessment service export helper."""

from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.services.assessment import assess_building_for_export


def test_assess_building_for_export_returns_result_and_rates(office_input):
    # The lifespan loads the models into app.state.
    with TestClient(fastapi_app):
        mm = fastapi_app.state.model_manager
        cc = fastapi_app.state.cost_calculator
        imp = getattr(fastapi_app.state, "imputation_service", None)
        result, rates = assess_building_for_export(office_input, mm, cc, imp)

    assert result.baseline.eui_by_fuel.electricity > 0
    assert isinstance(rates, dict)
    assert rates.get("electricity", 0) > 0
