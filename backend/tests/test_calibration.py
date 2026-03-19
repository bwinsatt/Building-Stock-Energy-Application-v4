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
