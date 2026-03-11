"""
Applicability Rules Engine (V2 – ComStock/ResStock Aligned)

Determines which upgrade measures apply to a given building based on its
characteristics.  Rules are derived from NREL ComStock and ResStock measure
applicability logic, adapted to work with the abstracted XGBoost feature
columns rather than the full EnergyPlus/OpenStudio model.

Two checks per upgrade:
1. A trained model must exist (``upgrade_id in available_upgrades``).
2. Feature-based rules disqualify upgrades that conflict with the building's
   current equipment, envelope, or building type.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Set

logger = logging.getLogger(__name__)

# ============================================================================
# Public API
# ============================================================================


def check_applicability(
    upgrade_id: int,
    dataset: str,
    features: dict,
    available_upgrades: set,
) -> bool:
    """Check if an upgrade measure is applicable to a building.

    Args:
        upgrade_id: The upgrade number (e.g. 1, 43, 54 ...).
        dataset: ``'comstock'`` or ``'resstock'``.
        features: Dict of model feature column names to values for the
            building under consideration.
        available_upgrades: Set of upgrade IDs that have trained models.

    Returns:
        ``True`` if the upgrade is applicable to this building.
    """
    if upgrade_id not in available_upgrades:
        return False
    return _check_hard_rules(upgrade_id, dataset, features)


def get_applicable_upgrades(
    dataset: str,
    features: dict,
    available_upgrades: Iterable[int],
) -> List[int]:
    """Return the sorted list of applicable upgrade IDs for a building.

    Convenience wrapper around :func:`check_applicability` that filters a full
    set of available upgrades down to those that pass the hard rules.
    """
    available = set(available_upgrades)
    return sorted(
        uid
        for uid in available
        if check_applicability(uid, dataset, features, available)
    )


# ============================================================================
# Hard rules — dispatch
# ============================================================================


def _check_hard_rules(upgrade_id: int, dataset: str, features: dict) -> bool:
    dataset = dataset.lower()
    if dataset == "comstock":
        return _check_comstock_rules(upgrade_id, features)
    elif dataset == "resstock":
        return _check_resstock_rules(upgrade_id, features)
    else:
        logger.warning("Unknown dataset '%s'; skipping hard rules", dataset)
        return True


# ============================================================================
# Feature helpers
# ============================================================================


def _get(features: dict, key: str, default: str = "") -> str:
    return str(features.get(key, default))


# ============================================================================
# ComStock rules
# ============================================================================

# ── Upgrade-ID groups ────────────────────────────────────────────────────────

_CS_HP_RTU: Set[int] = set(range(1, 11))          # 1-10: HP-RTU variants
_CS_VRF_MINISPLIT: Set[int] = {12, 13, 14}        # VRF/DOAS minisplit
_CS_BOILER_ALL: Set[int] = {15, 16, 17, 18}       # All boiler upgrades
_CS_BOILER_GAS: Set[int] = {16, 17}               # Need gas fuel
_CS_DEMAND_FLEX: Set[int] = set(range(32, 43))    # 32-42: Demand flexibility
_CS_NO_RULES: Set[int] = (
    {0, 25, 27, 44, 46, 47, 49, 52, 53, 65}       # Broadly applicable
    | _CS_DEMAND_FLEX
)

_CS_GHP_NOT_ALREADY: Set[str] = {"GSHP", "WSHP"}
_CS_HP_NOT_ALREADY: Set[str] = {"ASHP", "GSHP", "WSHP"}
_CS_NO_AHU_VENT: Set[str] = {"DOAS+Zone terminal equipment", "Zone terminal equipment"}
_CS_FOOD_BUILDINGS: Set[str] = {"Food Sales", "Food Service"}
_CS_DCV_EXCLUDED_BLDG: Set[str] = {"Lodging", "Food Service"}
_CS_CHILLER_COOL: Set[str] = {"WCC", "ACC"}
_CS_HYDRONIC_COOL: Set[str] = {"WCC", "District"}
_CS_PACKAGED_CATEGORIES: Set[str] = {"Small Packaged Unit", "Residential Style Central Systems"}


def _check_comstock_rules(upgrade_id: int, features: dict) -> bool:
    """Apply ComStock-specific applicability rules."""

    # ── No rules for these upgrades ──
    if upgrade_id in _CS_NO_RULES:
        return True

    hvac_category = _get(features, "in.hvac_category")
    hvac_cool = _get(features, "in.hvac_cool_type")
    hvac_heat = _get(features, "in.hvac_heat_type")
    hvac_vent = _get(features, "in.hvac_vent_type")
    lighting = _get(features, "in.interior_lighting_generation")
    wall = _get(features, "in.wall_construction_type")
    building_type = _get(features, "in.comstock_building_type_group")
    heating_fuel = _get(features, "in.heating_fuel")
    window = _get(features, "in.window_type")
    has_boiler = "Boiler" in hvac_heat
    is_doas = hvac_vent == "DOAS+Zone terminal equipment"
    is_district = hvac_heat == "District" or hvac_cool == "District"

    # ── HP-RTU (1-10) ──
    if upgrade_id in _CS_HP_RTU:
        if hvac_category not in _CS_PACKAGED_CATEGORIES:
            return False
        if is_doas:
            return False
        if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
            return False
        return True

    # ── Advanced RTU (11) ──
    if upgrade_id == 11:
        if hvac_category != "Small Packaged Unit":
            return False
        if is_doas:
            return False
        return True

    # ── VRF / Minisplit (12-14) ──
    if upgrade_id in _CS_VRF_MINISPLIT:
        if is_doas:
            return False
        if hvac_cool == "District":
            return False
        if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
            return False
        return True

    # ── Boiler upgrades (15-18) ──
    if upgrade_id in _CS_BOILER_ALL:
        if not has_boiler:
            return False
        if upgrade_id in _CS_BOILER_GAS and heating_fuel != "NaturalGas":
            return False
        return True

    # ── Economizer (19) ──
    if upgrade_id == 19:
        return hvac_vent not in _CS_NO_AHU_VENT

    # ── DCV (20) ──
    if upgrade_id == 20:
        if hvac_vent in _CS_NO_AHU_VENT:
            return False
        if building_type in _CS_DCV_EXCLUDED_BLDG:
            return False
        return True

    # ── Energy Recovery (21) ──
    if upgrade_id == 21:
        return hvac_vent != "Zone terminal equipment"

    # ── Advanced RTU Controls (22) ──
    if upgrade_id == 22:
        return hvac_category == "Small Packaged Unit"

    # ── Unoccupied AHU Control (23) ──
    if upgrade_id == 23:
        return hvac_vent != "Zone terminal equipment"

    # ── Fan Static Pressure Reset (24) ──
    if upgrade_id == 24:
        return hvac_category == "Multizone CAV/VAV"

    # ── VFD Pumps (26) ──
    if upgrade_id == 26:
        return has_boiler or hvac_cool in _CS_HYDRONIC_COOL

    # ── Hydronic GHP (28) ──
    if upgrade_id == 28:
        if is_district:
            return False
        if not has_boiler:
            return False
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        return True

    # ── Packaged GHP (29) ──
    if upgrade_id == 29:
        if is_district:
            return False
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        if hvac_category not in _CS_PACKAGED_CATEGORIES:
            return False
        return True

    # ── Console GHP (30) ──
    if upgrade_id == 30:
        if is_district:
            return False
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        if hvac_category != "Zone-by-Zone":
            return False
        return True

    # ── Chiller Replacement (31) ──
    if upgrade_id == 31:
        return hvac_cool in _CS_CHILLER_COOL

    # ── LED Lighting (43) ──
    if upgrade_id == 43:
        return lighting not in {"gen4_led", "gen5_led"}

    # ── Electric Kitchen Equipment (45) ──
    if upgrade_id == 45:
        return building_type in _CS_FOOD_BUILDINGS

    # ── Wall Insulation (48) ──
    if upgrade_id == 48:
        return wall != "Metal Building"

    # ── Secondary Windows (50) ──
    if upgrade_id == 50:
        return "Triple" not in window

    # ── Window Film (51) ──
    if upgrade_id == 51:
        return "Triple" not in window

    # ── Package 1 (54): Wall + Roof + Windows ──
    if upgrade_id == 54:
        return wall != "Metal Building"

    # ── Package 2 (55): LED + HP-RTU/HP-Boiler ──
    if upgrade_id == 55:
        return lighting not in {"gen4_led", "gen5_led"}

    # ── Package 3 (56): Package 2 with Std HP-RTU ──
    if upgrade_id == 56:
        return lighting not in {"gen4_led", "gen5_led"}

    # ── Package 4 (57): Package 1 + Package 2 ──
    if upgrade_id == 57:
        if wall == "Metal Building":
            return False
        if lighting in {"gen4_led", "gen5_led"}:
            return False
        return True

    # ── Package 5 (58): HP-RTU + Economizer + DCV + ER ──
    if upgrade_id == 58:
        if hvac_category not in _CS_PACKAGED_CATEGORIES:
            return False
        if is_doas:
            return False
        if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
            return False
        return True

    # ── Package 6 (59): GHP variants ──
    # Applicable only if at least one component GHP upgrade applies
    if upgrade_id == 59:
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        return (
            _check_comstock_rules(28, features)
            or _check_comstock_rules(29, features)
            or _check_comstock_rules(30, features)
        )

    # ── Packages 7-9, 12 (60-62, 65): DF/PV combos, no rules ──
    if upgrade_id in {60, 61, 62}:
        return True

    # ── Package 10 (63): Package 1 + Package 6 ──
    if upgrade_id == 63:
        if wall == "Metal Building":
            return False
        # Package 6 must be applicable
        if not _check_comstock_rules(59, features):
            return False
        return True

    # ── Package 11 (64): Package 10 + LED ──
    if upgrade_id == 64:
        if wall == "Metal Building":
            return False
        if not _check_comstock_rules(59, features):
            return False
        if lighting in {"gen4_led", "gen5_led"}:
            return False
        return True

    # ── Fallback: allow unknown upgrade IDs ──
    return True


# ============================================================================
# ResStock rules
# ============================================================================

_RS_DUCTED: Set[str] = {"Ducted Heating", "Ducted Heat Pump"}
_RS_HP_TYPES: Set[str] = {"Ducted Heat Pump", "Non-Ducted Heat Pump"}
_RS_PROPANE_OIL: Set[str] = {"Fuel Oil", "Propane"}
_RS_DUCT_UPGRADES: Set[int] = {13, 15, 18, 30, 31, 32}
_RS_NO_RULES: Set[int] = {0, 3, 6, 7, 8, 9, 11, 12, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29}


def _check_resstock_rules(upgrade_id: int, features: dict) -> bool:
    """Apply ResStock-specific applicability rules."""

    if upgrade_id in _RS_NO_RULES:
        return True

    heating_type = _get(features, "in.hvac_heating_type")
    heating_fuel = _get(features, "in.heating_fuel")
    wall_type = _get(features, "in.geometry_wall_type")
    wh_fuel = _get(features, "in.water_heater_fuel")
    windows = _get(features, "in.windows")
    is_ducted = heating_type in _RS_DUCTED
    is_hp = heating_type in _RS_HP_TYPES

    # ── Gas Furnace 95% (1) ──
    if upgrade_id == 1:
        return heating_fuel == "Natural Gas" and heating_type == "Ducted Heating"

    # ── Propane/Oil Furnace 95% (2) ──
    if upgrade_id == 2:
        return heating_fuel in _RS_PROPANE_OIL and heating_type == "Ducted Heating"

    # ── Cold Climate ASHP (4) ──
    if upgrade_id == 4:
        return not is_hp

    # ── Dual Fuel (5) ──
    if upgrade_id == 5:
        if is_hp:
            return False
        if heating_fuel == "Electricity":
            return False
        return True

    # ── Gas Tankless Water Heater (10) ──
    if upgrade_id == 10:
        return wh_fuel == "Natural Gas"

    # ── Duct Sealing (13), and packages that include duct sealing ──
    if upgrade_id in _RS_DUCT_UPGRADES:
        return is_ducted

    # ── Air Sealing + Attic + Duct + Wall (16): duct + wood frame ──
    if upgrade_id == 16:
        return is_ducted and wall_type == "Wood Frame"

    # ── Drill & Fill Wall Insulation (14) ──
    if upgrade_id == 14:
        return wall_type == "Wood Frame"

    # ── EnergyStar Windows (17) ──
    if upgrade_id == 17:
        return "Triple" not in windows

    return True
