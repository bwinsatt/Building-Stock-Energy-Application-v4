"""Test the carbon performance export endpoint (service mocked + full e2e)."""

import io

import openpyxl
from fastapi.testclient import TestClient

from app.main import app
from app.api import routes
from tests.test_export_service import assert_valid_xlsx


def test_export_endpoint_returns_xlsx(monkeypatch):
    monkeypatch.setattr(
        routes, "build_carbon_performance_workbook", lambda *a, **k: b"PK\x03\x04fake"
    )
    with TestClient(app) as client:
        payload = {
            "building": {
                "building_type": "Office", "sqft": 1000, "num_stories": 3,
                "zipcode": "00501", "year_built": 1985,
            },
            "selected_upgrade_ids": [7],
            "espm_property_type": "Office",
        }
        resp = client.post("/export/carbon-performance", json=payload)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "CarbonPerformance_00501.xlsx" in resp.headers["content-disposition"]
    assert resp.content == b"PK\x03\x04fake"


def test_export_endpoint_end_to_end(office_input):
    """Full stack: real assessment + rates + openpyxl through the endpoint."""
    with TestClient(app) as client:
        payload = {
            "building": office_input.model_dump(),
            "selected_upgrade_ids": [],          # exercise the applicable fallback
            "espm_property_type": "Office",
        }
        resp = client.post("/export/carbon-performance", json=payload)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Full package integrity: no external links, no dangling relationships
    # (this is the corruption Excel flagged but openpyxl tolerates).
    assert_valid_xlsx(resp.content)

    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb["Export BlueLynx"]

    # Reference-table named ranges survived the round-trip
    assert "ESPM_Prop_Types" in wb.defined_names

    # At least one measure written and baseline metrics populated
    assert ws["C6"].value is not None and str(ws["C6"].value).strip() != ""
    assert ws["AJ8"].value == office_input.zipcode
    assert ws["AJ9"].value == "Office"
    assert ws["AJ24"].value == office_input.sqft
    assert ws["AJ16"].value is not None       # baseline electric kWh
    assert ws["AJ32"].value == "NREL Cambium, 2022"
