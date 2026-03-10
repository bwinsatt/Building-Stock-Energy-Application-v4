"""Tests for the cost calculator service."""

import json
import pytest
from pathlib import Path

from app.services.cost_calculator import CostCalculatorService


@pytest.fixture
def cost_svc():
    """CostCalculatorService backed by the real lookup JSON."""
    return CostCalculatorService()


@pytest.fixture
def tiny_lookup(tmp_path):
    """Create a minimal cost lookup JSON for isolated unit tests."""
    data = {
        "comstock": {
            "100": {
                "upgrade_id": 100,
                "cost_mid": 5.0,
                "cost_low": 3.0,
                "cost_high": 7.0,
                "cost_basis": "$/ft^2 floor",
                "useful_life_years": 15,
                "confidence": "high",
            },
            "101": {
                "upgrade_id": 101,
                "cost_mid": 200.0,
                "cost_low": 180.0,
                "cost_high": 220.0,
                "cost_basis": "$/kBtu/h heating",
                "useful_life_years": 20,
                "confidence": "high",
            },
            "102": {
                "upgrade_id": 102,
                "cost_mid": 50.0,
                "cost_low": 40.0,
                "cost_high": 60.0,
                "cost_basis": "$/kBtu/h cooling",
                "useful_life_years": 18,
            },
            "103": {
                "upgrade_id": 103,
                "cost_mid": 12.0,
                "cost_low": 10.0,
                "cost_high": 14.0,
                "cost_basis": "$/ft^2 wall",
                "useful_life_years": 25,
            },
        },
        "resstock": {},
        "regional_adjustments": {
            "NY": {"city": "New York", "residential": 1.36, "commercial": 1.32},
            "TX": {"city": "Houston", "residential": 0.87, "commercial": 0.89},
        },
    }
    path = tmp_path / "test_cost_lookup.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def tiny_svc(tiny_lookup):
    return CostCalculatorService(lookup_path=tiny_lookup)


BASIC_SIZING = {
    "heating_capacity": 500,
    "cooling_capacity": 100,
    "wall_area": 200,
    "roof_area": 300,
    "window_area": 80,
}


# ---------------------------------------------------------------------------
# Floor area basis
# ---------------------------------------------------------------------------


def test_floor_area_basis(tiny_svc):
    """$/ft^2 floor → total = cost_mid * sqft."""
    result = tiny_svc.calculate_cost(
        upgrade_id=100, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    # No regional adjustment for unknown state (factor=1.0)
    assert result.installed_cost_total == pytest.approx(5.0 * 10000, rel=1e-2)
    assert result.cost_range["low"] == pytest.approx(3.0 * 10000, rel=1e-2)
    assert result.cost_range["high"] == pytest.approx(7.0 * 10000, rel=1e-2)


# ---------------------------------------------------------------------------
# Heating capacity basis
# ---------------------------------------------------------------------------


def test_heating_capacity_basis(tiny_svc):
    """$/kBtu/h heating → total = cost_mid * heating_capacity."""
    result = tiny_svc.calculate_cost(
        upgrade_id=101, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    assert result.installed_cost_total == pytest.approx(200.0 * 500, rel=1e-2)


# ---------------------------------------------------------------------------
# Cooling capacity (ComStock tons → kBtu/h)
# ---------------------------------------------------------------------------


def test_cooling_capacity_comstock(tiny_svc):
    """ComStock cooling: tons * 12 → kBtu/h, then * unit cost."""
    result = tiny_svc.calculate_cost(
        upgrade_id=102, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    expected = 50.0 * (100 * 12)  # cost_mid * (capacity * 12)
    assert result.installed_cost_total == pytest.approx(expected, rel=1e-2)


# ---------------------------------------------------------------------------
# Wall area (sizing now provides ft² directly via geometric calculation)
# ---------------------------------------------------------------------------


def test_wall_area_comstock(tiny_svc):
    """Wall area sizing values are in ft² (no m² conversion needed)."""
    result = tiny_svc.calculate_cost(
        upgrade_id=103, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    expected = 12.0 * 200  # $/ft² wall * wall_area in ft²
    assert result.installed_cost_total == pytest.approx(expected, rel=1e-2)


# ---------------------------------------------------------------------------
# Regional adjustment
# ---------------------------------------------------------------------------


def test_regional_adjustment(tiny_svc):
    """NY commercial multiplier (1.32) should be applied."""
    result = tiny_svc.calculate_cost(
        upgrade_id=100, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="NY",
    )
    expected = 5.0 * 10000 * 1.32
    assert result.installed_cost_total == pytest.approx(expected, rel=1e-2)
    assert result.regional_factor == pytest.approx(1.32, rel=1e-3)


# ---------------------------------------------------------------------------
# Unknown upgrade
# ---------------------------------------------------------------------------


def test_unknown_upgrade_raises(tiny_svc):
    with pytest.raises(ValueError, match="not found"):
        tiny_svc.calculate_cost(
            upgrade_id=999, dataset="comstock", sqft=10000,
            sizing=BASIC_SIZING, state="XX",
        )


# ---------------------------------------------------------------------------
# Cost range
# ---------------------------------------------------------------------------


def test_cost_range(tiny_svc):
    """Verify cost_range dict has low < high."""
    result = tiny_svc.calculate_cost(
        upgrade_id=100, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    assert "low" in result.cost_range
    assert "high" in result.cost_range
    assert result.cost_range["low"] <= result.cost_range["high"]


# ---------------------------------------------------------------------------
# Confidence determination
# ---------------------------------------------------------------------------


def test_confidence_determination(tiny_svc):
    """Entry with explicit 'high' confidence should return 'high'."""
    result = tiny_svc.calculate_cost(
        upgrade_id=100, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    assert result.confidence == "high"


def test_confidence_heuristic_medium(tiny_svc):
    """Entry without explicit confidence and non-simple basis → 'medium'."""
    result = tiny_svc.calculate_cost(
        upgrade_id=102, dataset="comstock", sqft=10000,
        sizing=BASIC_SIZING, state="XX",
    )
    assert result.confidence == "medium"


# ---------------------------------------------------------------------------
# Integration: real lookup file
# ---------------------------------------------------------------------------


def test_real_lookup_comstock_upgrade_1(cost_svc):
    """Smoke test with real cost lookup for ComStock upgrade 1."""
    result = cost_svc.calculate_cost(
        upgrade_id=1, dataset="comstock", sqft=50000,
        sizing=BASIC_SIZING, state="NY",
    )
    assert result.installed_cost_total > 0
    assert result.installed_cost_per_sf > 0
    assert result.confidence in ("high", "medium", "low")
