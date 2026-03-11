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
    @pytest.mark.parametrize("uid", [12, 13])
    def test_applicable_for_standard_system(self, uid):
        features = _comstock_features()
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", [12, 13])
    def test_skip_when_already_doas(self, uid):
        features = _comstock_features(**{
            "in.hvac_vent_type": "DOAS+Zone terminal equipment",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", [12, 13])
    def test_skip_when_already_gshp(self, uid):
        features = _comstock_features(**{"in.hvac_cool_type": "GSHP"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", [12, 13])
    def test_skip_when_already_ashp(self, uid):
        """VRF excludes buildings already with ASHP."""
        features = _comstock_features(**{"in.hvac_cool_type": "ASHP"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", [12, 13])
    def test_skip_when_district_cooling(self, uid):
        """VRF excludes buildings with district cooling."""
        features = _comstock_features(**{"in.hvac_cool_type": "District"})
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", [12, 13])
    def test_applicable_when_district_heat_but_dx_cool(self, uid):
        """VRF allows district-heat buildings if cooling is conventional."""
        features = _comstock_features(**{
            "in.hvac_heat_type": "District",
            "in.hvac_cool_type": "DX",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True


# ── ComStock DOAS HP Minisplits (14) ──────────────────────────────────────

class TestComstockDoasMinisplit:
    """DOAS HP Minisplits (14) require single-zone packaged, not already HP."""

    def test_applicable_for_packaged_system(self):
        features = _comstock_features()  # Small Packaged Unit
        assert check_applicability(14, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_when_multizone_vav(self):
        features = _comstock_features(**{"in.hvac_category": "Multizone CAV/VAV"})
        assert check_applicability(14, "comstock", features, ALL_COMSTOCK) is False

    def test_skip_when_zone_by_zone(self):
        features = _comstock_features(**{"in.hvac_category": "Zone-by-Zone"})
        assert check_applicability(14, "comstock", features, ALL_COMSTOCK) is False

    def test_skip_when_already_gshp(self):
        features = _comstock_features(**{"in.hvac_cool_type": "GSHP"})
        assert check_applicability(14, "comstock", features, ALL_COMSTOCK) is False

    def test_skip_when_already_ashp(self):
        features = _comstock_features(**{"in.hvac_cool_type": "ASHP"})
        assert check_applicability(14, "comstock", features, ALL_COMSTOCK) is False


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

    def test_hydronic_ghp_skip_when_boiler_but_no_chiller(self):
        """Hydronic GHP requires both boiler AND chiller."""
        features = _comstock_features(**{
            "in.hvac_heat_type": "Boiler ",
            "in.hvac_cool_type": "DX",
        })
        assert check_applicability(28, "comstock", features, ALL_COMSTOCK) is False

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

    def test_combined_envelope_wall_skip_non_ducted(self):
        """Upgrade 16 (air seal + attic + duct + wall) needs ducts."""
        features = _resstock_features(**{
            "in.hvac_heating_type": "Non-Ducted Heating",
        })
        assert check_applicability(16, "resstock", features, ALL_RESSTOCK) is False

    def test_combined_envelope_wall_skip_non_wood_frame(self):
        """Upgrade 16 includes wall insulation, needs Wood Frame."""
        features = _resstock_features(**{"in.geometry_wall_type": "Brick"})
        assert check_applicability(16, "resstock", features, ALL_RESSTOCK) is False

    def test_combined_envelope_wall_applicable(self):
        """Upgrade 16 applies when ducted + wood frame."""
        features = _resstock_features()  # Ducted Heating + Wood Frame
        assert check_applicability(16, "resstock", features, ALL_RESSTOCK) is True


# ── get_applicable_upgrades ───────────────────────────────────────────────

class TestGetApplicableUpgrades:
    def test_filters_by_rules_and_availability(self):
        features = _comstock_features(**{
            "in.interior_lighting_generation": "gen4_led",
        })
        available = {0, 1, 43}  # baseline, HP-RTU 1, LED
        result = get_applicable_upgrades("comstock", features, available)
        assert 0 in result      # baseline always applicable
        assert 1 in result      # HP-RTU applicable for packaged DX
        assert 43 not in result  # LED skipped (already LED)

    def test_returns_sorted(self):
        features = _comstock_features()
        available = {5, 1, 3, 0}
        result = get_applicable_upgrades("comstock", features, available)
        assert result == sorted(result)


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
