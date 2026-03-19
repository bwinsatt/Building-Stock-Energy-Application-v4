"""
Shared constants for unit conversions and emission factors.

All conversion constants used across the application should live here
to avoid duplication and ensure consistency.
"""

# Energy unit conversions
KWH_TO_KBTU = 3.412
KWH_TO_THERMS = 0.03412
KWH_PER_GALLON_FUEL_OIL = 40.6    # 138,500 BTU/gallon / 3,412 BTU/kWh
KWH_PER_GALLON_PROPANE = 26.8     # 91,500 BTU/gallon / 3,412 BTU/kWh
KWH_PER_THERM = 29.31             # 1 / KWH_TO_THERMS
TONS_TO_KBTUH = 12.0

# Area conversions
SQFT_PER_M2 = 10.7639
M2_PER_SQFT = 1 / SQFT_PER_M2  # ~0.0929

# Fossil fuel emission factors (kg CO2e per kBtu)
# Source: NREL archive calculations, standard EPA factors
# Geometric defaults for building sizing
STORY_HEIGHT_COMMERCIAL = 12  # feet
STORY_HEIGHT_RESIDENTIAL = 10  # feet
ASPECT_RATIO = 1.8  # length / width

# Fossil fuel emission factors (kg CO2e per kBtu)
FOSSIL_FUEL_EMISSION_FACTORS = {
    "natural_gas": 0.05311,
    "propane": 0.06195,
    "fuel_oil": 0.07421,
    "district_heating": 0.0664,
}
