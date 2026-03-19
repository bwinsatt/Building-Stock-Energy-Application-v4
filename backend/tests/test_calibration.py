"""Tests for utility data calibration helpers."""

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
