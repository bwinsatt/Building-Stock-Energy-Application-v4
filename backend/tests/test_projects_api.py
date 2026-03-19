"""Tests for project CRUD API endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

    from app.main import app
    from app.services.database import Database

    db = Database()
    db.init()
    app.state.database = db

    with TestClient(app) as c:
        yield c


def test_create_project(client):
    resp = client.post("/projects", json={"name": "Test Project"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Project"
    assert "id" in data


def test_list_projects(client):
    client.post("/projects", json={"name": "Project A"})
    client.post("/projects", json={"name": "Project B"})
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_project(client):
    client.post("/projects", json={"name": "Test Project"})
    resp = client.get("/projects/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"
    assert "buildings" in resp.json()


def test_get_project_not_found(client):
    resp = client.get("/projects/999")
    assert resp.status_code == 404


def test_delete_project(client):
    client.post("/projects", json={"name": "Test Project"})
    resp = client.delete("/projects/1")
    assert resp.status_code == 200
    assert client.get("/projects/1").status_code == 404


def test_create_building(client):
    client.post("/projects", json={"name": "Test Project"})
    resp = client.post("/projects/1/buildings", json={
        "address": "123 Main St",
        "building_input": {"building_type": "OfficeSmall", "sqft": 50000},
    })
    assert resp.status_code == 200
    assert resp.json()["address"] == "123 Main St"


def test_save_assessment(client):
    client.post("/projects", json={"name": "Test Project"})
    client.post("/projects/1/buildings", json={
        "address": "123 Main St",
        "building_input": {"building_type": "OfficeSmall"},
    })
    resp = client.post("/projects/1/buildings/1/assessments", json={
        "result": {"baseline": {"total_eui_kbtu_sf": 51.0}},
        "calibrated": False,
    })
    assert resp.status_code == 200
    assert resp.json()["calibrated"] is False
