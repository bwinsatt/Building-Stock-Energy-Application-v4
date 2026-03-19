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


# ---------------------------------------------------------------------------
# Task 5: Async API handler tests
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.bps_query import _query_socrata, _query_arcgis, _query_ckan


@pytest.mark.asyncio
async def test_query_socrata_returns_records():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"address_1": "350 5TH AVENUE", "site_eui_kbtu_ft": "72.4"},
        {"address_1": "123 OTHER ST", "site_eui_kbtu_ft": "50.0"},
    ]
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    config = {
        "endpoints": {"2023": {"Benchmarking": "https://example.com/resource/abc.json"}},
        "address_field": "address_1",
        "api_type": "socrata",
    }
    records = await _query_socrata("350 Fifth Avenue", config, client=mock_client)
    assert len(records) == 2
    assert records[0]["address_1"] == "350 5TH AVENUE"


@pytest.mark.asyncio
async def test_query_arcgis_returns_records():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "features": [
            {"attributes": {"Street": "350 5TH AVE", "site_eui": "72.4"}},
        ]
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    config = {
        "endpoints": {"2023": {"Benchmarking": "https://example.com/query"}},
        "address_field": "Street",
        "api_type": "arcgis",
    }
    records = await _query_arcgis("350 Fifth Avenue", config, client=mock_client)
    assert len(records) == 1
    assert records[0]["Street"] == "350 5TH AVE"


@pytest.mark.asyncio
async def test_query_ckan_returns_records():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {"records": [{"Building Address": "100 MAIN ST", "eui": 50}]}
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    config = {
        "endpoints": {"2024": {"Benchmarking": "resource-id-abc"}},
        "base_url": "https://data.boston.gov/api/3/action/datastore_search",
        "address_field": "Building Address",
        "api_type": "ckan",
    }
    records = await _query_ckan("100 Main Street", config, client=mock_client)
    assert len(records) == 1


# ---------------------------------------------------------------------------
# Task 6: CSV handler tests
# ---------------------------------------------------------------------------

from app.services.bps_query import _query_csv


def test_query_csv_returns_records(tmp_path):
    csv_content = "Address,Site EUI\n123 Main Street,72.4\n456 Oak Ave,50.0\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    config = {
        "endpoints": {"2023": {"Benchmarking": str(csv_file)}},
        "address_field": "Address",
        "api_type": "csv",
    }
    records = _query_csv("123 Main Street", config)
    assert len(records) >= 1
    assert records[0]["Address"] == "123 Main Street"


def test_query_csv_no_match(tmp_path):
    csv_content = "Address,Site EUI\n999 Other Road,72.4\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    config = {
        "endpoints": {"2023": {"Benchmarking": str(csv_file)}},
        "address_field": "Address",
        "api_type": "csv",
    }
    records = _query_csv("123 Main Street", config)
    assert records == []


# ---------------------------------------------------------------------------
# Task 7: Transform + orchestrator tests
# ---------------------------------------------------------------------------

from app.services.bps_query import _transform_result, query_bps


def test_transform_result_with_per_fuel_data():
    record = {
        "address_1": "350 5TH AVE",
        "property_name": "Empire State Building",
        "site_eui_kbtu_ft": "72.4",
        "electricity_use_grid_purchase_1": "485200",
        "natural_gas_use_kbtu": "834000",
        "energy_star_score": "81",
    }
    field_mapping = {
        "site_eui_kbtu_ft": "site_eui_kbtu_sf",
        "electricity_use_grid_purchase_1": "electricity_kbtu",
        "natural_gas_use_kbtu": "natural_gas_kbtu",
        "energy_star_score": "energy_star_score",
        "property_name": "property_name",
        "address_1": "matched_address",
    }
    result = _transform_result(record, field_mapping)
    assert result["matched_address"] == "350 5TH AVE"
    assert result["site_eui_kbtu_sf"] == 72.4
    assert result["has_per_fuel_data"] is True
    # Verify kBtu -> kWh conversion
    assert result["electricity_kwh"] is not None
    assert abs(result["electricity_kwh"] - 485200 / 3.412) < 1
    # Verify kBtu -> therms conversion
    assert result["natural_gas_therms"] is not None
    assert abs(result["natural_gas_therms"] - 834000 / 100.0) < 1


def test_transform_result_without_per_fuel_data():
    record = {
        "address": "123 MAIN ST",
        "site_eui": "60.0",
    }
    field_mapping = {
        "site_eui": "site_eui_kbtu_sf",
        "address": "matched_address",
    }
    result = _transform_result(record, field_mapping)
    assert result["site_eui_kbtu_sf"] == 60.0
    assert result["has_per_fuel_data"] is False
    assert result["electricity_kwh"] is None


def test_transform_result_with_direct_kwh_therms():
    """Test that electricity_kwh and natural_gas_therms pass through without conversion."""
    record = {
        "address": "100 MAIN ST",
        "siteeui_kbtu_sf": "50.0",
        "electricity_kwh": "150000",
        "naturalgas_therms": "5000",
    }
    field_mapping = {
        "siteeui_kbtu_sf": "site_eui_kbtu_sf",
        "electricity_kwh": "electricity_kwh",
        "naturalgas_therms": "natural_gas_therms",
        "address": "matched_address",
    }
    result = _transform_result(record, field_mapping)
    assert result["electricity_kwh"] == 150000.0
    assert result["natural_gas_therms"] == 5000.0
    assert result["has_per_fuel_data"] is True


@pytest.mark.asyncio
async def test_query_bps_with_mock():
    mock_records = [{"address_1": "350 FIFTH AVENUE", "site_eui_kbtu_ft": "72.4"}]

    with patch("app.services.bps_query._query_socrata", new_callable=AsyncMock) as mock_socrata:
        mock_socrata.return_value = mock_records

        result = await query_bps(
            address="350 Fifth Avenue",
            city="new york",
            state="new york",
            county=None,
            zipcode="10118",
        )
        mock_socrata.assert_called_once()
        assert result is not None
        assert result["ordinance_name"] == "NYC LL84"
        assert result["match_confidence"] is not None
