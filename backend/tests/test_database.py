"""Tests for SQLite database CRUD operations."""
import json
import pytest
from app.services.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    database.init()
    return database


def test_create_project(db):
    project = db.create_project("Test Project")
    assert project["id"] == 1
    assert project["name"] == "Test Project"
    assert "created_at" in project


def test_list_projects(db):
    db.create_project("Project A")
    db.create_project("Project B")
    projects = db.list_projects()
    assert len(projects) == 2
    assert projects[0]["name"] == "Project A"


def test_get_project(db):
    db.create_project("Test Project")
    project = db.get_project(1)
    assert project["name"] == "Test Project"
    assert "buildings" in project


def test_get_project_not_found(db):
    result = db.get_project(999)
    assert result is None


def test_delete_project(db):
    db.create_project("Test Project")
    db.delete_project(1)
    assert db.get_project(1) is None


def test_create_building(db):
    db.create_project("Test Project")
    building_input = {"building_type": "OfficeSmall", "sqft": 50000}
    building = db.create_building(
        project_id=1,
        address="123 Main St",
        building_input=building_input,
    )
    assert building["id"] == 1
    assert building["address"] == "123 Main St"
    assert building["building_input"] == building_input


def test_create_building_with_utility_data(db):
    db.create_project("Test Project")
    utility_data = {"annual_electricity_kwh": 500000}
    building = db.create_building(
        project_id=1,
        address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
        utility_data=utility_data,
    )
    assert building["utility_data"] == utility_data


def test_save_assessment(db):
    db.create_project("Test Project")
    db.create_building(
        project_id=1, address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
    )
    result_data = {"baseline": {"total_eui_kbtu_sf": 51.0}}
    assessment = db.save_assessment(
        building_id=1, result=result_data, calibrated=False,
    )
    assert assessment["id"] == 1
    assert assessment["calibrated"] is False
    assert assessment["result"] == result_data


def test_get_building_assessments(db):
    db.create_project("Test Project")
    db.create_building(
        project_id=1, address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
    )
    db.save_assessment(building_id=1, result={"v": 1}, calibrated=False)
    db.save_assessment(building_id=1, result={"v": 2}, calibrated=True)
    assessments = db.get_assessments(building_id=1)
    assert len(assessments) == 2


def test_cascade_delete(db):
    db.create_project("Test Project")
    db.create_building(
        project_id=1, address="123 Main St",
        building_input={"building_type": "OfficeSmall"},
    )
    db.save_assessment(building_id=1, result={"v": 1}, calibrated=False)
    db.delete_project(1)
    assert db.get_assessments(building_id=1) == []
