# Upgrade Model Training Pipeline - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Train 66 ComStock + 33 ResStock XGBoost models that predict post-upgrade EUI for each energy efficiency measure, then validate baseline predictions against CBECS 2018 real-world data.

**Architecture:** Three scripts — a shared training library (`scripts/training_utils.py`), a ComStock training script (`scripts/train_comstock_upgrades.py`), and a ResStock training script (`scripts/train_resstock_upgrades.py`). Each upgrade gets its own XGBoost model trained on applicable buildings only, using Optuna for hyperparameter tuning on 3 representative measures then applying best params to similar measures. A fourth script (`scripts/validate_cbecs.py`) validates baseline predictions against CBECS. Models are saved to `XGB_Models/ComStock_Upgrades_2025_R3/` and `XGB_Models/ResStock_Upgrades_2025_R1/`.

**Tech Stack:** Python 3.13, xgboost, scikit-learn, optuna, pandas, pyarrow, joblib, numpy

---

### Task 1: Install Optuna Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Install optuna**

```bash
pip3 install optuna
```

**Step 2: Add to requirements.txt**

Add `optuna` to the requirements file.

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add optuna dependency for hyperparameter tuning"
```

---

### Task 2: Create Training Utilities Module

**Files:**
- Create: `scripts/training_utils.py`

This module contains all shared functions used by both ComStock and ResStock training scripts.

**Step 1: Write the training utilities module**

```python
"""
Shared utilities for training XGBoost upgrade models.
Used by train_comstock_upgrades.py and train_resstock_upgrades.py.
"""
import os
import json
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    print("WARNING: optuna not installed. Using default hyperparameters.")


def load_upgrades_lookup(path):
    """Load upgrade ID -> name mapping."""
    with open(path) as f:
        return json.load(f)


def encode_features(df, feature_cols, encoders=None):
    """
    Label-encode string/categorical columns for XGBoost.

    Args:
        df: DataFrame with feature columns
        feature_cols: list of column names to encode
        encoders: dict of pre-fitted LabelEncoders (for inference).
                  If None, fit new encoders.

    Returns:
        df_encoded: DataFrame with encoded features
        encoders: dict of {col_name: fitted LabelEncoder}
    """
    df_enc = df[feature_cols].copy()
    if encoders is None:
        encoders = {}
        fit = True
    else:
        fit = False

    for col in feature_cols:
        if df_enc[col].dtype == 'object' or str(df_enc[col].dtype) in ('large_string', 'string'):
            df_enc[col] = df_enc[col].astype(str)
            if fit:
                le = LabelEncoder()
                df_enc[col] = le.fit_transform(df_enc[col])
                encoders[col] = le
            else:
                le = encoders[col]
                # Handle unseen labels at inference
                known = set(le.classes_)
                df_enc[col] = df_enc[col].apply(lambda x: x if x in known else le.classes_[0])
                df_enc[col] = le.transform(df_enc[col])
        else:
            df_enc[col] = pd.to_numeric(df_enc[col], errors='coerce').fillna(0)

    return df_enc, encoders


def tune_hyperparameters(X_train, y_train, n_trials=50, cv_folds=5, random_state=42):
    """
    Use Optuna to find optimal XGBoost hyperparameters.

    Returns:
        best_params: dict of best hyperparameters
    """
    if not HAS_OPTUNA:
        return {
            'n_estimators': 300,
            'max_depth': 6,
            'learning_rate': 0.1,
            'min_child_weight': 5,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
        }

    def objective(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 100, 800),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-3, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
        }
        model = XGBRegressor(
            objective='reg:squarederror',
            random_state=random_state,
            n_jobs=-1,
            **params
        )
        scores = cross_val_score(
            model, X_train, y_train,
            cv=cv_folds,
            scoring='neg_mean_absolute_error',
            n_jobs=-1
        )
        return -scores.mean()  # Optuna minimizes

    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    return study.best_params


def train_single_model(X_train, y_train, params, random_state=42):
    """Train a single XGBoost model with given parameters."""
    model = XGBRegressor(
        objective='reg:squarederror',
        random_state=random_state,
        n_jobs=-1,
        **params
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test, convert_kbtu=True):
    """
    Evaluate model on test set.

    Returns dict with MAE, RMSE, R², and MAE in kBtu/sf if convert_kbtu=True.
    """
    y_pred = model.predict(X_test)
    metrics = {
        'mae_kwh_ft2': mean_absolute_error(y_test, y_pred),
        'rmse_kwh_ft2': np.sqrt(mean_squared_error(y_test, y_pred)),
        'r2': r2_score(y_test, y_pred),
        'n_samples': len(y_test),
    }
    if convert_kbtu:
        metrics['mae_kbtu_sf'] = metrics['mae_kwh_ft2'] * 3.412
    return metrics


def save_model_artifacts(model, encoders, feature_cols, metrics, output_dir, model_name):
    """
    Save model, encoders, and metadata to disk.

    Saves:
      - {model_name}.pkl (the XGBoost model)
      - {model_name}_encoders.pkl (label encoders for inference)
      - {model_name}_meta.json (feature list, metrics, training info)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Save model
    model_path = os.path.join(output_dir, f'{model_name}.pkl')
    joblib.dump(model, model_path)

    # Save encoders
    enc_path = os.path.join(output_dir, f'{model_name}_encoders.pkl')
    joblib.dump(encoders, enc_path)

    # Save metadata
    meta = {
        'feature_columns': feature_cols,
        'metrics': metrics,
        'model_file': f'{model_name}.pkl',
        'encoder_file': f'{model_name}_encoders.pkl',
    }
    meta_path = os.path.join(output_dir, f'{model_name}_meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    return model_path
```

**Step 2: Verify module imports**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 -c "from scripts.training_utils import encode_features, tune_hyperparameters; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add scripts/training_utils.py
git commit -m "feat: add shared training utilities for upgrade model pipeline"
```

---

### Task 3: Create ComStock Training Script

**Files:**
- Create: `scripts/train_comstock_upgrades.py`

This is the main script that trains all 66 ComStock models (baseline + 65 upgrades).

**Key design decisions:**
- Load raw parquet directly (no pre-cleaned file dependency)
- Deduplicate by bldg_id inline
- Filter to `applicability == True` and `completed_status == 'Success'` for upgrades
- Tune hyperparameters on 3 representative upgrades (baseline, LED=43, HP-RTU=1), reuse for similar measure groups
- Save models to `XGB_Models/ComStock_Upgrades_2025_R3/`
- Log all results to a summary Excel file

**Step 1: Write the ComStock training script**

```python
#!/usr/bin/env python3
"""
Train XGBoost models for ComStock 2025 R3 upgrade measures.
Produces 66 models: 1 baseline (upgrade 0) + 65 upgrade measures.

Usage:
    python3 scripts/train_comstock_upgrades.py                    # Train all
    python3 scripts/train_comstock_upgrades.py --upgrades 0 1 43  # Train specific upgrades
    python3 scripts/train_comstock_upgrades.py --tune-only        # Only run hyperparameter tuning
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from datetime import timedelta

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import (
    load_upgrades_lookup, encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
UPGRADES_JSON = os.path.join(RAW_DIR, 'upgrades_lookup.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3')

EUI_COL = 'out.site_energy.total.energy_consumption_intensity..kwh_per_ft2'

FEATURE_COLS = [
    'in.comstock_building_type_group',
    'in.sqft..ft2',
    'in.number_stories',
    'in.as_simulated_ashrae_iecc_climate_zone_2006',
    'cluster_name',
    'in.vintage',
    'in.heating_fuel',
    'in.service_water_heating_fuel',
    'in.hvac_category',
    'in.hvac_cool_type',
    'in.hvac_heat_type',
    'in.hvac_system_type',
    'in.hvac_vent_type',
    'in.wall_construction_type',
    'in.window_type',
    'in.window_to_wall_ratio_category',
    'in.airtightness..m3_per_m2_h',
    'in.interior_lighting_generation',
    'in.weekday_operating_hours..hr',
    'in.building_subtype',
    'in.aspect_ratio',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
]

# Columns to load from parquet (features + target + metadata)
LOAD_COLS = ['bldg_id', 'completed_status', 'applicability',
             'in.as_simulated_nhgis_county_gisjoin'] + FEATURE_COLS + [EUI_COL]
# Remove cluster_name from LOAD_COLS since it's derived
LOAD_COLS = [c for c in LOAD_COLS if c != 'cluster_name']

# Hyperparameter tuning groups: tune on representative, apply to similar measures
TUNE_GROUPS = {
    'baseline': [0],
    'hvac': list(range(1, 32)),
    'demand_flex': list(range(32, 43)),
    'lighting': [43, 44],
    'other': [45, 46, 47],
    'envelope': list(range(48, 54)),
    'packages': list(range(54, 66)),
}
# Representative upgrade to tune for each group
TUNE_REPRESENTATIVES = {
    'baseline': 0,
    'hvac': 1,       # HP-RTU (most common HVAC measure)
    'demand_flex': 32,
    'lighting': 43,  # LED
    'envelope': 49,  # Roof Insulation (100% applicability)
    'packages': 55,  # Package 2
    'other': 46,
}

# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    # Deduplicate to one cluster per county
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_upgrade_data(upgrade_id, cluster_lookup):
    """
    Load and clean data for a single upgrade.

    Returns:
        df: cleaned DataFrame with features + target, or None if file doesn't exist
        n_raw: number of raw rows
        n_clean: number of clean rows
    """
    if upgrade_id == 0:
        fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    else:
        fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}_agg.parquet')

    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)

    # Deduplicate by bldg_id (ComStock has duplicate rows with different weights)
    df = df.drop_duplicates(subset='bldg_id')

    # Filter to successful simulations only
    if upgrade_id > 0:
        df = df[df['completed_status'] == 'Success']
        df = df[df['applicability'] == True]

    # Merge cluster_name from spatial lookup
    df = df.merge(
        cluster_lookup,
        left_on='in.as_simulated_nhgis_county_gisjoin',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    # Fill missing clusters (shouldn't happen, but safety)
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows with null EUI
    df = df.dropna(subset=[EUI_COL])

    n_clean = len(df)

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'completed_status', 'applicability',
                           'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df, n_raw, n_clean


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def get_group_for_upgrade(uid):
    """Find which tuning group an upgrade belongs to."""
    for group, uids in TUNE_GROUPS.items():
        if uid in uids:
            return group
    return 'other'


def train_all(upgrade_ids, tune_trials=50):
    """Train models for specified upgrade IDs."""
    total_start = time.time()

    upgrades_lookup = load_upgrades_lookup(UPGRADES_JSON)
    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: Tune hyperparameters on representative upgrades
    print("=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING")
    print("=" * 70)

    tuned_params = {}
    groups_needed = set(get_group_for_upgrade(uid) for uid in upgrade_ids)

    for group in groups_needed:
        rep_uid = TUNE_REPRESENTATIVES[group]
        print(f"\nTuning group '{group}' using upgrade {rep_uid} "
              f"({upgrades_lookup.get(str(rep_uid), '?')})...")

        df, n_raw, n_clean = load_upgrade_data(rep_uid, cluster_lookup)
        if df is None or n_clean < 100:
            print(f"  Insufficient data ({n_clean} rows). Using defaults.")
            tuned_params[group] = None
            continue

        X_enc, _ = encode_features(df, FEATURE_COLS)
        y = df[EUI_COL].values

        # Use a subset for tuning if dataset is very large
        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y[idx]
        else:
            X_tune, y_tune = X_enc, y

        params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        tuned_params[group] = params
        print(f"  Best params: {params}")

    # Save tuned params
    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters.json')
    with open(params_path, 'w') as f:
        json.dump({k: v for k, v in tuned_params.items() if v is not None}, f, indent=2)
    print(f"\nSaved tuned params to {params_path}")

    # Phase 2: Train all models
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING")
    print("=" * 70)

    all_results = []

    for uid in upgrade_ids:
        measure_name = upgrades_lookup.get(str(uid), f'upgrade_{uid}')
        group = get_group_for_upgrade(uid)
        params = tuned_params.get(group)

        if params is None:
            # Fallback defaults
            params = {
                'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
                'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
            }

        print(f"\n--- Upgrade {uid}: {measure_name} (group: {group}) ---")

        df, n_raw, n_clean = load_upgrade_data(uid, cluster_lookup)
        if df is None or n_clean < 50:
            print(f"  SKIPPED: insufficient data ({n_clean} rows)")
            all_results.append({
                'upgrade_id': uid, 'measure_name': measure_name,
                'status': 'skipped', 'reason': f'insufficient data ({n_clean} rows)',
            })
            continue

        # Encode features
        X_enc, encoders = encode_features(df, FEATURE_COLS)
        y = df[EUI_COL].values

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_enc, y, test_size=0.2, random_state=42
        )

        # Train model
        t0 = time.time()
        model = train_single_model(X_train, y_train, params)
        train_time = time.time() - t0

        # Evaluate
        train_metrics = evaluate_model(model, X_train, y_train)
        test_metrics = evaluate_model(model, X_test, y_test)

        print(f"  Train: MAE={train_metrics['mae_kbtu_sf']:.2f} kBtu/sf, R²={train_metrics['r2']:.4f}")
        print(f"  Test:  MAE={test_metrics['mae_kbtu_sf']:.2f} kBtu/sf, R²={test_metrics['r2']:.4f}")
        print(f"  Samples: {n_clean} applicable | Time: {train_time:.1f}s")

        # Save model
        model_name = f'XGB_upgrade{uid}'
        save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                             OUTPUT_DIR, model_name)

        # Record results
        all_results.append({
            'upgrade_id': uid,
            'measure_name': measure_name,
            'group': group,
            'status': 'success',
            'n_raw': n_raw,
            'n_applicable': n_clean,
            'train_mae_kbtu_sf': train_metrics['mae_kbtu_sf'],
            'train_r2': train_metrics['r2'],
            'test_mae_kbtu_sf': test_metrics['mae_kbtu_sf'],
            'test_r2': test_metrics['r2'],
            'test_rmse_kwh_ft2': test_metrics['rmse_kwh_ft2'],
            'train_time_s': train_time,
        })

    # Save summary results
    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_summary.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {len([r for r in all_results if r.get('status') == 'success'])} "
          f"models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train ComStock upgrade models')
    parser.add_argument('--upgrades', nargs='+', type=int, default=None,
                        help='Specific upgrade IDs to train (default: all 0-65)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials per tuning group (default: 50)')
    parser.add_argument('--tune-only', action='store_true',
                        help='Only run hyperparameter tuning, skip model training')
    args = parser.parse_args()

    if args.upgrades is None:
        upgrade_ids = list(range(0, 66))
    else:
        upgrade_ids = args.upgrades

    print(f"Training {len(upgrade_ids)} ComStock upgrade models")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Tune trials per group: {args.tune_trials}")

    train_all(upgrade_ids, tune_trials=args.tune_trials)


if __name__ == '__main__':
    main()
```

**Step 2: Test with a single upgrade (baseline)**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 scripts/train_comstock_upgrades.py --upgrades 0 --tune-trials 5
```

Expected: Model trains successfully, files appear in `XGB_Models/ComStock_Upgrades_2025_R3/`.

**Step 3: Verify output files**

```bash
ls XGB_Models/ComStock_Upgrades_2025_R3/
```

Expected: `XGB_upgrade0.pkl`, `XGB_upgrade0_encoders.pkl`, `XGB_upgrade0_meta.json`, `training_results_summary.xlsx`, `tuned_hyperparameters.json`

**Step 4: Commit**

```bash
git add scripts/train_comstock_upgrades.py
git commit -m "feat: add ComStock upgrade model training script with Optuna tuning"
```

---

### Task 4: Create ResStock Training Script

**Files:**
- Create: `scripts/train_resstock_upgrades.py`

Same structure as ComStock but with ResStock-specific features, MF filter, and vacancy exclusion.

**Step 1: Write the ResStock training script**

```python
#!/usr/bin/env python3
"""
Train XGBoost models for ResStock 2025 R1 upgrade measures (Multi-Family 4+ units).
Produces up to 33 models: 1 baseline (upgrade 0) + 32 upgrade measures.
Skips upgrades with 0% MF applicability (e.g., upgrade 12 attic insulation).

Usage:
    python3 scripts/train_resstock_upgrades.py                    # Train all
    python3 scripts/train_resstock_upgrades.py --upgrades 0 4 17  # Train specific upgrades
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from datetime import timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import (
    load_upgrades_lookup, encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ResStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
UPGRADES_JSON = os.path.join(RAW_DIR, 'upgrades_lookup.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Upgrades_2025_R1')

EUI_COL = 'out.site_energy.total.energy_consumption_intensity..kwh_per_ft2'

FEATURE_COLS = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
    'in.sqft..ft2',
    'in.geometry_stories',
    'in.ashrae_iecc_climate_zone_2004',
    'cluster_name',
    'in.vintage',
    'in.heating_fuel',
    'in.hvac_heating_type',
    'in.hvac_heating_efficiency',
    'in.hvac_cooling_type',
    'in.hvac_cooling_efficiency',
    'in.hvac_has_shared_system',
    'in.water_heater_fuel',
    'in.water_heater_efficiency',
    'in.geometry_wall_type',
    'in.insulation_wall',
    'in.insulation_floor',
    'in.window_areas',
    'in.windows',
    'in.lighting',
    'in.infiltration',
    'in.geometry_foundation_type',
]

# Columns to load from parquet
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + FEATURE_COLS + [EUI_COL]
LOAD_COLS = [c for c in LOAD_COLS if c != 'cluster_name']

# Hyperparameter tuning groups
TUNE_GROUPS = {
    'baseline': [0],
    'hvac': [1, 2, 3, 4, 5, 6, 7, 8],
    'water_heating': [9, 10],
    'envelope': [11, 12, 13, 14, 15, 16, 17, 29, 30],
    'packages': [18, 31, 32],
    'ev': [19, 20, 21, 22, 23],
    'demand_flex': [24, 25, 26, 27, 28],
}
TUNE_REPRESENTATIVES = {
    'baseline': 0,
    'hvac': 4,       # Cold Climate ASHP
    'water_heating': 9,  # HPWH
    'envelope': 17,  # Windows (100% applicability)
    'packages': 18,
    'ev': 20,
    'demand_flex': 24,
}

# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def filter_mf_occupied(df):
    """Filter to multi-family 4+ units, occupied only."""
    # Parse number of units
    units = df['in.geometry_building_number_units_mf'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    mf_mask = units >= 4
    occ_mask = df['in.vacancy_status'] == 'Occupied'
    return df[mf_mask & occ_mask].copy()


def load_upgrade_data(upgrade_id, cluster_lookup):
    """Load and clean ResStock data for a single upgrade."""
    fname = os.path.join(RAW_DIR, f'upgrade{upgrade_id}.parquet')

    if not os.path.exists(fname):
        print(f"  File not found: {fname}")
        return None, 0, 0

    df = pd.read_parquet(fname, columns=LOAD_COLS)
    n_raw = len(df)

    # Filter to MF 4+ occupied
    df = filter_mf_occupied(df)

    # Filter to applicable (for upgrades)
    if upgrade_id > 0:
        df = df[df['applicability'] == True]

    # Merge cluster_name
    df = df.merge(
        cluster_lookup,
        left_on='in.county',
        right_on='nhgis_county_gisjoin',
        how='left'
    )
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows with null EUI
    df = df.dropna(subset=[EUI_COL])

    n_clean = len(df)

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'applicability',
                           'in.geometry_building_number_units_mf', 'in.vacancy_status',
                           'in.county', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df, n_raw, n_clean


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def get_group_for_upgrade(uid):
    for group, uids in TUNE_GROUPS.items():
        if uid in uids:
            return group
    return 'envelope'  # fallback


def train_all(upgrade_ids, tune_trials=50):
    """Train models for specified upgrade IDs."""
    total_start = time.time()

    upgrades_lookup = load_upgrades_lookup(UPGRADES_JSON)
    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: Tune hyperparameters
    print("=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ResStock MF)")
    print("=" * 70)

    tuned_params = {}
    groups_needed = set(get_group_for_upgrade(uid) for uid in upgrade_ids)

    for group in groups_needed:
        rep_uid = TUNE_REPRESENTATIVES[group]
        print(f"\nTuning group '{group}' using upgrade {rep_uid} "
              f"({upgrades_lookup.get(str(rep_uid), '?')})...")

        df, n_raw, n_clean = load_upgrade_data(rep_uid, cluster_lookup)
        if df is None or n_clean < 100:
            print(f"  Insufficient data ({n_clean} rows). Using defaults.")
            tuned_params[group] = None
            continue

        X_enc, _ = encode_features(df, FEATURE_COLS)
        y = df[EUI_COL].values

        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y[idx]
        else:
            X_tune, y_tune = X_enc, y

        params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        tuned_params[group] = params
        print(f"  Best params: {params}")

    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters.json')
    with open(params_path, 'w') as f:
        json.dump({k: v for k, v in tuned_params.items() if v is not None}, f, indent=2)

    # Phase 2: Train all models
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ResStock MF)")
    print("=" * 70)

    all_results = []
    from sklearn.model_selection import train_test_split

    for uid in upgrade_ids:
        measure_name = upgrades_lookup.get(str(uid), f'upgrade_{uid}')
        group = get_group_for_upgrade(uid)
        params = tuned_params.get(group)

        if params is None:
            params = {
                'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
                'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
            }

        print(f"\n--- Upgrade {uid}: {measure_name} (group: {group}) ---")

        df, n_raw, n_clean = load_upgrade_data(uid, cluster_lookup)
        if df is None or n_clean < 50:
            print(f"  SKIPPED: insufficient data ({n_clean} rows)")
            all_results.append({
                'upgrade_id': uid, 'measure_name': measure_name,
                'status': 'skipped', 'reason': f'insufficient data ({n_clean} rows)',
            })
            continue

        X_enc, encoders = encode_features(df, FEATURE_COLS)
        y = df[EUI_COL].values

        X_train, X_test, y_train, y_test = train_test_split(
            X_enc, y, test_size=0.2, random_state=42
        )

        t0 = time.time()
        model = train_single_model(X_train, y_train, params)
        train_time = time.time() - t0

        train_metrics = evaluate_model(model, X_train, y_train)
        test_metrics = evaluate_model(model, X_test, y_test)

        print(f"  Train: MAE={train_metrics['mae_kbtu_sf']:.2f} kBtu/sf, R²={train_metrics['r2']:.4f}")
        print(f"  Test:  MAE={test_metrics['mae_kbtu_sf']:.2f} kBtu/sf, R²={test_metrics['r2']:.4f}")
        print(f"  Samples: {n_clean} applicable | Time: {train_time:.1f}s")

        model_name = f'XGB_upgrade{uid}'
        save_model_artifacts(model, encoders, FEATURE_COLS, test_metrics,
                             OUTPUT_DIR, model_name)

        all_results.append({
            'upgrade_id': uid,
            'measure_name': measure_name,
            'group': group,
            'status': 'success',
            'n_raw': n_raw,
            'n_applicable': n_clean,
            'train_mae_kbtu_sf': train_metrics['mae_kbtu_sf'],
            'train_r2': train_metrics['r2'],
            'test_mae_kbtu_sf': test_metrics['mae_kbtu_sf'],
            'test_r2': test_metrics['r2'],
            'test_rmse_kwh_ft2': test_metrics['rmse_kwh_ft2'],
            'train_time_s': train_time,
        })

    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_summary.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {len([r for r in all_results if r.get('status') == 'success'])} "
          f"models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description='Train ResStock MF upgrade models')
    parser.add_argument('--upgrades', nargs='+', type=int, default=None,
                        help='Specific upgrade IDs to train (default: all 0-32)')
    parser.add_argument('--tune-trials', type=int, default=50,
                        help='Number of Optuna trials per tuning group (default: 50)')
    args = parser.parse_args()

    if args.upgrades is None:
        upgrade_ids = list(range(0, 33))
    else:
        upgrade_ids = args.upgrades

    print(f"Training {len(upgrade_ids)} ResStock MF upgrade models")
    print(f"Output directory: {OUTPUT_DIR}")

    train_all(upgrade_ids, tune_trials=args.tune_trials)


if __name__ == '__main__':
    main()
```

**Step 2: Test with baseline**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 scripts/train_resstock_upgrades.py --upgrades 0 --tune-trials 5
```

Expected: Model trains, files in `XGB_Models/ResStock_Upgrades_2025_R1/`.

**Step 3: Commit**

```bash
git add scripts/train_resstock_upgrades.py
git commit -m "feat: add ResStock MF upgrade model training script"
```

---

### Task 5: Create CBECS Validation Script

**Files:**
- Create: `scripts/validate_cbecs.py`

Loads trained ComStock baseline model, runs predictions on CBECS mapped data, compares to actual EUI.

**Step 1: Write the validation script**

```python
#!/usr/bin/env python3
"""
Validate ComStock baseline model predictions against CBECS 2018 real-world data.

Loads the trained baseline model (upgrade 0) and compares predictions to actual
EUI values from the CBECS 2018 survey. CBECS is an approximation of real-world
data — the mappings are approximate and results may diverge for reasons beyond
model accuracy.

Usage:
    python3 scripts/validate_cbecs.py
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

CBECS_PATH = os.path.join(PROJECT_ROOT, 'Validation', 'CBECS', 'cbecs2018_mapped_for_xgb.csv')
MODEL_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3')
BASELINE_MODEL = os.path.join(MODEL_DIR, 'XGB_upgrade0.pkl')
BASELINE_ENCODERS = os.path.join(MODEL_DIR, 'XGB_upgrade0_encoders.pkl')
BASELINE_META = os.path.join(MODEL_DIR, 'XGB_upgrade0_meta.json')

# CBECS column -> ComStock feature mapping
# CBECS was mapped to the OLD model features (9 categorical, binned).
# Our new model uses 25 features with raw values.
# We need to map CBECS columns to the new feature names.
CBECS_TO_COMSTOCK = {
    'in.building_type': 'in.comstock_building_type_group',
    'SQFT': 'in.sqft..ft2',
    'NFLOOR': 'in.number_stories',
    'climate_zone_ashrae_2006': 'in.as_simulated_ashrae_iecc_climate_zone_2006',
    'cluster_name': 'cluster_name',
    'year_built': 'in.vintage',
    'in.heating_fuel': 'in.heating_fuel',
    'in.water_heater_fuel': 'in.service_water_heating_fuel',
    'in.hvac_category': 'in.hvac_category',
}

# Building type mapping: CBECS uses detailed types, ComStock uses groups
BT_TO_GROUP = {
    'SmallOffice': 'Office', 'MediumOffice': 'Office', 'LargeOffice': 'Office',
    'SmallHotel': 'Lodging', 'LargeHotel': 'Lodging',
    'QuickServiceRestaurant': 'Food Service', 'FullServiceRestaurant': 'Food Service',
    'Outpatient': 'Healthcare', 'Hospital': 'Healthcare',
    'PrimarySchool': 'Education', 'SecondarySchool': 'Education',
    'RetailStandalone': 'Mercantile', 'RetailStripmall': 'Mercantile',
    'Warehouse': 'Warehouse and Storage',
}

# Vintage mapping: CBECS bins -> ComStock vintage values
YEARBUILT_TO_VINTAGE = {
    '<1946': 'Before 1980',
    '1946-1959': 'Before 1980',
    '1960-1979': 'Before 1980',
    '1980-1999': '1980 to 1989',  # approximation
    '2000-2009': '2000 to 2012',
    '>2010': '2013+',
}


def main():
    print("=" * 70)
    print("CBECS 2018 VALIDATION")
    print("NOTE: CBECS is an approximation of real-world data.")
    print("Mappings are approximate. Results may diverge from model predictions")
    print("for reasons beyond model accuracy.")
    print("=" * 70)

    # Check model exists
    if not os.path.exists(BASELINE_MODEL):
        print(f"\nERROR: Baseline model not found at {BASELINE_MODEL}")
        print("Run train_comstock_upgrades.py --upgrades 0 first.")
        sys.exit(1)

    # Load CBECS data
    cbecs = pd.read_csv(CBECS_PATH)
    print(f"\nLoaded CBECS: {len(cbecs)} buildings")

    # Filter to buildings with valid building type and EUI
    cbecs = cbecs[cbecs['in.building_type'].notna()].copy()
    cbecs = cbecs[cbecs['total_site_eui'].notna() & (cbecs['total_site_eui'] > 0)].copy()
    print(f"After filtering: {len(cbecs)} buildings with valid type + EUI")

    # Load model and metadata
    model = joblib.load(BASELINE_MODEL)
    encoders = joblib.load(BASELINE_ENCODERS)
    with open(BASELINE_META) as f:
        meta = json.load(f)
    feature_cols = meta['feature_columns']

    # Map CBECS columns to model features
    # Start with the features the model expects, fill what we can from CBECS
    pred_df = pd.DataFrame(index=cbecs.index)

    # Map building type to group
    pred_df['in.comstock_building_type_group'] = cbecs['in.building_type'].map(BT_TO_GROUP)
    pred_df['in.sqft..ft2'] = cbecs['SQFT'].astype(float)
    pred_df['in.number_stories'] = cbecs['NFLOOR'].astype(str)
    pred_df['in.as_simulated_ashrae_iecc_climate_zone_2006'] = cbecs['climate_zone_ashrae_2006']
    pred_df['cluster_name'] = cbecs['cluster_name'].fillna('Unknown')
    pred_df['in.vintage'] = cbecs['year_built'].map(YEARBUILT_TO_VINTAGE).fillna('1980 to 1989')
    pred_df['in.heating_fuel'] = cbecs['in.heating_fuel'].fillna('NaturalGas')
    pred_df['in.service_water_heating_fuel'] = cbecs['in.water_heater_fuel'].fillna('NaturalGas')
    pred_df['in.hvac_category'] = cbecs['in.hvac_category'].fillna('Small Packaged Unit')

    # Fill remaining features with most common values (imputation)
    # These features aren't available in CBECS
    defaults = {
        'in.hvac_cool_type': 'DX',
        'in.hvac_heat_type': 'Furnace',
        'in.hvac_system_type': 'PSZ-AC with gas coil',
        'in.hvac_vent_type': 'Central Single-zone RTU',
        'in.wall_construction_type': 'SteelFramed',
        'in.window_type': 'Double - No LowE - Clear - Aluminum',
        'in.window_to_wall_ratio_category': '11_25pct',
        'in.airtightness..m3_per_m2_h': '20',
        'in.interior_lighting_generation': 'gen2_t8_halogen',
        'in.weekday_operating_hours..hr': '9',
        'in.building_subtype': 'NA',
        'in.aspect_ratio': '1',
        'in.energy_code_followed_during_last_hvac_replacement': 'ComStock DOE Ref 1980-2004',
        'in.energy_code_followed_during_last_roof_replacement': 'ComStock DOE Ref Pre-1980',
        'in.energy_code_followed_during_last_walls_replacement': 'ComStock DOE Ref Pre-1980',
        'in.energy_code_followed_during_last_svc_water_htg_replacement': 'ComStock DOE Ref Pre-1980',
    }
    for col, default in defaults.items():
        if col in feature_cols:
            pred_df[col] = default

    # Drop rows where building type mapping failed
    valid_mask = pred_df['in.comstock_building_type_group'].notna()
    pred_df = pred_df[valid_mask]
    cbecs_valid = cbecs[valid_mask]
    print(f"After building type mapping: {len(pred_df)} buildings")

    # Encode features using the trained encoders
    from scripts.training_utils import encode_features
    X_enc, _ = encode_features(pred_df, feature_cols, encoders=encoders)

    # Predict
    y_pred_kwh = model.predict(X_enc)
    y_pred_kbtu = y_pred_kwh * 3.412  # Convert to kBtu/sf
    y_actual_kbtu = cbecs_valid['total_site_eui'].values

    # Overall metrics
    mae = mean_absolute_error(y_actual_kbtu, y_pred_kbtu)
    rmse = np.sqrt(mean_squared_error(y_actual_kbtu, y_pred_kbtu))
    r2 = r2_score(y_actual_kbtu, y_pred_kbtu)
    mape = np.mean(np.abs((y_actual_kbtu - y_pred_kbtu) / np.maximum(y_actual_kbtu, 1))) * 100

    print(f"\n{'=' * 50}")
    print(f"OVERALL RESULTS (n={len(y_actual_kbtu)})")
    print(f"{'=' * 50}")
    print(f"  MAE:  {mae:.1f} kBtu/sf")
    print(f"  RMSE: {rmse:.1f} kBtu/sf")
    print(f"  R²:   {r2:.4f}")
    print(f"  MAPE: {mape:.1f}%")
    print(f"  Actual mean EUI:    {y_actual_kbtu.mean():.1f} kBtu/sf")
    print(f"  Predicted mean EUI: {y_pred_kbtu.mean():.1f} kBtu/sf")

    # Per building type
    print(f"\n{'=' * 50}")
    print(f"RESULTS BY BUILDING TYPE")
    print(f"{'=' * 50}")
    bt_col = pred_df['in.comstock_building_type_group'].values
    results_by_bt = []
    for bt in sorted(set(bt_col)):
        mask = bt_col == bt
        if mask.sum() < 5:
            continue
        bt_mae = mean_absolute_error(y_actual_kbtu[mask], y_pred_kbtu[mask])
        bt_r2 = r2_score(y_actual_kbtu[mask], y_pred_kbtu[mask]) if mask.sum() > 1 else float('nan')
        bt_actual_mean = y_actual_kbtu[mask].mean()
        bt_pred_mean = y_pred_kbtu[mask].mean()
        results_by_bt.append({
            'building_type': bt, 'n': mask.sum(),
            'actual_mean_eui': bt_actual_mean, 'predicted_mean_eui': bt_pred_mean,
            'mae_kbtu_sf': bt_mae, 'r2': bt_r2,
        })
        print(f"  {bt:<25} n={mask.sum():<5} actual={bt_actual_mean:6.1f}  pred={bt_pred_mean:6.1f}  "
              f"MAE={bt_mae:5.1f}  R²={bt_r2:.3f}")

    # Save results
    output_dir = os.path.join(PROJECT_ROOT, 'Validation', 'CBECS')
    results_df = pd.DataFrame(results_by_bt)
    results_df.to_excel(os.path.join(output_dir, 'cbecs_validation_results.xlsx'), index=False)

    # Save predictions for inspection
    comparison = cbecs_valid[['PUBID', 'in.building_type', 'SQFT', 'climate_zone_ashrae_2006',
                               'total_site_eui']].copy()
    comparison['predicted_total_eui_kbtu'] = y_pred_kbtu
    comparison['residual'] = y_actual_kbtu - y_pred_kbtu
    comparison.to_csv(os.path.join(output_dir, 'cbecs_predictions_vs_actual.csv'), index=False)

    print(f"\nResults saved to {output_dir}")


if __name__ == '__main__':
    main()
```

**Step 2: Run validation (after baseline model is trained)**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 scripts/validate_cbecs.py
```

**Step 3: Commit**

```bash
git add scripts/validate_cbecs.py
git commit -m "feat: add CBECS validation script for baseline model comparison"
```

---

### Task 6: Test Full Pipeline (Smoke Test)

Run ComStock baseline + one upgrade + CBECS validation end-to-end.

**Step 1: Train baseline + LED (upgrade 43) with minimal tuning**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 scripts/train_comstock_upgrades.py --upgrades 0 43 --tune-trials 10
```

**Step 2: Run CBECS validation**

```bash
python3 scripts/validate_cbecs.py
```

**Step 3: Verify model output directory structure**

```bash
ls -la XGB_Models/ComStock_Upgrades_2025_R3/
```

Expected structure:
```
XGB_Models/ComStock_Upgrades_2025_R3/
├── XGB_upgrade0.pkl
├── XGB_upgrade0_encoders.pkl
├── XGB_upgrade0_meta.json
├── XGB_upgrade43.pkl
├── XGB_upgrade43_encoders.pkl
├── XGB_upgrade43_meta.json
├── tuned_hyperparameters.json
└── training_results_summary.xlsx
```

**Step 4: Review results and adjust if needed**

Check `training_results_summary.xlsx` for MAE and R² values. If metrics look reasonable, proceed to full training.

---

### Task 7: Train All ComStock Models (Full Run)

**Step 1: Run full ComStock training**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 scripts/train_comstock_upgrades.py --tune-trials 50
```

This trains all 66 models. Expected runtime: 1-3 hours depending on hardware.

**Step 2: Review training_results_summary.xlsx**

Check for any models with very poor R² or unexpected MAE values.

**Step 3: Commit models and results**

```bash
git add XGB_Models/ComStock_Upgrades_2025_R3/training_results_summary.xlsx
git add XGB_Models/ComStock_Upgrades_2025_R3/tuned_hyperparameters.json
git commit -m "feat: train all 66 ComStock upgrade models with Optuna-tuned hyperparameters"
```

Note: .pkl model files are large and may not belong in git. Consider .gitignore for them.

---

### Task 8: Train All ResStock Models (Full Run)

**Step 1: Run full ResStock training**

```bash
cd "/Users/brandonwinsatt/Documents/BuildingStock Energy Estimation"
python3 scripts/train_resstock_upgrades.py --tune-trials 50
```

Expected: ~32 models (upgrade 12 should be skipped due to 0% MF applicability).

**Step 2: Review results**

Check `XGB_Models/ResStock_Upgrades_2025_R1/training_results_summary.xlsx`.

**Step 3: Commit**

```bash
git add XGB_Models/ResStock_Upgrades_2025_R1/training_results_summary.xlsx
git add XGB_Models/ResStock_Upgrades_2025_R1/tuned_hyperparameters.json
git commit -m "feat: train all ResStock MF upgrade models"
```

---

### Task 9: Run CBECS Validation and Review

**Step 1: Run validation with fully trained baseline**

```bash
python3 scripts/validate_cbecs.py
```

**Step 2: Review output files**

- `Validation/CBECS/cbecs_validation_results.xlsx` — per-building-type metrics
- `Validation/CBECS/cbecs_predictions_vs_actual.csv` — building-level comparison

**Step 3: Commit**

```bash
git add Validation/CBECS/cbecs_validation_results.xlsx
git add Validation/CBECS/cbecs_predictions_vs_actual.csv
git commit -m "feat: CBECS baseline validation results"
```

---

## Output Directory Structure

After full training, the model directories will look like:

```
XGB_Models/
├── ComStock_Upgrades_2025_R3/          # NEW - 66 upgrade models
│   ├── XGB_upgrade0.pkl                # Baseline model
│   ├── XGB_upgrade0_encoders.pkl       # Label encoders for inference
│   ├── XGB_upgrade0_meta.json          # Feature list + test metrics
│   ├── XGB_upgrade1.pkl                # HP-RTU model
│   ├── XGB_upgrade1_encoders.pkl
│   ├── XGB_upgrade1_meta.json
│   ├── ... (through upgrade65)
│   ├── tuned_hyperparameters.json      # Optuna results by group
│   └── training_results_summary.xlsx   # All models' metrics
├── ResStock_Upgrades_2025_R1/          # NEW - 33 MF upgrade models
│   ├── XGB_upgrade0.pkl                # MF baseline model
│   ├── ... (through upgrade32)
│   ├── tuned_hyperparameters.json
│   └── training_results_summary.xlsx
├── All_Building_Types_models_v3.1/     # EXISTING - prior baseline models
└── BuildingTypes_models_v3/            # EXISTING - prior per-type models
```
