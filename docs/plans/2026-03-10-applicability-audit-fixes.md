# Applicability Rules Audit Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all critical and moderate applicability rule gaps identified in `docs/audits/2026-03-10-applicability-audit.md`, ensuring our rules match ComStock/ResStock source logic and training data patterns.

**Architecture:** All changes are in `backend/app/inference/applicability.py` (rule logic) and `backend/tests/test_applicability.py` (tests). Each fix adds/modifies feature-value checks in `_check_comstock_rules()` or `_check_resstock_rules()`. TDD approach — write failing test first, then fix the rule.

**Tech Stack:** Python, pytest

---

## Task 1: VRF District Cooling Exclusion (Finding 1 — Critical)

ComStock VRF excludes district energy systems. Training data confirms: 0 district-cool buildings got VRF, but 435 district-heat+DX-cool buildings correctly got VRF. Only exclude district COOLING, not district heating.

**Files:**
- Modify: `backend/app/inference/applicability.py:157-163`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

Add to `TestComstockVrfMinisplit` class in `backend/tests/test_applicability.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit::test_skip_when_district_cooling -v`
Expected: FAIL — currently returns True for district-cool buildings

**Step 3: Fix the VRF rule**

In `applicability.py`, modify the VRF block (lines 157-163). Add a district cooling check:

```python
# ── VRF / Minisplit (12-14) ──
if upgrade_id in _CS_VRF_MINISPLIT:
    if is_doas:
        return False
    if hvac_cool == "District":
        return False
    if hvac_cool in _CS_GHP_NOT_ALREADY:
        return False
    return True
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: exclude district-cooled buildings from VRF applicability"
```

---

## Task 2: VRF ASHP Exclusion (Finding 2 — Critical)

ComStock VRF excludes existing heat pumps (ASHP, GSHP, WSHP). Training data: 0/17,694 ASHP buildings got VRF. Our code only excludes GSHP/WSHP. Switch from `_CS_GHP_NOT_ALREADY` to `_CS_HP_NOT_ALREADY` for VRF.

**Files:**
- Modify: `backend/app/inference/applicability.py:157-163`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing test**

Add to `TestComstockVrfMinisplit`:

```python
@pytest.mark.parametrize("uid", [12, 13])
def test_skip_when_already_ashp(self, uid):
    """VRF excludes buildings already with ASHP."""
    features = _comstock_features(**{"in.hvac_cool_type": "ASHP"})
    assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit::test_skip_when_already_ashp -v`
Expected: FAIL — ASHP is not in `_CS_GHP_NOT_ALREADY`

**Step 3: Fix the VRF rule**

Change the VRF exclusion from `_CS_GHP_NOT_ALREADY` to `_CS_HP_NOT_ALREADY`:

```python
# ── VRF / Minisplit (12-14) ──
if upgrade_id in _CS_VRF_MINISPLIT:
    if is_doas:
        return False
    if hvac_cool == "District":
        return False
    if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
        return False
    return True
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit -v`
Expected: ALL PASS

Note: The existing `test_skip_when_already_gshp` still passes since GSHP is in `_CS_HP_NOT_ALREADY`.

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: exclude ASHP buildings from VRF applicability"
```

---

## Task 3: Hydronic GHP Chiller Requirement (Finding 3 — Critical)

ComStock hydronic GHP requires BOTH boilers AND chillers. Training data: 100% of 12,283 recipients had WCC/ACC cooling. 0/17,017 boiler+DX buildings got it. Add chiller requirement.

**Files:**
- Modify: `backend/app/inference/applicability.py:206-213`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing test**

Add to `TestComstockGhp`:

```python
def test_hydronic_ghp_skip_when_boiler_but_no_chiller(self):
    """Hydronic GHP requires both boiler AND chiller."""
    features = _comstock_features(**{
        "in.hvac_heat_type": "Boiler ",
        "in.hvac_cool_type": "DX",
    })
    assert check_applicability(28, "comstock", features, ALL_COMSTOCK) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockGhp::test_hydronic_ghp_skip_when_boiler_but_no_chiller -v`
Expected: FAIL — currently returns True (only checks for boiler, not chiller)

**Step 3: Fix the hydronic GHP rule**

In `applicability.py`, add chiller requirement to upgrade 28 block:

```python
# ── Hydronic GHP (28) ──
if upgrade_id == 28:
    if is_district:
        return False
    if not has_boiler:
        return False
    if hvac_cool not in _CS_CHILLER_COOL:
        return False
    if hvac_cool in _CS_GHP_NOT_ALREADY:
        return False
    return True
```

Note: `_CS_CHILLER_COOL = {"WCC", "ACC"}` is already defined at line 114.

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockGhp -v`
Expected: ALL PASS — existing `test_hydronic_ghp_applicable_when_boiler` already uses `"in.hvac_cool_type": "WCC"`, so it still passes.

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: require chiller (WCC/ACC) for hydronic GHP applicability"
```

---

## Task 4: Separate DOAS HP Minisplits from VRF Group (Finding 4 — Critical)

Upgrade 14 (DOAS HP Minisplits) uses a different ComStock measure than VRF (12-13). It requires single-zone packaged systems (like HP-RTU), not just "not DOAS, not GHP". Separate it from `_CS_VRF_MINISPLIT` and give it its own rule block.

**Files:**
- Modify: `backend/app/inference/applicability.py:99,157-163`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

Replace the `TestComstockVrfMinisplit` class structure to separate VRF (12-13) from Minisplit (14). Add a new test class:

```python
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
```

Also update `TestComstockVrfMinisplit` to only parametrize over `[12, 13]` instead of `[12, 13, 14]`.

**Step 2: Run tests to verify the new ones fail**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockDoasMinisplit::test_skip_when_multizone_vav -v`
Expected: FAIL — currently upgrade 14 uses VRF rules which don't check `hvac_category`

**Step 3: Update the code**

In `applicability.py`:

1. Change `_CS_VRF_MINISPLIT` from `{12, 13, 14}` to `{12, 13}` (rename to `_CS_VRF`):

```python
_CS_VRF: Set[int] = {12, 13}                    # VRF/DOAS
```

2. Update the VRF block comment:

```python
# ── VRF (12-13) ──
if upgrade_id in _CS_VRF:
```

3. Add a new block for upgrade 14 after the VRF block:

```python
# ── DOAS HP Minisplits (14) ──
if upgrade_id == 14:
    if hvac_category not in _CS_PACKAGED_CATEGORIES:
        return False
    if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
        return False
    return True
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockDoasMinisplit -v && cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: separate DOAS HP minisplit (14) from VRF group, add single-zone requirement"
```

---

## Task 5: Energy Recovery Restaurant Exclusion (Finding 5 — Critical)

ComStock energy recovery explicitly excludes restaurant building types. Add Food Service exclusion.

**Files:**
- Modify: `backend/app/inference/applicability.py:186-187`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing test**

Add a new test class:

```python
class TestComstockEnergyRecovery:
    def test_applicable_for_office(self):
        features = _comstock_features(**{
            "in.hvac_vent_type": "Central Multi-zone VAV RTU",
        })
        assert check_applicability(21, "comstock", features, ALL_COMSTOCK) is True

    def test_skip_zone_terminal(self):
        features = _comstock_features(**{
            "in.hvac_vent_type": "Zone terminal equipment",
        })
        assert check_applicability(21, "comstock", features, ALL_COMSTOCK) is False

    def test_skip_food_service(self):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Food Service",
        })
        assert check_applicability(21, "comstock", features, ALL_COMSTOCK) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockEnergyRecovery::test_skip_food_service -v`
Expected: FAIL — currently no building type check for upgrade 21

**Step 3: Fix the energy recovery rule**

Replace the upgrade 21 block:

```python
# ── Energy Recovery (21) ──
if upgrade_id == 21:
    if hvac_vent == "Zone terminal equipment":
        return False
    if building_type == "Food Service":
        return False
    return True
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockEnergyRecovery -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: exclude Food Service buildings from energy recovery applicability"
```

---

## Task 6: Demand Flex Building Type Whitelist (Finding 6 — Moderate)

Training data confirms upgrades 32-37 are restricted to Office/Education/Warehouse. Upgrades 38-42 (GEB Gem) are broadly applicable. Split the groups.

**Files:**
- Modify: `backend/app/inference/applicability.py:103-107,119-124`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

```python
class TestComstockDemandFlex:
    """Demand flex 32-37 restricted to Office/Education/Warehouse; 38-42 broadly applicable."""

    @pytest.mark.parametrize("uid", range(32, 38))
    def test_applicable_for_office(self, uid):
        features = _comstock_features()  # Office
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", range(32, 38))
    def test_applicable_for_education(self, uid):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Education",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", range(32, 38))
    def test_applicable_for_warehouse(self, uid):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Warehouse and Storage",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True

    @pytest.mark.parametrize("uid", range(32, 38))
    def test_skip_food_service(self, uid):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Food Service",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", range(32, 38))
    def test_skip_healthcare(self, uid):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Healthcare",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

    @pytest.mark.parametrize("uid", range(38, 43))
    def test_geb_gem_applicable_for_any_building(self, uid):
        features = _comstock_features(**{
            "in.comstock_building_type_group": "Healthcare",
        })
        assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is True
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockDemandFlex::test_skip_food_service -v`
Expected: FAIL — currently all demand flex is in `_CS_NO_RULES`

**Step 3: Fix the demand flex rules**

In `applicability.py`:

1. Replace the demand flex set definitions:

```python
_CS_DEMAND_FLEX_RESTRICTED: Set[int] = set(range(32, 38))  # 32-37: DF with building type filter
_CS_DEMAND_FLEX_BROAD: Set[int] = set(range(38, 43))       # 38-42: GEB Gem, broadly applicable
_CS_DF_BUILDING_TYPES: Set[str] = {"Office", "Warehouse and Storage", "Education"}
```

2. Update `_CS_NO_RULES` to remove 32-37 but keep 38-42:

```python
_CS_NO_RULES: Set[int] = (
    {0, 25, 27, 44, 46, 47, 49, 52, 53, 65}       # Broadly applicable
    | _CS_DEMAND_FLEX_BROAD
)
```

3. Add a new rule block (after the `_CS_NO_RULES` check at line 123):

```python
# ── Demand Flexibility restricted (32-37) ──
if upgrade_id in _CS_DEMAND_FLEX_RESTRICTED:
    return building_type in _CS_DF_BUILDING_TYPES
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockDemandFlex -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: restrict demand flex 32-37 to Office/Education/Warehouse building types"
```

---

## Task 7: Unoccupied AHU Control DOAS Exclusion (Finding 7 — Moderate)

ComStock excludes DOAS air loops from unoccupied AHU control.

**Files:**
- Modify: `backend/app/inference/applicability.py:194-195`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing test**

Add to `TestComstockControls`:

```python
def test_unoccupied_ahu_skip_doas(self):
    features = _comstock_features(**{
        "in.hvac_vent_type": "DOAS+Zone terminal equipment",
    })
    assert check_applicability(23, "comstock", features, ALL_COMSTOCK) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockControls::test_unoccupied_ahu_skip_doas -v`
Expected: FAIL — currently only checks for `Zone terminal equipment`

**Step 3: Fix the rule**

Replace the upgrade 23 block:

```python
# ── Unoccupied AHU Control (23) ──
if upgrade_id == 23:
    return hvac_vent not in _CS_NO_AHU_VENT
```

Note: `_CS_NO_AHU_VENT` already includes both `"DOAS+Zone terminal equipment"` and `"Zone terminal equipment"` (defined at line 111). The current code uses `!= "Zone terminal equipment"` which misses DOAS. Change to use the set check.

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockControls -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: exclude DOAS from unoccupied AHU control applicability"
```

---

## Task 8: VRF Building Type Exclusions (Finding 8 — Moderate)

ComStock VRF excludes restaurants and hospitals (large exhaust buildings).

**Files:**
- Modify: `backend/app/inference/applicability.py:157-163`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

Add to `TestComstockVrfMinisplit`:

```python
@pytest.mark.parametrize("uid", [12, 13])
def test_skip_food_service(self, uid):
    features = _comstock_features(**{
        "in.comstock_building_type_group": "Food Service",
    })
    assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False

@pytest.mark.parametrize("uid", [12, 13])
def test_skip_healthcare(self, uid):
    features = _comstock_features(**{
        "in.comstock_building_type_group": "Healthcare",
    })
    assert check_applicability(uid, "comstock", features, ALL_COMSTOCK) is False
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit::test_skip_food_service -v`
Expected: FAIL

**Step 3: Fix the VRF rule**

Add a set constant and building type check:

```python
_CS_VRF_EXCLUDED_BLDG: Set[str] = {"Food Service", "Healthcare"}
```

In the VRF block:

```python
# ── VRF (12-13) ──
if upgrade_id in _CS_VRF:
    if is_doas:
        return False
    if hvac_cool == "District":
        return False
    if building_type in _CS_VRF_EXCLUDED_BLDG:
        return False
    if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
        return False
    return True
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockVrfMinisplit -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: exclude Food Service and Healthcare from VRF applicability"
```

---

## Task 9: ResStock GHP Rules (Finding 16 — Moderate)

ResStock GHP (our upgrades 6-8) is in `_RS_NO_RULES` with zero checks. ResStock requires ducted systems. Note: we can't check ground thermal conductivity or building height (not in our features), but we can check for ducted systems.

**Files:**
- Modify: `backend/app/inference/applicability.py:335-341`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

```python
class TestResstockGhp:
    """ResStock GHP (6-8) requires ducted systems."""

    @pytest.mark.parametrize("uid", [6, 7, 8])
    def test_applicable_when_ducted(self, uid):
        features = _resstock_features()  # Ducted Heating
        assert check_applicability(uid, "resstock", features, ALL_RESSTOCK) is True

    @pytest.mark.parametrize("uid", [6, 7, 8])
    def test_skip_when_non_ducted(self, uid):
        features = _resstock_features(**{
            "in.hvac_heating_type": "Non-Ducted Heating",
        })
        assert check_applicability(uid, "resstock", features, ALL_RESSTOCK) is False

    @pytest.mark.parametrize("uid", [6, 7, 8])
    def test_skip_when_already_hp(self, uid):
        features = _resstock_features(**{
            "in.hvac_heating_type": "Ducted Heat Pump",
        })
        assert check_applicability(uid, "resstock", features, ALL_RESSTOCK) is False
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py::TestResstockGhp::test_skip_when_non_ducted -v`
Expected: FAIL — upgrades 6-8 are in `_RS_NO_RULES`

**Step 3: Fix the ResStock GHP rules**

1. Remove 6, 7, 8 from `_RS_NO_RULES`:

```python
_RS_NO_RULES: Set[int] = {0, 3, 9, 11, 12, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29}
```

2. Add rule block in `_check_resstock_rules` (after the dual fuel block):

```python
# ── GHP variants (6-8) ──
if upgrade_id in {6, 7, 8}:
    if not is_ducted:
        return False
    if is_hp:
        return False
    return True
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py::TestResstockGhp -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: add ducted + not-already-HP requirement for ResStock GHP (6-8)"
```

---

## Task 10: ResStock HPWH Rules (Finding 18 — Moderate)

ResStock HP Water Heater (our upgrade 9) is in `_RS_NO_RULES`. ResStock excludes Solar Thermal, Other Fuel, Wood water heater fuels, and already-HP efficiency. We can at minimum exclude non-standard fuels.

**Files:**
- Modify: `backend/app/inference/applicability.py:335`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

```python
class TestResstockHpwh:
    """ResStock HPWH (9) excludes Other Fuel water heater fuel."""

    def test_applicable_when_gas_wh(self):
        features = _resstock_features()  # Natural Gas WH
        assert check_applicability(9, "resstock", features, ALL_RESSTOCK) is True

    def test_applicable_when_electric_wh(self):
        features = _resstock_features(**{"in.water_heater_fuel": "Electricity"})
        assert check_applicability(9, "resstock", features, ALL_RESSTOCK) is True

    def test_skip_when_other_fuel_wh(self):
        features = _resstock_features(**{"in.water_heater_fuel": "Other Fuel"})
        assert check_applicability(9, "resstock", features, ALL_RESSTOCK) is False
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py::TestResstockHpwh::test_skip_when_other_fuel_wh -v`
Expected: FAIL — upgrade 9 is in `_RS_NO_RULES`

**Step 3: Fix the ResStock HPWH rule**

1. Remove 9 from `_RS_NO_RULES`:

```python
_RS_NO_RULES: Set[int] = {0, 3, 11, 12, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29}
```

2. Add rule block:

```python
# ── HP Water Heater (9) ──
if upgrade_id == 9:
    return wh_fuel not in {"Other Fuel"}
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py::TestResstockHpwh -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: exclude Other Fuel water heaters from ResStock HPWH applicability"
```

---

## Task 11: Minor Fixes — Window Film + Advanced RTU (Findings 12-13)

Two minor corrections: (a) remove triple-pane exclusion from window film (51) to match ComStock, and (b) add HP exclusion to Advanced RTU (11).

**Files:**
- Modify: `backend/app/inference/applicability.py:255-257,149-155`
- Test: `backend/tests/test_applicability.py`

**Step 1: Write the failing tests**

For window film — change the existing test expectation:

Update `TestComstockEnvelope::test_window_film_skip_triple` to expect `True` instead of `False`, and rename it:

```python
def test_window_film_applicable_for_triple_pane(self):
    """ComStock does NOT exclude triple-pane from window film."""
    features = _comstock_features(**{
        "in.window_type": "Triple - LowE - Clear - Thermally Broken Aluminum",
    })
    assert check_applicability(51, "comstock", features, ALL_COMSTOCK) is True
```

For advanced RTU — add new test:

```python
def test_advanced_rtu_skip_when_already_hp(self):
    features = _comstock_features(**{"in.hvac_cool_type": "ASHP"})
    assert check_applicability(11, "comstock", features, ALL_COMSTOCK) is False
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applicability.py::TestComstockEnvelope::test_window_film_applicable_for_triple_pane -v`
Expected: FAIL — currently returns False for triple-pane

Run: `cd backend && pytest tests/test_applicability.py::TestComstockAdvancedRtu::test_advanced_rtu_skip_when_already_hp -v`
Expected: FAIL — currently no HP check

**Step 3: Fix both rules**

Window Film (51) — remove the triple-pane check:

```python
# ── Window Film (51) ──
if upgrade_id == 51:
    return True
```

Advanced RTU (11) — add HP exclusion:

```python
# ── Advanced RTU (11) ──
if upgrade_id == 11:
    if hvac_category != "Small Packaged Unit":
        return False
    if is_doas:
        return False
    if hvac_cool in _CS_HP_NOT_ALREADY or hvac_heat in _CS_HP_NOT_ALREADY:
        return False
    return True
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_applicability.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: remove triple-pane exclusion from window film, add HP exclusion to advanced RTU"
```

---

## Task 12: Run Full Test Suite + Regression Check

Verify all changes work together and no existing tests are broken.

**Step 1: Run all applicability tests**

Run: `cd backend && pytest tests/test_applicability.py -v`
Expected: ALL PASS

**Step 2: Run full backend test suite**

Run: `cd backend && pytest`
Expected: ALL PASS — no regressions in other test files

**Step 3: Commit any remaining changes**

If any tests needed adjustment, commit with descriptive message.

---

## Summary of All Changes

| Task | Finding | Change |
|------|---------|--------|
| 1 | VRF district cool | Add `hvac_cool == "District"` check to VRF |
| 2 | VRF ASHP | Switch VRF from `_CS_GHP_NOT_ALREADY` to `_CS_HP_NOT_ALREADY` |
| 3 | Hydronic GHP chiller | Add `hvac_cool in _CS_CHILLER_COOL` requirement |
| 4 | DOAS Minisplit | Separate upgrade 14 from VRF, add packaged category requirement |
| 5 | Energy Recovery restaurant | Add Food Service exclusion |
| 6 | Demand Flex whitelist | Split 32-37 (restricted) from 38-42 (broad) |
| 7 | Unoccupied AHU DOAS | Use `_CS_NO_AHU_VENT` set instead of single value |
| 8 | VRF building types | Add Food Service, Healthcare exclusion |
| 9 | ResStock GHP | Remove from `_RS_NO_RULES`, add ducted + not-HP check |
| 10 | ResStock HPWH | Remove from `_RS_NO_RULES`, exclude Other Fuel WH |
| 11 | Window Film + Adv RTU | Remove triple-pane from window film, add HP to Adv RTU |
| 12 | Regression check | Full test suite verification |

### Known Limitations (Documented, Not Fixable)
- **VRF floor area limit** (200k SF): `in.sqft..ft2` is total building area, could add check but ComStock's 200k threshold may differ from our feature
- **DCV ERV exclusion**: No ERV feature column available
- **ResStock shared HVAC**: No shared HVAC feature column
- **ResStock infiltration level**: No ACH50 feature column
- **ResStock ground thermal conductivity**: Not in our feature space
- **Hydronic GHP evap cooler/baseboard**: Not mappable to our features
