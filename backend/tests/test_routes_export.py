"""Test the carbon performance export endpoint (service mocked)."""

from fastapi.testclient import TestClient

from app.main import app
from app.api import routes


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
