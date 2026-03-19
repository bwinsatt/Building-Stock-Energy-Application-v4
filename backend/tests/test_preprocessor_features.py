"""Tests for new advanced input fields and derived features."""
import pytest
from app.schemas.request import BuildingInput


def test_advanced_fields_optional():
    """All new advanced fields should be optional and default to None."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985,
    )
    assert b.thermostat_heating_setpoint is None
    assert b.thermostat_cooling_setpoint is None
    assert b.thermostat_heating_setback is None
    assert b.thermostat_cooling_setback is None
    assert b.weekend_operating_hours is None


def test_advanced_fields_populated():
    """Advanced fields should accept values when provided."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985,
        thermostat_heating_setpoint=70.0,
        thermostat_cooling_setpoint=75.0,
        thermostat_heating_setback=5.0,
        thermostat_cooling_setback=3.0,
        weekend_operating_hours=16.0,
    )
    assert b.thermostat_heating_setpoint == 70.0
    assert b.thermostat_cooling_setpoint == 75.0
    assert b.thermostat_heating_setback == 5.0
    assert b.thermostat_cooling_setback == 3.0
    assert b.weekend_operating_hours == 16.0
