"""Tests for new advanced input fields and derived features."""
import math
import pytest
from app.schemas.request import BuildingInput
from app.services.preprocessor import preprocess


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


def test_hdd_cdd_derived_from_zipcode():
    """HDD/CDD should be automatically derived from zipcode lookup."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    features, _, dataset, _, _ = preprocess(b)
    assert 'hdd65f' in features
    assert 'cdd65f' in features
    assert features['hdd65f'] > 0
    assert features['cdd65f'] > 0


def test_floor_plate_sqft_derived():
    """floor_plate_sqft should be sqft / num_stories."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=5,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    features, _, _, _, _ = preprocess(b)
    assert 'floor_plate_sqft' in features
    assert features['floor_plate_sqft'] == pytest.approx(10000.0)


def test_advanced_inputs_mapped_to_features():
    """When user provides thermostat setpoints, they should appear in features."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
        thermostat_heating_setpoint=70.0,
        thermostat_cooling_setpoint=75.0,
    )
    features, _, _, _, _ = preprocess(b)
    assert features.get('in.tstat_htg_sp_f..f') == 70.0
    assert features.get('in.tstat_clg_sp_f..f') == 75.0


def test_advanced_inputs_none_when_not_provided():
    """When user doesn't provide advanced inputs, they should be NaN."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    features, _, _, _, _ = preprocess(b)
    tstat_val = features.get('in.tstat_htg_sp_f..f')
    assert tstat_val is None or (isinstance(tstat_val, float) and math.isnan(tstat_val))
