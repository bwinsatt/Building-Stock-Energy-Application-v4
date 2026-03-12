# ResStock Central System & Unified HVAC Categories — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify HVAC category labels across ComStock and ResStock, and add a "Central Boiler + Chiller" option for ResStock that sets `in.hvac_has_shared_system` and overrides efficiency values.

**Architecture:** Modify the HVAC category config in `dropdowns.ts` to rename/merge categories, add dataset-aware variant filtering, update the preprocessor to handle new central system variant values (`"Fan Coil Units"`, `"Baseboards / Radiators"`), and update `AdvancedDetails.vue` to disable efficiency fields when a central system variant is active.

**Tech Stack:** Vue 3, TypeScript, Python/FastAPI, pytest

---

### Task 1: Backend — Add central system variant mapping to preprocessor

**Files:**
- Modify: `backend/app/services/preprocessor.py` (lines 354-444 and 477-552)
- Test: `backend/tests/test_preprocessor.py`

**Step 1: Write failing tests for central system variant mapping**

Add to `backend/tests/test_preprocessor.py`:

```python
def test_fan_coil_units_sets_shared_system_heating_and_cooling():
    """Fan Coil Units variant should set shared system to Heating and Cooling."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=10,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="Fan Coil Units",
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(inp)
    assert dataset == "resstock"
    assert features["in.hvac_has_shared_system"] == "Heating and Cooling"
    assert features["in.hvac_heating_type"] == "Ducted Heating"
    assert features["in.hvac_heating_efficiency"] == "Shared Heating"
    assert features["in.hvac_cooling_efficiency"] == "Shared Cooling"


def test_baseboards_radiators_sets_shared_system_heating_only():
    """Baseboards / Radiators variant should set shared system to Heating Only."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=10,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="Baseboards / Radiators",
    )
    features, imputed_details, dataset, climate_zone, state = preprocess(inp)
    assert dataset == "resstock"
    assert features["in.hvac_has_shared_system"] == "Heating Only"
    assert features["in.hvac_heating_type"] == "Non-Ducted Heating"
    assert features["in.hvac_heating_efficiency"] == "Shared Heating"
    # Cooling efficiency should NOT be "Shared Cooling" for heating-only
    assert features["in.hvac_cooling_efficiency"] != "Shared Cooling"


def test_central_system_overrides_user_efficiency_selections():
    """When a central system variant is selected, user efficiency overrides are ignored."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=10,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="Fan Coil Units",
        hvac_heating_efficiency="Fuel Furnace, 80% AFUE",
        hvac_cooling_efficiency="AC, SEER 13",
    )
    features, _, _, _, _ = preprocess(inp)
    # Central system should override user selections
    assert features["in.hvac_heating_efficiency"] == "Shared Heating"
    assert features["in.hvac_cooling_efficiency"] == "Shared Cooling"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_preprocessor.py::test_fan_coil_units_sets_shared_system_heating_and_cooling tests/test_preprocessor.py::test_baseboards_radiators_sets_shared_system_heating_only tests/test_preprocessor.py::test_central_system_overrides_user_efficiency_selections -v`
Expected: FAIL — the new variant values aren't handled yet

**Step 3: Implement central system mapping in preprocessor**

In `backend/app/services/preprocessor.py`, make three changes:

**3a.** Add the new variant values to `_RESSTOCK_VALUE_MAP["hvac_system_type"]` (around line 384):

```python
        # --- Central system variants ---
        "Fan Coil Units": "Ducted Heating",
        "Baseboards / Radiators": "Non-Ducted Heating",
```

**3b.** Add a constant for central system variant → shared system mapping (above `_resstock_context_impute`):

```python
# Central system variants that set in.hvac_has_shared_system
_RESSTOCK_CENTRAL_SYSTEM_MAP: dict[str, dict[str, str]] = {
    "Fan Coil Units": {
        "in.hvac_has_shared_system": "Heating and Cooling",
        "in.hvac_heating_efficiency": "Shared Heating",
        "in.hvac_cooling_efficiency": "Shared Cooling",
        "in.hvac_cooling_type": "Shared Cooling",
    },
    "Baseboards / Radiators": {
        "in.hvac_has_shared_system": "Heating Only",
        "in.hvac_heating_efficiency": "Shared Heating",
    },
}
```

**3c.** In `_resstock_context_impute` (line 477), add central system handling. Insert this block **after** the existing efficiency logic but **before** the user-provided overrides section (before line 543). This ensures the central system values take precedence:

```python
    # --- Central system overrides (takes precedence over all above) ---
    raw_hvac = resolved.get("hvac_system_type", "")
    central_overrides = _RESSTOCK_CENTRAL_SYSTEM_MAP.get(str(raw_hvac))
    if central_overrides:
        auto_impute.update(central_overrides)
        return  # Skip user-provided efficiency overrides for central systems
```

**3d.** Update the Multi-Family default in `DEFAULTS` (line 743) to use the new category key:

```python
    "hvac_system_type": "forced_air_furnace",
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_preprocessor.py -v`
Expected: ALL PASS (including new and existing tests)

**Step 5: Commit**

```bash
git add backend/app/services/preprocessor.py backend/tests/test_preprocessor.py
git commit -m "feat: add central system variant mapping for ResStock shared HVAC"
```

---

### Task 2: Frontend — Update HVAC categories in dropdowns.ts

**Files:**
- Modify: `frontend/src/config/dropdowns.ts`

**Step 1: Add `dataset` field to `HvacVariant` interface**

Change `HvacVariant` (line 20-23):

```typescript
export interface HvacVariant {
  value: string
  label: string
  dataset?: 'comstock' | 'resstock'
}
```

**Step 2: Replace the HVAC_CATEGORIES array**

Replace the entire `HVAC_CATEGORIES` array (lines 33-162) with:

```typescript
export const HVAC_CATEGORIES: HvacCategory[] = [
  {
    key: 'packaged_rooftop',
    label: 'Packaged Rooftop (DX)',
    defaultVariant: 'PSZ-AC with gas coil',
    datasets: ['comstock'],
    variants: [
      { value: 'PSZ-AC with gas coil', label: 'Gas Heating Coil' },
      { value: 'PSZ-AC with gas boiler', label: 'Gas Boiler' },
      { value: 'PSZ-AC with electric coil', label: 'Electric Heating Coil' },
      { value: 'PSZ-AC with district hot water', label: 'District Hot Water' },
    ],
  },
  {
    key: 'packaged_heat_pump',
    label: 'Packaged Heat Pump',
    defaultVariant: 'PSZ-HP',
    datasets: ['comstock'],
    variants: [
      { value: 'PSZ-HP', label: 'PSZ-HP' },
    ],
  },
  {
    key: 'through_wall',
    label: 'Through-Wall / PTAC',
    defaultVariant: 'PTAC with gas coil',
    datasets: ['comstock'],
    variants: [
      { value: 'PTAC with gas coil', label: 'Gas Heating Coil' },
      { value: 'PTAC with gas boiler', label: 'Gas Boiler' },
      { value: 'PTAC with electric coil', label: 'Electric Heating Coil' },
    ],
  },
  {
    key: 'through_wall_heat_pump',
    label: 'Through-Wall Heat Pump',
    defaultVariant: 'PTHP',
    datasets: ['comstock'],
    variants: [
      { value: 'PTHP', label: 'PTHP' },
    ],
  },
  {
    key: 'central_chiller_boiler',
    label: 'Central Boiler + Chiller',
    defaultVariant: 'VAV chiller with gas boiler reheat',
    datasets: ['comstock', 'resstock'],
    variants: [
      { value: 'VAV chiller with gas boiler reheat', label: 'VAV - Water-Cooled Chiller, Gas Boiler', dataset: 'comstock' },
      { value: 'VAV chiller with PFP boxes', label: 'VAV - Water-Cooled Chiller, Electric Reheat', dataset: 'comstock' },
      { value: 'VAV chiller with district hot water reheat', label: 'VAV - Water-Cooled Chiller, District Hot Water', dataset: 'comstock' },
      { value: 'VAV air-cooled chiller with gas boiler reheat', label: 'VAV - Air-Cooled Chiller, Gas Boiler', dataset: 'comstock' },
      { value: 'VAV air-cooled chiller with PFP boxes', label: 'VAV - Air-Cooled Chiller, Electric Reheat', dataset: 'comstock' },
      { value: 'VAV air-cooled chiller with district hot water reheat', label: 'VAV - Air-Cooled Chiller, District Hot Water', dataset: 'comstock' },
      { value: 'VAV district chilled water with district hot water reheat', label: 'VAV - District Chilled Water', dataset: 'comstock' },
      { value: 'Fan Coil Units', label: 'Fan Coil Units', dataset: 'resstock' },
      { value: 'Baseboards / Radiators', label: 'Baseboards / Radiators', dataset: 'resstock' },
    ],
  },
  {
    key: 'packaged_vav',
    label: 'Packaged VAV (Rooftop)',
    defaultVariant: 'PVAV with gas heat with electric reheat',
    datasets: ['comstock'],
    variants: [
      { value: 'PVAV with gas boiler reheat', label: 'PVAV - Gas Boiler Reheat' },
      { value: 'PVAV with gas heat with electric reheat', label: 'PVAV - Gas Heat, Electric Reheat' },
      { value: 'PVAV with PFP boxes', label: 'PVAV - Electric Reheat' },
      { value: 'PVAV with district hot water reheat', label: 'PVAV - District Hot Water' },
    ],
  },
  {
    key: 'doas_fan_coil',
    label: 'DOAS + Fan Coil',
    defaultVariant: 'DOAS with fan coil chiller with boiler',
    datasets: ['comstock'],
    variants: [
      { value: 'DOAS with fan coil chiller with boiler', label: 'Fan Coil - Chiller + Boiler' },
      { value: 'DOAS with fan coil air-cooled chiller with boiler', label: 'Fan Coil - Air-Cooled Chiller + Boiler' },
      { value: 'DOAS with fan coil chiller with baseboard electric', label: 'Fan Coil - Chiller + Electric Baseboard' },
      { value: 'DOAS with fan coil chiller with district hot water', label: 'Fan Coil - Chiller + District Hot Water' },
      { value: 'DOAS with fan coil district chilled water with baseboard electric', label: 'Fan Coil - District Chilled Water + Electric' },
      { value: 'DOAS with fan coil district chilled water with district hot water', label: 'Fan Coil - District Chilled Water + District Hot Water' },
      { value: 'DOAS with water source heat pumps cooling tower with boiler', label: 'Water Source Heat Pumps - Cooling Tower + Boiler' },
      { value: 'DOAS with water source heat pumps with ground source heat pump', label: 'Water Source Heat Pumps - Ground Source' },
    ],
  },
  {
    key: 'forced_air_furnace',
    label: 'Forced Air Furnace + AC',
    defaultVariant: 'Residential AC with residential forced air furnace',
    datasets: ['comstock', 'resstock'],
    variants: [
      { value: 'Residential AC with residential forced air furnace', label: 'Forced Air Furnace + AC', dataset: 'comstock' },
      { value: 'Ducted Heating', label: 'Forced Air Furnace + AC', dataset: 'resstock' },
    ],
  },
  {
    key: 'ducted_heat_pump',
    label: 'Ducted Heat Pump',
    defaultVariant: 'Ducted Heat Pump',
    datasets: ['resstock'],
    variants: [
      { value: 'Ducted Heat Pump', label: 'Ducted Heat Pump' },
    ],
  },
  {
    key: 'baseboard_wall_unit',
    label: 'Baseboard / Wall Unit',
    defaultVariant: 'Non-Ducted Heating',
    datasets: ['resstock'],
    variants: [
      { value: 'Non-Ducted Heating', label: 'Baseboard / Wall Unit' },
    ],
  },
  {
    key: 'mini_split_heat_pump',
    label: 'Mini-Split Heat Pump',
    defaultVariant: 'Non-Ducted Heat Pump',
    datasets: ['resstock'],
    variants: [
      { value: 'Non-Ducted Heat Pump', label: 'Mini-Split Heat Pump' },
    ],
  },
]
```

**Step 3: Update `getHvacCategoriesForDataset` to also filter variants**

Replace the function (line 166-169):

```typescript
/** Get categories filtered by dataset, with variants filtered too */
export function getHvacCategoriesForDataset(buildingType: string): HvacCategory[] {
  const dataset = buildingType === 'Multi-Family' ? 'resstock' : 'comstock'
  return HVAC_CATEGORIES
    .filter(c => c.datasets.includes(dataset))
    .map(c => ({
      ...c,
      variants: c.variants.filter(v => !v.dataset || v.dataset === dataset),
      defaultVariant: c.variants.find(v => !v.dataset || v.dataset === dataset)?.value ?? c.defaultVariant,
    }))
}
```

**Step 4: Update `getHvacCategoryForValue` legacy map**

Replace the `legacyMap` (lines 184-198):

```typescript
  const legacyMap: Record<string, string> = {
    'PSZ-AC': 'packaged_rooftop',
    'PSZ-HP': 'packaged_heat_pump',
    'PTAC': 'through_wall',
    'PTHP': 'through_wall_heat_pump',
    'VAV_chiller_boiler': 'central_chiller_boiler',
    'VAV_air_cooled_chiller_boiler': 'central_chiller_boiler',
    'PVAV_gas_boiler': 'packaged_vav',
    'PVAV_gas_heat': 'packaged_vav',
    'Residential_AC_gas_furnace': 'forced_air_furnace',
    'Residential_forced_air_furnace': 'forced_air_furnace',
    'Residential_AC_electric_baseboard': 'forced_air_furnace',
    // Old ResStock category keys
    'ducted_heating': 'forced_air_furnace',
    'non_ducted_heating': 'baseboard_wall_unit',
    'non_ducted_heat_pump': 'mini_split_heat_pump',
    'residential_furnace': 'forced_air_furnace',
  }
```

**Step 5: Commit**

```bash
git add frontend/src/config/dropdowns.ts
git commit -m "feat: unify HVAC categories across ComStock and ResStock with dataset-aware variants"
```

---

### Task 3: Frontend — Update AdvancedDetails.vue for central system behavior

**Files:**
- Modify: `frontend/src/components/AdvancedDetails.vue`

**Step 1: Add dataset-aware variant filtering and central system detection**

Update the `<script setup>` section. Add a `buildingType`-derived dataset computed property and modify `hvacVariants` to filter by dataset. Add a computed property to detect central system variants:

After the existing imports (line 16), add:

```typescript
const CENTRAL_SYSTEM_VARIANTS = ['Fan Coil Units', 'Baseboards / Radiators']
```

Replace the `hvacVariants` computed (lines 34-38):

```typescript
const currentDataset = computed(() => props.buildingType === 'Multi-Family' ? 'resstock' : 'comstock')

const hvacVariants = computed<HvacVariant[]>(() => {
  if (!props.hvacCategory) return []
  const cat = HVAC_CATEGORIES.find(c => c.key === props.hvacCategory)
  if (!cat) return []
  return cat.variants.filter(v => !v.dataset || v.dataset === currentDataset.value)
})

const isCentralSystem = computed(() => CENTRAL_SYSTEM_VARIANTS.includes(selectedVariant.value))
```

**Step 2: Disable efficiency dropdowns when central system is active**

In the template, update the Heating Efficiency and Cooling Efficiency selects (around lines 170-194) to add `:disabled="isCentralSystem"`:

For Heating Efficiency select (line 172):
```html
            <select
              id="heating-efficiency"
              :value="isCentralSystem ? 'Shared Heating' : (modelValue.hvac_heating_efficiency ?? '')"
              class="form-select"
              :disabled="isCentralSystem"
              @change="update('hvac_heating_efficiency', ($event.target as HTMLSelectElement).value || undefined)"
            >
```

For Cooling Efficiency select (line 186):
```html
            <select
              id="cooling-efficiency"
              :value="isCentralSystem ? 'Shared Cooling' : (modelValue.hvac_cooling_efficiency ?? '')"
              class="form-select"
              :disabled="isCentralSystem"
              @change="update('hvac_cooling_efficiency', ($event.target as HTMLSelectElement).value || undefined)"
            >
```

**Step 3: Commit**

```bash
git add frontend/src/components/AdvancedDetails.vue
git commit -m "feat: disable efficiency fields when central system variant is selected"
```

---

### Task 4: Backend — Update preprocessor value maps for renamed category keys

**Files:**
- Modify: `backend/app/services/preprocessor.py`

**Step 1: Write failing test for new category key**

Add to `backend/tests/test_preprocessor.py`:

```python
def test_forced_air_furnace_key_maps_correctly_for_resstock():
    """The new 'forced_air_furnace' key should map to Ducted Heating for ResStock."""
    inp = BuildingInput(
        building_type="Multi-Family",
        sqft=25000,
        num_stories=5,
        zipcode="10001",
        year_built=1985,
        hvac_system_type="forced_air_furnace",
    )
    features, _, dataset, _, _ = preprocess(inp)
    assert dataset == "resstock"
    assert features["in.hvac_heating_type"] == "Ducted Heating"


def test_forced_air_furnace_key_maps_correctly_for_comstock():
    """The new 'forced_air_furnace' key should work for ComStock too."""
    inp = BuildingInput(
        building_type="Office",
        sqft=50000,
        num_stories=3,
        zipcode="20001",
        year_built=1985,
        hvac_system_type="forced_air_furnace",
    )
    features, _, dataset, _, _ = preprocess(inp)
    assert dataset == "comstock"
    # Should resolve to the Residential style HVAC
    assert features["in.hvac_system_type"] == "Residential AC with residential forced air furnace"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_preprocessor.py::test_forced_air_furnace_key_maps_correctly_for_resstock tests/test_preprocessor.py::test_forced_air_furnace_key_maps_correctly_for_comstock -v`
Expected: FAIL

**Step 3: Add the new key mappings**

In `_RESSTOCK_VALUE_MAP["hvac_system_type"]` add:

```python
        "forced_air_furnace": "Ducted Heating",
        "baseboard_wall_unit": "Non-Ducted Heating",
        "mini_split_heat_pump": "Non-Ducted Heat Pump",
```

In `COMSTOCK_HVAC_MAP` (the ComStock HVAC lookup dict, around line 177), add:

```python
    "forced_air_furnace": {
        "in.hvac_category": "Residential Style Central Systems",
        "in.hvac_cool_type": "DX",
        "in.hvac_heat_type": "Furnace",
        "in.hvac_vent_type": "Residential forced air",
    },
```

Also add `"forced_air_furnace"` to the ComStock value map for `hvac_system_type` if one exists, or ensure the lookup in `COMSTOCK_HVAC_MAP` resolves to the correct variant string `"Residential AC with residential forced air furnace"`.

Check how the ComStock preprocessor resolves `hvac_system_type` — it likely uses `COMSTOCK_HVAC_MAP` to expand the key into sub-features, and separately maps the value to `in.hvac_system_type`. The `in.hvac_system_type` value needs to be `"Residential AC with residential forced air furnace"`. Look at how other category keys (like `central_chiller_boiler`) are handled and follow the same pattern.

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_preprocessor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/services/preprocessor.py backend/tests/test_preprocessor.py
git commit -m "feat: add forced_air_furnace and renamed category key mappings"
```

---

### Task 5: Integration verification — run full test suite

**Step 1: Run backend tests**

Run: `cd backend && pytest -v`
Expected: ALL PASS

**Step 2: Run frontend type check**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Manual smoke test**

Run: `cd backend && uvicorn app.main:app --reload`

Test with curl:
```bash
# Test central system variant
curl -X POST http://localhost:8000/assess -H 'Content-Type: application/json' -d '{
  "building_type": "Multi-Family",
  "sqft": 25000,
  "num_stories": 12,
  "zipcode": "10001",
  "year_built": 1975,
  "hvac_system_type": "Fan Coil Units"
}'

# Test renamed category key
curl -X POST http://localhost:8000/assess -H 'Content-Type: application/json' -d '{
  "building_type": "Multi-Family",
  "sqft": 25000,
  "num_stories": 5,
  "zipcode": "10001",
  "year_built": 1985,
  "hvac_system_type": "forced_air_furnace"
}'
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: unified HVAC categories with ResStock central system support"
```
