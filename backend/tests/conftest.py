import sys
import os

import pytest
from fastapi.testclient import TestClient

# Ensure backend/ is on sys.path so `from app.xxx` imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult, FuelBreakdown
from app.main import app as fastapi_app


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e", action="store_true", default=False,
        help="Run e2e tests that hit live external APIs",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: marks tests that hit live external APIs")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-e2e"):
        return
    skip_e2e = pytest.mark.skip(reason="needs --run-e2e to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


@pytest.fixture
def office_input():
    return BuildingInput(
        building_type="Office",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        heating_fuel="NaturalGas",
    )


@pytest.fixture
def mf_input():
    return BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=5,
        zipcode="10001",
        year_built=1985,
    )


@pytest.fixture
def minimal_input():
    """Only required fields, everything else None."""
    return BuildingInput(
        building_type="Office",
        sqft=10000,
        num_stories=2,
        zipcode="90210",
        year_built=1990,
    )


@pytest.fixture
def sample_baseline():
    return BaselineResult(
        total_eui_kbtu_sf=54.2,
        eui_by_fuel=FuelBreakdown(
            electricity=25.0,
            natural_gas=20.0,
            fuel_oil=0.0,
            propane=0.0,
            district_heating=0.0,
        ),
    )


@pytest.fixture
def app_client():
    with TestClient(fastapi_app) as client:
        yield client
