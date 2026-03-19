import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.schemas.energy_star import EnergyStarRequest, EnergyStarResponse
from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult, FuelBreakdown
from app.services.energy_star import (
    BUILDING_TYPE_TO_ESPM,
    ESPM_PROPERTY_USE_ELEMENT,
    FUEL_MAPPING,
    EnergyStarService,
    build_target_finder_xml,
    parse_target_finder_response,
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


# ---------------------------------------------------------------------------
# Task 4: Response Parser tests
# ---------------------------------------------------------------------------

SAMPLE_RESPONSE_WITH_SCORE = """<?xml version="1.0" encoding="UTF-8"?>
<propertyMetrics>
    <metric name="medianSiteIntensity" uom="kBtu/ft2" dataType="numeric"><value>77.4</value></metric>
    <metric name="designSiteIntensity" uom="kBtu/ft2" dataType="numeric"><value>54.2</value></metric>
    <metric name="designScore" dataType="numeric"><value>72</value></metric>
    <metric name="designTargetSiteIntensity" uom="kBtu/ft2" dataType="numeric"><value>48.3</value></metric>
</propertyMetrics>"""

SAMPLE_RESPONSE_NO_SCORE = """<?xml version="1.0" encoding="UTF-8"?>
<propertyMetrics>
    <metric name="medianSiteIntensity" uom="kBtu/ft2" dataType="numeric"><value>120.5</value></metric>
    <metric name="designSiteIntensity" uom="kBtu/ft2" dataType="numeric"><value>95.0</value></metric>
    <metric name="designTargetSiteIntensity" uom="kBtu/ft2" dataType="numeric"><value>60.0</value></metric>
</propertyMetrics>"""


def test_parse_response_with_score():
    """parse_target_finder_response extracts score, EUI values, and sets eligible=True."""
    resp = parse_target_finder_response(SAMPLE_RESPONSE_WITH_SCORE, "Office")
    assert resp.score == 72
    assert resp.eligible is True
    assert resp.median_eui_kbtu_sf == 77.4
    assert resp.target_eui_kbtu_sf == 48.3
    assert resp.design_eui_kbtu_sf == 54.2
    assert "72%" in resp.percentile_text
    assert resp.espm_property_type == "Office"


def test_parse_response_no_score():
    """parse_target_finder_response sets eligible=False and reasons when no designScore present."""
    resp = parse_target_finder_response(SAMPLE_RESPONSE_NO_SCORE, "Convention Center")
    assert resp.score is None
    assert resp.eligible is False
    assert resp.median_eui_kbtu_sf == 120.5
    assert resp.reasons_for_no_score is not None
    assert len(resp.reasons_for_no_score) > 0
    assert resp.espm_property_type == "Convention Center"


# ---------------------------------------------------------------------------
# Task 5: EnergyStarService tests
# ---------------------------------------------------------------------------


def test_get_score_success(office_input, sample_baseline):
    """EnergyStarService.get_score returns score=72 and eligible=True on a 200 response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_RESPONSE_WITH_SCORE

    with patch("app.services.energy_star.httpx.post", return_value=mock_response) as mock_post:
        service = EnergyStarService(base_url="https://test.example.com", username="u", password="p")
        result = service.get_score(office_input, sample_baseline)

    assert result.eligible is True
    assert result.score == 72
    mock_post.assert_called_once()


def test_get_score_with_address(office_input, sample_baseline):
    """EnergyStarService.get_score includes the address in the XML sent to the API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_RESPONSE_WITH_SCORE

    address = "1600 Pennsylvania Ave NW, Washington, DC 20500"
    with patch("app.services.energy_star.httpx.post", return_value=mock_response) as mock_post:
        service = EnergyStarService(base_url="https://test.example.com", username="u", password="p")
        service.get_score(office_input, sample_baseline, address=address)

    call_kwargs = mock_post.call_args
    xml_body = call_kwargs.kwargs.get("content") or call_kwargs.args[1]
    assert "1600 Pennsylvania Ave NW" in xml_body


def test_get_score_unmapped_type(sample_baseline):
    """EnergyStarService.get_score returns eligible=False without calling the API for unmapped types."""
    unknown_building = BuildingInput(
        building_type="UnknownType",
        sqft=10000,
        num_stories=1,
        zipcode="20001",
        year_built=2000,
    )
    with patch("app.services.energy_star.httpx.post") as mock_post:
        service = EnergyStarService(base_url="https://test.example.com", username="u", password="p")
        result = service.get_score(unknown_building, sample_baseline)

    assert result.eligible is False
    assert result.reasons_for_no_score is not None
    assert any("UnknownType" in r for r in result.reasons_for_no_score)
    mock_post.assert_not_called()


def test_get_score_api_error(office_input, sample_baseline):
    """EnergyStarService.get_score raises RuntimeError when httpx.ConnectError is thrown."""
    with patch("app.services.energy_star.httpx.post", side_effect=httpx.ConnectError("connection refused")):
        service = EnergyStarService(base_url="https://test.example.com", username="u", password="p")
        with pytest.raises(RuntimeError, match="unavailable"):
            service.get_score(office_input, sample_baseline)


def test_get_score_auth_failure(office_input, sample_baseline):
    """EnergyStarService.get_score raises RuntimeError on a 401 response."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("app.services.energy_star.httpx.post", return_value=mock_response):
        service = EnergyStarService(base_url="https://test.example.com", username="u", password="p")
        with pytest.raises(RuntimeError, match="authentication failed"):
            service.get_score(office_input, sample_baseline)


# ---------------------------------------------------------------------------
# Task 6: FastAPI endpoint tests
# ---------------------------------------------------------------------------


def test_energy_star_endpoint(app_client, office_input, sample_baseline):
    """POST /energy-star/score returns score=72 when ESPM responds with a valid score."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_RESPONSE_WITH_SCORE

    payload = {
        "building": office_input.model_dump(),
        "baseline": sample_baseline.model_dump(),
    }

    with patch("app.services.energy_star.httpx.post", return_value=mock_response):
        resp = app_client.post("/energy-star/score", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 72
    assert data["eligible"] is True


def test_energy_star_endpoint_api_down(app_client, office_input, sample_baseline):
    """POST /energy-star/score returns 502 when the ESPM API is unreachable."""
    payload = {
        "building": office_input.model_dump(),
        "baseline": sample_baseline.model_dump(),
    }

    with patch("app.services.energy_star.httpx.post", side_effect=httpx.ConnectError("refused")):
        resp = app_client.post("/energy-star/score", json=payload)

    assert resp.status_code == 502
    assert "unavailable" in resp.json()["detail"]
