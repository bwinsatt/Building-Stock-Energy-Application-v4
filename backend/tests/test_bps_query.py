"""Tests for BPS benchmarking query service."""
from app.services.bps_config import BPS_CONFIGS, ZIPCODE_CITY_OVERRIDES, FIELD_MAPPINGS


def test_bps_configs_has_three_tiers():
    assert "city" in BPS_CONFIGS
    assert "county" in BPS_CONFIGS
    assert "state" in BPS_CONFIGS


def test_nyc_config_exists():
    nyc = BPS_CONFIGS["city"]["new york, new york"]
    assert nyc["ordinance_name"] == "NYC LL84"
    assert nyc["api_type"] == "socrata"
    assert nyc["address_field"] == "address_1"
    assert "2023" in nyc["endpoints"]


def test_all_16_ordinances_present():
    total = (
        len(BPS_CONFIGS["city"])
        + len(BPS_CONFIGS["county"])
        + len(BPS_CONFIGS["state"])
    )
    assert total == 18


def test_zipcode_overrides_nyc():
    assert ZIPCODE_CITY_OVERRIDES.get("11201") == "new york"


def test_zipcode_overrides_boston():
    assert ZIPCODE_CITY_OVERRIDES.get("02125") == "boston"


def test_field_mappings_has_nyc():
    assert "NYC LL84" in FIELD_MAPPINGS
    nyc_map = FIELD_MAPPINGS["NYC LL84"]
    assert "site_eui_kbtu_ft" in nyc_map


from app.services.bps_query import (
    _extract_building_number,
    _normalize_address,
    _match_address,
)


def test_extract_building_number_simple():
    assert _extract_building_number("123 Main Street") == "123"


def test_extract_building_number_hyphenated():
    assert _extract_building_number("45-18 Court Square") == "45-18"


def test_extract_building_number_none():
    assert _extract_building_number("Main Street") is None


def test_normalize_address_abbreviations():
    result = _normalize_address("123 Main St NW")
    assert "street" in result
    assert "northwest" in result


def test_normalize_address_lowercase():
    result = _normalize_address("123 BROADWAY")
    assert result == "123 broadway"


def test_match_address_direct():
    records = [
        {"address": "123 Main Street", "eui": 50},
        {"address": "123 Oak Avenue", "eui": 60},
    ]
    result = _match_address(records, "123 Main Street", "address")
    assert result is not None
    assert result["record"]["eui"] == 50


def test_match_address_fuzzy():
    records = [
        {"address": "123 MAIN ST", "eui": 50},
        {"address": "456 Oak Ave", "eui": 60},
    ]
    result = _match_address(records, "123 Main Street", "address")
    assert result is not None
    assert result["record"]["eui"] == 50
    assert result["confidence"] >= 0.88


def test_match_address_no_match():
    records = [
        {"address": "999 Completely Different Road", "eui": 50},
    ]
    result = _match_address(records, "123 Main Street", "address")
    assert result is None


from app.services.bps_query import check_bps_availability


def test_check_availability_nyc():
    result = check_bps_availability("new york", "new york", None)
    assert result is not None
    assert result["ordinance_name"] == "NYC LL84"


def test_check_availability_county():
    result = check_bps_availability("silver spring", "maryland", "montgomery county")
    assert result is not None
    assert result["ordinance_name"] == "Montgomery County Benchmarking"


def test_check_availability_state():
    result = check_bps_availability("sacramento", "california", None)
    assert result is not None
    assert result["ordinance_name"] == "CA AB802"


def test_check_availability_city_over_state():
    result = check_bps_availability("los angeles", "california", None)
    assert result is not None
    assert result["ordinance_name"] == "LA EBEWE"


def test_check_availability_not_found():
    result = check_bps_availability("dallas", "texas", None)
    assert result is None


def test_check_availability_zipcode_override_brooklyn():
    result = check_bps_availability("brooklyn", "new york", None, zipcode="11201")
    assert result is not None
    assert result["ordinance_name"] == "NYC LL84"
