"""Tests for utility data calibration conversions."""
from app.constants import (
    KWH_PER_GALLON_FUEL_OIL,
    KWH_PER_GALLON_PROPANE,
    KWH_PER_THERM,
    KWH_TO_THERMS,
)


def test_kwh_per_gallon_fuel_oil():
    """138,500 BTU/gallon / 3,412 BTU/kWh ≈ 40.6."""
    assert 40.0 < KWH_PER_GALLON_FUEL_OIL < 41.0


def test_kwh_per_gallon_propane():
    """91,500 BTU/gallon / 3,412 BTU/kWh ≈ 26.8."""
    assert 26.0 < KWH_PER_GALLON_PROPANE < 27.5


def test_kwh_per_therm_is_inverse():
    """KWH_PER_THERM should be the inverse of KWH_TO_THERMS."""
    assert abs(KWH_PER_THERM - (1.0 / KWH_TO_THERMS)) < 0.1


from app.schemas.request import BuildingInput


def test_building_input_accepts_utility_data():
    """BuildingInput should accept optional utility data fields."""
    inp = BuildingInput(
        building_type="OfficeSmall",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        annual_electricity_kwh=500000,
        annual_natural_gas_therms=10000,
    )
    assert inp.annual_electricity_kwh == 500000
    assert inp.annual_natural_gas_therms == 10000
    assert inp.annual_fuel_oil_gallons is None
    assert inp.annual_propane_gallons is None
    assert inp.annual_district_heating_kbtu is None


def test_building_input_without_utility_data():
    """BuildingInput without utility data should still work."""
    inp = BuildingInput(
        building_type="OfficeSmall",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
    )
    assert inp.annual_electricity_kwh is None


from app.schemas.response import BaselineResult, BuildingResult, FuelBreakdown


def test_baseline_result_with_actual_eui():
    """BaselineResult should accept actual EUI fields."""
    fuel = FuelBreakdown(
        electricity=10.0, natural_gas=5.0, fuel_oil=0, propane=0, district_heating=0,
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=51.18,
        eui_by_fuel=fuel,
        actual_eui_by_fuel=fuel,
        actual_total_eui_kbtu_sf=60.0,
    )
    assert baseline.actual_total_eui_kbtu_sf == 60.0
    assert baseline.actual_eui_by_fuel.electricity == 10.0


def test_baseline_result_without_actual_eui():
    """BaselineResult without actual EUI should default to None."""
    fuel = FuelBreakdown(
        electricity=10.0, natural_gas=5.0, fuel_oil=0, propane=0, district_heating=0,
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=51.18,
        eui_by_fuel=fuel,
    )
    assert baseline.actual_eui_by_fuel is None
    assert baseline.actual_total_eui_kbtu_sf is None


from app.services.assessment import convert_utility_to_eui


def test_convert_utility_to_eui_electricity_only():
    """Convert annual kWh to kWh/sqft."""
    result = convert_utility_to_eui(
        annual_electricity_kwh=500000,
        sqft=50000,
    )
    assert result["electricity"] == 10.0
    assert result["natural_gas"] == 0.0


def test_convert_utility_to_eui_all_fuels():
    """Convert all fuel types to kWh/sqft."""
    result = convert_utility_to_eui(
        annual_electricity_kwh=500000,
        annual_natural_gas_therms=10000,
        annual_fuel_oil_gallons=1000,
        annual_propane_gallons=500,
        annual_district_heating_kbtu=100000,
        sqft=50000,
    )
    assert result["electricity"] == 10.0  # 500000 / 50000
    assert abs(result["natural_gas"] - 5.862) < 0.01  # 10000 * 29.31 / 50000
    assert abs(result["fuel_oil"] - 0.812) < 0.01  # 1000 * 40.6 / 50000
    assert abs(result["propane"] - 0.268) < 0.01  # 500 * 26.8 / 50000
    assert abs(result["district_heating"] - 0.586) < 0.01  # 100000 / 3.412 / 50000


def test_convert_utility_to_eui_none_input():
    """When no utility data provided, return None."""
    result = convert_utility_to_eui(sqft=50000)
    assert result is None


import pytest
from app.services.assessment import _assess_single


def _get_app_state():
    """Return (mm, cc, imp) from app.state, or None if models not loaded."""
    try:
        from app.main import app
        mm = app.state.model_manager
        cc = app.state.cost_calculator
        imp = getattr(app.state, "imputation_service", None)
        # Check that at least one dataset has baseline models loaded
        has_models = any(
            mm._loaded.get(ds, {}).get("baseline")
            for ds in ("comstock", "resstock")
        )
        if not has_models:
            return None
        return mm, cc, imp
    except AttributeError:
        return None


@pytest.mark.skipif(
    not pytest.importorskip("app.inference.model_manager", reason="Models not available"),
    reason="Models not available",
)
def test_calibrated_assessment_returns_calibrated_flag(calibrated_office_input):
    """Integration test: assessment with utility data should return calibrated=True."""
    state = _get_app_state()
    if state is None:
        pytest.skip("Models not loaded — run with a live app context")
    mm, cc, imp = state

    result = _assess_single(calibrated_office_input, 0, mm, cc, imp)
    assert result.calibrated is True
    assert result.baseline.actual_eui_by_fuel is not None
    assert result.baseline.actual_total_eui_kbtu_sf is not None
    assert result.baseline.actual_total_eui_kbtu_sf > 0


def test_uncalibrated_assessment_returns_not_calibrated(office_input):
    """Integration test: assessment without utility data should return calibrated=False."""
    state = _get_app_state()
    if state is None:
        pytest.skip("Models not loaded — run with a live app context")
    mm, cc, imp = state

    result = _assess_single(office_input, 0, mm, cc, imp)
    assert result.calibrated is False
    assert result.baseline.actual_eui_by_fuel is None
