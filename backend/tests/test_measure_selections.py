"""Tests for measure selection API endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """TestClient with a fresh temporary database."""
    import os
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")

    from app.main import app
    from app.services.database import Database

    db = Database(str(tmp_path / "test.db"))
    db.init()
    app.state.database = db

    with TestClient(app) as c:
        # Create a project and building for testing
        project = db.create_project("Test")
        db.create_building(
            project["id"], "123 Main St",
            {"building_type": "Office", "sqft": 50000, "num_stories": 3,
             "zipcode": "20001", "year_built": 1985},
        )
        yield c


def test_get_selections_empty(client):
    resp = client.get("/projects/1/buildings/1/selections")
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_upgrade_ids"] == []
    assert data["projected_espm"] is None


def test_put_selections(client):
    resp = client.put(
        "/projects/1/buildings/1/selections",
        json={"selected_upgrade_ids": [3, 5, 8]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_upgrade_ids"] == [3, 5, 8]


def test_put_then_get_selections(client):
    client.put(
        "/projects/1/buildings/1/selections",
        json={"selected_upgrade_ids": [3, 5]},
    )
    resp = client.get("/projects/1/buildings/1/selections")
    assert resp.status_code == 200
    assert resp.json()["selected_upgrade_ids"] == [3, 5]


def test_put_selections_upsert(client):
    client.put("/projects/1/buildings/1/selections", json={"selected_upgrade_ids": [3]})
    client.put("/projects/1/buildings/1/selections", json={"selected_upgrade_ids": [3, 5, 8]})
    resp = client.get("/projects/1/buildings/1/selections")
    assert resp.json()["selected_upgrade_ids"] == [3, 5, 8]
