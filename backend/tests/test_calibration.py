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
