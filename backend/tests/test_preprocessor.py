"""Tests for the preprocessor service."""

import pytest

from app.schemas.request import BuildingInput
from app.services.preprocessor import (
    PreprocessingError,
    preprocess,
    year_to_vintage,
    COMSTOCK_FIELD_MAP,
    COMSTOCK_AUTO_IMPUTE,
    RESSTOCK_FIELD_MAP,
    RESSTOCK_AUTO_IMPUTE,
    _ENERGY_CODE_FIELDS,
)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_valid_office_input(office_input):
    """Preprocess a valid office building; verify ComStock features."""
    features, imputed_details, dataset, climate_zone, state = preprocess(office_input)

    assert dataset == "comstock"
    # Should have all ComStock field-map columns + auto-imputed columns + energy codes
    expected_cols = set(COMSTOCK_FIELD_MAP.values()) | set(COMSTOCK_AUTO_IMPUTE.keys()) | set(_ENERGY_CODE_FIELDS)
    assert set(features.keys()) == expected_cols
    assert climate_zone  # non-empty
    assert state  # non-empty


def test_valid_mf_input(mf_input):
    """Preprocess Multi-Family; verify ResStock features."""
    features, imputed_details, dataset, climate_zone, state = preprocess(mf_input)

    assert dataset == "resstock"
    expected_cols = set(RESSTOCK_FIELD_MAP.values()) | set(RESSTOCK_AUTO_IMPUTE.keys())
    # building_type_height is added dynamically based on num_stories
    expected_cols.add("in.geometry_building_type_height")
    assert set(features.keys()) == expected_cols


def test_imputation_fills_missing(minimal_input):
    """Minimal input (only required fields) should trigger imputation."""
    features, imputed_details, dataset, climate_zone, state = preprocess(minimal_input)

    assert len(imputed_details) > 0
    # year_built is now required, so it should NOT be imputed
    assert "year_built" not in imputed_details
    # Other optional fields should still be imputed
    assert "heating_fuel" in imputed_details


def test_no_imputation_when_all_provided():
    """When every optional field is provided, imputed_details should be empty."""
    full_input = BuildingInput(
        building_type="Office",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        heating_fuel="NaturalGas",
        dhw_fuel="NaturalGas",
        hvac_system_type="VAV_chiller_boiler",
        wall_construction="Mass",
        window_type="Double, Low-E, Non-metal",
        window_to_wall_ratio="20-30%",
        lighting_type="LED",
        operating_hours=50.0,
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(full_input)
    # No user-facing fields should be imputed, but derived HVAC sub-features
    # are always included for ComStock
    for key, detail in imputed_details.items():
        assert detail["source"] == "derived", (
            f"Field '{key}' should only be 'derived', got '{detail['source']}'"
        )


def test_preprocess_returns_imputed_details():
    """Preprocessor should return dict of imputed field details, not just names."""
    inp = BuildingInput(
        building_type="Office",
        sqft=10000,
        num_stories=2,
        zipcode="90210",
        year_built=1990,
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(inp)
    # imputed_details is now a dict, not a list
    assert isinstance(imputed_details, dict)
    assert "heating_fuel" in imputed_details
    assert "value" in imputed_details["heating_fuel"]
    assert "label" in imputed_details["heating_fuel"]
    assert "source" in imputed_details["heating_fuel"]


# ---------------------------------------------------------------------------
# ML imputation path (source="model")
# ---------------------------------------------------------------------------


class _MockImputationService:
    """Fake imputation service returning canned predictions."""

    def __init__(self, predictions: dict[str, dict]):
        # predictions: {field: {value, source, confidence}}
        self._predictions = predictions
        # models dict controls which fields the preprocessor considers available
        self.models = {f: True for f in predictions}

    def predict(self, known_fields, fields_to_predict=None):
        result = {}
        for f in (fields_to_predict or self._predictions):
            result[f] = self._predictions.get(
                f, {"value": None, "source": None, "confidence": None}
            )
        return result


def test_ml_imputation_populates_model_source_and_confidence():
    """When an imputation service is provided, imputed_details should use
    source='model' with confidence scores for fields the service covers."""
    inp = BuildingInput(
        building_type="Office",
        sqft=10000,
        num_stories=2,
        zipcode="90210",
        year_built=1990,
        # Leave heating_fuel and lighting_type as None so they get imputed.
        # Provide everything else to isolate what we're testing.
        dhw_fuel="NaturalGas",
        hvac_system_type="PSZ-AC",
        wall_construction="Mass",
        window_type="Double, Low-E, Non-metal",
        window_to_wall_ratio="20-30%",
        operating_hours=50.0,
    )

    mock_service = _MockImputationService({
        "heating_fuel": {
            "value": "Electricity",
            "source": "imputed",
            "confidence": 0.87,
        },
        "lighting_type": {
            "value": "gen4_led",
            "source": "imputed",
            "confidence": 0.93,
        },
    })

    features, imputed_details, dataset, climate_zone, state = preprocess(
        inp, imputation_service=mock_service
    )

    # Both fields should be present with source="model"
    assert "heating_fuel" in imputed_details
    assert "lighting_type" in imputed_details

    # heating_fuel: value passes through as-is (no display map needed)
    hf = imputed_details["heating_fuel"]
    assert hf["source"] == "model"
    assert hf["confidence"] == 0.87
    assert hf["value"] == "Electricity"
    assert hf["label"] == "Heating Fuel"

    # lighting_type: _COMSTOCK_DISPLAY_MAP should reverse "gen4_led" -> "LED"
    lt = imputed_details["lighting_type"]
    assert lt["source"] == "model"
    assert lt["confidence"] == 0.93
    assert lt["value"] == "LED"
    assert lt["label"] == "Lighting Type"

    # The resolved value fed into the feature map should also be the
    # user-facing value so value-mapping in step 6 works correctly.
    # For ComStock lighting, "LED" maps to "gen4_led" in _COMSTOCK_VALUE_MAP.
    assert features[COMSTOCK_FIELD_MAP["lighting_type"]] == "gen4_led"


def test_ml_imputation_falls_back_when_prediction_is_none():
    """If the imputation service returns value=None for a field, the
    preprocessor should fall back to the static default."""
    inp = BuildingInput(
        building_type="Office",
        sqft=10000,
        num_stories=2,
        zipcode="90210",
        year_built=1990,
    )

    mock_service = _MockImputationService({
        "heating_fuel": {
            "value": None,
            "source": None,
            "confidence": None,
        },
    })

    _, imputed_details, _, _, _ = preprocess(
        inp, imputation_service=mock_service
    )

    # heating_fuel should fall back to static default
    hf = imputed_details["heating_fuel"]
    assert hf["source"] == "default"
    assert hf["confidence"] is None
    assert hf["value"] == "NaturalGas"  # Office default


# ---------------------------------------------------------------------------
# Vintage mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "year, expected",
    [
        (1940, "Before 1946"),
        (1985, "1980 to 1989"),
        (2022, "2013 to 2018"),
        (1950, "1946 to 1959"),
        (1965, "1960 to 1969"),
        (2003, "2000 to 2012"),
        (2017, "2013 to 2018"),
    ],
)
def test_vintage_mapping(year, expected):
    assert year_to_vintage(year) == expected


# ---------------------------------------------------------------------------
# Location derivation
# ---------------------------------------------------------------------------


def test_climate_zone_derivation():
    """Zipcode 20001 (DC) should resolve to climate zone 4A."""
    inp = BuildingInput(
        building_type="Office", sqft=1000, num_stories=1, zipcode="20001",
        year_built=1990,
    )
    _, _, _, climate_zone, _ = preprocess(inp)
    assert climate_zone == "4A"


def test_state_derivation():
    """Zipcode 10001 (New York) should resolve to state NY."""
    inp = BuildingInput(
        building_type="Office", sqft=1000, num_stories=1, zipcode="10001",
        year_built=1990,
    )
    _, _, _, _, state = preprocess(inp)
    assert state == "NY"


# ---------------------------------------------------------------------------
# Validation / error tests
# ---------------------------------------------------------------------------


def test_invalid_building_type():
    inp = BuildingInput(
        building_type="SpaceStation", sqft=1000, num_stories=1, zipcode="20001",
        year_built=1990,
    )
    with pytest.raises(PreprocessingError):
        preprocess(inp)


def test_invalid_sqft_zero():
    """sqft=0 should be caught by Pydantic (gt=0), but if bypassed, preprocessor raises."""
    # Pydantic itself rejects sqft=0 via gt=0, so we test at the Pydantic level
    with pytest.raises(Exception):
        BuildingInput(
            building_type="Office", sqft=0, num_stories=1, zipcode="20001"
        )


def test_invalid_zipcode_short():
    """Zipcode '1234' should fail Pydantic min_length=5 validation."""
    with pytest.raises(Exception):
        BuildingInput(
            building_type="Office", sqft=1000, num_stories=1, zipcode="1234"
        )


def test_invalid_zipcode_letters():
    """Zipcode 'abcde' passes length check but fails preprocessor digit check."""
    inp = BuildingInput(
        building_type="Office", sqft=1000, num_stories=1, zipcode="abcde",
        year_built=1990,
    )
    with pytest.raises(PreprocessingError):
        preprocess(inp)


@pytest.mark.parametrize("stories,expected", [
    (1, "1"),
    (3, "3"),
    (14, "14"),
    (15, "15_25"),
    (20, "15_25"),
    (25, "15_25"),
    (26, "over_25"),
    (40, "over_25"),
    (100, "over_25"),
])
def test_comstock_number_stories_encoding(stories, expected):
    """Integer num_stories should map to ComStock categorical bins."""
    from app.services.preprocessor import _comstock_number_stories
    assert _comstock_number_stories(stories) == expected


def test_preprocess_40_story_office_encodes_stories():
    """A 40-story office should encode in.number_stories as 'over_25'."""
    from app.schemas.request import BuildingInput
    from app.services.preprocessor import preprocess

    building = BuildingInput(
        building_type="Office", sqft=350000, num_stories=40,
        zipcode="10019", year_built=1982, heating_fuel="NaturalGas",
    )
    features, _, dataset, _, _ = preprocess(building)
    assert dataset == "comstock"
    assert features["in.number_stories"] == "over_25"


def test_preprocess_3_story_office_encodes_stories():
    """A 3-story office should encode in.number_stories as '3'."""
    from app.schemas.request import BuildingInput
    from app.services.preprocessor import preprocess

    building = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985,
    )
    features, _, dataset, _, _ = preprocess(building)
    assert features["in.number_stories"] == "3"


def test_year_built_required():
    """year_built is now required; omitting it should fail Pydantic validation."""
    with pytest.raises(Exception):
        BuildingInput(
            building_type="Office",
            sqft=10000,
            num_stories=2,
            zipcode="90210",
        )


# ---------------------------------------------------------------------------
# Central system variant mapping
# ---------------------------------------------------------------------------


def test_fan_coil_units_sets_shared_system_heating_and_cooling():
    """Fan Coil Units variant should set shared system to Heating and Cooling."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=10,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="Fan Coil Units",
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(inp)
    assert dataset == "resstock"
    assert features["in.hvac_has_shared_system"] == "Heating and Cooling"
    assert features["in.hvac_heating_type"] == "Ducted Heating"
    assert features["in.hvac_heating_efficiency"] == "Shared Heating"
    assert features["in.hvac_cooling_efficiency"] == "Shared Cooling"


def test_baseboards_radiators_sets_shared_system_heating_only():
    """Baseboards / Radiators variant should set shared system to Heating Only."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=10,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="Baseboards / Radiators",
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(inp)
    assert dataset == "resstock"
    assert features["in.hvac_has_shared_system"] == "Heating Only"
    assert features["in.hvac_heating_type"] == "Non-Ducted Heating"
    assert features["in.hvac_heating_efficiency"] == "Shared Heating"
    # Cooling efficiency should NOT be "Shared Cooling" for heating-only
    assert features["in.hvac_cooling_efficiency"] != "Shared Cooling"


def test_central_system_overrides_user_efficiency_selections():
    """When a central system variant is selected, user efficiency overrides are ignored."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=10,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="Fan Coil Units",
        hvac_heating_efficiency="Fuel Furnace, 80% AFUE",
        hvac_cooling_efficiency="AC, SEER 13",
    )
    features, _, _, _, _ = preprocess(inp)
    # Central system should override user selections
    assert features["in.hvac_heating_efficiency"] == "Shared Heating"
    assert features["in.hvac_cooling_efficiency"] == "Shared Cooling"


# ---------------------------------------------------------------------------
# Renamed category key mapping
# ---------------------------------------------------------------------------


def test_forced_air_furnace_key_maps_correctly_for_resstock():
    """The new 'forced_air_furnace' key should map to Ducted Heating for ResStock."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=5,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="forced_air_furnace",
    )
    features, _, dataset, _, _ = preprocess(inp)
    assert dataset == "resstock"
    assert features["in.hvac_heating_type"] == "Ducted Heating"


def test_forced_air_furnace_key_maps_correctly_for_comstock():
    """The new 'forced_air_furnace' key should work for ComStock too."""
    inp = BuildingInput(
        building_type="Office",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        hvac_system_type="forced_air_furnace",
    )
    features, _, dataset, _, _ = preprocess(inp)
    assert dataset == "comstock"
    # Should resolve to the Residential style HVAC
    assert features["in.hvac_system_type"] == "Residential AC with residential forced air furnace"
