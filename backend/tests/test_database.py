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


def test_save_selections(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5, 8])
    result = db.get_selections(building_id=1)
    assert result is not None
    assert result["selected_upgrade_ids"] == [3, 5, 8]
    assert result["projected_espm"] is None
    assert result["updated_at"] is not None


def test_save_selections_upsert(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    db.save_selections(building_id=1, upgrade_ids=[3, 5, 8, 10])
    result = db.get_selections(building_id=1)
    assert result["selected_upgrade_ids"] == [3, 5, 8, 10]


def test_get_selections_empty(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    result = db.get_selections(building_id=1)
    assert result is not None
    assert result["selected_upgrade_ids"] == []
    assert result["projected_espm"] is None
    assert result["updated_at"] is None


def test_save_projected_espm(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    espm = {"score": 72, "eligible": True, "espm_property_type": "Office"}
    db.save_projected_espm(building_id=1, espm_result=espm)
    result = db.get_selections(building_id=1)
    assert result["projected_espm"]["score"] == 72


def test_clear_projected_espm(db):
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    db.save_projected_espm(building_id=1, espm_result={"score": 72})
    db.clear_projected_espm(building_id=1)
    result = db.get_selections(building_id=1)
    assert result["projected_espm"] is None
    assert result["selected_upgrade_ids"] == [3, 5]  # preserved


def test_clear_projected_espm_on_reassessment(db):
    """Saving a new assessment should clear projected ESPM."""
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3, 5])
    db.save_projected_espm(building_id=1, espm_result={"score": 72})
    db.save_assessment(building_id=1, result={"baseline": {}}, calibrated=False)
    result = db.get_selections(building_id=1)
    assert result["projected_espm"] is None
    assert result["selected_upgrade_ids"] == [3, 5]


def test_selections_cascade_delete(db):
    """Deleting a building should cascade-delete its selections."""
    db.create_project("Test Project")
    db.create_building(1, "123 Main St", {"building_type": "Office", "sqft": 50000})
    db.save_selections(building_id=1, upgrade_ids=[3])
    db.delete_project(1)
    result = db.get_selections(building_id=1)
    assert result["selected_upgrade_ids"] == []
