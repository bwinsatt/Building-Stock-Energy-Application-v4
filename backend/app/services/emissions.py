"""
Emissions calculation module.

Calculates carbon emissions (kg CO2e) from per-fuel energy consumption.
Designed to be reusable for both baseline and post-upgrade energy values.
"""

from __future__ import annotations

from typing import Optional

from app.constants import KWH_TO_KBTU, FOSSIL_FUEL_EMISSION_FACTORS


def calculate_emissions(
    energy_by_fuel_kwh: dict[str, float],
    electricity_ef: Optional[float] = None,
) -> float:
    """Calculate total emissions in kg CO2e/sf from per-fuel energy.

    Args:
        energy_by_fuel_kwh: dict of fuel_type -> energy in kWh/sf.
        electricity_ef: electricity emission factor in kg CO2e/kWh
            (region-specific, from eGRID via zipcode lookup).
            If None, electricity emissions are excluded.

    Returns:
        Total emissions in kg CO2e/sf.
    """
    total = 0.0

    for fuel, kwh in energy_by_fuel_kwh.items():
        if kwh == 0.0:
            continue

        if fuel == "electricity":
            if electricity_ef is not None:
                total += kwh * electricity_ef
        elif fuel in FOSSIL_FUEL_EMISSION_FACTORS:
            kbtu = kwh * KWH_TO_KBTU
            total += kbtu * FOSSIL_FUEL_EMISSION_FACTORS[fuel]

    return total


def calculate_emissions_reduction_pct(
    baseline_energy_kwh: dict[str, float],
    post_upgrade_energy_kwh: dict[str, float],
    electricity_ef: Optional[float] = None,
) -> float:
    """Calculate emissions reduction as a percentage.

    Args:
        baseline_energy_kwh: baseline per-fuel energy in kWh/sf.
        post_upgrade_energy_kwh: post-upgrade per-fuel energy in kWh/sf.
        electricity_ef: electricity emission factor in kg CO2e/kWh.

    Returns:
        Emissions reduction percentage (0-100). Returns 0.0 if baseline
        emissions are zero.
    """
    baseline_emissions = calculate_emissions(baseline_energy_kwh, electricity_ef)
    post_emissions = calculate_emissions(post_upgrade_energy_kwh, electricity_ef)

    if baseline_emissions <= 0:
        return 0.0

    return (baseline_emissions - post_emissions) / baseline_emissions * 100
