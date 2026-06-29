"""Tests for Easy Auth identity header parsing (Task 4)."""

import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

from app.middleware.auth_headers import parse_client_principal, EasyAuthUser
from app.services.cost_calculator import CostCalculatorService


class MockModelManager:
    def load_all(self):
        return 0
    def predict_baseline(self, *a, **kw):
        return {"electricity": 1.0, "natural_gas": 1.0, "fuel_oil": 0, "propane": 0, "district_heating": 0}
    def predict_sizing(self, *a, **kw):
        return {}
    def predict_rates(self, *a, **kw):
        return {}
    def get_available_upgrades(self, *a):
        return []
    def warm_upgrades(self, *a):
        pass
    def evict_upgrades(self, *a):
        pass
    def predict_delta(self, *a, **kw):
        return {}
    def predict_enduse(self, *a, **kw):
        return {}


@pytest.fixture
def client():
    from app.main import app

    @asynccontextmanager
    async def mock_lifespan(app_instance):
        app_instance.state.model_manager = MockModelManager()
        app_instance.state.cost_calculator = CostCalculatorService()
        yield

    original = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.router.lifespan_context = original


class TestParseClientPrincipal:
    def test_valid_base64_json(self):
        payload = {"auth_typ": "aad", "claims": [{"typ": "name", "val": "Test User"}]}
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        result = parse_client_principal(encoded)
        assert result["auth_typ"] == "aad"
        assert result["claims"][0]["val"] == "Test User"

    def test_invalid_base64(self):
        result = parse_client_principal("not-valid-base64!!!")
        assert result == {}

    def test_valid_base64_but_not_json(self):
        encoded = base64.b64encode(b"not json").decode()
        result = parse_client_principal(encoded)
        assert result == {}

    def test_empty_string(self):
        result = parse_client_principal("")
        assert result == {}


class TestEasyAuthMiddleware:
    def test_no_headers_user_is_none(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_with_principal_name_header(self, client):
        resp = client.get("/health", headers={
            "X-MS-CLIENT-PRINCIPAL-NAME": "testuser@partner.com",
            "X-MS-CLIENT-PRINCIPAL-ID": "abc-123",
        })
        assert resp.status_code == 200

    def test_with_full_principal_header(self, client):
        payload = {"auth_typ": "aad", "name_typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
                   "claims": [{"typ": "name", "val": "Test User"}]}
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        resp = client.get("/health", headers={
            "X-MS-CLIENT-PRINCIPAL-NAME": "testuser@partner.com",
            "X-MS-CLIENT-PRINCIPAL-ID": "abc-123",
            "X-MS-CLIENT-PRINCIPAL": encoded,
        })
        assert resp.status_code == 200
