import xml.etree.ElementTree as ET

import pytest

from app.schemas.energy_star import EnergyStarRequest, EnergyStarResponse
from app.schemas.response import BaselineResult, FuelBreakdown
from app.services.energy_star import (
    BUILDING_TYPE_TO_ESPM,
    ESPM_PROPERTY_USE_ELEMENT,
    FUEL_MAPPING,
    build_target_finder_xml,
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


# ---------------------------------------------------------------------------
# Task 3: XML Builder tests
# ---------------------------------------------------------------------------


def test_build_xml_office(office_input, sample_baseline):
    """build_target_finder_xml produces correct propertyInfo, propertyUses, and 2 energy entries."""
    xml_str = build_target_finder_xml(
        building=office_input,
        baseline=sample_baseline,
        address="1600 Pennsylvania Ave NW",
        state="DC",
    )
    root = ET.fromstring(xml_str)

    # propertyInfo checks
    assert root.find(".//primaryFunction").text == "Office"
    assert root.find(".//grossFloorArea/value").text == "50000"
    assert root.find(".//plannedConstructionCompletionYear").text == "1985"
    address_el = root.find(".//address")
    assert address_el.get("address1") == "1600 Pennsylvania Ave NW"
    assert address_el.get("postalCode") == "20001"
    assert address_el.get("state") == "DC"
    assert address_el.get("country") == "US"

    # propertyUses checks — office element
    assert root.find(".//propertyUses/office") is not None
    assert root.find(".//propertyUses/office/name").text == "Office"
    assert root.find(".//propertyUses/office/useDetails/totalGrossFloorArea/value").text == "50000"

    # energy entries — sample_baseline has electricity=25.0 and natural_gas=20.0 (fuel_oil/propane/district=0)
    entries = root.findall(".//designEntry")
    assert len(entries) == 2
    energy_types = {e.find("energyType").text for e in entries}
    assert "Electric" in energy_types
    assert "Natural Gas" in energy_types

    # target score
    assert root.find(".//target/targetTypeScore/value").text == "75"


def test_build_xml_no_address(office_input, sample_baseline):
    """build_target_finder_xml uses address1='N/A' when address is None."""
    xml_str = build_target_finder_xml(
        building=office_input,
        baseline=sample_baseline,
        address=None,
        state="DC",
    )
    root = ET.fromstring(xml_str)
    address_el = root.find(".//address")
    assert address_el.get("address1") == "N/A"


def test_build_xml_skips_zero_fuels(office_input):
    """build_target_finder_xml only includes designEntry elements for fuels with EUI > 0."""
    electricity_only_baseline = BaselineResult(
        total_eui_kbtu_sf=30.0,
        eui_by_fuel=FuelBreakdown(
            electricity=30.0,
            natural_gas=0.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )
    xml_str = build_target_finder_xml(
        building=office_input,
        baseline=electricity_only_baseline,
        address=None,
        state="DC",
    )
    root = ET.fromstring(xml_str)
    entries = root.findall(".//designEntry")
    assert len(entries) == 1
    assert entries[0].find("energyType").text == "Electric"
