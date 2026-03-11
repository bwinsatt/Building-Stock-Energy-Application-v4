# Applicability Rules Audit: Our Implementation vs ComStock/ResStock Source

**Date:** 2026-03-10
**Scope:** All ComStock upgrades 1-65 and ResStock upgrades 1-32
**Method:** Compared `applicability.py` rules against `measure.rb` applicability checks fetched from NREL/ComStock GitHub repo (`main` branch) and ResStock upgrade YAML (`develop` branch)

---

## Executive Summary

Audited all applicability rules in `backend/app/inference/applicability.py` against the actual NREL source code. Found **5 critical gaps**, **6 moderate gaps**, and **4 minor issues**. Critical gaps include missing district energy exclusions for VRF measures, missing chiller requirement for hydronic GHP, and demand flexibility being too broadly applied.

---

## ComStock Findings

### CRITICAL — Missing exclusions that could cause incorrect costs/savings

#### 1. VRF (12-13): Missing district COOLING exclusion
- **ComStock source** (`upgrade_hvac_vrf_hr_doas/measure.rb`): Checks `air_loop_hvac_served_by_district_energy?` → not applicable
- **Training data validation**: 435 district-HEAT buildings (with DX cooling) correctly got VRF with real savings (mean 6.3 kWh/ft²). 0 district-COOL buildings got VRF. 0 district-heat+district-cool buildings got VRF.
- **Our code**: No district check for VRF — allows district-cool buildings through
- **Impact**: District-cooled buildings could get VRF recommended incorrectly
- **Fix**: Add `if hvac_cool == "District": return False` to VRF block (NOT a blanket `is_district` check — district-heat with DX-cool is valid)

#### 2. VRF (12-14): Missing existing ASHP exclusion
- **ComStock source**: Excludes DX heating coils or name containing "HP"/"heat pump" — covers ASHP, GSHP, WSHP
- **Training data validation**: 0 out of 17,694 ASHP buildings received VRF (upgrades 12/13). Confirms ASHP should be excluded.
- **Our code**: Only excludes `_CS_GHP_NOT_ALREADY = {"GSHP", "WSHP"}`, missing ASHP. Currently works by accident (ASHP buildings excluded by other feature combinations), but is not robust.
- **Fix**: Use `_CS_HP_NOT_ALREADY` (includes ASHP) instead of `_CS_GHP_NOT_ALREADY` for VRF exclusion check

#### 3. Hydronic GHP (28): Missing chiller requirement — CONFIRMED
- **ComStock source** (`upgrade_hvac_hydronic_gshp/measure.rb`): Requires both boilers AND chillers (`No boilers or chillers in model`)
- **Training data validation**: 12,283 buildings got upgrade 28. **100% have WCC or ACC cooling.** 0 out of 17,017 boiler+DX buildings received it. Confirms chiller is required.
- **Our code**: Only checks `has_boiler`, no chiller check. Would incorrectly allow 17,017 boiler+DX buildings.
- **Fix**: Add `if hvac_cool not in _CS_CHILLER_COOL: return False` to upgrade 28 block

#### 4. DOAS HP Minisplits (14): Missing single-zone requirement
- **ComStock source** (`upgrade_hvac_doas_hp_minisplits/measure.rb`): Excludes multi-zone systems (`thermalZones.length > 1`), VAV, water coils
- **Our code**: Groups upgrade 14 with VRF (12-13) in `_CS_VRF_MINISPLIT`, only checks not DOAS, not GSHP/WSHP
- **Impact**: Multi-zone VAV buildings could receive minisplit recommendation when ComStock would exclude them
- **Fix**: Separate upgrade 14 from VRF group; add `hvac_category` check (should be in packaged categories, similar to HP-RTU)

#### 5. Energy Recovery (21): Missing restaurant building type exclusion
- **ComStock source** (`upgrade_hvac_exhaust_air_energy_or_heat_recovery/measure.rb`): Explicitly excludes restaurant building types (RFF, RSD, QuickServiceRestaurant, FullServiceRestaurant)
- **Our code**: Only checks `hvac_vent != "Zone terminal equipment"`
- **Impact**: Restaurants could get energy recovery recommended when ComStock would exclude them due to large exhaust requirements
- **Fix**: Add `if building_type == "Food Service": return False`

---

### MODERATE — Overly permissive rules

#### 6. Demand Flexibility (32-37): Missing building type whitelist — CONFIRMED
- **ComStock source**: Load shed/shift measures require Office, Warehouse, or Education building types
- **Training data validation**: Upgrades 32-37 are 100% restricted to Office (54.5%), Education (26.9%), Warehouse (18.6%). Upgrades 38-42 (GEB Gem variants) apply to ALL building types (97.6-97.9% applicability).
- **Our code**: All 32-42 in `_CS_NO_RULES` — no restrictions
- **Fix**: Split demand flex into two groups:
  - Upgrades 32-37: Add `building_type in {"Office", "Warehouse and Storage", "Education"}` filter
  - Upgrades 38-42: Keep as no rules (correctly broad)

#### 7. Unoccupied AHU Control (23): Missing DOAS exclusion
- **ComStock source** (`upgrade_unoccupied_oa_controls/measure.rb`): Excludes DOAS air loops (`air_loop_doas?`)
- **Our code**: Only checks `hvac_vent != "Zone terminal equipment"`, does not exclude DOAS
- **Impact**: DOAS buildings could get unoccupied AHU control recommended
- **Fix**: Add `if is_doas: return False`

#### 8. VRF (12-13): Missing building type exclusions
- **ComStock source** (`upgrade_hvac_vrf_hr_doas/measure.rb`): Excludes `Restaurant Fast-Food`, `Restaurant Sit-Down`, `Hospital` and other building types with large exhaust
- **Our code**: No building type check for VRF
- **Impact**: Restaurants and hospitals could receive VRF recommendations
- **Fix**: Add `if building_type in {"Food Service", "Healthcare"}: return False`

#### 9. VRF (12-13): Missing floor area limit
- **ComStock source**: Excludes buildings >= 200,000 SF total floor area
- **Our code**: No area check
- **Note**: We may not have total floor area as a model feature. If we do (e.g., `in.sqft`), add the check. If not, document as known limitation.

#### 10. Hydronic GHP (28): Missing additional equipment exclusions
- **ComStock source**: Also excludes evaporative coolers, baseboard heaters, PSZ with hot water heating, packaged VAV with hot water reheat
- **Our code**: Only checks district, boiler, not GSHP/WSHP
- **Impact**: Edge cases with these equipment types could get incorrect recommendations
- **Fix**: Some of these may not map to our features; document as known limitations

#### 11. DCV (20): Missing ERV exclusion
- **ComStock source** (`upgrade_hvac_dcv/measure.rb`): Excludes systems with ERV components
- **Our code**: No ERV check
- **Note**: We don't have an ERV feature column, so this can't be implemented. Document as known limitation.

---

### MINOR — Acceptable approximations or conservative overrides

#### 12. Window Film (51): Triple-pane exclusion may be too restrictive
- **ComStock source** (`upgrade_env_window_film/measure.rb`): Does NOT exclude triple-pane windows. Checks window presence and climate zone only.
- **Our code**: Excludes `"Triple" in window`
- **Impact**: We're more conservative — triple-pane buildings won't get window film recommendation. Since window film on triple-pane is unlikely to improve performance much, this is acceptable.
- **Recommendation**: Remove the triple-pane check for upgrade 51 to match ComStock

#### 13. Advanced RTU (11): HP exclusion present in ComStock but not in our code
- **ComStock source** (`upgrade_hvac_rtu_adv/measure.rb`): Excludes existing heat pumps (DX heating coil or "HP" in name)
- **Our code**: Only checks `hvac_category == "Small Packaged Unit"` and `not is_doas`
- **Impact**: HP-RTU buildings could get advanced RTU controls when they already have HP. Low impact since advanced controls still apply.
- **Recommendation**: Consider adding HP exclusion for correctness

#### 14. Console GHP (30): Our district check is more conservative than ComStock
- **ComStock source** (`upgrade_hvac_console_gshp/measure.rb`): Does NOT explicitly check district energy; instead excludes by equipment type (no unitary systems)
- **Our code**: Checks `is_district` explicitly
- **Impact**: Our check is conservative and correct — district buildings shouldn't get console GHP. The equipment-type check in ComStock achieves the same result indirectly.

#### 15. Package compositions are generally correct
- Package 6 (59) correctly requires at least one component GHP to be applicable
- Packages 63, 64 correctly cascade Package 6 applicability
- Package 5 (58) correctly applies HP-RTU rules

---

## ResStock Findings

### MODERATE Gaps

#### 16. GHP variants (our upgrades 6-8): In `_RS_NO_RULES` with no checks
- **ResStock YAML**: Multiple exclusions:
  - `HVAC Has Ducts|Yes` required
  - Excludes Wood, Other Fuel, None heating fuel
  - Excludes shared boiler/fan coil systems
  - Excludes `Multi-Family with 5+ Units, 8+ Stories`
  - Excludes low ground thermal conductivity (0.5, 0.8)
- **Our code**: No rules at all (in `_RS_NO_RULES`)
- **Fix**: At minimum, exclude non-ducted systems and check heating fuel

#### 17. ASHP upgrades (our upgrades 4-5): Missing fuel exclusions
- **ResStock YAML** (upgrades 4-7): Excludes Wood, Other Fuel, None heating fuel
- **Our code**: Upgrade 4 only checks `not is_hp`; Upgrade 5 checks not HP and not Electricity
- **Impact**: Wood-heated buildings could get ASHP recommendation
- **Note**: Our ResStock features may not have a "Wood" fuel category. Verify against training data. If present, add exclusion.

#### 18. HP Water Heater (our upgrade 9): In `_RS_NO_RULES` with no checks
- **ResStock YAML** (upgrade 11): Excludes already-HP efficiency (3.5 UEF), Solar Thermal, Other Fuel, Wood water heater fuels
- **Our code**: No rules
- **Fix**: At minimum, check that water heater fuel is not already electric HP

#### 19. Furnace upgrades (our 1-3): Missing shared HVAC exclusion
- **ResStock YAML**: Excludes shared boiler/fan coil systems (`HVAC Shared Efficiencies`)
- **Our code**: Checks heating fuel and ducted type, but not shared HVAC
- **Note**: We may not have a "shared HVAC" feature. Document as known limitation.

#### 20. Gas Tankless WH (our upgrade 10): Should be more nuanced
- **ResStock YAML** (upgrade 12): Excludes already-tankless, solar thermal, other fuel, wood. Requires gas connection somewhere (water heater, heating, dryer, range, etc.)
- **Our code**: Only checks `wh_fuel == "Natural Gas"`
- **Impact**: Low — our check is actually more restrictive (requires gas water heater specifically)

#### 21. Air Sealing (our upgrade 11): Missing infiltration level check
- **ResStock YAML** (upgrade 13): Only applies when infiltration >= 6 ACH50
- **Our code**: No rules
- **Note**: We likely don't have ACH50 as a feature. Document as known limitation.

#### 22. Windows (our upgrade 17): More nuanced than our check
- **ResStock YAML** (upgrade 19): Climate-zone-specific EnergyStar windows; only upgrades single/double pane to better; no upgrade for Triple Low-E with certain characteristics
- **Our code**: `"Triple" not in windows` — correct direction but simplified
- **Impact**: Acceptable approximation

---

## Validation Against Training Data — COMPLETED

Validated against actual ComStock 2025 R3 parquet data (149,272 buildings):

| Finding | Validated? | Training Data Evidence |
|---------|-----------|----------------------|
| VRF + District cool | **YES** | 0 district-cool buildings got VRF; 435 district-heat+DX-cool buildings correctly got VRF |
| Hydronic GHP + No chiller | **YES** | 0 out of 17,017 boiler+DX buildings got upgrade 28; 100% of 12,283 recipients had WCC/ACC |
| Demand Flex building types | **YES** | Upgrades 32-37: 100% Office/Education/Warehouse. Upgrades 38-42: all building types |
| VRF + ASHP | **YES** | 0 out of 17,694 ASHP buildings got VRF (upgrades 12/13) |

---

## Recommended Fix Priority

### Phase 1 — Critical (fix now)
1. VRF district energy exclusion (finding 1)
2. VRF ASHP exclusion (finding 2)
3. Hydronic GHP chiller requirement (finding 3)
4. Separate DOAS HP Minisplit from VRF group (finding 4)
5. Energy Recovery restaurant exclusion (finding 5)

### Phase 2 — Moderate (fix soon)
6. Demand Flex building type whitelist (finding 6)
7. Unoccupied AHU Control DOAS exclusion (finding 7)
8. VRF building type exclusions (finding 8)
9. ResStock GHP rules (finding 16)
10. ResStock HPWH rules (finding 18)

### Phase 3 — Minor (address later)
11. Window Film triple-pane check (finding 12)
12. Advanced RTU HP exclusion (finding 13)
13. ResStock fuel exclusions (finding 17)
14. Document known limitations for unmappable checks

---

## Appendix: Upgrade-to-Measure Directory Mapping

| Our ID | Measure Name | ComStock measure.rb directory |
|--------|-------------|-------------------------------|
| 1-10 | HP-RTU variants | `upgrade_hvac_add_heat_pump_rtu` |
| 11 | Advanced RTU | `upgrade_hvac_rtu_adv` |
| 12-13 | VRF variants | `upgrade_hvac_vrf_hr_doas` |
| 14 | DOAS HP Minisplits | `upgrade_hvac_doas_hp_minisplits` |
| 15-16 | HP Boiler | `upgrade_hvac_replace_boiler_by_heatpump` |
| 17 | Condensing Boiler | `upgrade_hvac_condensing_boiler` |
| 18 | Electric Boiler | `upgrade_hvac_electric_boiler` |
| 19 | Economizer | `upgrade_hvac_economizer` |
| 20 | DCV | `upgrade_hvac_dcv` |
| 21 | Energy Recovery | `upgrade_hvac_exhaust_air_energy_or_heat_recovery` |
| 22 | Advanced RTU Controls | `upgrade_advanced_rtu_control` |
| 23 | Unoccupied AHU Control | `upgrade_unoccupied_oa_controls` |
| 24 | Fan SP Reset | `upgrade_hvac_fan_static_pressure_reset` |
| 25 | Thermostat Setbacks | `upgrade_add_thermostat_setback` |
| 26 | VFD Pumps | `upgrade_hvac_pump` |
| 27 | Ideal Air Loads | `upgrade_hvac_enable_ideal_air_loads` |
| 28 | Hydronic GHP | `upgrade_hvac_hydronic_gshp` |
| 29 | Packaged GHP | `upgrade_hvac_packaged_gshp` |
| 30 | Console GHP | `upgrade_hvac_console_gshp` |
| 31 | Chiller | `upgrade_hvac_chiller` |
| 32-42 | Demand Flex | `upgrade_df_load_shed` / `upgrade_df_thermostat_control_load_shift` |
| 43 | LED | `upgrade_light_led` |
| 44 | Lighting Controls | `upgrade_light_lighting_controls` |
| 45 | Electric Kitchen | `upgrade_ppl_electric_kitchen_equipment` |
| 46-47 | PV / PV+Battery | `upgrade_add_pvwatts` |
| 48 | Wall Insulation | `upgrade_env_exterior_wall_insulation` |
| 49 | Roof Insulation | `upgrade_env_roof_insul_aedg` |
| 50 | Secondary Windows | `upgrade_env_secondary_windows` |
| 51 | Window Film | `upgrade_env_window_film` |
| 52 | New Windows | `upgrade_env_new_aedg_windows` |
| 53 | Code Envelope | `upgrade_env_latest_envelope_code` |
| 54-65 | Packages 1-12 | Combinations of above |

## Rules That Are Correctly Implemented

The following upgrades have rules that match ComStock/ResStock source or are acceptable approximations:

- **HP-RTU (1-10)**: Correct — packaged category, not DOAS, not already HP ✓
- **Advanced RTU (11)**: Correct — Small Packaged Unit, not DOAS ✓
- **Boiler upgrades (15-18)**: Correct — has boiler, gas fuel where needed ✓
- **Economizer (19)**: Correct — needs AHU (not zone terminal, not DOAS) ✓
- **DCV (20)**: Mostly correct — needs AHU, excludes lodging/food service ✓ (minor: missing ERV check)
- **Advanced RTU Controls (22)**: Correct — Small Packaged Unit ✓
- **Fan SP Reset (24)**: Correct — Multizone CAV/VAV ✓
- **VFD Pumps (26)**: Correct — needs hydronic loop ✓
- **Packaged GHP (29)**: Correct — not district, not GHP, packaged categories ✓
- **Console GHP (30)**: Correct — not district, not GHP, Zone-by-Zone ✓
- **Chiller (31)**: Correct — needs chiller (WCC or ACC) ✓
- **LED (43)**: Correct — not already LED ✓
- **Electric Kitchen (45)**: Correct — food buildings ✓
- **Wall Insulation (48)**: Correct — not Metal Building ✓
- **Secondary Windows (50)**: Correct — not triple-pane ✓
- **All packages (54-65)**: Generally correct composition logic ✓
