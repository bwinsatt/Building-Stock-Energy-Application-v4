# Ensemble Blending + Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve EUI prediction accuracy by (1) enriching zipcode lookup with HDD/CDD from ComStock data, (2) adding derived and optional advanced features to the training pipeline and preprocessor, (3) training an ensemble blend (XGBoost + LightGBM + CatBoost), and (4) validating improvement via experiment.

**Architecture:** Three layers of improvement applied incrementally:
- **Data enrichment**: One-time script extracts cluster-level median HDD65/CDD65 from ComStock's `out.params` and adds them to `zipcode_lookup.json`. County GISJOIN also added where possible for future use.
- **Feature engineering**: Training scripts gain new features (HDD/CDD, thermostat setpoints, derived features like `floor_plate_sqft`). The preprocessor gains these as optional advanced inputs (NaN when not provided — XGBoost handles natively) and derives HDD/CDD automatically from the zipcode lookup.
- **Ensemble blend**: Training scripts produce XGBoost + LightGBM + CatBoost models. Inference blends predictions with equal weights (experiment showed weighted ≈ equal). Multi-output XGBoost explored as an additional experiment.

**Tech Stack:** Python, XGBoost, LightGBM, CatBoost, Pandas, scikit-learn, Pydantic v2

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/build_hdd_cdd_lookup.py` | Create | One-time script: extract cluster→HDD/CDD and county→GISJOIN mappings from ComStock data, merge into zipcode_lookup.json. Also outputs `backend/app/data/cluster_hdd_cdd.json` for training scripts |
| `backend/app/data/zipcode_lookup.json` | Modify | Add `hdd65f`, `cdd65f`, and `county_gisjoin` fields per zipcode prefix |
| `backend/app/data/cluster_hdd_cdd.json` | Create | Standalone cluster→HDD/CDD lookup for use by training scripts (especially ResStock which lacks `out.params` HDD/CDD) |
| `scripts/training_utils.py` | Modify | Add LightGBM/CatBoost training functions, ensemble evaluation helpers |
| `scripts/train_comstock_deltas.py` | Modify | Add new feature columns (HDD/CDD, thermostat, derived), train 3 model types |
| `scripts/train_resstock_deltas.py` | Modify | Add new feature columns (HDD/CDD, thermostat, derived), train 3 model types |
| `backend/app/schemas/request.py` | Modify | Add optional advanced input fields (thermostat setpoints, setback, weekend hours) |
| `backend/app/services/preprocessor.py` | Modify | Map new fields to model columns, derive HDD/CDD from zipcode lookup, compute `floor_plate_sqft` |
| `backend/app/inference/model_manager.py` | Modify | Load and blend predictions from 3 model types per target |
| `scripts/experiment_feature_engineering.py` | Create | Experiment script to validate feature engineering + ensemble gains before full retraining |
| `backend/tests/test_preprocessor_features.py` | Create | Tests for new feature derivation and advanced input handling |
| `backend/tests/test_ensemble_inference.py` | Create | Tests for ensemble blending in model_manager |

---

## Task 1: Build HDD/CDD Lookup Enrichment Script

**Files:**
- Create: `scripts/build_hdd_cdd_lookup.py`
- Modify: `backend/app/data/zipcode_lookup.json`

This one-time script extracts cluster-level median HDD65/CDD65 from ComStock's `out.params.hdd65f` and `out.params.cdd65f`, and merges the values into the existing zipcode lookup. Also saves a standalone `cluster_hdd_cdd.json` for use by training scripts (especially ResStock, which lacks `out.params` HDD/CDD columns).

**Important:** The column names `out.params.hdd65f` and `out.params.cdd65f` have been verified to exist in the ComStock parquet schema (confirmed via `pyarrow.parquet.read_schema`).

- [ ] **Step 0: Verify HDD/CDD columns exist in ComStock parquet**

Run: `python3 -c "import pyarrow.parquet as pq; schema = pq.read_schema('ComStock/raw_data/upgrade0_agg.parquet'); print([f.name for f in schema if 'hdd' in f.name.lower() or 'cdd' in f.name.lower()])"`
Expected: `['out.params.cdd50f', 'out.params.cdd65f', 'out.params.hdd50f', 'out.params.hdd65f']`

If these columns are missing, **STOP** — the HDD/CDD extraction approach must be revised.

- [ ] **Step 1: Write the enrichment script**

```python
#!/usr/bin/env python3
"""
One-time script: enrich zipcode_lookup.json with HDD/CDD and save cluster_hdd_cdd.json.

Extracts cluster-level median HDD65F and CDD65F from ComStock out.params,
then merges into each zipcode prefix entry via its cluster_name.
Also saves a standalone cluster_hdd_cdd.json for training scripts (ResStock needs this).

Usage:
    python3 scripts/build_hdd_cdd_lookup.py
    python3 scripts/build_hdd_cdd_lookup.py --dry-run  # preview without writing
"""
import os
import sys
import json
import argparse
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def build_cluster_hdd_cdd():
    """Extract cluster -> median HDD/CDD from ComStock baseline data."""
    raw_dir = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
    lookup_path = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')

    # Load baseline buildings with HDD/CDD
    df = pd.read_parquet(
        os.path.join(raw_dir, 'upgrade0_agg.parquet'),
        columns=['bldg_id', 'in.as_simulated_nhgis_county_gisjoin',
                 'out.params.hdd65f', 'out.params.cdd65f']
    )
    df = df.drop_duplicates(subset='bldg_id')

    # Join cluster_name
    cluster = pd.read_csv(lookup_path,
                           usecols=['nhgis_county_gisjoin', 'cluster_name'],
                           low_memory=False)
    cluster = cluster.drop_duplicates(subset='nhgis_county_gisjoin')
    df = df.merge(cluster,
                  left_on='in.as_simulated_nhgis_county_gisjoin',
                  right_on='nhgis_county_gisjoin', how='left')

    # Aggregate by cluster (median is robust to outliers)
    result = df.groupby('cluster_name').agg(
        hdd65f=('out.params.hdd65f', 'median'),
        cdd65f=('out.params.cdd65f', 'median'),
    ).round(1)

    return result.to_dict('index')


def save_cluster_hdd_cdd(cluster_hdd_cdd, dry_run=False):
    """Save standalone cluster -> HDD/CDD JSON for training scripts."""
    out_path = os.path.join(
        PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json'
    )
    if not dry_run:
        with open(out_path, 'w') as f:
            json.dump(cluster_hdd_cdd, f, indent=2)
        print(f"Saved cluster_hdd_cdd.json ({len(cluster_hdd_cdd)} clusters) to {out_path}")
    else:
        print(f"DRY RUN — would save {len(cluster_hdd_cdd)} clusters to {out_path}")


def enrich_zipcode_lookup(cluster_hdd_cdd, dry_run=False):
    """Add hdd65f and cdd65f to each prefix entry in zipcode_lookup.json."""
    lookup_path = os.path.join(
        PROJECT_ROOT, 'backend', 'app', 'data', 'zipcode_lookup.json'
    )
    with open(lookup_path) as f:
        data = json.load(f)

    prefixes = data['prefixes']
    matched = 0
    unmatched = 0
    unmatched_clusters = set()

    for prefix, entry in prefixes.items():
        cluster = entry.get('cluster_name')
        if cluster and cluster in cluster_hdd_cdd:
            entry['hdd65f'] = cluster_hdd_cdd[cluster]['hdd65f']
            entry['cdd65f'] = cluster_hdd_cdd[cluster]['cdd65f']
            matched += 1
        else:
            # Fallback: use national median
            entry['hdd65f'] = 4800.0
            entry['cdd65f'] = 1400.0
            unmatched += 1
            if cluster:
                unmatched_clusters.add(cluster)

    # Also enrich state_defaults if they exist
    if 'state_defaults' in data:
        for state, entry in data['state_defaults'].items():
            cluster = entry.get('cluster_name')
            if cluster and cluster in cluster_hdd_cdd:
                entry['hdd65f'] = cluster_hdd_cdd[cluster]['hdd65f']
                entry['cdd65f'] = cluster_hdd_cdd[cluster]['cdd65f']

    print(f"Enriched {matched} prefixes with cluster-level HDD/CDD")
    if unmatched:
        print(f"  {unmatched} prefixes used national median fallback")
        if unmatched_clusters:
            print(f"  Unmatched clusters: {unmatched_clusters}")

    if not dry_run:
        with open(lookup_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Written to {lookup_path}")
    else:
        print("DRY RUN — no files written")
        # Show a sample
        sample_prefix = list(prefixes.keys())[0]
        print(f"  Sample entry '{sample_prefix}': {json.dumps(prefixes[sample_prefix], indent=2)}")


def main():
    parser = argparse.ArgumentParser(description='Enrich zipcode_lookup.json with HDD/CDD')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = parser.parse_args()

    print("Building cluster -> HDD/CDD mapping from ComStock data...")
    cluster_hdd_cdd = build_cluster_hdd_cdd()
    print(f"  {len(cluster_hdd_cdd)} clusters with HDD/CDD values")

    print("\nSaving cluster_hdd_cdd.json...")
    save_cluster_hdd_cdd(cluster_hdd_cdd, dry_run=args.dry_run)

    print("\nEnriching zipcode_lookup.json...")
    enrich_zipcode_lookup(cluster_hdd_cdd, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run with --dry-run to verify**

Run: `python3 scripts/build_hdd_cdd_lookup.py --dry-run`
Expected: Output showing matched count (~900+ prefixes), sample entry with `hdd65f`/`cdd65f` fields.

- [ ] **Step 3: Run for real to enrich zipcode_lookup.json**

Run: `python3 scripts/build_hdd_cdd_lookup.py`
Expected: `zipcode_lookup.json` now has `hdd65f` and `cdd65f` in each prefix entry.

- [ ] **Step 4: Verify the enriched file**

Run: `python3 -c "import json; d=json.load(open('backend/app/data/zipcode_lookup.json')); e=d['prefixes']['100']; print(e)"`
Expected: Entry for NYC (prefix 100) shows `hdd65f` ~4964 and `cdd65f` ~1365 (Greater NYC Area cluster values).

- [ ] **Step 5: Commit**

```bash
git add scripts/build_hdd_cdd_lookup.py backend/app/data/zipcode_lookup.json
git commit -m "feat: enrich zipcode lookup with HDD/CDD from ComStock cluster data"
```

---

## Task 2: Feature Engineering Experiment

**Files:**
- Create: `scripts/experiment_feature_engineering.py`

Before modifying the training pipeline or preprocessor, validate that the new features actually improve accuracy. This experiment runs on ComStock baseline data with the same XGBoost/LightGBM/CatBoost comparison from the earlier ensemble experiment, but with the new features added.

- [ ] **Step 1: Write the experiment script**

The script should:
1. Load ComStock baseline data (full 91K buildings)
2. Add new features:
   - `out.params.hdd65f` and `out.params.cdd65f` (from ComStock data directly for training)
   - `in.tstat_clg_sp_f..f` and `in.tstat_htg_sp_f..f` (thermostat setpoints)
   - `in.tstat_clg_delta_f..delta_f` and `in.tstat_htg_delta_f..delta_f` (setback deltas)
   - `in.weekend_operating_hours..hr` (weekend hours)
   - Derived: `floor_plate_sqft` = `sqft / stories`
3. Train XGBoost, LightGBM, CatBoost on electricity and natural_gas targets
4. Compare against the previous experiment results (no new features)
5. Print improvement table

Key implementation details:
- Reuse the `encode_features()` from `training_utils.py` — the new numeric features pass through automatically
- The new ComStock columns (`out.params.hdd65f`, thermostat setpoints) are loaded directly from the parquet for training. At inference time, they come from zipcode lookup (HDD/CDD) or user input / NaN (thermostat).

- [ ] **Step 2: Run the experiment**

Run: `python3 scripts/experiment_feature_engineering.py`
Expected: Comparison table showing MAE/RMSE/R² for old features vs new features, per model type.

**Decision gate:** If new features improve natural gas MAE by >3% and don't hurt electricity, proceed to Tasks 3-6. If not, re-evaluate which features to keep.

- [ ] **Step 3: Commit**

```bash
git add scripts/experiment_feature_engineering.py
git commit -m "experiment: feature engineering validation (HDD/CDD, thermostat, derived)"
```

---

## Task 3: Add Advanced Input Fields to Schema

**Files:**
- Modify: `backend/app/schemas/request.py`
- Create: `backend/tests/test_preprocessor_features.py`

Add optional advanced input fields to `BuildingInput`. These are NaN when not provided — XGBoost handles missing values natively, so no imputation needed.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_preprocessor_features.py
"""Tests for new advanced input fields and derived features."""
import pytest
from app.schemas.request import BuildingInput


def test_advanced_fields_optional():
    """All new advanced fields should be optional and default to None."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985,
    )
    assert b.thermostat_heating_setpoint is None
    assert b.thermostat_cooling_setpoint is None
    assert b.thermostat_heating_setback is None
    assert b.thermostat_cooling_setback is None
    assert b.weekend_operating_hours is None


def test_advanced_fields_populated():
    """Advanced fields should accept values when provided."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985,
        thermostat_heating_setpoint=70.0,
        thermostat_cooling_setpoint=75.0,
        thermostat_heating_setback=5.0,
        thermostat_cooling_setback=3.0,
        weekend_operating_hours=16.0,
    )
    assert b.thermostat_heating_setpoint == 70.0
    assert b.thermostat_cooling_setpoint == 75.0
    assert b.thermostat_heating_setback == 5.0
    assert b.thermostat_cooling_setback == 3.0
    assert b.weekend_operating_hours == 16.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_preprocessor_features.py -v`
Expected: FAIL — `BuildingInput` doesn't have these fields yet.

- [ ] **Step 3: Add the fields to BuildingInput**

In `backend/app/schemas/request.py`, add after the existing optional fields (before utility bill fields):

```python
    # Advanced inputs (optional — XGBoost handles NaN natively)
    thermostat_heating_setpoint: Optional[float] = Field(
        None, ge=50, le=85, description="Heating setpoint (°F)"
    )
    thermostat_cooling_setpoint: Optional[float] = Field(
        None, ge=65, le=90, description="Cooling setpoint (°F)"
    )
    thermostat_heating_setback: Optional[float] = Field(
        None, ge=0, le=20, description="Heating setback delta (°F)"
    )
    thermostat_cooling_setback: Optional[float] = Field(
        None, ge=0, le=20, description="Cooling setback delta (°F)"
    )
    weekend_operating_hours: Optional[float] = Field(
        None, ge=0, le=24, description="Weekend operating hours per day"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_preprocessor_features.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/request.py backend/tests/test_preprocessor_features.py
git commit -m "feat: add optional advanced input fields (thermostat, weekend hours)"
```

---

## Task 4: Update Preprocessor to Derive New Features

**Files:**
- Modify: `backend/app/services/preprocessor.py`
- Modify: `backend/tests/test_preprocessor_features.py`

The preprocessor needs to:
1. Read `hdd65f`/`cdd65f` from the zipcode lookup (automatic, no user input)
2. Map advanced user inputs to model column names (or leave as NaN)
3. Compute derived feature: `floor_plate_sqft`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_preprocessor_features.py`:

```python
from app.services.preprocessor import preprocess


def test_hdd_cdd_derived_from_zipcode():
    """HDD/CDD should be automatically derived from zipcode lookup."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    features, _, dataset, _, _ = preprocess(b)
    assert 'hdd65f' in features
    assert 'cdd65f' in features
    assert features['hdd65f'] > 0
    assert features['cdd65f'] > 0


def test_floor_plate_sqft_derived():
    """floor_plate_sqft should be sqft / num_stories."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=5,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    features, _, _, _, _ = preprocess(b)
    assert 'floor_plate_sqft' in features
    assert features['floor_plate_sqft'] == pytest.approx(10000.0)



def test_advanced_inputs_mapped_to_features():
    """When user provides thermostat setpoints, they should appear in features."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
        thermostat_heating_setpoint=70.0,
        thermostat_cooling_setpoint=75.0,
    )
    features, _, _, _, _ = preprocess(b)
    assert features.get('in.tstat_htg_sp_f..f') == 70.0
    assert features.get('in.tstat_clg_sp_f..f') == 75.0


def test_advanced_inputs_none_when_not_provided():
    """When user doesn't provide advanced inputs, they should be NaN (not present or None)."""
    b = BuildingInput(
        building_type="Office", sqft=50000, num_stories=3,
        zipcode="20001", year_built=1985, heating_fuel="NaturalGas",
    )
    features, _, _, _, _ = preprocess(b)
    # Thermostat features should be NaN (None or float('nan'))
    import math
    tstat_val = features.get('in.tstat_htg_sp_f..f')
    assert tstat_val is None or (isinstance(tstat_val, float) and math.isnan(tstat_val))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_preprocessor_features.py -v`
Expected: FAIL — preprocessor doesn't produce these features yet.

- [ ] **Step 3: Add a `get_hdd_cdd()` method to _ZipcodeLookup (DO NOT change `lookup()` signature)**

**Critical:** Do NOT change the return signature of `lookup()` — it returns `(state, climate_zone, cluster_name)` and is called by multiple files:
- `preprocessor.py` line ~1156 (`preprocess()`)
- `energy_star.py` line ~157
- `address_lookup.py` line ~662

Instead, add a **separate method** for HDD/CDD:

```python
def get_hdd_cdd(self, zipcode: str) -> tuple[float, float]:
    """Return (hdd65f, cdd65f) for a zipcode. Falls back to national medians."""
    if self._prefixes is None:
        self._load()
    assert self._prefixes is not None

    prefix = zipcode[:3]
    entry = self._prefixes.get(prefix)
    if entry is not None:
        return entry.get("hdd65f", 4800.0), entry.get("cdd65f", 1400.0)
    return 4800.0, 1400.0  # national median fallback
```

Then in `preprocess()`, call it after the existing location lookup:
```python
    state, climate_zone, cluster_name = _get_location_from_zipcode(building_input.zipcode)
    hdd65f, cdd65f = _zip_lookup.get_hdd_cdd(building_input.zipcode)
```

This avoids breaking any existing call sites.

- [ ] **Step 4: Add new feature mapping in COMSTOCK_FIELD_MAP**

Add new entries to the field maps and the `preprocess()` function:

ComStock advanced field map (add after existing `COMSTOCK_FIELD_MAP`):
```python
COMSTOCK_ADVANCED_FIELD_MAP = {
    "thermostat_heating_setpoint": "in.tstat_htg_sp_f..f",
    "thermostat_cooling_setpoint": "in.tstat_clg_sp_f..f",
    "thermostat_heating_setback": "in.tstat_htg_delta_f..delta_f",
    "thermostat_cooling_setback": "in.tstat_clg_delta_f..delta_f",
    "weekend_operating_hours": "in.weekend_operating_hours..hr",
}

RESSTOCK_ADVANCED_FIELD_MAP = {
    "thermostat_heating_setpoint": "in.heating_setpoint",
    "thermostat_cooling_setpoint": "in.cooling_setpoint",
    "thermostat_heating_setback": "in.heating_setpoint_offset_magnitude",
    "thermostat_cooling_setback": "in.cooling_setpoint_offset_magnitude",
}
```

- [ ] **Step 5: Add derived feature computation in preprocess()**

After step 8b (energy code resolution) in the `preprocess()` function, add:

```python
    # --- 8c. Derive HDD/CDD and interaction features ---
    features['hdd65f'] = hdd65f  # from zipcode lookup (step 3)
    features['cdd65f'] = cdd65f

    # Floor plate sqft (derived from existing inputs)
    features['floor_plate_sqft'] = building_input.sqft / building_input.num_stories

    # --- 8d. Map advanced optional inputs (NaN when not provided) ---
    advanced_map = COMSTOCK_ADVANCED_FIELD_MAP if not is_resstock else RESSTOCK_ADVANCED_FIELD_MAP
    for user_field, model_col in advanced_map.items():
        value = getattr(building_input, user_field, None)
        if value is not None:
            features[model_col] = value
        else:
            features[model_col] = float('nan')  # XGBoost handles NaN natively
```

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_preprocessor_features.py -v`
Expected: PASS

- [ ] **Step 7: Run existing tests to ensure no regressions**

Run: `cd backend && pytest tests/ -v`
Expected: All existing tests still pass. Note: `_get_location_from_zipcode()` signature is unchanged (still returns 3 values). The new `get_hdd_cdd()` method is additive. The most likely regression point is the features dict now containing additional keys (`hdd65f`, `cdd65f`, `floor_plate_sqft`, etc.) — verify that downstream consumers (model_manager, assessment) handle extra keys gracefully.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/preprocessor.py backend/tests/test_preprocessor_features.py
git commit -m "feat: derive HDD/CDD and interaction features in preprocessor"
```

---

## Task 5: Update Training Scripts with New Features

**Files:**
- Modify: `scripts/training_utils.py`
- Modify: `scripts/train_comstock_deltas.py`
- Modify: `scripts/train_resstock_deltas.py`

Add the new features to the training pipeline so retrained models expect them.

- [ ] **Step 1: Add LightGBM and CatBoost training functions to training_utils.py**

Add after the existing `train_single_model()`:

**Categorical encoding differs per model type:**
- **XGBoost**: Uses `pd.Categorical` + `enable_categorical=True` (existing `encode_features()` output)
- **LightGBM**: Uses `pd.Categorical` dtype — same as XGBoost. Pass `categorical_feature=cat_indices` to `.fit()`
- **CatBoost**: Requires **string-typed** categoricals, NOT `pd.Categorical`. Prepare a separate DataFrame with `astype(str)` for categorical columns. Pass `cat_features=cat_indices` to constructor.

Add a helper to prepare CatBoost-compatible data:

```python
def prepare_catboost_data(df, feature_cols, cat_feature_names):
    """Prepare DataFrame for CatBoost: string-typed categoricals, numeric pass-through."""
    df_cb = df[feature_cols].copy()
    for col in feature_cols:
        if col in cat_feature_names:
            df_cb[col] = df_cb[col].astype(str)
        else:
            df_cb[col] = pd.to_numeric(df_cb[col], errors='coerce').fillna(0)
    return df_cb
```

```python
def train_lightgbm_model(X_train, y_train, params, cat_indices, random_state=42):
    """Train a LightGBM model. X_train should have pd.Categorical dtype columns."""
    from lightgbm import LGBMRegressor
    lgbm_params = {
        'objective': 'regression',
        'n_estimators': params.get('n_estimators', 300),
        'max_depth': params.get('max_depth', 6),
        'learning_rate': params.get('learning_rate', 0.1),
        'min_child_weight': params.get('min_child_weight', 5),
        'subsample': params.get('subsample', 0.8),
        'colsample_bytree': params.get('colsample_bytree', 0.8),
        'random_state': random_state,
        'n_jobs': -1,
        'verbose': -1,
    }
    model = LGBMRegressor(**lgbm_params)
    model.fit(X_train, y_train, categorical_feature=cat_indices)
    return model


def train_catboost_model(X_train_str, y_train, params, cat_indices, random_state=42):
    """Train a CatBoost model. X_train_str must have string-typed categoricals (NOT pd.Categorical)."""
    from catboost import CatBoostRegressor
    model = CatBoostRegressor(
        iterations=params.get('n_estimators', 300),
        depth=min(params.get('max_depth', 6), 10),
        learning_rate=params.get('learning_rate', 0.1),
        random_seed=random_state,
        verbose=0,
        cat_features=cat_indices,
    )
    model.fit(X_train_str, y_train)
    return model
```

In the training loop, prepare data for each model type:
```python
# XGBoost/LightGBM: use encode_features() output (pd.Categorical)
X_enc, encoders = encode_features(df, FEATURE_COLS)

# CatBoost: prepare string-typed version
X_cb = prepare_catboost_data(df, FEATURE_COLS, CAT_FEATURE_NAMES)

# Identify categorical column indices for LightGBM/CatBoost
cat_indices = [i for i, col in enumerate(FEATURE_COLS) if col in CAT_FEATURE_NAMES]
```

- [ ] **Step 2: Update FEATURE_COLS in train_comstock_deltas.py**

**Important — Column name alignment:** Training data has `out.params.hdd65f` but the preprocessor produces `hdd65f`. Rename during data loading so the model feature columns match inference:

```python
# After loading parquet, rename HDD/CDD columns to match inference names:
df = df.rename(columns={
    'out.params.hdd65f': 'hdd65f',
    'out.params.cdd65f': 'cdd65f',
})
```

Then add to `FEATURE_COLS` list (using the renamed names):
```python
    # --- New features (HDD/CDD + thermostat + derived) ---
    'hdd65f',
    'cdd65f',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
    # --- Baseline EUI features (from utility calibration plan) ---
    'baseline_electricity',
    'baseline_natural_gas',
    'baseline_fuel_oil',
    'baseline_propane',
    'baseline_district_heating',
```

**Baseline EUI columns (from utility calibration plan):** After the baseline/upgrade merge (where deltas are computed), the baseline fuel EUI columns are already present in the merged DataFrame. Rename them to `baseline_{fuel}` and keep them as features:

```python
# Rename baseline fuel columns to baseline_{fuel} for use as features
FUEL_COL_MAP = {
    'out.electricity.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_electricity',
    'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_natural_gas',
    'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_fuel_oil',
    'out.propane.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_propane',
    'out.district_heating.total.energy_consumption_intensity..kwh_per_ft2': 'baseline_district_heating',
}
# After merge, rename the baseline (upgrade 0) fuel columns:
for orig_col, new_col in FUEL_COL_MAP.items():
    baseline_col = f"{orig_col}_baseline"  # suffixed by merge
    if baseline_col in df.columns:
        df[new_col] = df[baseline_col]
```

These columns will be NaN for baseline (upgrade 0) training rows, teaching the model to handle both calibrated (user provides utility data) and uncalibrated (no utility data) inference. At inference time, `predict_delta` passes `baseline_eui` only when the user provides actual utility bills; otherwise `None` → NaN. Validated: +12-18% R² with actual data, no regression without it (see `scripts/validate_baseline_feature.py` results).

Add to `LOAD_COLS` the new columns using their **original parquet names** (they get renamed after loading):
```python
# Add to LOAD_COLS (parquet column names):
'out.params.hdd65f', 'out.params.cdd65f',
'in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
'in.weekend_operating_hours..hr',
```

After data loading and renaming HDD/CDD columns, add derived feature computation:
```python
    # Derived features
    df['floor_plate_sqft'] = df['in.sqft..ft2'] / df['in.number_stories'].clip(lower=1)
```

Add the derived column to `FEATURE_COLS`:
```python
    'floor_plate_sqft',
```

- [ ] **Step 3: Update FEATURE_COLS in train_resstock_deltas.py**

Similar changes for ResStock, but using ResStock column names:
```python
    # New features — HDD/CDD come from cluster lookup (no out.params in ResStock)
    'hdd65f',  # joined from ComStock cluster-level data
    'cdd65f',
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
    # --- Baseline EUI features (from utility calibration plan) ---
    'baseline_electricity',
    'baseline_natural_gas',
    'baseline_fuel_oil',
    'baseline_propane',
```

**Baseline EUI columns for ResStock:** Same approach as ComStock (rename baseline fuel columns after merge), but ResStock has 4 fuel types (no district_heating).

ResStock doesn't have `out.params.hdd65f` — the HDD/CDD must be joined via the `cluster_hdd_cdd.json` file created in Task 1. Add this to `load_baseline_data()` after the cluster join:

```python
    # Join HDD/CDD from cluster_hdd_cdd.json (built by scripts/build_hdd_cdd_lookup.py)
    hdd_cdd_path = os.path.join(PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json')
    with open(hdd_cdd_path) as f:
        cluster_hdd_cdd = json.load(f)
    df['hdd65f'] = df['cluster_name'].map(lambda c: cluster_hdd_cdd.get(c, {}).get('hdd65f', 4800.0))
    df['cdd65f'] = df['cluster_name'].map(lambda c: cluster_hdd_cdd.get(c, {}).get('cdd65f', 1400.0))
```

This uses the standalone `cluster_hdd_cdd.json` saved by Task 1.

Also add derived feature (same as ComStock):
```python
    # Derived features (must match what preprocessor produces at inference time)
    df['floor_plate_sqft'] = df['in.sqft..ft2'] / pd.to_numeric(df['in.geometry_stories'], errors='coerce').clip(lower=1)
```

Add to ResStock `FEATURE_COLS`:
```python
    'floor_plate_sqft',
```

- [ ] **Step 4: Add ensemble training loop**

In the training loop (Phase 2), after training the XGBoost model for each fuel type, also train LightGBM and CatBoost. Save all three with naming convention:
- `XGB_upgrade{id}_{fuel}.pkl` (existing)
- `LGBM_upgrade{id}_{fuel}.pkl` (new)
- `CB_upgrade{id}_{fuel}.pkl` (new)

Each model gets its own `_meta.json` and `_encoders.pkl`.

- [ ] **Step 5: Run a single-upgrade training test**

Run: `python3 scripts/train_comstock_deltas.py --upgrades 1 --skip-tuning`
Expected: Trains 3 model types × 5 fuel types = 15 models for upgrade 1. Output shows metrics for each.

- [ ] **Step 6: Commit**

```bash
git add scripts/training_utils.py scripts/train_comstock_deltas.py scripts/train_resstock_deltas.py
git commit -m "feat: add new features and ensemble training (XGB + LGBM + CatBoost)"
```

---

## Task 6: Update Model Manager for Ensemble Inference

**Files:**
- Modify: `backend/app/inference/model_manager.py`
- Create: `backend/tests/test_ensemble_inference.py`

The model manager needs to load all three model types and average their predictions.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_ensemble_inference.py
"""Tests for ensemble blending in model_manager."""
import pytest
import numpy as np


def test_blend_predictions_simple_average():
    """Blend should average predictions from available models."""
    from app.inference.model_manager import _blend_predictions

    preds = {
        'xgb': np.array([10.0, 20.0, 30.0]),
        'lgbm': np.array([12.0, 18.0, 32.0]),
        'catboost': np.array([11.0, 22.0, 28.0]),
    }
    result = _blend_predictions(preds)
    expected = np.array([11.0, 20.0, 30.0])
    np.testing.assert_allclose(result, expected)


def test_blend_predictions_missing_model():
    """Blend should work with fewer than 3 models (graceful degradation)."""
    from app.inference.model_manager import _blend_predictions

    preds = {
        'xgb': np.array([10.0, 20.0]),
    }
    result = _blend_predictions(preds)
    np.testing.assert_allclose(result, np.array([10.0, 20.0]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ensemble_inference.py -v`
Expected: FAIL — `_blend_predictions` doesn't exist yet.

- [ ] **Step 3: Implement ensemble loading and blending**

In `model_manager.py`, the key changes:

1. Add a `_blend_predictions()` function:
```python
def _blend_predictions(predictions: dict[str, np.ndarray]) -> np.ndarray:
    """Average predictions from multiple model types. Equal weights."""
    arrays = list(predictions.values())
    if not arrays:
        raise ValueError("No predictions to blend")
    return np.mean(arrays, axis=0)
```

2. **Update regex patterns** to recognize all model prefixes. The existing regex is:
```python
_RE_UPGRADE = re.compile(r"^XGB_upgrade(\d+)_(.+)\.pkl$")
```
Change to match any prefix:
```python
_MODEL_PREFIXES = ('XGB', 'LGBM', 'CB')
_RE_UPGRADE = re.compile(r"^(XGB|LGBM|CB)_upgrade(\d+)_(.+)\.pkl$")
```

**Critical — regex group indices shift:** After adding the prefix capture group, update all `_index_directory` code that references match groups:
- Old: `m.group(1)` = upgrade_id, `m.group(2)` = fuel_name
- New: `m.group(1)` = prefix (XGB/LGBM/CB), `m.group(2)` = upgrade_id, `m.group(3)` = fuel_name

**Scope: Ensemble blending applies to upgrade + baseline models ONLY.** Sizing models (`_RE_SIZING`) and rate models (`_RE_RATE`) remain XGBoost-only — do NOT update their regex patterns. These are small models where ensemble overhead isn't justified.

3. **Update the index structure.** Currently models are indexed as `(upgrade_id, fuel_type) -> bundle_dict` where `bundle_dict` has keys `model`, `encoders`, `meta`. Change to store an **ensemble bundle**: `(upgrade_id, fuel_type) -> {'xgb': sub_bundle, 'lgbm': sub_bundle, 'cb': sub_bundle}` where each `sub_bundle` is `{'model': model, 'encoders': encoders, 'meta': meta}`.

**Critical — each model type needs its own encoders.** CatBoost uses string-typed categoricals while XGBoost/LightGBM use `pd.Categorical`. Each model type's `_encoders.pkl` file captures its own encoding. When predicting, apply the correct encoders for each model type:
```python
preds = {}
for prefix, sub_bundle in ensemble_bundle.items():
    model = sub_bundle['model']
    encoders = sub_bundle['encoders']
    X_enc = encode_for_model_type(features, encoders, prefix)  # prefix determines encoding strategy
    preds[prefix] = model.predict(X_enc)
return _blend_predictions(preds)
```

The `_load_bundle` method loads whichever prefixes exist on disk for a given (upgrade_id, fuel_type). If only XGB exists, the dict has one entry.

4. **Update LRU cache sizing.** The current `_DEFAULT_LRU_CAP = 400` was sized for XGBoost-only. Since each cache entry now holds up to 3 sub-bundles, the *entry count* stays the same but *memory per entry* increases. If memory is a concern, reduce to `_DEFAULT_LRU_CAP = 200`. Alternatively, keep at 400 since each individual LGBM/CatBoost model is similar in size to XGBoost.

5. **Save model artifacts with explicit naming convention.** In training scripts, construct model names per type:
```python
for model_type, model, X_data in [('XGB', xgb_model, X_enc), ('LGBM', lgbm_model, X_enc), ('CB', cb_model, X_cb)]:
    model_name = f'{model_type}_upgrade{uid}_{fuel_name}'
    save_model_artifacts(model, encoders_for_type, FEATURE_COLS, metrics, OUTPUT_DIR, model_name)
```

6. Update `predict_baseline()` and `predict_delta()` to call all loaded models and blend:
```python
def predict_baseline(self, features, dataset, fuel_type):
    ensemble = self._get_ensemble_bundle(dataset, 'upgrade0', fuel_type)
    preds = {}
    for prefix, sub_bundle in ensemble.items():
        X_enc = self._encode_features(features, sub_bundle['encoders'], prefix)
        preds[prefix] = sub_bundle['model'].predict(X_enc)
    return _blend_predictions(preds)
```

**Backward compatibility:** If only XGBoost models exist on disk (before retraining), the ensemble dict has a single `{'xgb': sub_bundle}` entry — `_blend_predictions` returns the XGBoost prediction unchanged. No behavior change.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_ensemble_inference.py tests/ -v`
Expected: All tests pass, including existing tests (backward compatibility).

- [ ] **Step 5: Commit**

```bash
git add backend/app/inference/model_manager.py backend/tests/test_ensemble_inference.py
git commit -m "feat: ensemble blending in model_manager (XGB + LGBM + CatBoost)"
```

---

## Task 7: Multi-Output XGBoost Experiment (Optional)

**Files:**
- Create: `scripts/experiment_multi_output.py`

This is a stretch experiment to test if predicting all fuel types jointly (via XGBoost's `multi_strategy='multi_output_tree'`) improves natural gas prediction by leveraging cross-fuel correlations.

- [ ] **Step 1: Write the experiment script**

Train a single multi-output XGBoost model that predicts `[electricity, natural_gas, fuel_oil, propane, district_heating]` jointly, using `multi_strategy='multi_output_tree'`. Compare natural gas MAE/R² against the independent per-fuel model.

Key code:
```python
from xgboost import XGBRegressor

model = XGBRegressor(
    objective='reg:squarederror',
    multi_strategy='multi_output_tree',
    n_estimators=300, max_depth=6, learning_rate=0.1,
    enable_categorical=True, random_state=42, n_jobs=-1,
)
y_multi = df[['elec_eui', 'gas_eui', 'oil_eui', 'propane_eui', 'dh_eui']].values
model.fit(X_train, y_multi_train)
y_pred = model.predict(X_test)  # shape: (n_samples, 5)
```

- [ ] **Step 2: Run and evaluate**

Run: `python3 scripts/experiment_multi_output.py`
Expected: Comparison table. If natural gas R² improves >2% with joint prediction, consider integrating this approach.

- [ ] **Step 3: Commit**

```bash
git add scripts/experiment_multi_output.py
git commit -m "experiment: multi-output XGBoost (joint fuel prediction)"
```

---

## Task 8: Full Retraining Run

**Files:** No new files — uses modified training scripts from Task 5.

After all code changes are validated, run a full retrain of all ComStock and ResStock models with the new features and ensemble approach.

- [ ] **Step 1: Retrain ComStock baseline + all upgrades**

Run: `python3 scripts/train_comstock_deltas.py --skip-tuning`
Expected: Trains 65 upgrades × 5 fuel types × 3 model types = 975 models. Runtime ~2-4 hours.

**Note:** Consider running with `--upgrades 0 1 4 13` first (baseline + a few representative upgrades) to validate before the full run.

- [ ] **Step 2: Retrain ResStock baseline + all upgrades**

Run: `python3 scripts/train_resstock_deltas.py --skip-tuning`
Expected: Trains 32 upgrades × 4 fuel types × 3 model types = 384 models.

- [ ] **Step 3: Validate retrained models via API**

Run the backend and submit a test assessment:
```bash
cd backend && uvicorn app.main:app --reload
# In another terminal:
curl -X POST http://localhost:8000/assess -H 'Content-Type: application/json' -d '{
  "buildings": [{"building_type": "Office", "sqft": 50000, "num_stories": 3,
                 "zipcode": "20001", "year_built": 1985}]
}'
```
Expected: Response includes EUI predictions. Compare baseline EUI values against pre-retrain results — they should be similar but slightly different (improved accuracy).

- [ ] **Step 4: Commit retrained models**

```bash
git add XGB_Models/
git commit -m "feat: retrained models with new features and ensemble (XGB+LGBM+CB)"
```

---

## Execution Order and Dependencies

```
Task 1 (HDD/CDD lookup) ──→ Task 2 (experiment) ──→ DECISION GATE
                                                          │
                                                     if >3% gain
                                                          │
                                    ┌─────────────────────┼─────────────────────┐
                                    ▼                     ▼                     ▼
                              Task 3 (schema)       Task 7 (optional         Task 5 (training
                                    │                multi-output              scripts)
                                    ▼                experiment)                  │
                              Task 4 (preprocessor)                              │
                                    │                                            │
                                    └────────────────────┬───────────────────────┘
                                                         ▼
                                                   Task 6 (model manager)
                                                         │
                                                         ▼
                                                   Task 8 (full retrain)
```

**Tasks 1-2** can be done independently as experiments. Task 1 only adds data to `zipcode_lookup.json` (harmless even if gate fails).
**Tasks 3-6** all happen AFTER the decision gate. Schema changes (Task 3) should not be committed before the gate passes, to avoid adding API fields that have no model support.
**Tasks 3-4** (schema + preprocessor) can be done in parallel with Task 5 (training scripts).
**Task 6** (model manager) depends on Tasks 4 and 5.
**Task 7** is optional and independent — can run in parallel with Tasks 3-6.
**Task 8** depends on all prior tasks.
