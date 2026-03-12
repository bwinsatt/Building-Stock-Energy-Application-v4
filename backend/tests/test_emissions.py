"""Tests for emissions calculation module."""

import logging

import pytest
from app.services.emissions import calculate_emissions


class TestCalculateEmissions:
    """Tests for calculate_emissions function."""

    def test_electricity_only(self):
        """Electricity emissions use the provided emission factor."""
        energy = {"electricity": 10.0}  # 10 kWh/sf
        ef = 0.4  # kg CO2e/kWh
        result = calculate_emissions(energy, electricity_ef=ef)
        assert abs(result - 4.0) < 0.001  # 10 * 0.4 = 4.0

    def test_natural_gas_only(self):
        """Natural gas: kWh -> kBtu -> kg CO2e."""
        energy = {"natural_gas": 10.0}  # 10 kWh/sf
        result = calculate_emissions(energy, electricity_ef=0.0)
        # 10 kWh * 3.412 kBtu/kWh * 0.05311 kg/kBtu = 1.8121
        assert abs(result - 1.8121) < 0.01

    def test_all_fuels(self):
        """All fuels contribute to total emissions."""
        energy = {
            "electricity": 5.0,
            "natural_gas": 3.0,
            "fuel_oil": 1.0,
            "propane": 0.5,
            "district_heating": 0.0,
        }
        ef = 0.3
        result = calculate_emissions(energy, electricity_ef=ef)
        assert result > 0

    def test_zero_energy_returns_zero(self):
        """All-zero energy should return zero emissions."""
        energy = {"electricity": 0.0, "natural_gas": 0.0}
        result = calculate_emissions(energy, electricity_ef=0.4)
        assert result == 0.0

    def test_empty_energy_returns_zero(self):
        """Empty dict should return zero emissions."""
        result = calculate_emissions({}, electricity_ef=0.4)
        assert result == 0.0

    def test_no_electricity_ef_ignores_electricity(self):
        """When electricity_ef is None, electricity is skipped."""
        energy = {"electricity": 10.0, "natural_gas": 5.0}
        result = calculate_emissions(energy, electricity_ef=None)
        # Only natural gas contributes
        expected_gas = 5.0 * 3.412 * 0.05311
        assert abs(result - expected_gas) < 0.01

    def test_unknown_fuel_ignored(self):
        """Unknown fuel types are ignored (no crash)."""
        energy = {"electricity": 5.0, "unknown_fuel": 10.0}
        result = calculate_emissions(energy, electricity_ef=0.3)
        # Only electricity contributes
        assert abs(result - 1.5) < 0.001


class TestEmissionsReductionPct:
    """Test the percentage reduction calculation."""

    def test_basic_reduction(self):
        """50% energy reduction should yield ~50% emissions reduction (same fuel mix)."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0, "natural_gas": 5.0}
        post_upgrade = {"electricity": 5.0, "natural_gas": 2.5}
        ef = 0.4

        result = calculate_emissions_reduction_pct(baseline, post_upgrade, ef)
        assert abs(result - 50.0) < 0.1

    def test_zero_baseline_returns_zero(self):
        """Zero baseline emissions should return 0% reduction (avoid division by zero)."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 0.0}
        post_upgrade = {"electricity": 0.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert result == 0.0

    def test_full_elimination(self):
        """Eliminating all energy should yield 100% reduction."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0}
        post_upgrade = {"electricity": 0.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert abs(result - 100.0) < 0.001

    def test_reduction_clamped_to_100_when_raw_exceeds_100(self):
        """Reductions should be clamped at 100%."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0}
        post_upgrade = {"electricity": -1.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert result == 100.0

    def test_negative_reduction_within_range_is_preserved(self):
        """Negative reductions within bounds should be preserved."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0}
        post_upgrade = {"electricity": 12.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert result == pytest.approx(-20.0)

    def test_reduction_clamped_to_minus_100_when_raw_below_range(self):
        """Very negative reductions should be clamped at -100%."""
        from app.services.emissions import calculate_emissions_reduction_pct

        baseline = {"electricity": 10.0}
        post_upgrade = {"electricity": 30.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)
        assert result == -100.0

    def test_logs_warning_when_reduction_is_clamped(self, caplog):
        """Out-of-range raw reductions should emit a warning for debugging."""
        from app.services.emissions import calculate_emissions_reduction_pct

        caplog.set_level(logging.WARNING)
        baseline = {"electricity": 10.0}
        post_upgrade = {"electricity": -1.0}
        result = calculate_emissions_reduction_pct(baseline, post_upgrade, 0.4)

        assert result == 100.0
        assert "out of range" in caplog.text
