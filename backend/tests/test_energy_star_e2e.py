"""E2E tests that hit the live ESPM test environment.

Run with: pytest --run-e2e tests/test_energy_star_e2e.py -v

Requires ESPM_USERNAME and ESPM_PASSWORD env vars to be set.
"""

import pytest
from app.services.energy_star import EnergyStarService
from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult, FuelBreakdown


@pytest.mark.e2e
def test_target_finder_office():
    service = EnergyStarService()
    building = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=54.2,
        eui_by_fuel=FuelBreakdown(
            electricity=25.0, natural_gas=20.0, fuel_oil=0.0, propane=0.0, district_heating=0.0,
        ),
    )
    result = service.get_score(building, baseline, address="123 Main St, Washington, DC")
    assert result.median_eui_kbtu_sf is not None
    assert result.median_eui_kbtu_sf > 0
    assert result.espm_property_type == "Office"
    if result.eligible:
        assert 1 <= result.score <= 100
        assert result.percentile_text is not None


@pytest.mark.e2e
def test_target_finder_multifamily():
    service = EnergyStarService()
    building = BuildingInput(
        building_type="Multi-Family", sqft=25000, num_stories=5,
        zipcode="10001", year_built=1985,
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=40.0,
        eui_by_fuel=FuelBreakdown(
            electricity=20.0, natural_gas=15.0, fuel_oil=5.0, propane=0.0, district_heating=0.0,
        ),
    )
    result = service.get_score(building, baseline)
    assert result.median_eui_kbtu_sf is not None
    assert result.espm_property_type == "Multifamily Housing"
