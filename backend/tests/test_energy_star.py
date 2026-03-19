import pytest

from app.schemas.energy_star import EnergyStarRequest, EnergyStarResponse
from app.services.energy_star import (
    BUILDING_TYPE_TO_ESPM,
    ESPM_PROPERTY_USE_ELEMENT,
    FUEL_MAPPING,
)

# ---------------------------------------------------------------------------
# Task 1: Schema tests
# ---------------------------------------------------------------------------

FRONTEND_BUILDING_TYPES = [
    "Education",
    "Food Sales",
    "Food Service",
    "Healthcare",
    "Lodging",
    "Mercantile",
    "Mixed Use",
    "Multi-Family",
    "Office",
    "Public Assembly",
    "Public Order and Safety",
    "Religious Worship",
    "Service",
    "Warehouse and Storage",
]


def test_energy_star_request_valid(office_input, sample_baseline):
    """EnergyStarRequest accepts a valid building + baseline + address."""
    req = EnergyStarRequest(
        building=office_input,
        baseline=sample_baseline,
        address="1600 Pennsylvania Ave NW, Washington, DC 20500",
    )
    assert req.building.building_type == "Office"
    assert req.baseline.total_eui_kbtu_sf == 54.2
    assert req.address is not None


def test_energy_star_request_no_address(office_input, sample_baseline):
    """address is optional — omitting it should succeed."""
    req = EnergyStarRequest(building=office_input, baseline=sample_baseline)
    assert req.address is None


def test_energy_star_response_with_score():
    """EnergyStarResponse with a valid score populates all relevant fields."""
    resp = EnergyStarResponse(
        score=78,
        eligible=True,
        median_eui_kbtu_sf=60.0,
        target_eui_kbtu_sf=50.0,
        design_eui_kbtu_sf=54.2,
        percentile_text="78th percentile",
        espm_property_type="Office",
    )
    assert resp.score == 78
    assert resp.eligible is True
    assert resp.reasons_for_no_score is None


def test_energy_star_response_ineligible():
    """EnergyStarResponse for an ineligible building has no score and carries reasons."""
    resp = EnergyStarResponse(
        score=None,
        eligible=False,
        espm_property_type="Convention Center",
        reasons_for_no_score=["Building type not eligible for ENERGY STAR score"],
    )
    assert resp.score is None
    assert resp.eligible is False
    assert resp.reasons_for_no_score == ["Building type not eligible for ENERGY STAR score"]


# ---------------------------------------------------------------------------
# Task 2: Mapping tests
# ---------------------------------------------------------------------------


def test_all_building_types_mapped():
    """Every frontend building type must have an entry in BUILDING_TYPE_TO_ESPM."""
    missing = [bt for bt in FRONTEND_BUILDING_TYPES if bt not in BUILDING_TYPE_TO_ESPM]
    assert missing == [], f"Missing ESPM mappings for: {missing}"


def test_property_use_elements_exist_for_scored_types():
    """Every ESPM property type produced by the mapping must have a property use element."""
    missing = []
    for espm_type in BUILDING_TYPE_TO_ESPM.values():
        if espm_type not in ESPM_PROPERTY_USE_ELEMENT:
            missing.append(espm_type)
    assert missing == [], f"Missing ESPM_PROPERTY_USE_ELEMENT entries for: {missing}"


def test_fuel_mapping_covers_all_fuels():
    """FUEL_MAPPING must cover every fuel field present in FuelBreakdown."""
    expected_fuels = {"electricity", "natural_gas", "fuel_oil", "propane", "district_heating"}
    assert set(FUEL_MAPPING.keys()) == expected_fuels
