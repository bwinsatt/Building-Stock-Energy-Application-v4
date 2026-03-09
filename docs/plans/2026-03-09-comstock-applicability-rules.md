# ComStock-Aligned Applicability Rules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the minimal V1 applicability rules with comprehensive, ComStock/ResStock-aligned rules that use available XGBoost feature columns to determine measure eligibility.

**Architecture:** Each measure's applicability is determined by inspecting the preprocessed feature dict (post-value-mapping). Rules are organized as lookup tables of feature constraints per upgrade ID, dispatched through the existing `_check_comstock_rules` / `_check_resstock_rules` functions. Package upgrades (ComStock 54-65) compose their component measure rules with AND logic.

**Tech Stack:** Python, pytest

---

## Background: ComStock's Applicability System

ComStock uses per-measure in-code checks against the full EnergyPlus/OpenStudio model. We replicate this logic using the abstracted feature columns available in our XGBoost models. The mapping from ComStock measure checks to our feature columns:

| ComStock Check | Our Feature Column | Available Values |
|---|---|---|
| Single-zone vs multi-zone | `in.hvac_category` | `Small Packaged Unit`, `Multizone CAV/VAV`, `Zone-by-Zone`, `Residential Style Central Systems` |
| DOAS system | `in.hvac_vent_type` | `DOAS+Zone terminal equipment`, `Central Single-zone RTU`, `Central Multi-zone VAV RTU`, `Zone terminal equipment`, `Residential forced air` |
| Heat pump presence | `in.hvac_cool_type` | `ASHP`, `DX`, `ACC`, `WCC`, `District`, `GSHP`, `WSHP` |
| Heat pump presence | `in.hvac_heat_type` | `ASHP`, `Furnace`, `Boiler `, `Electric Resistance`, `District`, `GSHP`, `WSHP` |
| Boiler presence | `in.hvac_heat_type` | check for `Boiler ` (note trailing space in training data) |
| Chiller presence | `in.hvac_cool_type` | check for `ACC` or `WCC` |
| Lighting technology | `in.interior_lighting_generation` | `gen1_t12_incandescent`, `gen2_t8_halogen`, `gen3_t5_cfl`, `gen4_led`, `gen5_led` |
| Wall construction | `in.wall_construction_type` | `Mass`, `Metal Building`, `SteelFramed`, `WoodFramed` |
| Building type | `in.comstock_building_type_group` | `Education`, `Food Sales`, `Food Service`, `Healthcare`, `Lodging`, `Mercantile`, `Office`, `Warehouse and Storage` |
| Heating fuel | `in.heating_fuel` | `NaturalGas`, `Electricity`, `FuelOil`, `Propane`, `DistrictHeating` |

## Upgrade-to-Rule Mapping

### ComStock Upgrades (1-65)

**HP-RTU Variants (1-10):** Replace existing RTU/packaged system with heat pump RTU.
ComStock checks: must be single-zone packaged, not DOAS, not already HP, not VAV/PVAV, not zone terminal, not GSHP/WSHP.
Our rules:
- `in.hvac_category` must be `"Small Packaged Unit"` or `"Residential Style Central Systems"`
- `in.hvac_vent_type` must NOT be `"DOAS+Zone terminal equipment"`
- `in.hvac_cool_type` must NOT be in `{"ASHP", "GSHP", "WSHP"}`
- `in.hvac_heat_type` must NOT be in `{"ASHP", "GSHP", "WSHP"}`

**Advanced RTU (11):** Advanced RTU controls for existing packaged units.
- `in.hvac_category` must be `"Small Packaged Unit"`
- `in.hvac_vent_type` must NOT be `"DOAS+Zone terminal equipment"`

**VRF with DOAS (12):** Replaces system with VRF + DOAS.
- `in.hvac_vent_type` must NOT already be `"DOAS+Zone terminal equipment"` (already has DOAS)
- `in.hvac_cool_type` must NOT be in `{"GSHP", "WSHP"}` (don't replace ground source)

**VRF with Upsizing (13):** VRF system replacement.
- Same as upgrade 12

**DOAS HP Minisplits (14):** Replaces system with DOAS + ductless minisplits.
- `in.hvac_vent_type` must NOT already be `"DOAS+Zone terminal equipment"`
- `in.hvac_cool_type` must NOT be in `{"GSHP", "WSHP"}`

**HP Boiler, Electric Backup (15):** Replace boiler with heat pump boiler.
- `in.hvac_heat_type` must contain `"Boiler"` (has a boiler to replace)

**HP Boiler, Gas Backup (16):** Replace boiler with HP boiler, gas backup.
- `in.hvac_heat_type` must contain `"Boiler"`
- `in.heating_fuel` must be `"NaturalGas"` (needs gas for backup)

**Condensing Gas Boiler (17):** Replace gas boiler with high-efficiency condensing boiler.
- `in.hvac_heat_type` must contain `"Boiler"`
- `in.heating_fuel` must be `"NaturalGas"`

**Electric Resistance Boiler (18):** Replace boiler with electric resistance.
- `in.hvac_heat_type` must contain `"Boiler"`

**Air-Side Economizers (19):** Add economizer to AHU.
ComStock checks: must have outdoor air system, not DOAS, not evap cooler.
- `in.hvac_vent_type` must NOT be in `{"DOAS+Zone terminal equipment", "Zone terminal equipment"}` (no AHU to add economizer to)

**DCV (20):** Add demand-controlled ventilation.
ComStock checks: not DOAS, not hotel/restaurant, must have OA system.
- `in.hvac_vent_type` must NOT be in `{"DOAS+Zone terminal equipment", "Zone terminal equipment"}`
- `in.comstock_building_type_group` must NOT be in `{"Lodging", "Food Service"}` (hotel/restaurant exclusion)

**Energy Recovery (21):** Add energy recovery to AHU.
- `in.hvac_vent_type` must NOT be `"Zone terminal equipment"` (no AHU)

**Advanced RTU Controls (22):** Add advanced controls to RTU.
- `in.hvac_category` must be `"Small Packaged Unit"`

**Unoccupied AHU Control (23):** Schedule-based AHU shutoff.
- `in.hvac_vent_type` must NOT be `"Zone terminal equipment"` (no AHU)

**Fan Static Pressure Reset (24):** For multizone VAV systems.
- `in.hvac_category` must be `"Multizone CAV/VAV"`

**Thermostat Setbacks (25):** Broadly applicable, no exclusions.

**VFD Pumps (26):** Variable-frequency drives on pumps (hydronic systems).
- `in.hvac_heat_type` must contain `"Boiler"` OR `in.hvac_cool_type` must be in `{"WCC", "District"}` (needs hydronic loop)

**Ideal Thermal Air Loads (27):** Modeling construct (theoretical max savings). No exclusions.

**Hydronic GHP (28):** Water-to-water geothermal replacing boiler+chiller.
- `in.hvac_heat_type` must contain `"Boiler"` (hydronic heating to replace)
- `in.hvac_cool_type` must NOT be in `{"GSHP", "WSHP"}` (not already geothermal)

**Packaged GHP (29):** Water-to-air geothermal replacing packaged systems.
- `in.hvac_cool_type` must NOT be in `{"GSHP", "WSHP"}`
- `in.hvac_category` must be `"Small Packaged Unit"` or `"Residential Style Central Systems"`

**Console GHP (30):** Water-to-air geothermal replacing zone terminal equipment.
- `in.hvac_cool_type` must NOT be in `{"GSHP", "WSHP"}`
- `in.hvac_category` must be `"Zone-by-Zone"`

**Chiller Replacement (31):** Replace chiller with higher efficiency.
- `in.hvac_cool_type` must be in `{"WCC", "ACC"}` (has a chiller)

**Demand Flexibility (32-42):** Controls-based, broadly applicable. No exclusions.

**LED Lighting (43):** Replace non-LED lighting with LED.
- `in.interior_lighting_generation` must NOT be in `{"gen4_led", "gen5_led"}` (not already LED)

**Lighting Controls (44):** Add lighting controls. No exclusions.

**Electric Kitchen Equipment (45):** Replace gas kitchen equipment.
- `in.comstock_building_type_group` must be in `{"Food Sales", "Food Service"}` (has kitchen equipment)
- `in.heating_fuel` should NOT be `"Electricity"` (already electric, though this checks heating not kitchen specifically — conservative approach: no fuel check, just building type)

**PV (46) and PV + Battery (47):** Broadly applicable. No exclusions.

**Wall Insulation (48):** Add exterior wall insulation.
ComStock checks: must not be Metal Building, must have low enough R-value.
- `in.wall_construction_type` must NOT be `"Metal Building"`

**Roof Insulation (49):** No exclusions.

**Secondary Windows (50):** Add storm/secondary windows.
- `in.window_type` should NOT already be triple-pane (contains "Triple")

**Window Film (51):** Apply window film.
- `in.window_type` should NOT already be triple-pane (contains "Triple")

**New Windows (52):** Full window replacement. No exclusions.

**Code Envelope (53):** Bring envelope to code. No exclusions.

**Package 1 (54):** Wall + Roof Insulation + New Windows.
- Same as upgrade 48 (wall insulation is most restrictive): `in.wall_construction_type` != `"Metal Building"`

**Package 2 (55):** LED + Variable Speed HP RTU or HP Boilers.
- LED rule (not already LED) AND (HP-RTU rules OR boiler rules)
- Simplified: `in.interior_lighting_generation` NOT in `{"gen4_led", "gen5_led"}`
- Note: The HP-RTU/boiler part is "or" so at least one HVAC measure applies. For simplicity, only enforce the LED constraint since that's the universal component.

**Package 3 (56):** Same as Package 2 but Standard Performance HP RTU.
- Same rules as 55.

**Package 4 (57):** Package 1 + Package 2.
- Combines 54 and 55 rules: wall not Metal Building AND lighting not already LED.

**Package 5 (58):** HP RTU + Economizer + DCV + Energy Recovery.
- HP-RTU rules apply (most restrictive): `in.hvac_category` in `{"Small Packaged Unit", "Residential Style Central Systems"}`, not DOAS, not already HP/GSHP/WSHP.

**Package 6 (59):** Hydronic/Packaged/Console GHP.
- Not already GSHP/WSHP: `in.hvac_cool_type` NOT in `{"GSHP", "WSHP"}`

**Package 7 (60):** Demand Flexibility Lighting + Thermostat. No exclusions.

**Package 8 (61):** DF + Lighting + Thermostat + PV. No exclusions.

**Package 9 (62):** DF + Lighting + Thermostat. No exclusions.

**Package 10 (63):** Package 1 + Package 6.
- Wall not Metal Building AND not already GSHP/WSHP.

**Package 11 (64):** Package 10 + LED.
- Wall not Metal Building AND not already GSHP/WSHP AND not already LED.

**Package 12 (65):** PV + Roof Insulation. No exclusions.

### ResStock Upgrades (1-32)

**Gas Furnace 95% (1):** High-eff gas furnace.
- `in.heating_fuel` must be `"Natural Gas"`
- `in.hvac_heating_type` must be `"Ducted Heating"` (has ducts for furnace)

**Propane/Oil Furnace 95% (2):** High-eff propane/oil furnace.
- `in.heating_fuel` must be in `{"Fuel Oil", "Propane"}`
- `in.hvac_heating_type` must be `"Ducted Heating"`

**Min Eff Boilers/Furnaces/AC (3):** Broadly applicable (brings to min code). No exclusions.

**Cold Climate Ducted ASHP (4):** Replace heating with ducted ASHP.
- `in.hvac_heating_type` must NOT be `"Ducted Heat Pump"` (not already ASHP)

**Dual Fuel Heating (5):** HP + gas backup.
- `in.hvac_heating_type` must NOT be `"Ducted Heat Pump"` or `"Non-Ducted Heat Pump"` (not already HP)
- `in.heating_fuel` must NOT be `"Electricity"` (needs fossil fuel backup)

**GHP Variants (6-8):** Geothermal heat pump replacement.
- `in.hvac_heating_type` must NOT already be `"Ducted Heat Pump"` or `"Non-Ducted Heat Pump"` (conservative; no way to identify GHP specifically in ResStock features)
- Note: ResStock doesn't have a GSHP-specific heating type, so this is approximate

**HP Water Heater (9):** Replace water heater with heat pump.
- `in.water_heater_fuel` should NOT already be `"Electricity"` with HP efficiency
- Simplified: no exclusion (broadly applicable)

**Gas Tankless WH (10):** High-eff gas tankless.
- `in.water_heater_fuel` must be `"Natural Gas"`

**Air Sealing (11):** Broadly applicable. No exclusions.

**Attic Insulation (12):** For unfinished attics. No exclusion (can't determine attic type from features).

**Duct Sealing (13):** For ducted systems.
- `in.hvac_heating_type` must be `"Ducted Heating"` or `"Ducted Heat Pump"` (must have ducts)

**Drill & Fill Wall Insulation (14):** Wall cavity insulation.
- `in.geometry_wall_type` should be `"Wood Frame"` (drill & fill is for wood frame walls with cavities)

**Air Sealing + Attic + Duct (15):** Combined envelope.
- `in.hvac_heating_type` must be `"Ducted Heating"` or `"Ducted Heat Pump"` (duct sealing component)

**Air Sealing + Attic + Duct + Wall (16):** Combined envelope.
- Same as 15 (duct sealing) AND `in.geometry_wall_type` should be `"Wood Frame"` (wall insulation component)

**EnergyStar Windows (17):** Window replacement.
- `in.windows` should NOT already contain `"Triple"` (already high-performance)

**Package GHP + Envelope (18):** GHP + air sealing + attic + duct.
- Same as GHP rules (6-8) AND duct sealing rules (13)

**EV Adoption (19-23):** Not building-characteristic-dependent. No exclusions.

**HVAC Demand Flexibility (24-28):** Broadly applicable. No exclusions.

**General Air Sealing (29):** No exclusions.

**Air Sealing + Attic + Duct (30):** Same as 15.

**GHP + Envelope Packages (31-32):** Same as 18.

---

## Task 1: Refactor Applicability Rules with ComStock-Aligned Logic

**Files:**
- Modify: `backend/app/inference/applicability.py`
- Test: `backend/tests/test_applicability.py` (create)

**Step 1: Write comprehensive tests for ComStock rules**

Create `backend/tests/test_applicability.py`:

```python
"""Tests for upgrade applicability rules aligned with ComStock/ResStock measures."""

import pytest
from app.inference.applicability import check_applicability, get_applicable_upgrades


# ── Helpers ──────────────────────────────────────────────────────────────────

# All upgrade IDs as "available" so we only test rule logic, not model existence
ALL_COMSTOCK = set(range(0, 66))
ALL_RESSTOCK = set(range(0, 33))


def _comstock_features(**overrides):
    """Return a typical ComStock feature dict with overrides."""
    base = {
        "in.comstock_building_type_group": "Office",
        "in.hvac_category": "Small Packaged Unit",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Central Single-zone RTU",
        "in.hvac_system_type": "PSZ-AC with gas coil",
        "in.interior_lighting_generation": "gen2_t8_halogen",
        "in.wall_construction_type": "Mass",
        "in.heating_fuel": "NaturalGas",
        "in.window_type": "Double - No LowE - Clear - Aluminum",
    }
    base.update(overrides)
    return base


def _resstock_features(**overrides):
    """Return a typical ResStock feature dict with overrides."""
    base = {
        "in.geometry_building_type_recs": "Multi-Family with 5+ Units",
        "in.hvac_heating_type": "Ducted Heating",
        "in.hvac_cooling_type": "Central AC",
        "in.heating_fuel": "Natural Gas",
        "in.water_heater_fuel": "Natural Gas",
        "in.geometry_wall_type": "Wood Frame",
        "in.windows": "Double, Clear, Metal, Air",
        "in.lighting": "100% CFL",
    }
    base.update(overrides)
    return base


# ── ComStock HP-RTU (1-10) ──────────────────────────────────────────────────

class TestComstockHpRtu:
    """HP-RTU upgrades require single-zone packaged, not DOAS, not already HP."""

    @pytest.mark.parametrize("uid", range(1, 11))
    def test_applicable_for_packaged_dx_system(self, uid):
        features = _comstock_features()
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", range(1, 11))
    def test_skip_when_multizone_vav(self, uid):
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", range(1, 11))
    def test_skip_when_zone_by_zone(self, uid):
        features = _comstock_features(**{"in.hvac_category": "Zone-by-Zone"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", range(1, 11))
    def test_skip_when_doas(self, uid):
        features = _comstock_features(**{
            "in.hvac_vent_type": "DOAS+Zone terminal equipment",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", range(1, 11))
    def test_skip_when_already_ashp(self, uid):
        features = _comstock_features(**{"in.hvac_cool_type": "ASHP"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", range(1, 11))
    def test_skip_when_already_gshp(self, uid):
        features = _comstock_features(**{"in.hvac_cool_type": "GSHP"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Advanced RTU (11) ──────────────────────────────────────────────

class TestComstockAdvancedRtu:
    def test_applicable_for_packaged(self):
        features = _comstock_features()
        assert check_applicability(11, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_when_not_packaged(self):
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(11, "comstock", features, ALL_COMSTOCK) is False

    def test_skip_when_doas(self):
        features = _comstock_features(**{
            "in.hvac_vent_type": "DOAS+Zone terminal equipment",
        })
        assert check_applicability(11, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock VRF/Minisplit (12-14) ──────────────────────────────────────────

class TestComstockVrfMinisplit:
    @pytest.mark.parametrize("uid", [12, 13, 14])
    def test_applicable_for_standard_system(self, uid):
        features = _comstock_features()
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", [12, 13, 14])
    def test_skip_when_already_doas(self, uid):
        features = _comstock_features(**{
            "in.hvac_vent_type": "DOAS+Zone terminal equipment",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", [12, 13, 14])
    def test_skip_when_already_gshp(self, uid):
        features = _comstock_features(**{"in.hvac_cool_type": "GSHP"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Boiler Upgrades (15-18) ────────────────────────────────────────

class TestComstockBoilers:
    @pytest.mark.parametrize("uid", [15, 16, 17, 18])
    def test_applicable_when_has_boiler(self, uid):
        features = _comstock_features(**{"in.hvac_heat_type": "Boiler "})
        if uid in (16, 17):
            features["in.heating_fuel"] = "NaturalGas"
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", [15, 16, 17, 18])
    def test_skip_when_no_boiler(self, uid):
        features = _comstock_features(**{"in.hvac_heat_type": "Furnace"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    def test_hp_boiler_gas_backup_skip_when_electric(self):
        features = _comstock_features(**{
            "in.hvac_heat_type": "Boiler ",
            "in.heating_fuel": "Electricity",
        })
        assert check_applicability(16, "comstock", features, ALL_COMSTOCK) is False

    def test_condensing_gas_boiler_skip_when_electric(self):
        features = _comstock_features(**{
            "in.hvac_heat_type": "Boiler ",
            "in.heating_fuel": "Electricity",
        })
        assert check_applicability(17, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Controls (19-24) ───────────────────────────────────────────────

class TestComstockControls:
    def test_economizer_applicable(self):
        features = _comstock_features()
        assert check_applicability(19, "comstock", features, ALL_COMSTOCK) is True

    def test_economizer_skip_zone_terminal(self):
        features = _comstock_features(**{
            "in.hvac_vent_type": "Zone terminal equipment",
        })
        assert check_applicability(19, "comstock", features, ALL_COMSTOCK) is False

    def test_economizer_skip_doas(self):
        features = _comstock_features(**{
            "in.hvac_vent_type": "DOAS+Zone terminal equipment",
        })
        assert check_applicability(19, "comstock", features, ALL_COMSTOCK) is False

    def test_dcv_skip_food_service(self):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Food Service",
        })
        assert check_applicability(20, "comstock", features, ALL_COMSTOCK) is False

    def test_dcv_skip_lodging(self):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Lodging",
        })
        assert check_applicability(20, "comstock", features, ALL_COMSTOCK) is False

    def test_dcv_applicable_for_office(self):
        features = _comstock_features()
        assert check_applicability(20, "comstock", features, ALL_COMSTOCK) is True

    def test_advanced_rtu_controls_needs_packaged(self):
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(22, "comstock", features, ALL_COMSTOCK) is False

    def test_fan_static_pressure_reset_needs_multizone(self):
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(24, "comstock", features, ALL_COMSTOCK) is True

    def test_fan_static_pressure_reset_skip_packaged(self):
        features = _comstock_features()  # Small Packaged Unit
        assert check_applicability(24, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock VFD Pumps (26) ─────────────────────────────────────────────────

class TestComstockVfdPumps:
    def test_applicable_when_boiler(self):
        features = _comstock_features(**{"in.hvac_heat_type": "Boiler "})
        assert check_applicability(26, "comstock", features, ALL_COMSTOCK) is True

    def test_applicable_when_chiller(self):
        features = _comstock_features(**{"in.hvac_cool_type": "WCC"})
        assert check_applicability(26, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_when_no_hydronic(self):
        features = _comstock_features()  # DX + Furnace
        assert check_applicability(26, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock GHP (28-30) ───────────────────────────────────────────────────

class TestComstockGhp:
    def test_hydronic_ghp_applicable_when_boiler(self):
        features = _comstock_features(**{
            "in.hvac_heat_type": "Boiler ",
            "in.hvac_cool_type": "WCC",
        })
        assert check_applicability(28, "comstock", features, ALL_COMSTOCK) is True

    def test_hydronic_ghp_skip_when_no_boiler(self):
        features = _comstock_features()
        assert check_applicability(28, "comstock", features, ALL_COMSTOCK) is False

    def test_packaged_ghp_applicable(self):
        features = _comstock_features()
        assert check_applicability(29, "comstock", features, ALL_COMSTOCK) is True

    def test_packaged_ghp_skip_when_already_gshp(self):
        features = _comstock_features(**{"in.hvac_cool_type": "GSHP"})
        assert check_applicability(29, "comstock", features, ALL_COMSTOCK) is False

    def test_packaged_ghp_skip_when_not_packaged(self):
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(29, "comstock", features, ALL_COMSTOCK) is False

    def test_console_ghp_applicable_zone_by_zone(self):
        features = _comstock_features(**{"in.hvac_category": "Zone-by-Zone"})
        assert check_applicability(30, "comstock", features, ALL_COMSTOCK) is True

    def test_console_ghp_skip_when_not_zone_by_zone(self):
        features = _comstock_features()  # Small Packaged Unit
        assert check_applicability(30, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Chiller (31) ──────────────────────────────────────────────────

class TestComstockChiller:
    def test_applicable_when_water_cooled_chiller(self):
        features = _comstock_features(**{"in.hvac_cool_type": "WCC"})
        assert check_applicability(31, "comstock", features, ALL_COMSTOCK) is True

    def test_applicable_when_air_cooled_chiller(self):
        features = _comstock_features(**{"in.hvac_cool_type": "ACC"})
        assert check_applicability(31, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_when_dx(self):
        features = _comstock_features()  # DX
        assert check_applicability(31, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock LED (43) ──────────────────────────────────────────────────────

class TestComstockLed:
    def test_applicable_when_t8(self):
        features = _comstock_features(**{
            "in.interior_lighting_generation": "gen2_t8_halogen",
        })
        assert check_applicability(43, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_when_gen4_led(self):
        features = _comstock_features(**{
            "in.interior_lighting_generation": "gen4_led",
        })
        assert check_applicability(43, "comstock", features, ALL_COMSTOCK) is False

    def test_skip_when_gen5_led(self):
        features = _comstock_features(**{
            "in.interior_lighting_generation": "gen5_led",
        })
        assert check_applicability(43, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Kitchen Equipment (45) ────────────────────────────────────────

class TestComstockKitchen:
    def test_applicable_for_food_service(self):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Food Service",
        })
        assert check_applicability(45, "comstock", features, ALL_COMSTOCK) is True

    def test_applicable_for_food_sales(self):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Food Sales",
        })
        assert check_applicability(45, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_for_office(self):
        features = _comstock_features()  # Office
        assert check_applicability(45, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Envelope (48-53) ──────────────────────────────────────────────

class TestComstockEnvelope:
    def test_wall_insulation_applicable(self):
        features = _comstock_features(**{
            "in.wall_construction_type": "Mass",
        })
        assert check_applicability(48, "comstock", features, ALL_COMSTOCK) is True

    def test_wall_insulation_skip_metal_building(self):
        features = _comstock_features(**{
            "in.wall_construction_type": "Metal Building",
        })
        assert check_applicability(48, "comstock", features, ALL_COMSTOCK) is False

    def test_secondary_windows_skip_triple(self):
        features = _comstock_features(**{
            "in.window_type": "Triple - LowE - Clear - Thermally Broken Aluminum",
        })
        assert check_applicability(50, "comstock", features, ALL_COMSTOCK) is False

    def test_window_film_skip_triple(self):
        features = _comstock_features(**{
            "in.window_type": "Triple - LowE - Clear - Thermally Broken Aluminum",
        })
        assert check_applicability(51, "comstock", features, ALL_COMSTOCK) is False


# ── ComStock Packages ──────────────────────────────────────────────────────

class TestComstockPackages:
    def test_package1_skip_metal_building(self):
        """Package 1 includes wall insulation, so metal building excluded."""
        features = _comstock_features(**{
            "in.wall_construction_type": "Metal Building",
        })
        assert check_applicability(54, "comstock", features, ALL_COMSTOCK) is False

    def test_package2_skip_already_led(self):
        """Package 2 includes LED, skip if already LED."""
        features = _comstock_features(**{
            "in.interior_lighting_generation": "gen4_led",
        })
        assert check_applicability(55, "comstock", features, ALL_COMSTOCK) is False

    def test_package5_skip_when_multizone(self):
        """Package 5 is HP-RTU based, skip if multizone."""
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(58, "comstock", features, ALL_COMSTOCK) is False

    def test_package6_skip_already_gshp(self):
        """Package 6 is GHP, skip if already geothermal."""
        features = _comstock_features(**{"in.hvac_cool_type": "GSHP"})
        assert check_applicability(59, "comstock", features, ALL_COMSTOCK) is False

    def test_package10_skip_metal_and_gshp(self):
        """Package 10 = Package 1 + Package 6."""
        features = _comstock_features(**{
            "in.wall_construction_type": "Metal Building",
        })
        assert check_applicability(63, "comstock", features, ALL_COMSTOCK) is False

    def test_package11_skip_already_led(self):
        """Package 11 = Package 10 + LED."""
        features = _comstock_features(**{
            "in.interior_lighting_generation": "gen4_led",
        })
        assert check_applicability(64, "comstock", features, ALL_COMSTOCK) is False


# ── ResStock HVAC ──────────────────────────────────────────────────────────

class TestResstockHvac:
    def test_gas_furnace_applicable(self):
        features = _resstock_features()
        assert check_applicability(1, "resstock", features, ALL_RESSTOCK) is True

    def test_gas_furnace_skip_when_electric(self):
        features = _resstock_features(**{"in.heating_fuel": "Electricity"})
        assert check_applicability(1, "resstock", features, ALL_RESSTOCK) is False

    def test_gas_furnace_skip_when_not_ducted(self):
        features = _resstock_features(**{
            "in.hvac_heating_type": "Non-Ducted Heating",
        })
        assert check_applicability(1, "resstock", features, ALL_RESSTOCK) is False

    def test_propane_oil_furnace_applicable(self):
        features = _resstock_features(**{"in.heating_fuel": "Fuel Oil"})
        assert check_applicability(2, "resstock", features, ALL_RESSTOCK) is True

    def test_propane_oil_furnace_skip_gas(self):
        features = _resstock_features()  # Natural Gas
        assert check_applicability(2, "resstock", features, ALL_RESSTOCK) is False

    def test_ashp_skip_when_already_ducted_hp(self):
        features = _resstock_features(**{
            "in.hvac_heating_type": "Ducted Heat Pump",
        })
        assert check_applicability(4, "resstock", features, ALL_RESSTOCK) is False

    def test_ashp_applicable_for_ducted_heating(self):
        features = _resstock_features()
        assert check_applicability(4, "resstock", features, ALL_RESSTOCK) is True

    def test_dual_fuel_skip_when_electric(self):
        features = _resstock_features(**{"in.heating_fuel": "Electricity"})
        assert check_applicability(5, "resstock", features, ALL_RESSTOCK) is False

    def test_dual_fuel_skip_when_already_hp(self):
        features = _resstock_features(**{
            "in.hvac_heating_type": "Ducted Heat Pump",
        })
        assert check_applicability(5, "resstock", features, ALL_RESSTOCK) is False


# ── ResStock Water Heater ──────────────────────────────────────────────────

class TestResstockWaterHeater:
    def test_gas_tankless_applicable(self):
        features = _resstock_features()
        assert check_applicability(10, "resstock", features, ALL_RESSTOCK) is True

    def test_gas_tankless_skip_when_electric(self):
        features = _resstock_features(**{"in.water_heater_fuel": "Electricity"})
        assert check_applicability(10, "resstock", features, ALL_RESSTOCK) is False


# ── ResStock Envelope ──────────────────────────────────────────────────────

class TestResstockEnvelope:
    def test_duct_sealing_applicable_ducted(self):
        features = _resstock_features()
        assert check_applicability(13, "resstock", features, ALL_RESSTOCK) is True

    def test_duct_sealing_skip_non_ducted(self):
        features = _resstock_features(**{
            "in.hvac_heating_type": "Non-Ducted Heating",
        })
        assert check_applicability(13, "resstock", features, ALL_RESSTOCK) is False

    def test_drill_fill_wall_applicable_wood_frame(self):
        features = _resstock_features()  # Wood Frame
        assert check_applicability(14, "resstock", features, ALL_RESSTOCK) is True

    def test_drill_fill_wall_skip_brick(self):
        features = _resstock_features(**{"in.geometry_wall_type": "Brick"})
        assert check_applicability(14, "resstock", features, ALL_RESSTOCK) is False

    def test_energystar_windows_skip_triple(self):
        features = _resstock_features(**{
            "in.windows": "Triple, Low-E, Non-metal, Air, L-Gain",
        })
        assert check_applicability(17, "resstock", features, ALL_RESSTOCK) is False


# ── ResStock Packages ──────────────────────────────────────────────────────

class TestResstockPackages:
    def test_package_ghp_envelope_skip_non_ducted(self):
        """Package 18 includes duct sealing, needs ducts."""
        features = _resstock_features(**{
            "in.hvac_heating_type": "Non-Ducted Heating",
        })
        assert check_applicability(18, "resstock", features, ALL_RESSTOCK) is False

    def test_combined_envelope_skip_non_ducted(self):
        """Upgrade 15 (air seal + attic + duct) needs ducts."""
        features = _resstock_features(**{
            "in.hvac_heating_type": "Non-Ducted Heating",
        })
        assert check_applicability(15, "resstock", features, ALL_RESSTOCK) is False


# ── Edge Cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_upgrade_not_in_available_returns_false(self):
        features = _comstock_features()
        assert check_applicability(43, "comstock", features, set()) is False

    def test_unknown_dataset_returns_true(self):
        features = _comstock_features()
        assert check_applicability(43, "unknown", features, ALL_COMSTOCK) is True

    def test_baseline_always_applicable(self):
        features = _comstock_features()
        assert check_applicability(0, "comstock", features, ALL_COMSTOCK) is True
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py -v --tb=short 2>&1 | tail -40`
Expected: Many FAILED (current rules are too simple)

**Step 3: Implement the comprehensive applicability rules**

Replace the contents of `backend/app/inference/applicability.py` with:

```python
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
_CS_LED: Set[int] = {43, 44}                      # LED lighting (43 only has LED rule; 44 has none)
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
        if hvac_cool in _CS_GHP_NOT_ALREADY:
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
        if not has_boiler:
            return False
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        return True

    # ── Packaged GHP (29) ──
    if upgrade_id == 29:
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        if hvac_category not in _CS_PACKAGED_CATEGORIES:
            return False
        return True

    # ── Console GHP (30) ──
    if upgrade_id == 30:
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
    if upgrade_id == 59:
        return hvac_cool not in _CS_GHP_NOT_ALREADY

    # ── Packages 7-9, 12 (60-62, 65): DF/PV combos, no rules ──
    if upgrade_id in {60, 61, 62}:
        return True

    # ── Package 10 (63): Package 1 + Package 6 ──
    if upgrade_id == 63:
        if wall == "Metal Building":
            return False
        if hvac_cool in _CS_GHP_NOT_ALREADY:
            return False
        return True

    # ── Package 11 (64): Package 10 + LED ──
    if upgrade_id == 64:
        if wall == "Metal Building":
            return False
        if hvac_cool in _CS_GHP_NOT_ALREADY:
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
_RS_DUCT_UPGRADES: Set[int] = {13, 15, 16, 18, 30, 31, 32}
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

    # ── Drill & Fill Wall Insulation (14) ──
    if upgrade_id == 14:
        return wall_type == "Wood Frame"

    # ── EnergyStar Windows (17) ──
    if upgrade_id == 17:
        return "Triple" not in windows

    return True
```

**Step 4: Run all tests**

Run: `cd backend && pytest tests/test_applicability.py -v`
Expected: ALL PASS

**Step 5: Run existing test suite to check for regressions**

Run: `cd backend && pytest`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "feat: implement ComStock/ResStock-aligned applicability rules

Replace minimal V1 rules with comprehensive measure applicability
checks derived from NREL ComStock/ResStock measure source code.
Rules use available XGBoost feature columns (hvac_category,
hvac_cool_type, hvac_heat_type, hvac_vent_type, lighting,
wall construction, building type, heating fuel) to determine
upgrade eligibility for all 66 ComStock and 33 ResStock measures."
```

---

## Reference: Upgrade ID Quick-Reference

### ComStock (0-65)
| ID | Measure | Key Rule |
|---|---|---|
| 0 | Baseline | Always applicable |
| 1-10 | HP-RTU variants | Packaged unit, not DOAS, not already HP |
| 11 | Advanced RTU | Small Packaged Unit, not DOAS |
| 12-14 | VRF / Minisplit | Not DOAS, not GSHP/WSHP |
| 15 | HP Boiler (elec backup) | Must have boiler |
| 16 | HP Boiler (gas backup) | Must have boiler + gas fuel |
| 17 | Condensing Gas Boiler | Must have boiler + gas fuel |
| 18 | Electric Boiler | Must have boiler |
| 19 | Economizer | Has AHU (not zone terminal/DOAS) |
| 20 | DCV | Has AHU, not hotel/restaurant |
| 21 | Energy Recovery | Not zone terminal only |
| 22 | Advanced RTU Controls | Small Packaged Unit |
| 23 | Unoccupied AHU Control | Not zone terminal only |
| 24 | Fan Static Pressure Reset | Multizone CAV/VAV |
| 25 | Thermostat Setbacks | No rules |
| 26 | VFD Pumps | Has boiler or chiller (hydronic) |
| 27 | Ideal Thermal Air Loads | No rules |
| 28 | Hydronic GHP | Has boiler, not already GHP |
| 29 | Packaged GHP | Packaged unit, not already GHP |
| 30 | Console GHP | Zone-by-Zone, not already GHP |
| 31 | Chiller Replacement | Has chiller (WCC/ACC) |
| 32-42 | Demand Flexibility | No rules |
| 43 | LED Lighting | Not already LED |
| 44 | Lighting Controls | No rules |
| 45 | Electric Kitchen Equip | Food Sales/Service only |
| 46-47 | PV / PV+Battery | No rules |
| 48 | Wall Insulation | Not Metal Building |
| 49 | Roof Insulation | No rules |
| 50 | Secondary Windows | Not triple-pane |
| 51 | Window Film | Not triple-pane |
| 52 | New Windows | No rules |
| 53 | Code Envelope | No rules |
| 54 | Pkg 1 (envelope) | Not Metal Building |
| 55-56 | Pkg 2-3 (LED+HVAC) | Not already LED |
| 57 | Pkg 4 (1+2) | Not Metal Building, not LED |
| 58 | Pkg 5 (HP-RTU+controls) | HP-RTU rules |
| 59 | Pkg 6 (GHP) | Not already GHP |
| 60-62 | Pkg 7-9 (DF) | No rules |
| 63 | Pkg 10 (envelope+GHP) | Not Metal Building, not GHP |
| 64 | Pkg 11 (10+LED) | Not Metal Building, not GHP, not LED |
| 65 | Pkg 12 (PV+roof) | No rules |

### ResStock (0-32)
| ID | Measure | Key Rule |
|---|---|---|
| 0 | Baseline | No rules |
| 1 | Gas Furnace 95% | Gas + Ducted Heating |
| 2 | Propane/Oil Furnace 95% | Propane/Oil + Ducted |
| 3 | Min Eff HVAC | No rules |
| 4 | Cold Climate ASHP | Not already HP |
| 5 | Dual Fuel | Not HP, not electric |
| 6-8 | GHP variants | No rules |
| 9 | HP Water Heater | No rules |
| 10 | Gas Tankless WH | Gas water heater fuel |
| 11-12 | Air Seal / Attic | No rules |
| 13 | Duct Sealing | Must be ducted |
| 14 | Drill & Fill Wall | Wood Frame only |
| 15-16 | Envelope combos | Must be ducted (duct component) |
| 17 | EnergyStar Windows | Not triple-pane |
| 18 | GHP + Envelope pkg | Must be ducted |
| 19-23 | EV Adoption | No rules |
| 24-28 | HVAC Demand Flex | No rules |
| 29 | General Air Sealing | No rules |
| 30 | Air Seal+Attic+Duct | Must be ducted |
| 31-32 | GHP+Envelope pkgs | Must be ducted |
