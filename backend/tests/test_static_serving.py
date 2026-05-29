"""Tests for SPA static file serving (Task 2: FastAPI serves the Vue SPA)."""

import os
import sys
import importlib
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

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

    def predict_delta(self, *a, **kw):
        return {}

    def predict_enduse(self, *a, **kw):
        return {}


def _mock_lifespan(app_instance):
    @asynccontextmanager
    async def lifespan(app_inst):
        app_inst.state.model_manager = MockModelManager()
        app_inst.state.cost_calculator = CostCalculatorService()
        yield
    return lifespan(app_instance)


@pytest.fixture
def static_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        assets_dir = os.path.join(tmpdir, "assets")
        os.makedirs(assets_dir)
        with open(os.path.join(tmpdir, "index.html"), "w") as f:
            f.write("<html><body>SPA</body></html>")
        with open(os.path.join(assets_dir, "index-abc123.js"), "w") as f:
            f.write("console.log('app')")
        with open(os.path.join(assets_dir, "style-def456.css"), "w") as f:
            f.write("body{}")
        yield tmpdir


@pytest.fixture
def client_with_static(static_dir):
    import app.main as main_module
    with patch.dict(os.environ, {"STATIC_DIR": static_dir}):
        importlib.reload(main_module)
        fastapi_app = main_module.app
        fastapi_app.router.lifespan_context = _mock_lifespan
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c
    importlib.reload(main_module)


@pytest.fixture
def client_without_static():
    import app.main as main_module
    env = {k: v for k, v in os.environ.items() if k != "STATIC_DIR"}
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(main_module)
        fastapi_app = main_module.app
        fastapi_app.router.lifespan_context = _mock_lifespan
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c
    importlib.reload(main_module)


class TestStaticServing:
    def test_index_html_served_at_root(self, client_with_static):
        resp = client_with_static.get("/")
        assert resp.status_code == 200
        assert "SPA" in resp.text

    def test_spa_catch_all_returns_index(self, client_with_static):
        resp = client_with_static.get("/some/deep/route")
        assert resp.status_code == 200
        assert "SPA" in resp.text

    def test_assets_served(self, client_with_static):
        resp = client_with_static.get("/assets/index-abc123.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text

    def test_css_assets_served(self, client_with_static):
        resp = client_with_static.get("/assets/style-def456.css")
        assert resp.status_code == 200
        assert "body{}" in resp.text

    def test_api_routes_still_work(self, client_with_static):
        resp = client_with_static.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_defined_api_route_not_masked(self, client_with_static):
        resp = client_with_static.get("/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert "building_types" in data

    def test_projects_route_not_masked_by_spa(self, client_with_static):
        resp = client_with_static.get("/projects/99999")
        assert resp.status_code != 200 or "SPA" not in resp.text
        assert "html" not in resp.headers.get("content-type", "").lower() or "SPA" not in resp.text


class TestWithoutStatic:
    def test_no_spa_serving_without_static_dir(self, client_without_static):
        resp = client_without_static.get("/")
        assert resp.status_code == 404

    def test_api_still_works_without_static(self, client_without_static):
        resp = client_without_static.get("/health")
        assert resp.status_code == 200
