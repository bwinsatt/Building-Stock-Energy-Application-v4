"""
Preprocessor service: validates user input, derives location fields from
zipcode, imputes missing optional fields, and maps user-facing field names
to the model feature column names expected by the XGBoost models.
"""

from __future__ import annotations

import json
import os

from app.schemas.request import BuildingInput

# ---------------------------------------------------------------------------
# Building-type constants
# ---------------------------------------------------------------------------

COMSTOCK_BUILDING_TYPES = [
    "Education",
    "Food Sales",
    "Food Service",
    "Healthcare",
    "Lodging",
    "Mercantile",
    "Mixed Use",
    "Office",
    "Public Assembly",
    "Public Order and Safety",
    "Religious Worship",
    "Service",
    "Warehouse and Storage",
]

RESSTOCK_BUILDING_TYPES = ["Multi-Family"]

ALL_BUILDING_TYPES = COMSTOCK_BUILDING_TYPES + RESSTOCK_BUILDING_TYPES

# ---------------------------------------------------------------------------
# Feature column mappings  (user input field -> model column name)
# ---------------------------------------------------------------------------

COMSTOCK_FIELD_MAP = {
    "building_type": "in.comstock_building_type_group",
    "sqft": "in.sqft..ft2",
    "num_stories": "in.number_stories",
    "climate_zone": "in.as_simulated_ashrae_iecc_climate_zone_2006",
    "cluster_name": "cluster_name",
    "year_built": "in.vintage",
    "heating_fuel": "in.heating_fuel",
    "dhw_fuel": "in.service_water_heating_fuel",
    "hvac_system_type": "in.hvac_system_type",
    "wall_construction": "in.wall_construction_type",
    "window_type": "in.window_type",
    "window_to_wall_ratio": "in.window_to_wall_ratio_category",
    "lighting_type": "in.interior_lighting_generation",
    "operating_hours": "in.weekday_operating_hours..hr",
}

RESSTOCK_FIELD_MAP = {
    "building_type": "in.geometry_building_type_recs",
    "sqft": "in.sqft..ft2",
    "num_stories": "in.geometry_stories",
    "climate_zone": "in.ashrae_iecc_climate_zone_2004",
    "cluster_name": "cluster_name",
    "year_built": "in.vintage",
    "heating_fuel": "in.heating_fuel",
    "hvac_system_type": "in.hvac_heating_type",
    "wall_construction": "in.geometry_wall_type",
    "window_type": "in.windows",
    "lighting_type": "in.lighting",
}

# ---------------------------------------------------------------------------
# Auto-imputed features (no direct user input; always filled automatically)
# ---------------------------------------------------------------------------

COMSTOCK_AUTO_IMPUTE: dict[str, object] = {
    "in.hvac_category": "Small Packaged Unit",
    "in.hvac_cool_type": "DX",
    "in.hvac_heat_type": "Furnace",
    "in.hvac_vent_type": "Central Single-zone RTU",
    "in.airtightness..m3_per_m2_h": 0.5,
    "in.building_subtype": "NA",  # overridden per building_type below
    "in.aspect_ratio": "2",
    "in.energy_code_followed_during_last_hvac_replacement": "ComStock DEER 1985",
    "in.energy_code_followed_during_last_roof_replacement": "ComStock DEER 1985",
    "in.energy_code_followed_during_last_walls_replacement": "ComStock DEER 1985",
    "in.energy_code_followed_during_last_svc_water_htg_replacement": "ComStock DEER 1985",
}

# Maps user-facing values to training-data values for ComStock
_COMSTOCK_VALUE_MAP: dict[str, dict[str, str]] = {
    "wall_construction": {
        "Mass": "Mass",
        "Metal": "Metal Building",
        "SteelFrame": "SteelFramed",
        "WoodFrame": "WoodFramed",
    },
    "window_to_wall_ratio": {
        "0-10%": "2_10pct",
        "10-20%": "2_10pct",
        "20-30%": "26_50pct",
        "30-40%": "26_50pct",
        "40-50%": "26_50pct",
        "50%+": "51_75pct",
    },
    "lighting_type": {
        "T12": "gen1_t12_incandescent",
        "T8": "gen2_t8_halogen",
        "T5": "gen3_t5_cfl",
        "CFL": "gen3_t5_cfl",
        "LED": "gen4_led",
    },
    "window_type": {
        "Single, Clear, Metal": "Single - No LowE - Clear - Aluminum",
        "Single, Clear, Non-metal": "Single - No LowE - Clear - Wood",
        "Double, Clear, Metal": "Double - No LowE - Clear - Aluminum",
        "Double, Clear, Non-metal": "Double - No LowE - Tinted/Reflective - Aluminum",
        "Double, Low-E, Metal": "Double - LowE - Clear - Aluminum",
        "Double, Low-E, Non-metal": "Double - LowE - Clear - Thermally Broken Aluminum",
        "Triple, Low-E, Metal": "Triple - LowE - Clear - Thermally Broken Aluminum",
        "Triple, Low-E, Non-metal": "Triple - LowE - Clear - Thermally Broken Aluminum",
    },
    "hvac_system_type": {
        # --- Category keys → default variant ---
        "packaged_rooftop": "PSZ-AC with gas coil",
        "packaged_heat_pump": "PSZ-HP",
        "through_wall": "PTAC with gas coil",
        "through_wall_heat_pump": "PTHP",
        "central_chiller_boiler": "VAV chiller with gas boiler reheat",
        "packaged_vav": "PVAV with gas heat with electric reheat",
        "doas_fan_coil": "DOAS with fan coil chiller with boiler",
        "residential_furnace": "Residential AC with residential forced air furnace",
        # --- Old codes → specific variant (backward compat) ---
        "PSZ-AC": "PSZ-AC with gas coil",
        "PSZ-HP": "PSZ-HP",
        "PTAC": "PTAC with gas coil",
        "PTHP": "PTHP",
        "VAV_chiller_boiler": "VAV chiller with gas boiler reheat",
        "VAV_air_cooled_chiller_boiler": "VAV air-cooled chiller with gas boiler reheat",
        "PVAV_gas_boiler": "PVAV with gas boiler reheat",
        "PVAV_gas_heat": "PVAV with gas heat with electric reheat",
        "Residential_AC_gas_furnace": "Residential AC with residential forced air furnace",
        "Residential_forced_air_furnace": "Residential AC with residential forced air furnace",
        # --- All 29 ComStock variant strings → pass-through ---
        "PSZ-AC with gas coil": "PSZ-AC with gas coil",
        "PSZ-AC with gas boiler": "PSZ-AC with gas boiler",
        "PSZ-AC with electric coil": "PSZ-AC with electric coil",
        "PSZ-AC with district hot water": "PSZ-AC with district hot water",
        "PSZ-HP": "PSZ-HP",
        "PTAC with gas coil": "PTAC with gas coil",
        "PTAC with gas boiler": "PTAC with gas boiler",
        "PTAC with electric coil": "PTAC with electric coil",
        "PTHP": "PTHP",
        "VAV chiller with gas boiler reheat": "VAV chiller with gas boiler reheat",
        "VAV chiller with PFP boxes": "VAV chiller with PFP boxes",
        "VAV chiller with district hot water reheat": "VAV chiller with district hot water reheat",
        "VAV air-cooled chiller with gas boiler reheat": "VAV air-cooled chiller with gas boiler reheat",
        "VAV air-cooled chiller with PFP boxes": "VAV air-cooled chiller with PFP boxes",
        "VAV air-cooled chiller with district hot water reheat": "VAV air-cooled chiller with district hot water reheat",
        "VAV district chilled water with district hot water reheat": "VAV district chilled water with district hot water reheat",
        "PVAV with gas boiler reheat": "PVAV with gas boiler reheat",
        "PVAV with gas heat with electric reheat": "PVAV with gas heat with electric reheat",
        "PVAV with PFP boxes": "PVAV with PFP boxes",
        "PVAV with district hot water reheat": "PVAV with district hot water reheat",
        "DOAS with fan coil chiller with boiler": "DOAS with fan coil chiller with boiler",
        "DOAS with fan coil air-cooled chiller with boiler": "DOAS with fan coil air-cooled chiller with boiler",
        "DOAS with fan coil chiller with baseboard electric": "DOAS with fan coil chiller with baseboard electric",
        "DOAS with fan coil chiller with district hot water": "DOAS with fan coil chiller with district hot water",
        "DOAS with fan coil district chilled water with baseboard electric": "DOAS with fan coil district chilled water with baseboard electric",
        "DOAS with fan coil district chilled water with district hot water": "DOAS with fan coil district chilled water with district hot water",
        "DOAS with water source heat pumps cooling tower with boiler": "DOAS with water source heat pumps cooling tower with boiler",
        "DOAS with water source heat pumps with ground source heat pump": "DOAS with water source heat pumps with ground source heat pump",
        "Residential AC with residential forced air furnace": "Residential AC with residential forced air furnace",
    },
}

# Mapping from ComStock HVAC system type (training value) to sub-features
_COMSTOCK_HVAC_SUBFEATURES: dict[str, dict[str, str]] = {
    "PSZ-AC with gas coil": {
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Central Single-zone RTU",
    },
    "PSZ-AC with gas boiler": {
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "Central Single-zone RTU",
    },
    "PSZ-AC with electric coil": {
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "Central Single-zone RTU",
    },
    "PSZ-AC with district hot water": {
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "Central Single-zone RTU",
    },
    "PSZ-HP": {
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "ASHP",
        "in.hvac_heat_type": "ASHP",
        "in.hvac_vent_type": "Central Single-zone RTU",
    },
    "PTAC with gas coil": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Zone terminal equipment",
    },
    "PTAC with gas boiler": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "Zone terminal equipment",
    },
    "PTAC with electric coil": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "Zone terminal equipment",
    },
    "PTHP": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "Zone terminal equipment",
    },
    "VAV chiller with gas boiler reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "WCC",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "VAV chiller with PFP boxes": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "WCC",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "VAV chiller with district hot water reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "WCC",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "VAV air-cooled chiller with gas boiler reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "ACC",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "VAV air-cooled chiller with PFP boxes": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "ACC",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "VAV air-cooled chiller with district hot water reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "ACC",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "VAV district chilled water with district hot water reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "District",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "PVAV with gas boiler reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "PVAV with gas heat with electric reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "PVAV with PFP boxes": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "PVAV with district hot water reheat": {
        "in.hvac_category": "Multizone CAV/VAV",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "Central Multi-zone VAV RTU",
    },
    "DOAS with fan coil chiller with boiler": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "WCC",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with fan coil air-cooled chiller with boiler": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "ACC",
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with fan coil chiller with baseboard electric": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "WCC",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with fan coil chiller with district hot water": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "WCC",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with fan coil district chilled water with baseboard electric": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "District",
        "in.hvac_heat_type": "Electric Resistance",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with fan coil district chilled water with district hot water": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "District",
        "in.hvac_heat_type": "District",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with water source heat pumps cooling tower with boiler": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "WSHP",
        "in.hvac_heat_type": "WSHP",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "DOAS with water source heat pumps with ground source heat pump": {
        "in.hvac_category": "Zone-by-Zone",
        "in.hvac_cool_type": "GSHP",
        "in.hvac_heat_type": "GSHP",
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    },
    "Residential AC with residential forced air furnace": {
        "in.hvac_category": "Residential Style Central Systems",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Residential forced air",
    },
}

RESSTOCK_AUTO_IMPUTE: dict[str, object] = {
    # in.geometry_building_type_height is set dynamically based on num_stories
    # NOTE: hvac_heating_efficiency, hvac_cooling_efficiency, water_heater_efficiency,
    # and insulation_wall are overridden in _resstock_context_impute() based on
    # resolved heating fuel, wall type, etc.
    "in.hvac_heating_efficiency": "Fuel Furnace, 80% AFUE",
    "in.hvac_cooling_type": "Central AC",
    "in.hvac_cooling_efficiency": "AC, SEER 13",
    "in.hvac_has_shared_system": "None",
    "in.water_heater_fuel": "Natural Gas",
    "in.water_heater_efficiency": "Natural Gas Standard",
    "in.insulation_wall": "Wood Stud, R-7",
    "in.insulation_floor": "Uninsulated",
    "in.window_areas": "F15 B15 L15 R15",
    "in.infiltration": "5 ACH50",
    "in.geometry_foundation_type": "Slab",
}

# ResStock value mapping: user-facing values → training-data values
_RESSTOCK_VALUE_MAP: dict[str, dict[str, str]] = {
    "building_type": {
        "Multi-Family": "Multi-Family with 5+ Units",
    },
    "heating_fuel": {
        "NaturalGas": "Natural Gas",
        "Electricity": "Electricity",
        "FuelOil": "Fuel Oil",
        "Propane": "Propane",
        "DistrictHeating": "Other Fuel",
    },
    "hvac_system_type": {
        # --- Category keys → ResStock values ---
        "packaged_rooftop": "Ducted Heating",
        "packaged_heat_pump": "Ducted Heat Pump",
        "through_wall": "Non-Ducted Heating",
        "through_wall_heat_pump": "Non-Ducted Heat Pump",
        "central_chiller_boiler": "Ducted Heating",
        "doas_fan_coil": "Ducted Heating",
        "residential_furnace": "Ducted Heating",
        "packaged_vav": "Ducted Heating",
        "ducted_heating": "Ducted Heating",
        "ducted_heat_pump": "Ducted Heat Pump",
        "non_ducted_heating": "Non-Ducted Heating",
        "non_ducted_heat_pump": "Non-Ducted Heat Pump",
        # --- Old codes (backward compat) ---
        "Ducted Heating": "Ducted Heating",
        "PSZ-AC": "Ducted Heating",
        "PSZ-HP": "Ducted Heat Pump",
        "PTAC": "Non-Ducted Heating",
        "PTHP": "Non-Ducted Heat Pump",
        "VAV_chiller_boiler": "Ducted Heating",
        "VAV_air_cooled_chiller_boiler": "Ducted Heating",
        "PVAV_gas_boiler": "Ducted Heating",
        "PVAV_gas_heat": "Ducted Heating",
        "Residential_AC_gas_furnace": "Ducted Heating",
        "Residential_forced_air_furnace": "Ducted Heating",
        # --- ComStock variant strings → ResStock values ---
        "PSZ-AC with gas coil": "Ducted Heating",
        "PSZ-AC with gas boiler": "Ducted Heating",
        "PSZ-AC with electric coil": "Ducted Heating",
        "PSZ-AC with district hot water": "Ducted Heating",
        "PSZ-HP": "Ducted Heat Pump",
        "PTAC with gas coil": "Non-Ducted Heating",
        "PTAC with gas boiler": "Non-Ducted Heating",
        "PTAC with electric coil": "Non-Ducted Heating",
        "PTHP": "Non-Ducted Heat Pump",
        "VAV chiller with gas boiler reheat": "Ducted Heating",
        "VAV chiller with PFP boxes": "Ducted Heating",
        "VAV chiller with district hot water reheat": "Ducted Heating",
        "VAV air-cooled chiller with gas boiler reheat": "Ducted Heating",
        "VAV air-cooled chiller with PFP boxes": "Ducted Heating",
        "VAV air-cooled chiller with district hot water reheat": "Ducted Heating",
        "VAV district chilled water with district hot water reheat": "Ducted Heating",
        "PVAV with gas boiler reheat": "Ducted Heating",
        "PVAV with gas heat with electric reheat": "Ducted Heating",
        "PVAV with PFP boxes": "Ducted Heating",
        "PVAV with district hot water reheat": "Ducted Heating",
        "DOAS with fan coil chiller with boiler": "Ducted Heating",
        "DOAS with fan coil air-cooled chiller with boiler": "Ducted Heating",
        "DOAS with fan coil chiller with baseboard electric": "Ducted Heating",
        "DOAS with fan coil chiller with district hot water": "Ducted Heating",
        "DOAS with fan coil district chilled water with baseboard electric": "Ducted Heating",
        "DOAS with fan coil district chilled water with district hot water": "Ducted Heating",
        "DOAS with water source heat pumps cooling tower with boiler": "Ducted Heating",
        "DOAS with water source heat pumps with ground source heat pump": "Ducted Heating",
        "Residential AC with residential forced air furnace": "Ducted Heating",
        # --- ResStock pass-through ---
        "Ducted Heat Pump": "Ducted Heat Pump",
        "Non-Ducted Heating": "Non-Ducted Heating",
        "Non-Ducted Heat Pump": "Non-Ducted Heat Pump",
    },
    "wall_construction": {
        "Mass": "Concrete",
        "Metal": "Steel Frame",
        "SteelFrame": "Steel Frame",
        "WoodFrame": "Wood Frame",
        "Wood Frame": "Wood Frame",
        "Brick": "Brick",
    },
    "window_type": {
        "Single, Clear, Metal": "Single, Clear, Metal",
        "Single, Clear, Non-metal": "Single, Clear, Non-metal",
        "Double, Clear, Metal": "Double, Clear, Metal, Air",
        "Double, Clear, Non-metal": "Double, Clear, Non-metal, Air",
        "Double, Low-E, Metal": "Double, Low-E, Non-metal, Air, M-Gain",
        "Double, Low-E, Non-metal": "Double, Low-E, Non-metal, Air, M-Gain",
        "Double, Low-E": "Double, Low-E, Non-metal, Air, M-Gain",
        "Triple, Low-E, Metal": "Triple, Low-E, Non-metal, Air, L-Gain",
        "Triple, Low-E, Non-metal": "Triple, Low-E, Non-metal, Air, L-Gain",
    },
    "lighting_type": {
        "LED": "100% LED",
        "100% LED": "100% LED",
        "CFL": "100% CFL",
        "100% CFL": "100% CFL",
        "T12": "100% Incandescent",
        "T8": "100% CFL",
        "T5": "100% CFL",
        "100% Incandescent": "100% Incandescent",
    },
}


def _resstock_context_impute(
    auto_impute: dict[str, object], resolved: dict[str, object]
) -> None:
    """Override ResStock auto-impute values based on resolved user inputs.

    Ensures that heating efficiency, cooling efficiency, water heater
    efficiency, and wall insulation categories match the training data
    and are consistent with user-specified fuel type, HVAC type, and wall
    construction.
    """
    # --- Heating efficiency based on fuel + HVAC type ---
    heating_fuel = resolved.get("heating_fuel", "NaturalGas")
    hvac_type = resolved.get("hvac_system_type", "Ducted Heating")

    if hvac_type in ("PSZ-HP", "Ducted Heat Pump", "packaged_heat_pump", "ducted_heat_pump"):
        auto_impute["in.hvac_heating_efficiency"] = "ASHP, SEER 13, 7.7 HSPF"
    elif hvac_type in ("PTHP", "Non-Ducted Heat Pump", "through_wall_heat_pump", "non_ducted_heat_pump"):
        auto_impute["in.hvac_heating_efficiency"] = "MSHP, SEER 14.5, 8.2 HSPF"
    elif heating_fuel == "Electricity":
        auto_impute["in.hvac_heating_efficiency"] = "Electric Baseboard, 100% Efficiency"
    else:
        # Gas, oil, propane → fuel furnace/boiler
        auto_impute["in.hvac_heating_efficiency"] = "Fuel Furnace, 80% AFUE"

    # --- Cooling efficiency based on HVAC type ---
    if hvac_type in ("PSZ-HP", "Ducted Heat Pump", "packaged_heat_pump", "ducted_heat_pump"):
        auto_impute["in.hvac_cooling_efficiency"] = "Ducted Heat Pump"
        auto_impute["in.hvac_cooling_type"] = "Ducted Heat Pump"
    elif hvac_type in ("PTHP", "Non-Ducted Heat Pump", "through_wall_heat_pump", "non_ducted_heat_pump"):
        auto_impute["in.hvac_cooling_efficiency"] = "Non-Ducted Heat Pump"
        auto_impute["in.hvac_cooling_type"] = "Non-Ducted Heat Pump"
    else:
        auto_impute["in.hvac_cooling_efficiency"] = "AC, SEER 13"
        auto_impute["in.hvac_cooling_type"] = "Central AC"

    # --- Water heater efficiency based on water heater fuel ---
    wh_fuel = auto_impute.get("in.water_heater_fuel", "Natural Gas")
    _WH_EFF_MAP = {
        "Natural Gas": "Natural Gas Standard",
        "Electricity": "Electric Standard",
        "Fuel Oil": "Fuel Oil Standard",
        "Propane": "Propane Standard",
        "Other Fuel": "Other Fuel",
    }
    auto_impute["in.water_heater_efficiency"] = _WH_EFF_MAP.get(
        str(wh_fuel), "Natural Gas Standard"
    )

    # --- Wall insulation based on wall construction ---
    wall_type = resolved.get("wall_construction", "Wood Frame")
    # After value mapping: "Wood Frame", "Brick", "Concrete", "Steel Frame"
    _WALL_INS_MAP = {
        "Wood Frame": "Wood Stud, R-7",
        "WoodFrame": "Wood Stud, R-7",
        "Brick": "Brick, 12-in, 3-wythe, R-7",
        "Mass": "CMU, 6-in Hollow, R-7",
        "Concrete": "CMU, 6-in Hollow, R-7",
        "Metal": "Wood Stud, R-7",
        "SteelFrame": "Wood Stud, R-7",
        "Steel Frame": "Wood Stud, R-7",
    }
    auto_impute["in.insulation_wall"] = _WALL_INS_MAP.get(
        str(wall_type), "Wood Stud, R-7"
    )

    # --- User-provided overrides (from new advanced fields) ---
    if resolved.get("hvac_heating_efficiency"):
        auto_impute["in.hvac_heating_efficiency"] = resolved["hvac_heating_efficiency"]
    if resolved.get("hvac_cooling_efficiency"):
        auto_impute["in.hvac_cooling_efficiency"] = resolved["hvac_cooling_efficiency"]
    if resolved.get("water_heater_efficiency"):
        auto_impute["in.water_heater_efficiency"] = resolved["water_heater_efficiency"]
    if resolved.get("insulation_wall"):
        auto_impute["in.insulation_wall"] = resolved["insulation_wall"]
    if resolved.get("infiltration"):
        auto_impute["in.infiltration"] = resolved["infiltration"]


def _resstock_building_type_height(num_stories: int) -> str:
    """Map number of stories to ResStock building_type_height category."""
    if num_stories <= 3:
        return "Multi-Family with 5+ Units, 1-3 Stories"
    elif num_stories <= 7:
        return "Multi-Family with 5+ Units, 4-7 Stories"
    else:
        return "Multi-Family with 5+ Units, 8+ Stories"


def _resstock_per_unit_sqft(total_sqft: float, num_stories: int) -> float:
    """Convert whole-building sqft to per-unit sqft for ResStock.

    ResStock models individual dwelling units (~900 ft² avg).
    Estimate number of units from total floor area and stories,
    assuming ~900 ft² per unit.
    """
    AVG_UNIT_SQFT = 900.0
    est_units = max(1, round(total_sqft / AVG_UNIT_SQFT))
    per_unit = total_sqft / est_units
    # Clamp to reasonable range seen in training data (300-6400 ft²)
    return max(300.0, min(6400.0, per_unit))

# ---------------------------------------------------------------------------
# Building-type imputation defaults  (mode-based, V1)
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, dict[str, object]] = {
    "Office": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "central_chiller_boiler",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "20-30%",
        "lighting_type": "LED",
        "operating_hours": 50.0,
        "year_built": 1985,
    },
    "Education": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 40.0,
        "year_built": 1975,
    },
    "Food Sales": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "0-10%",
        "lighting_type": "LED",
        "operating_hours": 70.0,
        "year_built": 1990,
    },
    "Food Service": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 60.0,
        "year_built": 1985,
    },
    "Healthcare": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "central_chiller_boiler",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 80.0,
        "year_built": 1980,
    },
    "Lodging": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "through_wall",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "20-30%",
        "lighting_type": "LED",
        "operating_hours": 168.0,
        "year_built": 1985,
    },
    "Mercantile": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 55.0,
        "year_built": 1990,
    },
    "Mixed Use": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "20-30%",
        "lighting_type": "LED",
        "operating_hours": 50.0,
        "year_built": 1985,
    },
    "Public Assembly": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 40.0,
        "year_built": 1980,
    },
    "Public Order and Safety": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 60.0,
        "year_built": 1985,
    },
    "Religious Worship": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "LED",
        "operating_hours": 20.0,
        "year_built": 1975,
    },
    "Service": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "0-10%",
        "lighting_type": "LED",
        "operating_hours": 45.0,
        "year_built": 1985,
    },
    "Warehouse and Storage": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "packaged_rooftop",
        "wall_construction": "Mass",
        "window_type": "Double, Low-E, Non-metal",
        "window_to_wall_ratio": "0-10%",
        "lighting_type": "LED",
        "operating_hours": 40.0,
        "year_built": 1990,
    },
    "Multi-Family": {
        "heating_fuel": "NaturalGas",
        "dhw_fuel": "NaturalGas",
        "hvac_system_type": "ducted_heating",
        "wall_construction": "Wood Frame",
        "window_type": "Double, Low-E",
        "window_to_wall_ratio": "10-20%",
        "lighting_type": "100% LED",
        "operating_hours": 168.0,
        "year_built": 1985,
    },
}

DEFAULT_FALLBACK: dict[str, object] = {
    "heating_fuel": "NaturalGas",
    "dhw_fuel": "NaturalGas",
    "hvac_system_type": "packaged_rooftop",
    "wall_construction": "Mass",
    "window_type": "Double, Low-E, Non-metal",
    "window_to_wall_ratio": "20-30%",
    "lighting_type": "LED",
    "operating_hours": 40.0,
    "year_built": 1990,
}

# ---------------------------------------------------------------------------
# Vintage mapping
# ---------------------------------------------------------------------------


def year_to_vintage(year: int, dataset: str = "comstock") -> str:
    """Map a construction year to the vintage bucket used by the models.

    ComStock and ResStock use different vintage bucket labels.
    """
    if dataset == "comstock":
        if year < 1946:
            return "Before 1946"
        elif year < 1960:
            return "1946 to 1959"
        elif year < 1970:
            return "1960 to 1969"
        elif year < 1980:
            return "1970 to 1979"
        elif year < 1990:
            return "1980 to 1989"
        elif year < 2000:
            return "1990 to 1999"
        elif year < 2013:
            return "2000 to 2012"
        else:
            return "2013 to 2018"
    else:
        # ResStock vintage buckets
        if year < 1950:
            return "<1950"
        elif year < 1960:
            return "1950s"
        elif year < 1970:
            return "1960s"
        elif year < 1980:
            return "1970s"
        elif year < 1990:
            return "1980s"
        elif year < 2000:
            return "1990s"
        elif year < 2010:
            return "2000s"
        elif year < 2020:
            return "2010s"
        else:
            return "2020s"


# ---------------------------------------------------------------------------
# Zipcode -> state / climate_zone / cluster  (JSON-backed lookup)
# ---------------------------------------------------------------------------


class _ZipcodeLookup:
    """
    Lazily loads ``zipcode_lookup.json`` and resolves a 5-digit US zipcode
    to (state, climate_zone, cluster_name) using three tiers:

    1. 3-digit prefix match  (sub-state granularity for metro areas)
    2. State-level defaults   (from mode values in the spatial tract table)
    3. Hardcoded fallback     (``4A`` / generic cluster)
    """

    _FALLBACK_CLIMATE_ZONE = "4A"
    _FALLBACK_CLUSTER = "the Greater New York City Area"

    def __init__(self) -> None:
        self._prefixes: dict[str, dict[str, str]] | None = None
        self._state_defaults: dict[str, dict[str, str]] | None = None

    # -- lazy loader --------------------------------------------------------

    def _load(self) -> None:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        path = os.path.join(data_dir, "zipcode_lookup.json")
        with open(path) as fh:
            data = json.load(fh)
        self._prefixes = data["prefixes"]
        self._state_defaults = data["state_defaults"]

    # -- public API ---------------------------------------------------------

    def lookup(self, zipcode: str) -> tuple[str, str, str]:
        """Return ``(state, climate_zone, cluster_name)`` for *zipcode*.

        Raises ``ValueError`` if the prefix cannot be mapped to a state.
        """
        if self._prefixes is None:
            self._load()
        assert self._prefixes is not None
        assert self._state_defaults is not None

        prefix = zipcode[:3]

        # Tier 1: 3-digit prefix match (most granular)
        entry = self._prefixes.get(prefix)
        if entry is not None:
            return entry["state"], entry["climate_zone"], entry["cluster_name"]

        # Tier 2: state-level defaults (fall back from prefix → state mapping
        # is not possible without the prefix data, so we cannot reach this
        # tier in normal operation — but we keep it for robustness if the
        # JSON is trimmed in the future).

        # Tier 3: hard fallback — raise so caller can surface a clear error.
        raise ValueError(
            f"Unrecognized zipcode prefix '{prefix}' from zipcode '{zipcode}'. "
            "Only US zipcodes are supported."
        )


_zip_lookup = _ZipcodeLookup()


def _get_location_from_zipcode(zipcode: str) -> tuple[str, str, str]:
    """
    Derive (state, climate_zone, cluster_name) from a 5-digit US zipcode.

    Uses a JSON lookup table (``backend/app/data/zipcode_lookup.json``)
    built from the ComStock spatial tract lookup.  Granularity is at the
    3-digit zipcode prefix level, with state-level defaults as fallback.

    Raises:
        ValueError: if the zipcode prefix is not recognized.
    """
    return _zip_lookup.lookup(zipcode)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class PreprocessingError(Exception):
    """Raised when input validation fails."""


def _validate(building: BuildingInput) -> None:
    """Validate user-supplied fields.  Raises ``PreprocessingError``."""
    if building.building_type not in ALL_BUILDING_TYPES:
        raise PreprocessingError(
            f"Invalid building_type '{building.building_type}'. "
            f"Must be one of: {ALL_BUILDING_TYPES}"
        )
    if building.sqft <= 0:
        raise PreprocessingError("sqft must be greater than 0.")
    if building.num_stories < 1:
        raise PreprocessingError("num_stories must be at least 1.")
    if not building.zipcode.isdigit() or len(building.zipcode) != 5:
        raise PreprocessingError(
            "zipcode must be a 5-digit US zip code (digits only)."
        )
    if building.year_built is not None and (
        building.year_built < 1800 or building.year_built > 2030
    ):
        raise PreprocessingError(
            "year_built must be between 1800 and 2030."
        )
    if building.operating_hours is not None and building.operating_hours < 0:
        raise PreprocessingError("operating_hours must be >= 0.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


FIELD_LABELS = {
    "heating_fuel": "Heating Fuel",
    "dhw_fuel": "Domestic Hot Water Fuel",
    "hvac_system_type": "HVAC System Type",
    "wall_construction": "Wall Construction",
    "window_type": "Window Type",
    "window_to_wall_ratio": "Window-to-Wall Ratio",
    "lighting_type": "Lighting Type",
    "operating_hours": "Operating Hours (hrs/week)",
    "hvac_heating_efficiency": "Heating Efficiency",
    "hvac_cooling_efficiency": "Cooling Efficiency",
    "water_heater_efficiency": "Water Heater Efficiency",
    "insulation_wall": "Wall Insulation",
    "infiltration": "Air Tightness",
    "hvac_category": "HVAC Category",
    "hvac_cool_type": "HVAC Cooling Type",
    "hvac_heat_type": "HVAC Heating Type",
    "hvac_vent_type": "HVAC Ventilation Type",
}

# Reverse display maps: training-data values -> user-facing values
# Used when the imputation model returns training-data format values
_COMSTOCK_DISPLAY_MAP: dict[str, dict[str, str]] = {
    "lighting_type": {
        "gen1_t12_incandescent": "T12",
        "gen2_t8_halogen": "T8",
        "gen3_t5_cfl": "CFL",
        "gen4_led": "LED",
        "gen5_led": "LED",
    },
    "hvac_system_type": {
        "PSZ-AC with gas coil": "packaged_rooftop",
        "PSZ-AC with gas boiler": "packaged_rooftop",
        "PSZ-AC with electric coil": "packaged_rooftop",
        "PSZ-AC with district hot water": "packaged_rooftop",
        "PSZ-HP": "packaged_heat_pump",
        "PTAC with gas coil": "through_wall",
        "PTAC with gas boiler": "through_wall",
        "PTAC with electric coil": "through_wall",
        "PTHP": "through_wall_heat_pump",
        "VAV chiller with gas boiler reheat": "central_chiller_boiler",
        "VAV chiller with PFP boxes": "central_chiller_boiler",
        "VAV chiller with district hot water reheat": "central_chiller_boiler",
        "VAV air-cooled chiller with gas boiler reheat": "central_chiller_boiler",
        "VAV air-cooled chiller with PFP boxes": "central_chiller_boiler",
        "VAV air-cooled chiller with district hot water reheat": "central_chiller_boiler",
        "VAV district chilled water with district hot water reheat": "central_chiller_boiler",
        "PVAV with gas boiler reheat": "packaged_vav",
        "PVAV with gas heat with electric reheat": "packaged_vav",
        "PVAV with PFP boxes": "packaged_vav",
        "PVAV with district hot water reheat": "packaged_vav",
        "DOAS with fan coil chiller with boiler": "doas_fan_coil",
        "DOAS with fan coil air-cooled chiller with boiler": "doas_fan_coil",
        "DOAS with fan coil chiller with baseboard electric": "doas_fan_coil",
        "DOAS with fan coil chiller with district hot water": "doas_fan_coil",
        "DOAS with fan coil district chilled water with baseboard electric": "doas_fan_coil",
        "DOAS with fan coil district chilled water with district hot water": "doas_fan_coil",
        "DOAS with water source heat pumps cooling tower with boiler": "doas_fan_coil",
        "DOAS with water source heat pumps with ground source heat pump": "doas_fan_coil",
        "Residential AC with residential forced air furnace": "residential_furnace",
    },
}


def preprocess(
    building_input: BuildingInput,
    imputation_service=None,
) -> tuple[dict, dict, str, str, str]:
    """
    Process user input into model-ready features.

    Args:
        building_input: Validated user input (a Pydantic ``BuildingInput``).
        imputation_service: Optional ``ImputationService`` instance for
            ML-based imputation of missing fields.

    Returns:
        A 5-tuple of:
        - **features_dict** -- ``{model_column_name: value}`` ready for
          model inference.
        - **imputed_details** -- dict mapping imputed field names to dicts
          with keys ``value``, ``label``, ``source``, and ``confidence``.
        - **dataset** -- ``'comstock'`` or ``'resstock'``.
        - **climate_zone** -- ASHRAE climate zone derived from zipcode.
        - **state** -- two-letter state abbreviation derived from zipcode.

    Raises:
        PreprocessingError: on invalid inputs.
        ValueError: on unrecognized zipcode.
    """

    # --- 1. Validate ---
    _validate(building_input)

    # --- 2. Determine dataset ---
    is_resstock = building_input.building_type in RESSTOCK_BUILDING_TYPES
    dataset = "resstock" if is_resstock else "comstock"
    field_map = RESSTOCK_FIELD_MAP if is_resstock else COMSTOCK_FIELD_MAP
    auto_impute = (
        dict(RESSTOCK_AUTO_IMPUTE) if is_resstock else dict(COMSTOCK_AUTO_IMPUTE)
    )

    # --- 3. Derive location from zipcode ---
    state, climate_zone, cluster_name = _get_location_from_zipcode(
        building_input.zipcode
    )

    # --- 4. Impute missing optional fields ---
    bt_defaults = DEFAULTS.get(building_input.building_type, DEFAULT_FALLBACK)
    imputed_details: dict[str, dict] = {}

    # Fields that may be imputed (user-facing name -> value on BuildingInput).
    optional_fields = [
        "heating_fuel",
        "dhw_fuel",
        "hvac_system_type",
        "wall_construction",
        "window_type",
        "window_to_wall_ratio",
        "lighting_type",
        "operating_hours",
    ]

    # Build a dict of resolved user-facing field values.
    resolved: dict[str, object] = {
        "building_type": building_input.building_type,
        "sqft": building_input.sqft,
        "num_stories": building_input.num_stories,
        "year_built": building_input.year_built,
        "climate_zone": climate_zone,
        "cluster_name": cluster_name,
    }

    # Reverse display map for current dataset
    display_map = _COMSTOCK_DISPLAY_MAP if not is_resstock else {}

    for field in optional_fields:
        value = getattr(building_input, field, None)
        if value is None:
            # Only impute if the field is in the field_map (relevant to dataset)
            if field in field_map:
                if imputation_service is not None and field in getattr(imputation_service, "models", {}):
                    known = {
                        "building_type": building_input.building_type,
                        "climate_zone": climate_zone,
                        "year_built": building_input.year_built,
                        "sqft": building_input.sqft,
                        "num_stories": building_input.num_stories,
                        "state": state,
                    }
                    try:
                        prediction = imputation_service.predict(known, fields_to_predict=[field])
                    except Exception:
                        logger.warning("Imputation failed for %s, falling back to default", field)
                        prediction = {}
                    if prediction.get(field, {}).get("value") is not None:
                        pred = prediction[field]
                        raw_val = pred["value"]
                        # Map training-data value to user-facing value if needed
                        if field in display_map and isinstance(raw_val, str):
                            display_val = display_map[field].get(raw_val, raw_val)
                        else:
                            display_val = raw_val
                        resolved[field] = display_val
                        imputed_details[field] = {
                            "value": str(display_val),
                            "label": FIELD_LABELS.get(field, field),
                            "source": "model",
                            "confidence": pred.get("confidence"),
                        }
                    else:
                        # Fallback to static default
                        default_val = bt_defaults.get(field, DEFAULT_FALLBACK.get(field))
                        resolved[field] = default_val
                        imputed_details[field] = {
                            "value": str(default_val),
                            "label": FIELD_LABELS.get(field, field),
                            "source": "default",
                            "confidence": None,
                        }
                else:
                    # No imputation service or no model for this field — static default
                    default_val = bt_defaults.get(field, DEFAULT_FALLBACK.get(field))
                    resolved[field] = default_val
                    imputed_details[field] = {
                        "value": str(default_val),
                        "label": FIELD_LABELS.get(field, field),
                        "source": "default",
                        "confidence": None,
                    }
        else:
            if field in field_map:
                resolved[field] = value

    # Pass-through efficiency/envelope overrides (no imputation, no mapping)
    _PASSTHROUGH_FIELDS = [
        "hvac_heating_efficiency",
        "hvac_cooling_efficiency",
        "water_heater_efficiency",
        "insulation_wall",
        "infiltration",
    ]
    for field in _PASSTHROUGH_FIELDS:
        value = getattr(building_input, field, None)
        if value is not None:
            resolved[field] = value

    # --- 5. ResStock-specific adjustments ---
    if is_resstock:
        # Convert whole-building sqft to per-unit sqft
        resolved["sqft"] = _resstock_per_unit_sqft(
            building_input.sqft, building_input.num_stories
        )
        # Set building_type_height based on stories
        auto_impute["in.geometry_building_type_height"] = (
            _resstock_building_type_height(building_input.num_stories)
        )
        # Override auto-impute values to match training categories
        # based on resolved heating fuel, HVAC type, wall type, etc.
        _resstock_context_impute(auto_impute, resolved)

    # --- 6. Map to model column names ---
    features: dict[str, object] = {}

    # Value mapping for fields that differ between user-facing and training
    value_map = _COMSTOCK_VALUE_MAP if not is_resstock else _RESSTOCK_VALUE_MAP

    for user_field, model_col in field_map.items():
        if user_field not in resolved:
            continue
        value = resolved[user_field]
        # Convert year_built to vintage bucket
        if user_field == "year_built" and isinstance(value, (int, float)):
            value = year_to_vintage(int(value), dataset)
        # Map user-facing values to training-data values
        elif user_field in value_map and isinstance(value, str):
            value = value_map[user_field].get(value, value)
        features[model_col] = value

    # --- 7. Add auto-imputed features ---
    # Override building_subtype for ComStock to match the building type.
    if not is_resstock:
        auto_impute["in.building_subtype"] = building_input.building_type

    features.update(auto_impute)

    # --- 8. ComStock: derive HVAC sub-features from system type ---
    # Must run AFTER auto_impute so derived values override the defaults.
    if not is_resstock:
        hvac_system = features.get("in.hvac_system_type")
        if hvac_system and hvac_system in _COMSTOCK_HVAC_SUBFEATURES:
            sub = _COMSTOCK_HVAC_SUBFEATURES[hvac_system]
            for col, val in sub.items():
                features[col] = val

    # --- 9. Expose resolved efficiency/envelope values in imputed_details ---
    # For ResStock: show the actual heating/cooling/DHW efficiency, wall
    # insulation, and infiltration values used (whether user-provided or
    # auto-derived from context).
    if is_resstock:
        _RESSTOCK_DETAIL_FIELDS = {
            "hvac_heating_efficiency": "in.hvac_heating_efficiency",
            "hvac_cooling_efficiency": "in.hvac_cooling_efficiency",
            "water_heater_efficiency": "in.water_heater_efficiency",
            "insulation_wall": "in.insulation_wall",
            "infiltration": "in.infiltration",
        }
        for field_key, model_col in _RESSTOCK_DETAIL_FIELDS.items():
            val = features.get(model_col, auto_impute.get(model_col))
            if val is not None:
                user_provided = getattr(building_input, field_key, None) is not None
                imputed_details[field_key] = {
                    "value": str(val),
                    "label": FIELD_LABELS.get(field_key, field_key),
                    "source": "user" if user_provided else "default",
                    "confidence": None,
                }

    # For ComStock: show the derived HVAC sub-features
    if not is_resstock:
        _COMSTOCK_SUBFEATURE_KEYS = {
            "hvac_category": "in.hvac_category",
            "hvac_cool_type": "in.hvac_cool_type",
            "hvac_heat_type": "in.hvac_heat_type",
            "hvac_vent_type": "in.hvac_vent_type",
        }
        for field_key, model_col in _COMSTOCK_SUBFEATURE_KEYS.items():
            val = features.get(model_col)
            if val is not None:
                imputed_details[field_key] = {
                    "value": str(val),
                    "label": FIELD_LABELS.get(field_key, field_key),
                    "source": "derived",
                    "confidence": None,
                }

    return features, imputed_details, dataset, climate_zone, state
