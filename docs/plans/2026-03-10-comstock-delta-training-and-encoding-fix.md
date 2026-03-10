# ComStock Delta Model Training & Number-of-Stories Encoding Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Retrain ComStock upgrade models as delta/savings models (matching ResStock approach) and fix the `in.number_stories` categorical encoding mismatch in the preprocessor.

**Architecture:** Create `train_comstock_deltas.py` mirroring `train_resstock_deltas.py` — joins baseline + upgrade parquets on `bldg_id`, computes `delta = baseline_consumption - upgrade_consumption` per fuel, trains XGBoost on deltas. Add a `_comstock_number_stories` binning function to the preprocessor to convert integer story counts to the categorical strings the models expect.

**Tech Stack:** Python, XGBoost, pandas, pytest

---

## Task 1: Fix `in.number_stories` Encoding in Preprocessor

**Files:**
- Modify: `backend/app/services/preprocessor.py` (~line 1148-1158, feature mapping section)
- Test: `backend/tests/test_preprocessor.py`

### Step 1: Write the failing test

Add to `backend/tests/test_preprocessor.py`:

```python
@pytest.mark.parametrize("stories,expected", [
    (1, "1"),
    (3, "3"),
    (14, "14"),
    (15, "15_25"),
    (20, "15_25"),
    (25, "15_25"),
    (26, "over_25"),
    (40, "over_25"),
    (100, "over_25"),
])
def test_comstock_number_stories_encoding(stories, expected):
    """Integer num_stories should map to ComStock categorical bins."""
    from app.services.preprocessor import _comstock_number_stories
    assert _comstock_number_stories(stories) == expected
```

### Step 2: Run test to verify it fails

Run: `cd backend && pytest tests/test_preprocessor.py::test_comstock_number_stories_encoding -v`
Expected: FAIL — `_comstock_number_stories` not defined

### Step 3: Write the binning function and wire it into preprocessing

In `backend/app/services/preprocessor.py`, add the function near the other ComStock helper functions (around line 555, near `_resstock_building_type_height`):

```python
def _comstock_number_stories(num_stories: int) -> str:
    """Map integer story count to ComStock categorical bin.

    ComStock training data uses string categories:
    '1' through '14', '15_25', and 'over_25'.
    """
    if num_stories <= 14:
        return str(num_stories)
    elif num_stories <= 25:
        return "15_25"
    else:
        return "over_25"
```

Then in the feature mapping loop (~line 1148-1158), add a conversion clause alongside the existing `year_built` → vintage conversion:

```python
    for user_field, model_col in field_map.items():
        if user_field not in resolved:
            continue
        value = resolved[user_field]
        # Convert year_built to vintage bucket
        if user_field == "year_built" and isinstance(value, (int, float)):
            value = year_to_vintage(int(value), dataset)
        # Convert num_stories to categorical bin (ComStock only)
        elif user_field == "num_stories" and not is_resstock and isinstance(value, (int, float)):
            value = _comstock_number_stories(int(value))
        # Map user-facing values to training-data values
        elif user_field in value_map and isinstance(value, str):
            value = value_map[user_field].get(value, value)
        features[model_col] = value
```

### Step 4: Run tests to verify they pass

Run: `cd backend && pytest tests/test_preprocessor.py::test_comstock_number_stories_encoding -v`
Expected: all 9 parametrized cases PASS

### Step 5: Write integration test verifying full preprocessing output

Add to `backend/tests/test_preprocessor.py`:

```python
def test_preprocess_40_story_office_encodes_stories():
    """A 40-story office should encode in.number_stories as 'over_25'."""
    from app.schemas.request import BuildingInput
    from app.services.preprocessor import preprocess

    building = BuildingInput(
        building_type="Office", sqft=350000, num_stories=40,
        zipcode="10019", year_built=1982, heating_fuel="NaturalGas",
    )
    features, _, dataset, _, _ = preprocess(building)
    assert dataset == "comstock"
    assert features["in.number_stories"] == "over_25"


def test_preprocess_3_story_office_encodes_stories():
    """A 3-story office should encode in.number_stories as '3'."""
    from app.schemas.request import BuildingInput
    from app.services.preprocessor import preprocess

    building = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985,
    )
    features, _, dataset, _, _ = preprocess(building)
    assert features["in.number_stories"] == "3"
```

### Step 6: Run full preprocessor test suite

Run: `cd backend && pytest tests/test_preprocessor.py -v`
Expected: all tests PASS

### Step 7: Commit

```bash
git add backend/app/services/preprocessor.py backend/tests/test_preprocessor.py
git commit -m "fix: bin ComStock num_stories integer to categorical string"
```

---

## Task 2: Create `train_comstock_deltas.py`

**Files:**
- Create: `scripts/train_comstock_deltas.py`
- Reference: `scripts/train_resstock_deltas.py` (template)
- Reference: `scripts/train_comstock_upgrades.py` (ComStock-specific config)

### Step 1: Create the training script

Create `scripts/train_comstock_deltas.py`. This mirrors `train_resstock_deltas.py` with these ComStock-specific differences:

- **5 fuel types** (adds `district_heating`), not 4
- **25 feature columns** from `train_comstock_upgrades.py` FEATURE_COLS
- **Data loading**: uses `completed_status == 'Success'` + `applicability == True` filtering (no MF/occupied filter)
- **Cluster join**: on `in.as_simulated_nhgis_county_gisjoin` (not `in.county`)
- **LOAD_COLS**: includes `completed_status` and `in.as_simulated_nhgis_county_gisjoin`
- **Dedup**: `drop_duplicates(subset='bldg_id')` before joining
- **Tune groups and representatives**: copied from `train_comstock_upgrades.py`
- **Output dir**: `XGB_Models/ComStock_Upgrades_2025_R3/` (same as current models — overwrites non-baseline)
- **Skips upgrade 0** (baseline stays as absolute EUI model)

Key structure:

```python
#!/usr/bin/env python3
"""
Train XGBoost delta/savings models for ComStock 2025 R3 upgrade measures.
Produces 5 models per upgrade (one per fuel type) targeting per-fuel savings
(baseline EUI - upgrade EUI) instead of absolute post-upgrade EUI.

Usage:
    python3 scripts/train_comstock_deltas.py                       # Train all
    python3 scripts/train_comstock_deltas.py --upgrades 1 43 53    # Train specific
    python3 scripts/train_comstock_deltas.py --skip-tuning         # Use saved params
"""

# CONFIGURATION section: copy FUEL_TYPES, FEATURE_COLS, TUNE_GROUPS,
# TUNE_REPRESENTATIVES from train_comstock_upgrades.py exactly.
# OUTPUT_DIR same: XGB_Models/ComStock_Upgrades_2025_R3/

# DATA LOADING:
# load_baseline_data() — loads upgrade0_agg.parquet, dedup by bldg_id,
#   merge cluster_name via nhgis_county_gisjoin, fill null fuels with 0
#
# load_paired_data(upgrade_id, df_baseline) — loads upgrade{N}_agg.parquet,
#   filter completed_status=='Success' & applicability==True, dedup by bldg_id,
#   inner join with baseline on bldg_id, compute delta_{fuel} = base - upgrade
#
# TRAINING LOOP: identical to train_resstock_deltas.py
#   - Skip upgrade 0
#   - Tune on delta_electricity per group
#   - Train per fuel, save with same naming convention
#   - Save training_results_delta.xlsx
```

### Step 2: Verify script runs on a single upgrade

Run: `cd /path/to/project && python3 scripts/train_comstock_deltas.py --upgrades 53 --skip-tuning`
Expected: trains 5 fuel models for upgrade 53, saves to `XGB_Models/ComStock_Upgrades_2025_R3/`

### Step 3: Spot-check predictions with new delta model

```python
# Quick validation: load the new upgrade 53 electricity model and predict
# for the 3-story 50k sqft DC office. Result should be small savings
# (roughly 0.1-1.5 kWh/ft2 electricity savings), not 13+ kWh/ft2.
```

### Step 4: Commit

```bash
git add scripts/train_comstock_deltas.py
git commit -m "feat: add ComStock delta/savings model training script"
```

---

## Task 3: Retrain All ComStock Upgrade Models

### Step 1: Run full training

Run: `python3 scripts/train_comstock_deltas.py --skip-tuning`

This trains upgrades 1-65 (skipping 0). Uses saved hyperparameters from existing `tuned_hyperparameters.json`. Overwrites the absolute-EUI upgrade models with delta models.

Expected: ~325 models (65 upgrades × 5 fuels), training_results_delta.xlsx saved.

### Step 2: Spot-check a few upgrades

Verify predictions for the test office building (50k sqft, 3-story, DC):
- Upgrade 53 (Code Envelope): electricity savings should be ~0.1-1.5 kWh/ft2
- Upgrade 43 (LED Lighting): electricity savings should be ~1-3 kWh/ft2
- Upgrade 31 (Chiller): electricity savings should be small positive

### Step 3: Commit the retrained models

```bash
git add XGB_Models/ComStock_Upgrades_2025_R3/
git commit -m "feat: retrain ComStock upgrades as delta/savings models"
```

---

## Task 4: Update CLAUDE.md Documentation

### Step 1: Update CLAUDE.md

The "Upgrade models are **delta/savings models**" statement is now accurate for both datasets. No change needed to that line, but add a note about the training scripts:

In the Architecture > Data & Models section, add:
```
- **Training scripts**: `scripts/train_comstock_deltas.py` and `scripts/train_resstock_deltas.py` train upgrade models on delta targets (baseline - upgrade EUI). Baseline models (upgrade 0) predict absolute EUI.
```

### Step 2: Commit

```bash
git add CLAUDE.md
git commit -m "docs: document delta model training scripts"
```

---

## Verification Checklist

After all tasks complete:

1. `cd backend && pytest tests/test_preprocessor.py -v` — all pass
2. `cd backend && pytest` — full test suite passes
3. For a 40-story 350k sqft NYC office:
   - `in.number_stories` encodes as `"over_25"` (not `"1"`)
   - Code Envelope savings should be ~6-10% (not 79%)
   - All upgrade savings should be in reasonable single/low-double-digit percentages
4. For a 3-story 50k sqft DC office (test fixture):
   - Results should match ComStock data expectations (~8-10% for Code Envelope)
