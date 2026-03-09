"""Tests for Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.request import BuildingInput
from app.schemas.response import (
    AssessmentResponse,
    BaselineResult,
    BuildingResult,
    CostEstimate,
    FuelBreakdown,
    InputSummary,
    MeasureResult,
)


# ---------------------------------------------------------------------------
# BuildingInput validation
# ---------------------------------------------------------------------------


def test_building_input_valid(office_input):
    """Valid input should create a model successfully."""
    assert office_input.building_type == "Office"
    assert office_input.sqft == 50000


def test_building_input_missing_required():
    """Missing building_type should raise ValidationError."""
    with pytest.raises(ValidationError):
        BuildingInput(sqft=1000, num_stories=2, zipcode="20001")


def test_building_input_sqft_zero():
    """sqft=0 should raise ValidationError (gt=0 constraint)."""
    with pytest.raises(ValidationError):
        BuildingInput(
            building_type="Office", sqft=0, num_stories=1, zipcode="20001",
            year_built=1990,
        )


def test_building_input_bad_zipcode_short():
    """Zipcode too short should raise ValidationError."""
    with pytest.raises(ValidationError):
        BuildingInput(
            building_type="Office", sqft=1000, num_stories=1, zipcode="1234",
            year_built=1990,
        )


def test_building_input_bad_zipcode_long():
    """Zipcode too long should raise ValidationError."""
    with pytest.raises(ValidationError):
        BuildingInput(
            building_type="Office", sqft=1000, num_stories=1, zipcode="123456",
            year_built=1990,
        )


# ---------------------------------------------------------------------------
# AssessmentResponse round-trip
# ---------------------------------------------------------------------------


def test_assessment_response_roundtrip():
    """Create AssessmentResponse from nested dicts and verify serialization."""
    data = {
        "results": [
            {
                "building_index": 0,
                "baseline": {
                    "total_eui_kbtu_sf": 85.0,
                    "eui_by_fuel": {
                        "electricity": 40.0,
                        "natural_gas": 35.0,
                        "fuel_oil": 5.0,
                        "propane": 5.0,
                        "district_heating": 0.0,
                    },
                    "emissions_kg_co2e_per_sf": 12.5,
                },
                "measures": [
                    {
                        "upgrade_id": 1,
                        "name": "HP-RTU",
                        "category": "hvac",
                        "applicable": True,
                        "post_upgrade_eui_kbtu_sf": 70.0,
                        "savings_kbtu_sf": 15.0,
                        "savings_pct": 0.176,
                    }
                ],
                "input_summary": {
                    "climate_zone": "4A",
                    "cluster_name": "Metro DC",
                    "state": "DC",
                    "vintage_bucket": "1980 to 1989",
                    "imputed_fields": ["heating_fuel"],
                    "imputed_details": {
                        "heating_fuel": {
                            "value": "NaturalGas",
                            "label": "Heating Fuel",
                            "source": "default",
                            "confidence": None,
                        }
                    },
                },
            }
        ]
    }
    response = AssessmentResponse(**data)
    assert len(response.results) == 1
    assert response.results[0].baseline.total_eui_kbtu_sf == 85.0
    assert response.results[0].measures[0].upgrade_id == 1

    # Round-trip through dict
    dumped = response.model_dump()
    restored = AssessmentResponse(**dumped)
    assert restored.results[0].input_summary.state == "DC"
