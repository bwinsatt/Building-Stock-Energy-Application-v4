# ENERGY STAR Target Finder Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-demand ENERGY STAR scoring via the Target Finder API, displayed as a dedicated section in the assessment results UI.

**Architecture:** A new `EnergyStarService` builds Target Finder XML from existing assessment output, calls the ESPM API, and parses the response. A new `POST /energy-star/score` endpoint exposes it. A new `EnergyStarScore.vue` component renders the result between BaselineSummary and MeasuresTable.

**Tech Stack:** Python (httpx, xml.etree.ElementTree, Pydantic v2), Vue 3 Composition API, TypeScript, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-18-energy-star-target-finder-design.md`

---

## File Structure

### Backend — New Files
- `backend/app/services/energy_star.py` — EnergyStarService class (XML building, API call, response parsing)
- `backend/app/schemas/energy_star.py` — EnergyStarRequest and EnergyStarResponse Pydantic models
- `backend/tests/test_energy_star.py` — Unit tests for service (mapping, XML, parsing)
- `backend/tests/test_energy_star_e2e.py` — E2e test hitting ESPM test environment

### Backend — Modified Files
- `backend/app/api/routes.py` — Add `POST /energy-star/score` endpoint

### Frontend — New Files
- `frontend/src/components/EnergyStarScore.vue` — Score display component
- `frontend/src/composables/useEnergyStarScore.ts` — API call composable

### Frontend — Modified Files
- `frontend/src/types/assessment.ts` — Add EnergyStarResponse interface
- `frontend/src/views/AssessmentView.vue` — Mount EnergyStarScore between BaselineSummary and MeasuresTable

---

## Task 1: Backend Schemas

**Files:**
- Create: `backend/app/schemas/energy_star.py`
- Test: `backend/tests/test_energy_star.py`

- [ ] **Step 1: Write the schema file**

Create `backend/app/schemas/energy_star.py`:

```python
from pydantic import BaseModel
from typing import Optional

from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult


class EnergyStarRequest(BaseModel):
    building: BuildingInput
    baseline: BaselineResult
    address: Optional[str] = None


class EnergyStarResponse(BaseModel):
    score: Optional[int] = None
    eligible: bool
    median_eui_kbtu_sf: Optional[float] = None
    target_eui_kbtu_sf: Optional[float] = None
    design_eui_kbtu_sf: Optional[float] = None
    percentile_text: Optional[str] = None
    espm_property_type: str
    reasons_for_no_score: Optional[list[str]] = None
```

- [ ] **Step 2: Write a smoke test for schema validation**

Create `backend/tests/test_energy_star.py`:

```python
import pytest
from app.schemas.energy_star import EnergyStarRequest, EnergyStarResponse
from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult, FuelBreakdown


@pytest.fixture
def sample_building():
    return BuildingInput(
        building_type="Office",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        heating_fuel="NaturalGas",
    )


@pytest.fixture
def sample_baseline():
    return BaselineResult(
        total_eui_kbtu_sf=54.2,
        eui_by_fuel=FuelBreakdown(
            electricity=25.0,
            natural_gas=20.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )


def test_energy_star_request_valid(sample_building, sample_baseline):
    req = EnergyStarRequest(
        building=sample_building,
        baseline=sample_baseline,
        address="123 Main St, Washington, DC 20001",
    )
    assert req.building.building_type == "Office"
    assert req.address is not None


def test_energy_star_request_no_address(sample_building, sample_baseline):
    req = EnergyStarRequest(building=sample_building, baseline=sample_baseline)
    assert req.address is None


def test_energy_star_response_with_score():
    resp = EnergyStarResponse(
        score=72,
        eligible=True,
        median_eui_kbtu_sf=77.4,
        target_eui_kbtu_sf=48.3,
        design_eui_kbtu_sf=54.2,
        percentile_text="Better than 72% of similar buildings",
        espm_property_type="Office",
    )
    assert resp.score == 72
    assert resp.eligible is True


def test_energy_star_response_ineligible():
    resp = EnergyStarResponse(
        eligible=False,
        median_eui_kbtu_sf=77.4,
        espm_property_type="Other - Services",
        reasons_for_no_score=["Property type not eligible for ENERGY STAR scoring"],
    )
    assert resp.score is None
    assert resp.eligible is False
    assert len(resp.reasons_for_no_score) == 1
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_energy_star.py -v`
Expected: All 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/energy_star.py backend/tests/test_energy_star.py
git commit -m "feat: add EnergyStarRequest/Response Pydantic schemas"
```

---

## Task 2: Building Type & Energy Mapping

**Files:**
- Create: `backend/app/services/energy_star.py` (partial — mappings only)
- Test: `backend/tests/test_energy_star.py` (append)

- [ ] **Step 1: Write failing tests for building type mapping**

Append to `backend/tests/test_energy_star.py`:

```python
from app.services.energy_star import (
    BUILDING_TYPE_TO_ESPM,
    ESPM_PROPERTY_USE_ELEMENT,
    FUEL_MAPPING,
)


def test_all_building_types_mapped():
    """Every frontend building type must have an ESPM mapping."""
    expected_types = [
        "Education", "Food Sales", "Food Service", "Healthcare",
        "Lodging", "Mercantile", "Mixed Use", "Multi-Family", "Office",
        "Public Assembly", "Public Order and Safety", "Religious Worship",
        "Service", "Warehouse and Storage",
    ]
    for bt in expected_types:
        assert bt in BUILDING_TYPE_TO_ESPM, f"Missing ESPM mapping for '{bt}'"


def test_property_use_elements_exist_for_scored_types():
    """Score-eligible types must have a property use XML element."""
    scored_types = ["Office", "Retail Store", "Hotel",
                    "Hospital (General Medical & Surgical)", "K-12 School",
                    "Supermarket/Grocery Store", "Multifamily Housing",
                    "Non-Refrigerated Warehouse"]
    for espm_type in scored_types:
        assert espm_type in ESPM_PROPERTY_USE_ELEMENT, (
            f"Missing property use element for '{espm_type}'"
        )


def test_fuel_mapping_covers_all_fuels():
    expected_fuels = ["electricity", "natural_gas", "fuel_oil", "propane", "district_heating"]
    for fuel in expected_fuels:
        assert fuel in FUEL_MAPPING, f"Missing fuel mapping for '{fuel}'"
        assert "energyType" in FUEL_MAPPING[fuel]
        assert "energyUnit" in FUEL_MAPPING[fuel]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_energy_star.py::test_all_building_types_mapped -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write the mappings in the service file**

Create `backend/app/services/energy_star.py`:

```python
"""ENERGY STAR Portfolio Manager Target Finder integration."""

import os

BUILDING_TYPE_TO_ESPM: dict[str, str] = {
    "Office": "Office",
    "Warehouse and Storage": "Non-Refrigerated Warehouse",
    "Mercantile": "Retail Store",
    "Lodging": "Hotel",
    "Healthcare": "Hospital (General Medical & Surgical)",
    "Education": "K-12 School",
    "Food Sales": "Supermarket/Grocery Store",
    "Food Service": "Restaurant",
    "Multi-Family": "Multifamily Housing",
    "Public Assembly": "Convention Center",
    "Public Order and Safety": "Courthouse",
    "Religious Worship": "Worship Facility",
    "Service": "Other - Services",
    "Mixed Use": "Mixed Use Property",
}

ESPM_PROPERTY_USE_ELEMENT: dict[str, str] = {
    "Office": "office",
    "Non-Refrigerated Warehouse": "nonRefrigeratedWarehouse",
    "Retail Store": "retail",
    "Hotel": "hotel",
    "Hospital (General Medical & Surgical)": "hospital",
    "K-12 School": "k12School",
    "Supermarket/Grocery Store": "supermarket",
    "Restaurant": "restaurant",
    "Multifamily Housing": "multifamilyHousing",
    "Convention Center": "other",
    "Courthouse": "other",
    "Worship Facility": "worshipFacility",
    "Other - Services": "other",
    "Mixed Use Property": "other",
}

FUEL_MAPPING: dict[str, dict[str, str]] = {
    "electricity": {
        "energyType": "Electric",
        "energyUnit": "kBtu (thousand Btu)",
    },
    "natural_gas": {
        "energyType": "Natural Gas",
        "energyUnit": "kBtu (thousand Btu)",
    },
    "fuel_oil": {
        "energyType": "Fuel Oil No 2",
        "energyUnit": "kBtu (thousand Btu)",
    },
    "propane": {
        "energyType": "Propane",
        "energyUnit": "kBtu (thousand Btu)",
    },
    "district_heating": {
        "energyType": "District Steam",
        "energyUnit": "kBtu (thousand Btu)",
    },
}

# Config
ESPM_BASE_URL = os.environ.get(
    "ESPM_BASE_URL", "https://portfoliomanager.energystar.gov/wstest"
)
ESPM_USERNAME = os.environ.get("ESPM_USERNAME", "")
ESPM_PASSWORD = os.environ.get("ESPM_PASSWORD", "")
ESPM_TIMEOUT = 15  # seconds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_energy_star.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/energy_star.py backend/tests/test_energy_star.py
git commit -m "feat: add ESPM building type, property use, and fuel mappings"
```

---

## Task 3: XML Builder

**Files:**
- Modify: `backend/app/services/energy_star.py`
- Test: `backend/tests/test_energy_star.py` (append)

- [ ] **Step 1: Write failing test for XML construction**

Append to `backend/tests/test_energy_star.py`:

```python
import xml.etree.ElementTree as ET
from app.services.energy_star import build_target_finder_xml


def test_build_xml_office(sample_building, sample_baseline):
    xml_str = build_target_finder_xml(
        building=sample_building,
        baseline=sample_baseline,
        address="123 Main St",
        state="DC",
    )
    root = ET.fromstring(xml_str)

    # propertyInfo
    info = root.find("propertyInfo")
    assert info is not None
    assert info.find("primaryFunction").text == "Office"
    assert info.find("grossFloorArea/value").text == "50000"
    assert info.find("plannedConstructionCompletionYear").text == "1985"
    addr = info.find("address")
    assert addr.get("address1") == "123 Main St"
    assert addr.get("postalCode") == "20001"
    assert addr.get("state") == "DC"
    assert addr.get("country") == "US"

    # propertyUses
    uses = root.find("propertyUses")
    office = uses.find("office")
    assert office is not None
    gfa = office.find("useDetails/totalGrossFloorArea/value")
    assert gfa.text == "50000"

    # estimatedEnergyList — should have 2 entries (electricity + natural gas)
    entries = root.findall("estimatedEnergyList/entries/designEntry")
    assert len(entries) == 2
    energy_types = {e.find("energyType").text for e in entries}
    assert energy_types == {"Electric", "Natural Gas"}

    # target
    target_score = root.find("target/targetTypeScore/value")
    assert target_score.text == "75"


def test_build_xml_no_address(sample_building, sample_baseline):
    xml_str = build_target_finder_xml(
        building=sample_building,
        baseline=sample_baseline,
        address=None,
        state="DC",
    )
    root = ET.fromstring(xml_str)
    addr = root.find("propertyInfo/address")
    assert addr.get("address1") == "N/A"


def test_build_xml_skips_zero_fuels(sample_building):
    """Fuels with 0 EUI should not appear in estimatedEnergyList."""
    baseline = BaselineResult(
        total_eui_kbtu_sf=25.0,
        eui_by_fuel=FuelBreakdown(
            electricity=25.0,
            natural_gas=0.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )
    xml_str = build_target_finder_xml(
        building=sample_building, baseline=baseline, address=None, state="DC"
    )
    root = ET.fromstring(xml_str)
    entries = root.findall("estimatedEnergyList/entries/designEntry")
    assert len(entries) == 1
    assert entries[0].find("energyType").text == "Electric"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_energy_star.py::test_build_xml_office -v`
Expected: FAIL with ImportError (build_target_finder_xml not defined)

- [ ] **Step 3: Implement `build_target_finder_xml`**

Add to `backend/app/services/energy_star.py`:

```python
import xml.etree.ElementTree as ET

from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult


def build_target_finder_xml(
    building: BuildingInput,
    baseline: BaselineResult,
    address: str | None,
    state: str,
) -> str:
    """Build the Target Finder XML request body."""
    espm_type = BUILDING_TYPE_TO_ESPM.get(building.building_type)
    if espm_type is None:
        raise ValueError(f"No ESPM mapping for building type '{building.building_type}'")

    use_element = ESPM_PROPERTY_USE_ELEMENT.get(espm_type, "other")

    root = ET.Element("targetFinder")

    # --- propertyInfo ---
    info = ET.SubElement(root, "propertyInfo")
    ET.SubElement(info, "name").text = (
        f"{building.building_type} - {address or building.zipcode}"
    )
    ET.SubElement(info, "primaryFunction").text = espm_type

    gfa = ET.SubElement(info, "grossFloorArea")
    gfa.set("units", "Square Feet")
    gfa.set("temporary", "false")
    ET.SubElement(gfa, "value").text = str(int(building.sqft))

    ET.SubElement(info, "plannedConstructionCompletionYear").text = str(
        building.year_built
    )

    addr_el = ET.SubElement(info, "address")
    addr_el.set("address1", address or "N/A")
    addr_el.set("postalCode", building.zipcode)
    addr_el.set("state", state)
    addr_el.set("country", "US")

    ET.SubElement(info, "numberOfBuildings").text = "1"

    # --- propertyUses ---
    uses = ET.SubElement(root, "propertyUses")
    use = ET.SubElement(uses, use_element)
    ET.SubElement(use, "name").text = building.building_type
    details = ET.SubElement(use, "useDetails")
    total_gfa = ET.SubElement(details, "totalGrossFloorArea")
    total_gfa.set("units", "Square Feet")
    ET.SubElement(total_gfa, "value").text = str(int(building.sqft))

    # --- estimatedEnergyList ---
    fuel_data = baseline.eui_by_fuel
    fuel_entries = []
    for fuel_key, mapping in FUEL_MAPPING.items():
        eui_kbtu_sf = getattr(fuel_data, fuel_key, 0.0)
        if eui_kbtu_sf > 0:
            annual_kbtu = eui_kbtu_sf * building.sqft
            fuel_entries.append((mapping, annual_kbtu))

    if fuel_entries:
        energy_list = ET.SubElement(root, "estimatedEnergyList")
        entries = ET.SubElement(energy_list, "entries")
        for mapping, annual_kbtu in fuel_entries:
            entry = ET.SubElement(entries, "designEntry")
            ET.SubElement(entry, "energyType").text = mapping["energyType"]
            ET.SubElement(entry, "energyUnit").text = mapping["energyUnit"]
            ET.SubElement(entry, "estimatedAnnualEnergyUsage").text = str(
                round(annual_kbtu, 2)
            )

    # --- target ---
    target = ET.SubElement(root, "target")
    score_target = ET.SubElement(target, "targetTypeScore")
    ET.SubElement(score_target, "value").text = "75"

    return ET.tostring(root, encoding="unicode", xml_declaration=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_energy_star.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/energy_star.py backend/tests/test_energy_star.py
git commit -m "feat: implement Target Finder XML builder"
```

---

## Task 4: Response Parser

**Files:**
- Modify: `backend/app/services/energy_star.py`
- Test: `backend/tests/test_energy_star.py` (append)

- [ ] **Step 1: Write failing tests for response parsing**

Append to `backend/tests/test_energy_star.py`:

```python
from app.services.energy_star import parse_target_finder_response


SAMPLE_RESPONSE_WITH_SCORE = """<?xml version="1.0" encoding="UTF-8"?>
<propertyMetrics>
    <metric name="medianSiteIntensity" uom="kBtu/ft2" dataType="numeric">
        <value>77.4</value>
    </metric>
    <metric name="designSiteIntensity" uom="kBtu/ft2" dataType="numeric">
        <value>54.2</value>
    </metric>
    <metric name="designScore" dataType="numeric">
        <value>72</value>
    </metric>
    <metric name="designTargetSiteIntensity" uom="kBtu/ft2" dataType="numeric">
        <value>48.3</value>
    </metric>
</propertyMetrics>
"""

SAMPLE_RESPONSE_NO_SCORE = """<?xml version="1.0" encoding="UTF-8"?>
<propertyMetrics>
    <metric name="medianSiteIntensity" uom="kBtu/ft2" dataType="numeric">
        <value>120.5</value>
    </metric>
    <metric name="designSiteIntensity" uom="kBtu/ft2" dataType="numeric">
        <value>95.0</value>
    </metric>
    <metric name="designTargetSiteIntensity" uom="kBtu/ft2" dataType="numeric">
        <value>60.0</value>
    </metric>
</propertyMetrics>
"""


def test_parse_response_with_score():
    result = parse_target_finder_response(SAMPLE_RESPONSE_WITH_SCORE, "Office")
    assert result.score == 72
    assert result.eligible is True
    assert result.median_eui_kbtu_sf == 77.4
    assert result.target_eui_kbtu_sf == 48.3
    assert result.design_eui_kbtu_sf == 54.2
    assert result.espm_property_type == "Office"
    assert "72%" in result.percentile_text


def test_parse_response_no_score():
    result = parse_target_finder_response(SAMPLE_RESPONSE_NO_SCORE, "Other - Services")
    assert result.score is None
    assert result.eligible is False
    assert result.median_eui_kbtu_sf == 120.5
    assert result.espm_property_type == "Other - Services"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_energy_star.py::test_parse_response_with_score -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `parse_target_finder_response`**

Add to `backend/app/services/energy_star.py`:

```python
from app.schemas.energy_star import EnergyStarResponse


def parse_target_finder_response(
    xml_text: str, espm_property_type: str
) -> EnergyStarResponse:
    """Parse the ESPM Target Finder XML response into an EnergyStarResponse."""
    root = ET.fromstring(xml_text)

    def _metric(name: str) -> float | None:
        for m in root.findall("metric"):
            if m.get("name") == name:
                val = m.find("value")
                if val is not None and val.text:
                    try:
                        return float(val.text)
                    except ValueError:
                        return None
        return None

    design_score_raw = _metric("designScore")
    score = int(design_score_raw) if design_score_raw is not None else None
    eligible = score is not None
    median_eui = _metric("medianSiteIntensity")
    target_eui = _metric("designTargetSiteIntensity")
    design_eui = _metric("designSiteIntensity")

    percentile_text = None
    reasons = None
    if score is not None:
        percentile_text = f"Better than {score}% of similar buildings"
    else:
        reasons = ["ENERGY STAR score not available for this property type or configuration"]

    return EnergyStarResponse(
        score=score,
        eligible=eligible,
        median_eui_kbtu_sf=median_eui,
        target_eui_kbtu_sf=target_eui,
        design_eui_kbtu_sf=design_eui,
        percentile_text=percentile_text,
        espm_property_type=espm_property_type,
        reasons_for_no_score=reasons,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_energy_star.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/energy_star.py backend/tests/test_energy_star.py
git commit -m "feat: implement Target Finder response parser"
```

---

## Task 5: EnergyStarService (API Call Orchestration)

**Files:**
- Modify: `backend/app/services/energy_star.py`
- Test: `backend/tests/test_energy_star.py` (append)

- [ ] **Step 1: Write failing test for EnergyStarService.get_score**

Append to `backend/tests/test_energy_star.py`:

```python
from unittest.mock import patch, MagicMock
from app.services.energy_star import EnergyStarService


def test_get_score_success(sample_building, sample_baseline):
    """Mock httpx to return a scored response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_RESPONSE_WITH_SCORE

    service = EnergyStarService()
    with patch("app.services.energy_star.httpx.post", return_value=mock_response):
        result = service.get_score(sample_building, sample_baseline)

    assert result.score == 72
    assert result.eligible is True
    assert result.espm_property_type == "Office"


def test_get_score_with_address(sample_building, sample_baseline):
    """Verify address is passed through to XML."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_RESPONSE_WITH_SCORE

    service = EnergyStarService()
    with patch("app.services.energy_star.httpx.post", return_value=mock_response) as mock_post:
        service.get_score(sample_building, sample_baseline, address="456 Oak Ave")

    # Verify the XML sent contains the address
    call_kwargs = mock_post.call_args
    sent_xml = call_kwargs.kwargs.get("content") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("data", "")
    assert "456 Oak Ave" in str(sent_xml)


def test_get_score_unmapped_type(sample_baseline):
    """Unknown building type should return eligible=False without calling API."""
    building = BuildingInput(
        building_type="UnknownType",
        sqft=10000, num_stories=1, zipcode="20001", year_built=2000,
    )
    service = EnergyStarService()
    with patch("app.services.energy_star.httpx.post") as mock_post:
        result = service.get_score(building, sample_baseline)
        mock_post.assert_not_called()

    assert result.eligible is False
    assert result.score is None
    assert result.reasons_for_no_score is not None


def test_get_score_api_error(sample_building, sample_baseline):
    """Network error should raise."""
    import httpx as httpx_module

    service = EnergyStarService()
    with patch(
        "app.services.energy_star.httpx.post",
        side_effect=httpx_module.ConnectError("Connection refused"),
    ):
        with pytest.raises(Exception):
            service.get_score(sample_building, sample_baseline)


def test_get_score_auth_failure(sample_building, sample_baseline):
    """401 should raise."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    service = EnergyStarService()
    with patch("app.services.energy_star.httpx.post", return_value=mock_response):
        with pytest.raises(Exception):
            service.get_score(sample_building, sample_baseline)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_energy_star.py::test_get_score_success -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement EnergyStarService**

Add to `backend/app/services/energy_star.py`:

```python
import logging
import httpx

logger = logging.getLogger(__name__)


class EnergyStarService:
    """Calls the ESPM Target Finder API to get an ENERGY STAR score."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.base_url = base_url or ESPM_BASE_URL
        self.username = username or ESPM_USERNAME
        self.password = password or ESPM_PASSWORD

    def get_score(
        self,
        building: BuildingInput,
        baseline: BaselineResult,
        address: str | None = None,
    ) -> EnergyStarResponse:
        espm_type = BUILDING_TYPE_TO_ESPM.get(building.building_type)
        if espm_type is None:
            return EnergyStarResponse(
                eligible=False,
                espm_property_type=building.building_type,
                reasons_for_no_score=[
                    f"No ESPM mapping for building type '{building.building_type}'"
                ],
            )

        # Resolve state from zipcode
        from app.services.preprocessor import _zip_lookup

        try:
            state, _, _ = _zip_lookup.lookup(building.zipcode)
        except ValueError:
            state = ""

        xml_body = build_target_finder_xml(building, baseline, address, state)

        url = f"{self.base_url}/targetFinder?measurementSystem=EPA"
        try:
            response = httpx.post(
                url,
                content=xml_body,
                headers={"Content-Type": "application/xml"},
                auth=(self.username, self.password),
                timeout=ESPM_TIMEOUT,
            )
        except httpx.ConnectError as exc:
            raise RuntimeError("ENERGY STAR service unavailable") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("ENERGY STAR service timed out") from exc

        if response.status_code == 401:
            raise RuntimeError("ENERGY STAR authentication failed")

        if response.status_code != 200:
            logger.error("ESPM API error %d: %s", response.status_code, response.text)
            raise RuntimeError(
                f"ENERGY STAR API returned status {response.status_code}"
            )

        return parse_target_finder_response(response.text, espm_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_energy_star.py -v`
Expected: All 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/energy_star.py backend/tests/test_energy_star.py
git commit -m "feat: implement EnergyStarService with API call orchestration"
```

---

## Task 6: FastAPI Endpoint

**Files:**
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_energy_star.py` (append)

- [ ] **Step 1: Write failing test for the endpoint**

Append to `backend/tests/test_energy_star.py`:

```python
def test_energy_star_endpoint(app_client, sample_building, sample_baseline):
    """POST /energy-star/score returns a score via mocked ESPM."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_RESPONSE_WITH_SCORE

    with patch("app.services.energy_star.httpx.post", return_value=mock_response):
        resp = app_client.post(
            "/energy-star/score",
            json={
                "building": sample_building.model_dump(),
                "baseline": sample_baseline.model_dump(),
                "address": "123 Main St",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 72
    assert data["eligible"] is True
    assert data["espm_property_type"] == "Office"


def test_energy_star_endpoint_api_down(app_client, sample_building, sample_baseline):
    """POST /energy-star/score returns 502 when ESPM is down."""
    import httpx as httpx_module

    with patch(
        "app.services.energy_star.httpx.post",
        side_effect=httpx_module.ConnectError("Connection refused"),
    ):
        resp = app_client.post(
            "/energy-star/score",
            json={
                "building": sample_building.model_dump(),
                "baseline": sample_baseline.model_dump(),
            },
        )

    assert resp.status_code == 502
```

Note: The `app_client` fixture is defined in `conftest.py`. The existing `office_input` fixture in conftest is identical to `sample_building` — use it directly. Add a `sample_baseline` fixture to conftest so it's shared.

- [ ] **Step 2: Add sample_baseline to conftest.py, remove local sample_building**

Add to `backend/tests/conftest.py`:

```python
from app.schemas.response import BaselineResult, FuelBreakdown


@pytest.fixture
def sample_baseline():
    return BaselineResult(
        total_eui_kbtu_sf=54.2,
        eui_by_fuel=FuelBreakdown(
            electricity=25.0,
            natural_gas=20.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )
```

Delete the `sample_building` fixture from `test_energy_star.py` — use the existing `office_input` fixture from conftest instead. Update all test function signatures and references from `sample_building` to `office_input` throughout the test file.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_energy_star.py::test_energy_star_endpoint -v`
Expected: FAIL (404, endpoint doesn't exist yet)

- [ ] **Step 4: Add endpoint to routes.py**

Add to `backend/app/api/routes.py`:

```python
from app.schemas.energy_star import EnergyStarRequest, EnergyStarResponse
from app.services.energy_star import EnergyStarService
```

Add the endpoint:

```python
@router.post("/energy-star/score", response_model=EnergyStarResponse)
async def energy_star_score(request: EnergyStarRequest):
    service = EnergyStarService()
    try:
        return service.get_score(
            building=request.building,
            baseline=request.baseline,
            address=request.address,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_energy_star.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full backend test suite to check for regressions**

Run: `cd backend && pytest -v`
Expected: All existing tests still PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes.py backend/tests/test_energy_star.py backend/tests/conftest.py
git commit -m "feat: add POST /energy-star/score endpoint"
```

---

## Task 7: E2E Test (ESPM Test Environment)

**Files:**
- Create: `backend/tests/test_energy_star_e2e.py`

- [ ] **Step 1: Write e2e test**

Create `backend/tests/test_energy_star_e2e.py`:

```python
"""E2E tests that hit the live ESPM test environment.

Run with: pytest --run-e2e tests/test_energy_star_e2e.py -v

Requires ESPM_USERNAME and ESPM_PASSWORD env vars to be set.
"""

import os
import pytest
from app.services.energy_star import EnergyStarService
from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult, FuelBreakdown


@pytest.mark.e2e
def test_target_finder_office():
    """Hit ESPM test env with an Office building and verify we get metrics."""
    service = EnergyStarService()

    building = BuildingInput(
        building_type="Office",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        heating_fuel="NaturalGas",
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=54.2,
        eui_by_fuel=FuelBreakdown(
            electricity=25.0,
            natural_gas=20.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )

    result = service.get_score(building, baseline, address="123 Main St, Washington, DC")

    # We should at least get median EUI back
    assert result.median_eui_kbtu_sf is not None
    assert result.median_eui_kbtu_sf > 0
    assert result.espm_property_type == "Office"
    # Score may or may not be returned depending on ESPM test env state
    if result.eligible:
        assert 1 <= result.score <= 100
        assert result.percentile_text is not None


@pytest.mark.e2e
def test_target_finder_multifamily():
    """Hit ESPM test env with a Multi-Family building."""
    service = EnergyStarService()

    building = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=5,
        zipcode="10001",
        year_built=1985,
    )
    baseline = BaselineResult(
        total_eui_kbtu_sf=40.0,
        eui_by_fuel=FuelBreakdown(
            electricity=20.0,
            natural_gas=15.0,
            fuel_oil=5.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )

    result = service.get_score(building, baseline)
    assert result.median_eui_kbtu_sf is not None
    assert result.espm_property_type == "Multifamily Housing"
```

- [ ] **Step 2: Verify test is skipped without --run-e2e**

Run: `cd backend && pytest tests/test_energy_star_e2e.py -v`
Expected: 2 tests SKIPPED

- [ ] **Step 3: Run with e2e flag (requires ESPM credentials in env)**

Run: `cd backend && ESPM_USERNAME=<username> ESPM_PASSWORD=<password> pytest --run-e2e tests/test_energy_star_e2e.py -v`
Expected: Tests PASS (verify ESPM test env returns data)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_energy_star_e2e.py
git commit -m "test: add e2e tests for ESPM Target Finder integration"
```

---

## Task 8: Frontend Types & Composable

**Files:**
- Modify: `frontend/src/types/assessment.ts`
- Create: `frontend/src/composables/useEnergyStarScore.ts`

- [ ] **Step 1: Add EnergyStarResponse interface**

Add to `frontend/src/types/assessment.ts`:

```typescript
export interface EnergyStarResponse {
  score: number | null
  eligible: boolean
  median_eui_kbtu_sf: number | null
  target_eui_kbtu_sf: number | null
  design_eui_kbtu_sf: number | null
  percentile_text: string | null
  espm_property_type: string
  reasons_for_no_score: string[] | null
}
```

- [ ] **Step 2: Create the composable**

Create `frontend/src/composables/useEnergyStarScore.ts`:

```typescript
import { ref } from 'vue'
import type { BuildingInput, BaselineResult, EnergyStarResponse } from '../types/assessment'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useEnergyStarScore() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const result = ref<EnergyStarResponse | null>(null)

  async function fetchScore(
    building: BuildingInput,
    baseline: BaselineResult,
    address?: string | null,
  ) {
    loading.value = true
    error.value = null
    result.value = null
    try {
      const response = await fetch(`${API_BASE}/energy-star/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ building, baseline, address: address ?? null }),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      result.value = await response.json()
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  function reset() {
    result.value = null
    error.value = null
  }

  return { loading, error, result, fetchScore, reset }
}
```

- [ ] **Step 3: Type check**

Run: `cd frontend && npm run type-check`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/assessment.ts frontend/src/composables/useEnergyStarScore.ts
git commit -m "feat: add EnergyStarResponse type and useEnergyStarScore composable"
```

---

## Task 9: EnergyStarScore Component

**Files:**
- Create: `frontend/src/components/EnergyStarScore.vue`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/EnergyStarScore.vue`. The component has these states:

1. **Ready**: "Calculate ENERGY STAR Score" button
2. **Loading**: Spinner
3. **Result with score**: Circular gauge + metrics card
4. **Result without score**: "Not available" + median EUI
5. **Error**: Error message with retry

```vue
<script setup lang="ts">
import { PTypography, PButton, PIcon } from '@partnerdevops/partner-components'
import { useEnergyStarScore } from '../composables/useEnergyStarScore'
import type { BuildingInput, BaselineResult } from '../types/assessment'

const props = defineProps<{
  building: BuildingInput
  baseline: BaselineResult
  address?: string | null
}>()

const { loading, error, result, fetchScore } = useEnergyStarScore()

function handleClick() {
  fetchScore(props.building, props.baseline, props.address)
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}
</script>

<template>
  <div class="es-section">
    <!-- Ready state: button -->
    <button
      v-if="!result && !loading && !error"
      class="es-trigger"
      @click="handleClick"
    >
      <span class="es-trigger__icon">⭐</span>
      <span class="es-trigger__text">
        <span class="es-trigger__title">Calculate ENERGY STAR Score</span>
        <span class="es-trigger__subtitle">Compare against similar buildings nationwide</span>
      </span>
      <PIcon name="chevron-right" class="es-trigger__arrow" />
    </button>

    <!-- Loading state -->
    <div v-if="loading" class="es-card es-card--loading">
      <div class="es-loading-spinner" aria-label="Calculating score">
        <svg viewBox="0 0 50 50">
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="#e2e8f0" />
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--app-accent)"
                  stroke-linecap="round" stroke-dasharray="80, 200" />
        </svg>
      </div>
      <PTypography variant="body2" class="es-loading-text">
        Calculating ENERGY STAR score...
      </PTypography>
    </div>

    <!-- Error state -->
    <div v-if="error" class="es-card es-card--error">
      <PTypography variant="body2" class="es-error-text">{{ error }}</PTypography>
      <PButton size="sm" variant="outline" @click="handleClick">Retry</PButton>
    </div>

    <!-- Result state -->
    <div v-if="result" class="es-card">
      <div class="es-result">
        <!-- Score gauge -->
        <div class="es-gauge">
          <svg viewBox="0 0 120 120" class="es-gauge__svg">
            <!-- Background circle -->
            <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="8" />
            <!-- Score arc -->
            <circle
              v-if="result.eligible && result.score != null"
              cx="60" cy="60" r="50" fill="none"
              :stroke="result.score >= 75 ? '#22c55e' : result.score >= 50 ? '#eab308' : '#ef4444'"
              stroke-width="8" stroke-linecap="round"
              :stroke-dasharray="`${(result.score / 100) * 314} 314`"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="es-gauge__value">
            <template v-if="result.eligible && result.score != null">
              <span class="es-gauge__number" :style="{
                color: result.score >= 75 ? '#22c55e' : result.score >= 50 ? '#eab308' : '#ef4444'
              }">{{ result.score }}</span>
              <span class="es-gauge__label">out of 100</span>
            </template>
            <template v-else>
              <span class="es-gauge__na">N/A</span>
              <span class="es-gauge__label">not eligible</span>
            </template>
          </div>
          <div class="es-gauge__caption">ENERGY STAR&reg; Score</div>
        </div>

        <!-- Metrics -->
        <div class="es-metrics">
          <div v-if="result.eligible && result.percentile_text" class="es-metrics__headline">
            {{ result.percentile_text }}
          </div>
          <div v-else class="es-metrics__headline es-metrics__headline--muted">
            Score not available for this building type
          </div>

          <div v-if="result.reasons_for_no_score" class="es-metrics__reasons">
            <PTypography v-for="reason in result.reasons_for_no_score" :key="reason" variant="body2">
              {{ reason }}
            </PTypography>
          </div>

          <div class="es-metrics__cards">
            <div v-if="result.target_eui_kbtu_sf != null" class="es-metric-chip">
              <span class="es-metric-chip__label">Target EUI (75)</span>
              <span class="es-metric-chip__value">{{ formatNumber(result.target_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
            <div v-if="result.median_eui_kbtu_sf != null" class="es-metric-chip">
              <span class="es-metric-chip__label">Median EUI</span>
              <span class="es-metric-chip__value">{{ formatNumber(result.median_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
            <div v-if="result.design_eui_kbtu_sf != null" class="es-metric-chip">
              <span class="es-metric-chip__label">Your EUI</span>
              <span class="es-metric-chip__value">{{ formatNumber(result.design_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
          </div>

          <PTypography variant="caption" class="es-metrics__type">
            ESPM property type: {{ result.espm_property_type }}
          </PTypography>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* --- Trigger button --- */
.es-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  text-align: left;
}
.es-trigger:hover {
  border-color: var(--app-accent);
  box-shadow: 0 0 0 1px var(--app-accent-muted);
}
.es-trigger__icon { font-size: 1.5rem; }
.es-trigger__text { flex: 1; display: flex; flex-direction: column; }
.es-trigger__title {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--partner-text-primary, #333e47);
}
.es-trigger__subtitle {
  font-size: 0.8125rem;
  color: #64748b;
  margin-top: 0.125rem;
}
.es-trigger__arrow { color: #94a3b8; font-size: 1.25rem; }

/* --- Card --- */
.es-card {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1.5rem;
}
.es-card--loading {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
}
.es-card--error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-left: 3px solid #ef4444;
}

/* --- Loading --- */
.es-loading-spinner {
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
}
.es-loading-spinner svg { animation: es-spin 1.2s linear infinite; }
.es-loading-text { color: #64748b; }
@keyframes es-spin { 100% { transform: rotate(360deg); } }

/* --- Error --- */
.es-error-text { color: #ef4444; }

/* --- Result --- */
.es-result {
  display: flex;
  align-items: center;
  gap: 2rem;
}

/* --- Gauge --- */
.es-gauge {
  flex-shrink: 0;
  text-align: center;
  width: 120px;
}
.es-gauge__svg { width: 100px; height: 100px; display: block; margin: 0 auto; }
.es-gauge__value {
  margin-top: -70px;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60px;
}
.es-gauge__number { font-size: 2rem; font-weight: 700; line-height: 1; }
.es-gauge__label { font-size: 0.6875rem; color: #94a3b8; }
.es-gauge__na { font-size: 1.25rem; font-weight: 600; color: #94a3b8; }
.es-gauge__caption {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-top: 0.5rem;
}

/* --- Metrics --- */
.es-metrics { flex: 1; min-width: 0; }
.es-metrics__headline {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--partner-text-primary, #333e47);
  margin-bottom: 0.75rem;
}
.es-metrics__headline--muted { color: #94a3b8; }
.es-metrics__reasons { margin-bottom: 0.75rem; color: #64748b; }
.es-metrics__cards {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}
.es-metric-chip {
  display: flex;
  flex-direction: column;
  padding: 0.5rem 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
}
.es-metric-chip__label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}
.es-metric-chip__value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--partner-text-primary, #333e47);
}
.es-metrics__type { color: #94a3b8; }

/* --- Responsive --- */
@media (max-width: 640px) {
  .es-result { flex-direction: column; align-items: stretch; }
  .es-gauge { margin: 0 auto; }
  .es-metrics__cards { flex-direction: column; }
}
</style>
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npm run type-check`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EnergyStarScore.vue
git commit -m "feat: add EnergyStarScore component with gauge, metrics, and state management"
```

---

## Task 10: Wire Component into AssessmentView

**Files:**
- Modify: `frontend/src/views/AssessmentView.vue`

- [ ] **Step 1: Add import and mount the component**

In `frontend/src/views/AssessmentView.vue`:

Add to the `<script setup>` imports:

```typescript
import EnergyStarScore from '../components/EnergyStarScore.vue'
```

The `onSubmit` function already captures input. We need to track the last submitted building input so we can pass it to the EnergyStarScore component. Add a ref:

```typescript
const lastBuilding = ref<BuildingInput | null>(null)
```

Update `onSubmit`:

```typescript
function onSubmit(input: BuildingInput) {
  lastSqft.value = input.sqft
  lastBuilding.value = input
  assess(input)
}
```

In the template, add the EnergyStarScore component between BaselineSummary and the section separator:

```html
<BaselineSummary :baseline="result.baseline" :sqft="lastSqft" />

<!-- ENERGY STAR Score section -->
<EnergyStarScore
  v-if="lastBuilding"
  :building="lastBuilding"
  :baseline="result.baseline"
/>

<!-- Separator between baseline and measures -->
<div class="section-separator" aria-hidden="true" />
```

Note: The `address` prop is optional and not wired yet. It will be connected when the address lookup flow is integrated with the assessment form in a future task. For now, the component works without it (the service fabricates a minimal address from zipcode).

- [ ] **Step 2: Type check**

Run: `cd frontend && npm run type-check`
Expected: No type errors

- [ ] **Step 3: Verify dev server loads**

Run: `cd frontend && npm run dev`
Expected: No build errors, page loads, EnergyStarScore button appears between baseline and measures after running an assessment

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/AssessmentView.vue
git commit -m "feat: wire EnergyStarScore component into AssessmentView"
```

---

## Task 11: Manual Integration Test

This is a manual verification step — no code changes.

- [ ] **Step 1: Set ESPM credentials**

Add to your `.env` or export in terminal:
```bash
export ESPM_USERNAME=<your_username>
export ESPM_PASSWORD=<your_password>
```

- [ ] **Step 2: Start backend**

Run: `cd backend && uvicorn app.main:app --reload`

- [ ] **Step 3: Start frontend**

Run: `cd frontend && npm run dev`

- [ ] **Step 4: Test the full flow**

1. Enter an Office building (50k sqft, 3 stories, DC 20001, 1985)
2. Run assessment
3. Click "Calculate ENERGY STAR Score" button
4. Verify score card appears with gauge, percentile text, target/median/your EUI
5. Try a building type that may not be eligible (e.g., Service) and verify the "not available" state with median EUI

- [ ] **Step 5: Verify error handling**

1. Stop the backend
2. Click the score button
3. Verify error message appears with retry button
