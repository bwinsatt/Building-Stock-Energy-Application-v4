"""Tests for shared constants module."""

from app.constants import (
    KWH_TO_KBTU,
    KWH_TO_THERMS,
    TONS_TO_KBTUH,
    SQFT_PER_M2,
    M2_PER_SQFT,
    FOSSIL_FUEL_EMISSION_FACTORS,
)


def test_kwh_to_kbtu():
    assert KWH_TO_KBTU == 3.412


def test_kwh_to_therms():
    assert KWH_TO_THERMS == 0.03412


def test_tons_to_kbtuh():
    assert TONS_TO_KBTUH == 12.0


def test_sqft_m2_roundtrip():
    """Converting sqft -> m2 -> sqft should return approximately the same value."""
    sqft = 1000.0
    m2 = sqft * M2_PER_SQFT
    back = m2 * SQFT_PER_M2
    assert abs(back - sqft) < 0.01


def test_fossil_fuel_emission_factors_keys():
    expected_fuels = {"natural_gas", "propane", "fuel_oil", "district_heating"}
    assert set(FOSSIL_FUEL_EMISSION_FACTORS.keys()) == expected_fuels


def test_fossil_fuel_emission_factors_positive():
    for fuel, factor in FOSSIL_FUEL_EMISSION_FACTORS.items():
        assert factor > 0, f"{fuel} emission factor should be positive"
