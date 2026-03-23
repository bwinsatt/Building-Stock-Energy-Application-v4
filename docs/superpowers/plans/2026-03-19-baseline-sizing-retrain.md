# Baseline & Sizing Model Retraining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retrain baseline (upgrade 0) and sizing models with the new feature set (HDD/CDD, thermostat setpoints, floor_plate_sqft) and ensemble approach (XGBoost + LightGBM + CatBoost), bringing them in line with the recently retrained delta/upgrade models.

**Architecture:** Four training scripts are updated to add the same new features used in delta model training, plus ensemble blending for baseline models. Baseline models predict absolute EUI (not deltas), so they have no paired-data step — they train directly on upgrade0 data with fuel EUI as the target. Sizing models predict equipment capacity/area and remain XGBoost-only (ensemble overhead not justified for 5 geometric targets). The model manager already handles multi-prefix ensemble loading and CatBoost encoding, so no inference code changes are needed — only the training scripts and their output models change.

**Prerequisite:** The feature pipeline fixes (`docs/superpowers/plans/2026-03-19-feature-pipeline-fixes.md`) must be completed first. Those fixes updated `CAT_FEATURE_NAMES` in both delta training scripts — the baseline/sizing scripts here must match exactly. Key changes from that plan: `in.number_stories`, `in.weekday_operating_hours..hr`, `in.aspect_ratio`, and 5 ComStock thermostat/weekend columns added to ComStock CAT_FEATURE_NAMES; `in.geometry_stories` and 4 ResStock thermostat columns added to ResStock CAT_FEATURE_NAMES.

**Tech Stack:** Python, XGBoost, LightGBM, CatBoost, Pandas, scikit-learn

---

## Current State Summary

| Model Category | Feature Set | Ensemble | Location |
|---|---|---|---|
| Baseline (upgrade 0) | OLD (25 ComStock / 23 ResStock features) | XGB-only | `ComStock_Upgrades_2025_R3/XGB_upgrade0_*` |
| Sizing | OLD (25 ComStock / 23 ResStock features) | XGB-only | `ComStock_Sizing/`, `ResStock_Sizing/` |
| Delta/Upgrades | **NEW** (38 ComStock / 35 ResStock features incl baseline_eui) | XGB+LGBM+CB | `ComStock_Upgrades_2025_R3/`, `ResStock_Upgrades_2025_R1/` |

After this plan, baseline models will use the new feature set + ensemble (38 ComStock / 35 ResStock features), and sizing models will use the new feature set minus baseline_eui (33 ComStock / 30 ResStock features, XGB-only).

## Key Design Decisions

1. **Baseline models get ensemble (XGB+LGBM+CB)** — they are high-impact (every assessment starts with baseline prediction) and benefit from the same accuracy gains seen in delta models.

2. **Sizing models stay XGB-only** — they predict geometric quantities (wall/roof/window area, heating/cooling capacity) where R² is already 0.97+ for ComStock. Ensemble overhead not justified. They DO get the new features though (HDD/CDD helps heating/cooling capacity prediction).

3. **Baseline models do NOT use baseline_eui features** — unlike delta models which can condition on "what's the current consumption?", baseline IS the current consumption prediction. Those 5 columns are set to NaN during baseline training (as the delta training script already does in `load_baseline_data()`).

4. **No changes to model_manager.py** — baseline ensemble loading already works (the index detects `XGB_upgrade0_*`, `LGBM_upgrade0_*`, `CB_upgrade0_*` via `_RE_UPGRADE` regex). Sizing models remain XGB-only with `_RE_SIZING` pattern.

5. **No changes to preprocessor.py** — it already produces all new features (hdd65f, cdd65f, floor_plate_sqft, thermostat columns). The old models simply ignored the extra features because they weren't in the model's `feature_columns` metadata. Retrained models will pick them up.

6. **Constant-target handling** — CatBoost crashes on constant targets (e.g., district_heating = 0 for most buildings). The delta training script already skips these (`np.std(y_train) < 1e-10`). Baseline training must apply the same check per fuel type.

7. **CAT_FEATURE_NAMES must exactly match delta scripts** — The feature pipeline fixes (commits `6115262` through `8ffb63d`) updated `CAT_FEATURE_NAMES` in both delta scripts. The baseline and sizing scripts here use identical lists to ensure encoders are consistent across all model categories.

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/train_comstock_baseline.py` | Create | ComStock baseline (upgrade 0) training with new features + ensemble |
| `scripts/train_resstock_baseline.py` | Create | ResStock baseline (upgrade 0) training with new features + ensemble |
| `scripts/train_comstock_sizing.py` | Modify | Add new features (HDD/CDD, thermostat, floor_plate_sqft) |
| `scripts/train_resstock_sizing.py` | Modify | Add new features (HDD/CDD, thermostat, floor_plate_sqft) |

**Why new scripts for baseline instead of modifying delta scripts?** The delta scripts skip upgrade 0 (`if uid == 0: continue`) because baseline has no "paired data" step. Baseline training loads upgrade0 data directly and trains on absolute EUI values — a fundamentally different data flow. Keeping them separate avoids spaghetti conditionals in the delta scripts.

---

## Task 1: Create ComStock Baseline Training Script

**Files:**
- Create: `scripts/train_comstock_baseline.py`

This script trains baseline (upgrade 0) models that predict absolute per-fuel EUI. It uses the same FEATURE_COLS as the delta training script (34 features including HDD/CDD, thermostat, floor_plate_sqft) and trains XGB + LGBM + CatBoost per fuel type.

Key differences from delta training:
- **Target**: absolute fuel EUI (e.g., `out.electricity.total.energy_consumption_intensity..kwh_per_ft2`), NOT delta
- **No paired data**: trains directly on upgrade0 data
- **baseline_eui features = NaN**: since we're predicting baseline, these are unknown
- **No applicability filter**: all buildings are valid for baseline

- [ ] **Step 1: Write the training script**

```python
#!/usr/bin/env python3
"""
Train ensemble baseline (upgrade 0) models for ComStock 2025 R3.
Produces XGB + LGBM + CatBoost models per fuel type that predict
absolute per-fuel EUI (kWh/ft2).

Usage:
    python3 scripts/train_comstock_baseline.py                    # Train all (with tuning)
    python3 scripts/train_comstock_baseline.py --skip-tuning      # Use saved hyperparameters
    python3 scripts/train_comstock_baseline.py --fuels electricity natural_gas  # Specific fuels
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
    encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
    prepare_catboost_data, train_lightgbm_model, train_catboost_model,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ComStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3')

FUEL_TYPES = {
    'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
    'fuel_oil': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
    'propane': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
    'district_heating': 'out.district_heating.total.energy_consumption_intensity..kwh_per_ft2',
}

# Same 34 features as delta training script
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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
    'floor_plate_sqft',
    # --- Baseline EUI features (always NaN for baseline training) ---
    'baseline_electricity',
    'baseline_natural_gas',
    'baseline_fuel_oil',
    'baseline_propane',
    'baseline_district_heating',
]

# Must match train_comstock_deltas.py exactly (updated by feature pipeline fixes)
CAT_FEATURE_NAMES = [
    'in.comstock_building_type_group',
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
    'in.interior_lighting_generation',
    'in.weekday_operating_hours..hr',
    'in.building_subtype',
    'in.aspect_ratio',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
]

# Columns to load from parquet (cluster_name and derived cols are added after loading)
LOAD_COLS = ['bldg_id', 'completed_status',
             'in.as_simulated_nhgis_county_gisjoin'] + \
            [c for c in FEATURE_COLS if c not in (
                'cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft',
                'baseline_electricity', 'baseline_natural_gas',
                'baseline_fuel_oil', 'baseline_propane', 'baseline_district_heating',
            )] + \
            list(FUEL_TYPES.values()) + [
                'out.params.hdd65f', 'out.params.cdd65f',
            ]
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))  # deduplicate


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_cluster_lookup():
    """Load county GISJOIN -> cluster_name mapping."""
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def load_baseline_data(cluster_lookup):
    """Load and prepare baseline (upgrade 0) data for absolute EUI training."""
    fname = os.path.join(RAW_DIR, 'upgrade0_agg.parquet')
    df = pd.read_parquet(fname, columns=LOAD_COLS)
    df = df.drop_duplicates(subset='bldg_id')

    # Merge cluster_name
    df = df.merge(cluster_lookup,
                  left_on='in.as_simulated_nhgis_county_gisjoin',
                  right_on='nhgis_county_gisjoin', how='left')
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Drop rows where ALL fuel EUIs are null
    fuel_cols = list(FUEL_TYPES.values())
    df = df.dropna(subset=fuel_cols, how='all')
    for col in fuel_cols:
        df[col] = df[col].fillna(0)

    # Rename HDD/CDD to match inference names
    df = df.rename(columns={
        'out.params.hdd65f': 'hdd65f',
        'out.params.cdd65f': 'cdd65f',
    })

    # Clean thermostat sentinel values (999 = no data → NaN)
    tstat_cols = [
        'in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
        'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
        'in.weekend_operating_hours..hr',
    ]
    for col in tstat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df.loc[df[col] >= 999, col] = float('nan')

    # Derived features
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.number_stories'], errors='coerce').clip(lower=1)
    )

    # Baseline EUI features are NaN for upgrade 0 training
    # (teaches model to handle missing — at inference, these are also unknown)
    for fuel_name in FUEL_TYPES:
        df[f'baseline_{fuel_name}'] = float('nan')

    # Drop metadata columns
    df = df.drop(columns=['bldg_id', 'completed_status',
                           'in.as_simulated_nhgis_county_gisjoin', 'nhgis_county_gisjoin'],
                  errors='ignore')

    return df


# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def train_all(fuel_keys, tune_trials=50, skip_tuning=False):
    """Train baseline ensemble models for specified fuel types."""
    total_start = time.time()
    from sklearn.model_selection import train_test_split

    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading baseline data (upgrade 0)...")
    df = load_baseline_data(cluster_lookup)
    print(f"  Baseline buildings: {len(df):,}")

    # Phase 1: Hyperparameter tuning (tune on electricity — largest signal)
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ComStock baseline)")
    print("=" * 70)

    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters_baseline.json')

    if skip_tuning:
        if os.path.exists(params_path):
            with open(params_path) as f:
                tuned_params = json.load(f)
            print(f"\nLoaded saved hyperparameters from {params_path}")
        else:
            print(f"\nWARNING: --skip-tuning but no saved params at {params_path}")
            tuned_params = None
    else:
        X_enc, _ = encode_features(df, FEATURE_COLS)
        y_tune = df[FUEL_TYPES['electricity']].values

        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y_tune[idx]
        else:
            X_tune = X_enc

        tuned_params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        print(f"  Best params: {tuned_params}")

        with open(params_path, 'w') as f:
            json.dump(tuned_params, f, indent=2)
        print(f"\nSaved tuned params to {params_path}")

    params = tuned_params or {
        'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
        'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
    }

    # Phase 2: Train ensemble per fuel type
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ComStock baseline, absolute EUI per fuel)")
    print("=" * 70)

    # Encode features for XGBoost/LightGBM
    X_enc, encoders = encode_features(df, FEATURE_COLS)
    cat_indices = [i for i, col in enumerate(FEATURE_COLS) if col in CAT_FEATURE_NAMES]

    # Prepare CatBoost data (string categoricals)
    X_cb = prepare_catboost_data(df, FEATURE_COLS, CAT_FEATURE_NAMES)

    # Same train/test split for all fuel types
    train_idx, test_idx = train_test_split(
        np.arange(len(X_enc)), test_size=0.2, random_state=42
    )

    all_results = []
    n_models_trained = 0

    for fuel_name in fuel_keys:
        target_col = FUEL_TYPES[fuel_name]
        y = df[target_col].values
        y_train, y_test = y[train_idx], y[test_idx]

        # Skip if target is constant (e.g., district_heating all zeros)
        if np.std(y_train) < 1e-10:
            print(f"  {fuel_name:>18}: SKIPPED (constant target)")
            continue

        trained_models = []

        # Train XGBoost
        xgb_model = train_single_model(X_enc.iloc[train_idx], y_train, params)
        xgb_metrics = evaluate_model(xgb_model, X_enc.iloc[test_idx], y_test)
        trained_models.append(('XGB', xgb_model, xgb_metrics))

        # Train LightGBM
        try:
            lgbm_model = train_lightgbm_model(X_enc.iloc[train_idx], y_train, params, cat_indices)
            lgbm_metrics = evaluate_model(lgbm_model, X_enc.iloc[test_idx], y_test)
            trained_models.append(('LGBM', lgbm_model, lgbm_metrics))
        except Exception as e:
            print(f"  {fuel_name:>18}: LGBM skipped ({e})")

        # Train CatBoost
        try:
            cb_model = train_catboost_model(X_cb.iloc[train_idx], y_train, params, cat_indices)
            cb_metrics = evaluate_model(cb_model, X_cb.iloc[test_idx], y_test)
            trained_models.append(('CB', cb_model, cb_metrics))
        except Exception as e:
            print(f"  {fuel_name:>18}: CB skipped ({e})")

        mae_parts = [f"{p}={m['mae_kbtu_sf']:5.2f}" for p, _, m in trained_models]
        print(f"  {fuel_name:>18}: {' '.join(mae_parts)} kBtu/sf")

        # Save all models — naming convention: {PREFIX}_upgrade0_{fuel}.pkl
        for prefix, model, metrics in trained_models:
            model_name = f'{prefix}_upgrade0_{fuel_name}'
            save_model_artifacts(model, encoders, FEATURE_COLS, metrics, OUTPUT_DIR, model_name)
            n_models_trained += 1

            all_results.append({
                'fuel_type': fuel_name,
                'model_prefix': prefix,
                'status': 'success',
                'model_type': 'baseline_absolute',
                'test_mae_kbtu_sf': metrics['mae_kbtu_sf'],
                'test_r2': metrics['r2'],
                'test_rmse_kwh_ft2': metrics['rmse_kwh_ft2'],
            })

    # Save results
    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_baseline.xlsx')
    results_df.to_excel(results_path, index=False)
    print(f"\nResults saved to {results_path}")

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} baseline models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description='Train ComStock baseline models (ensemble)')
    parser.add_argument('--fuels', nargs='+', type=str, default=None,
                        choices=list(FUEL_TYPES.keys()),
                        help='Specific fuel types to train (default: all)')
    parser.add_argument('--tune-trials', type=int, default=50)
    parser.add_argument('--skip-tuning', action='store_true')
    args = parser.parse_args()

    fuel_keys = args.fuels or list(FUEL_TYPES.keys())
    print(f"Training {len(fuel_keys)} ComStock baseline models × 3 model types")
    print(f"Output directory: {OUTPUT_DIR}")

    train_all(fuel_keys, tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify the script runs on a single fuel type**

Run: `python3 scripts/train_comstock_baseline.py --fuels electricity --skip-tuning`
Expected: Trains XGB + LGBM + CatBoost for electricity. Outputs 3 models to `XGB_Models/ComStock_Upgrades_2025_R3/`:
- `XGB_upgrade0_electricity.pkl` (overwrites old)
- `LGBM_upgrade0_electricity.pkl` (new)
- `CB_upgrade0_electricity.pkl` (new)

Verify the new model's `feature_columns` in `XGB_upgrade0_electricity_meta.json` lists all 38 features (25 original + 8 new + 5 baseline_eui NaN placeholders).

- [ ] **Step 3: Compare metrics against old baseline model**

Old electricity baseline: MAE=13.36 kBtu/sf, R²=0.844
New model should show improvement (expect MAE ~11-12 kBtu/sf, R² ~0.87+) due to HDD/CDD and thermostat features.

If metrics are WORSE, investigate — likely a data loading issue.

- [ ] **Step 4: Commit**

```bash
git add scripts/train_comstock_baseline.py
git commit -m "feat: ComStock baseline training script with new features + ensemble"
```

---

## Task 2: Create ResStock Baseline Training Script

**Files:**
- Create: `scripts/train_resstock_baseline.py`

Same approach as Task 1 but for ResStock: 4 fuel types (no district_heating), MF 4+ occupied filter, HDD/CDD from cluster_hdd_cdd.json lookup, ResStock-specific features.

- [ ] **Step 1: Write the training script**

Key differences from ComStock baseline:
- Filter to Multi-Family 4+ units, occupied only (same as `train_resstock_deltas.py`)
- 4 fuel types (no district_heating)
- HDD/CDD from `cluster_hdd_cdd.json` (not parquet — ResStock lacks `out.params.hdd65f`)
- ResStock feature columns (31 features from `train_resstock_deltas.py` FEATURE_COLS)
- ResStock-specific thermostat columns (`in.heating_setpoint`, `in.cooling_setpoint`, etc.)
- County column = `in.county` (not `in.as_simulated_nhgis_county_gisjoin`)

```python
#!/usr/bin/env python3
"""
Train ensemble baseline (upgrade 0) models for ResStock 2025 R1.
Multi-Family 4+ units, occupied only.

Usage:
    python3 scripts/train_resstock_baseline.py
    python3 scripts/train_resstock_baseline.py --skip-tuning
    python3 scripts/train_resstock_baseline.py --fuels electricity natural_gas
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
    encode_features, tune_hyperparameters,
    train_single_model, evaluate_model, save_model_artifacts,
    prepare_catboost_data, train_lightgbm_model, train_catboost_model,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_DIR = os.path.join(PROJECT_ROOT, 'ResStock', 'raw_data')
LOOKUP_PATH = os.path.join(PROJECT_ROOT, 'ComStock', 'spatial_tract_lookup_table.csv')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Upgrades_2025_R1')
HDD_CDD_PATH = os.path.join(PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json')

FUEL_TYPES = {
    'electricity': 'out.electricity.total.energy_consumption_intensity..kwh_per_ft2',
    'natural_gas': 'out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2',
    'fuel_oil': 'out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2',
    'propane': 'out.propane.total.energy_consumption_intensity..kwh_per_ft2',
}

# Same features as train_resstock_deltas.py (31 features)
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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
    'floor_plate_sqft',
    # --- Baseline EUI features (always NaN for baseline training) ---
    'baseline_electricity',
    'baseline_natural_gas',
    'baseline_fuel_oil',
    'baseline_propane',
]

# Must match train_resstock_deltas.py exactly (updated by feature pipeline fixes)
CAT_FEATURE_NAMES = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
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
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
]

# Columns to load from parquet
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + \
            [c for c in FEATURE_COLS if c not in (
                'cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft',
                'in.geometry_building_type_height',  # derived from stories
                'baseline_electricity', 'baseline_natural_gas',
                'baseline_fuel_oil', 'baseline_propane',
            )] + \
            list(FUEL_TYPES.values())
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))


def load_cluster_lookup():
    lookup = pd.read_csv(LOOKUP_PATH, usecols=['nhgis_county_gisjoin', 'cluster_name'],
                         low_memory=False)
    return lookup.drop_duplicates(subset='nhgis_county_gisjoin')


def filter_mf_occupied(df):
    units = df['in.geometry_building_number_units_mf'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    mf_mask = units >= 4
    occ_mask = df['in.vacancy_status'] == 'Occupied'
    return df[mf_mask & occ_mask].copy()


def load_baseline_data(cluster_lookup):
    fname = os.path.join(RAW_DIR, 'upgrade0.parquet')
    df = pd.read_parquet(fname, columns=LOAD_COLS)
    df = df.drop_duplicates(subset='bldg_id')

    # Filter to MF 4+ occupied
    df = filter_mf_occupied(df)

    # Merge cluster_name
    df = df.merge(cluster_lookup, left_on='in.county',
                  right_on='nhgis_county_gisjoin', how='left')
    df['cluster_name'] = df['cluster_name'].fillna('Unknown')

    # Fill null fuel EUIs with 0
    for col in FUEL_TYPES.values():
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # HDD/CDD from cluster lookup (ResStock lacks out.params HDD/CDD)
    with open(HDD_CDD_PATH) as f:
        cluster_hdd_cdd = json.load(f)
    df['hdd65f'] = df['cluster_name'].map(
        lambda c: cluster_hdd_cdd.get(c, {}).get('hdd65f', 4800.0))
    df['cdd65f'] = df['cluster_name'].map(
        lambda c: cluster_hdd_cdd.get(c, {}).get('cdd65f', 1400.0))

    # Derived features
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.geometry_stories'], errors='coerce').clip(lower=1)
    )

    # Building type height from stories
    stories = pd.to_numeric(df['in.geometry_stories'], errors='coerce').fillna(1)
    df['in.geometry_building_type_height'] = stories.apply(
        lambda s: '1-3' if s <= 3 else ('4-7' if s <= 7 else '8+')
    )

    # Baseline EUI features = NaN (we're predicting these)
    for fuel_name in FUEL_TYPES:
        df[f'baseline_{fuel_name}'] = float('nan')

    # Drop metadata
    df = df.drop(columns=['bldg_id', 'applicability',
                           'in.geometry_building_number_units_mf', 'in.vacancy_status',
                           'in.county', 'nhgis_county_gisjoin'], errors='ignore')

    return df


def train_all(fuel_keys, tune_trials=50, skip_tuning=False):
    total_start = time.time()
    from sklearn.model_selection import train_test_split

    cluster_lookup = load_cluster_lookup()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading ResStock baseline data...")
    df = load_baseline_data(cluster_lookup)
    print(f"  Buildings: {len(df):,}")

    # Phase 1: Hyperparameter tuning
    print("\n" + "=" * 70)
    print("PHASE 1: HYPERPARAMETER TUNING (ResStock baseline)")
    print("=" * 70)

    params_path = os.path.join(OUTPUT_DIR, 'tuned_hyperparameters_baseline.json')

    if skip_tuning:
        if os.path.exists(params_path):
            with open(params_path) as f:
                tuned_params = json.load(f)
            print(f"\nLoaded saved hyperparameters from {params_path}")
        else:
            print(f"\nWARNING: --skip-tuning but no saved params")
            tuned_params = None
    else:
        X_enc, _ = encode_features(df, FEATURE_COLS)
        y_tune = df[FUEL_TYPES['electricity']].values
        if len(X_enc) > 30000:
            idx = np.random.RandomState(42).choice(len(X_enc), 30000, replace=False)
            X_tune, y_tune = X_enc.iloc[idx], y_tune[idx]
        else:
            X_tune = X_enc
        tuned_params = tune_hyperparameters(X_tune, y_tune, n_trials=tune_trials)
        with open(params_path, 'w') as f:
            json.dump(tuned_params, f, indent=2)

    params = tuned_params or {
        'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.1,
        'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8,
    }

    # Phase 2: Train ensemble
    print("\n" + "=" * 70)
    print("PHASE 2: MODEL TRAINING (ResStock baseline)")
    print("=" * 70)

    X_enc, encoders = encode_features(df, FEATURE_COLS)
    cat_indices = [i for i, col in enumerate(FEATURE_COLS) if col in CAT_FEATURE_NAMES]
    X_cb = prepare_catboost_data(df, FEATURE_COLS, CAT_FEATURE_NAMES)

    train_idx, test_idx = train_test_split(
        np.arange(len(X_enc)), test_size=0.2, random_state=42
    )

    all_results = []
    n_models_trained = 0

    for fuel_name in fuel_keys:
        target_col = FUEL_TYPES[fuel_name]
        y = df[target_col].values
        y_train, y_test = y[train_idx], y[test_idx]

        if np.std(y_train) < 1e-10:
            print(f"  {fuel_name:>18}: SKIPPED (constant target)")
            continue

        trained_models = []

        xgb_model = train_single_model(X_enc.iloc[train_idx], y_train, params)
        xgb_metrics = evaluate_model(xgb_model, X_enc.iloc[test_idx], y_test)
        trained_models.append(('XGB', xgb_model, xgb_metrics))

        try:
            lgbm_model = train_lightgbm_model(X_enc.iloc[train_idx], y_train, params, cat_indices)
            lgbm_metrics = evaluate_model(lgbm_model, X_enc.iloc[test_idx], y_test)
            trained_models.append(('LGBM', lgbm_model, lgbm_metrics))
        except Exception as e:
            print(f"  {fuel_name:>18}: LGBM skipped ({e})")

        try:
            cb_model = train_catboost_model(X_cb.iloc[train_idx], y_train, params, cat_indices)
            cb_metrics = evaluate_model(cb_model, X_cb.iloc[test_idx], y_test)
            trained_models.append(('CB', cb_model, cb_metrics))
        except Exception as e:
            print(f"  {fuel_name:>18}: CB skipped ({e})")

        mae_parts = [f"{p}={m['mae_kbtu_sf']:5.2f}" for p, _, m in trained_models]
        print(f"  {fuel_name:>18}: {' '.join(mae_parts)} kBtu/sf")

        for prefix, model, metrics in trained_models:
            model_name = f'{prefix}_upgrade0_{fuel_name}'
            save_model_artifacts(model, encoders, FEATURE_COLS, metrics, OUTPUT_DIR, model_name)
            n_models_trained += 1
            all_results.append({
                'fuel_type': fuel_name, 'model_prefix': prefix,
                'status': 'success', 'model_type': 'baseline_absolute',
                'test_mae_kbtu_sf': metrics['mae_kbtu_sf'],
                'test_r2': metrics['r2'],
            })

    results_df = pd.DataFrame(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'training_results_baseline.xlsx')
    results_df.to_excel(results_path, index=False)

    total_time = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {n_models_trained} baseline models trained in {timedelta(seconds=total_time)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description='Train ResStock baseline models (ensemble)')
    parser.add_argument('--fuels', nargs='+', type=str, default=None,
                        choices=list(FUEL_TYPES.keys()))
    parser.add_argument('--tune-trials', type=int, default=50)
    parser.add_argument('--skip-tuning', action='store_true')
    args = parser.parse_args()

    fuel_keys = args.fuels or list(FUEL_TYPES.keys())
    print(f"Training {len(fuel_keys)} ResStock baseline models × 3 model types")

    train_all(fuel_keys, tune_trials=args.tune_trials, skip_tuning=args.skip_tuning)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify with a single fuel type**

Run: `python3 scripts/train_resstock_baseline.py --fuels electricity --skip-tuning`
Expected: 3 models created. Old ResStock electricity baseline: MAE=6.83 kBtu/sf, R²=0.684. New should improve due to HDD/CDD.

- [ ] **Step 3: Commit**

```bash
git add scripts/train_resstock_baseline.py
git commit -m "feat: ResStock baseline training script with new features + ensemble"
```

---

## Task 3: Update ComStock Sizing Training Script

**Files:**
- Modify: `scripts/train_comstock_sizing.py`

Add the same new features (HDD/CDD, thermostat, floor_plate_sqft) to sizing models. Stays XGB-only — no ensemble for sizing.

**Rationale for adding features:** HDD/CDD directly affects heating/cooling capacity requirements. Thermostat setpoints influence required capacity sizing. Floor plate sqft provides better geometric signal for wall/roof/window areas.

- [ ] **Step 1: Update FEATURE_COLS to match the new feature set**

In `scripts/train_comstock_sizing.py`, replace the existing `FEATURE_COLS` list (lines 54-80) with the expanded version. Add the same new features as the baseline/delta scripts, EXCEPT the `baseline_*` columns (sizing has no baseline EUI concept):

```python
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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
    'floor_plate_sqft',
]
```

- [ ] **Step 1b: Add CAT_FEATURE_NAMES**

The current sizing script has no `CAT_FEATURE_NAMES` — `encode_features()` auto-detects string columns. But with the pipeline fixes, categorical columns must be explicitly declared for CatBoost consistency. Even though sizing stays XGB-only, having `CAT_FEATURE_NAMES` ensures the encoders are correct if ensemble is added later.

Add after `FEATURE_COLS`:
```python
CAT_FEATURE_NAMES = [
    'in.comstock_building_type_group',
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
    'in.interior_lighting_generation',
    'in.weekday_operating_hours..hr',
    'in.building_subtype',
    'in.aspect_ratio',
    'in.energy_code_followed_during_last_hvac_replacement',
    'in.energy_code_followed_during_last_roof_replacement',
    'in.energy_code_followed_during_last_walls_replacement',
    'in.energy_code_followed_during_last_svc_water_htg_replacement',
    'in.tstat_clg_sp_f..f',
    'in.tstat_htg_sp_f..f',
    'in.tstat_clg_delta_f..delta_f',
    'in.tstat_htg_delta_f..delta_f',
    'in.weekend_operating_hours..hr',
]
```

Note: This list matches the ComStock baseline/delta scripts. The sizing script doesn't train CatBoost, but the encoders stored in `_encoders.pkl` need to be consistent — if `encode_features()` auto-detects, it might miss columns that the preprocessor sends as strings (e.g., `in.number_stories` as categorical bin).

- [ ] **Step 2: Update LOAD_COLS to include new parquet columns**

Update `LOAD_COLS` to load the new columns from parquet (using their original parquet names):

```python
LOAD_COLS = ['bldg_id', 'completed_status',
             'in.as_simulated_nhgis_county_gisjoin'] + \
            [c for c in FEATURE_COLS if c not in (
                'cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft',
            )] + \
            list(SIZING_TARGETS.values()) + [
                'out.params.hdd65f', 'out.params.cdd65f',
            ]
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))
```

- [ ] **Step 3: Update load_baseline_data() to derive new features**

After the cluster_name merge and target cleaning, add:

```python
    # Rename HDD/CDD to match inference names
    df = df.rename(columns={
        'out.params.hdd65f': 'hdd65f',
        'out.params.cdd65f': 'cdd65f',
    })

    # Clean thermostat sentinel values
    tstat_cols = [
        'in.tstat_clg_sp_f..f', 'in.tstat_htg_sp_f..f',
        'in.tstat_clg_delta_f..delta_f', 'in.tstat_htg_delta_f..delta_f',
        'in.weekend_operating_hours..hr',
    ]
    for col in tstat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df.loc[df[col] >= 999, col] = float('nan')

    # Derived features
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.number_stories'], errors='coerce').clip(lower=1)
    )
```

- [ ] **Step 4: Run a single target to validate**

Run: `python3 scripts/train_comstock_sizing.py --targets heating_capacity --skip-tuning`
Expected: Model trains with 33 features (was 24). Old heating_capacity R²=0.975, new should be ≥0.975 (HDD/CDD helps capacity prediction).

- [ ] **Step 5: Commit**

```bash
git add scripts/train_comstock_sizing.py
git commit -m "feat: add new features to ComStock sizing training (HDD/CDD, thermostat, floor_plate)"
```

---

## Task 4: Update ResStock Sizing Training Script

**Files:**
- Modify: `scripts/train_resstock_sizing.py`

Same approach as Task 3 but for ResStock: add HDD/CDD (from cluster lookup), thermostat setpoints, floor_plate_sqft.

- [ ] **Step 1: Update FEATURE_COLS**

Replace lines 51-75 with expanded list matching `train_resstock_deltas.py` features, minus `baseline_*`:

```python
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
    # --- New features ---
    'hdd65f',
    'cdd65f',
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
    'floor_plate_sqft',
]
```

- [ ] **Step 1b: Add CAT_FEATURE_NAMES**

Add after `FEATURE_COLS` — must match `train_resstock_deltas.py`:
```python
CAT_FEATURE_NAMES = [
    'in.geometry_building_type_recs',
    'in.geometry_building_type_height',
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
    'in.heating_setpoint',
    'in.cooling_setpoint',
    'in.heating_setpoint_offset_magnitude',
    'in.cooling_setpoint_offset_magnitude',
]
```

- [ ] **Step 2: Add HDD_CDD_PATH constant and update LOAD_COLS**

Add at the top of the configuration section:
```python
HDD_CDD_PATH = os.path.join(PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json')
```

Update LOAD_COLS to exclude derived columns:
```python
LOAD_COLS = ['bldg_id', 'applicability',
             'in.geometry_building_number_units_mf', 'in.vacancy_status',
             'in.county'] + \
            [c for c in FEATURE_COLS if c not in (
                'cluster_name', 'hdd65f', 'cdd65f', 'floor_plate_sqft',
                'in.geometry_building_type_height',  # derived from stories
            )] + \
            list(SIZING_TARGETS.values())
LOAD_COLS = list(dict.fromkeys(LOAD_COLS))
```

- [ ] **Step 3: Update load_baseline_data() to derive new features**

After the cluster_name merge in `load_baseline_data()`, add:

```python
    # HDD/CDD from cluster lookup (ResStock lacks out.params HDD/CDD)
    with open(HDD_CDD_PATH) as f:
        cluster_hdd_cdd = json.load(f)
    df['hdd65f'] = df['cluster_name'].map(
        lambda c: cluster_hdd_cdd.get(c, {}).get('hdd65f', 4800.0))
    df['cdd65f'] = df['cluster_name'].map(
        lambda c: cluster_hdd_cdd.get(c, {}).get('cdd65f', 1400.0))

    # Derived features
    df['floor_plate_sqft'] = (
        pd.to_numeric(df['in.sqft..ft2'], errors='coerce') /
        pd.to_numeric(df['in.geometry_stories'], errors='coerce').clip(lower=1)
    )

    # Building type height from stories (derived, not loaded from parquet)
    stories = pd.to_numeric(df['in.geometry_stories'], errors='coerce').fillna(1)
    df['in.geometry_building_type_height'] = stories.apply(
        lambda s: '1-3' if s <= 3 else ('4-7' if s <= 7 else '8+')
    )
```

Note: ResStock thermostat columns (`in.heating_setpoint`, etc.) are categorical strings in the parquet (e.g., "70F", "3F"). They are in `CAT_FEATURE_NAMES` and will be encoded as categoricals by `encode_features()`.

- [ ] **Step 4: Run a single target to validate**

Run: `python3 scripts/train_resstock_sizing.py --skip-tuning`
Expected: 5 sizing models train successfully with new features. Verify R² ≥ old values.

- [ ] **Step 5: Commit**

```bash
git add scripts/train_resstock_sizing.py
git commit -m "feat: add new features to ResStock sizing training (HDD/CDD, thermostat, floor_plate)"
```

---

## Task 5: Full Retraining Run

**Files:** No new files — uses scripts from Tasks 1-4.

After all scripts are validated, run the full retraining. Archive old models first.

- [ ] **Step 1: Archive old baseline models**

```bash
mkdir -p XGB_Models/archive/pre_ensemble_baseline
cp XGB_Models/ComStock_Upgrades_2025_R3/XGB_upgrade0_* XGB_Models/archive/pre_ensemble_baseline/
cp XGB_Models/ResStock_Upgrades_2025_R1/XGB_upgrade0_* XGB_Models/archive/pre_ensemble_baseline/
```

- [ ] **Step 2: Archive old sizing models**

```bash
cp -r XGB_Models/ComStock_Sizing XGB_Models/archive/ComStock_Sizing_pre_new_features
cp -r XGB_Models/ResStock_Sizing XGB_Models/archive/ResStock_Sizing_pre_new_features
```

- [ ] **Step 3: Retrain ComStock baseline**

Run: `python3 scripts/train_comstock_baseline.py`
Note: First run performs hyperparameter tuning (~30-60 min). Subsequent runs can use `--skip-tuning`.
Expected: 5 fuel types × 3 model types = up to 15 models (some fuels may skip due to constant target, e.g., district_heating might be skipped by CatBoost).

- [ ] **Step 4: Retrain ResStock baseline**

Run: `python3 scripts/train_resstock_baseline.py`
Note: First run performs hyperparameter tuning. Subsequent runs can use `--skip-tuning`.
Expected: 4 fuel types × 3 model types = up to 12 models.

- [ ] **Step 5: Retrain ComStock sizing**

Run: `python3 scripts/train_comstock_sizing.py --skip-tuning`
Expected: 5 sizing models with new features.

- [ ] **Step 6: Retrain ResStock sizing**

Run: `python3 scripts/train_resstock_sizing.py --skip-tuning`
Expected: 5 sizing models with new features.

- [ ] **Step 7: Validate via API**

Start backend and run a test assessment:
```bash
cd backend && uvicorn app.main:app --reload
```

Test ComStock:
```bash
curl -s -X POST http://localhost:8000/assess -H 'Content-Type: application/json' -d '{
  "building_type": "Office", "sqft": 50000, "num_stories": 3,
  "zipcode": "20001", "year_built": 1985
}' | python3 -m json.tool | head -30
```

Test ResStock:
```bash
curl -s -X POST http://localhost:8000/assess -H 'Content-Type: application/json' -d '{
  "building_type": "Multi-Family", "sqft": 25000, "num_stories": 5,
  "zipcode": "10001", "year_built": 1985
}' | python3 -m json.tool | head -30
```

Expected: Both return valid responses with baseline EUI values. Verify:
- No errors or traceback in server logs
- Baseline EUI values are reasonable (similar range to old, but slightly different)
- Sizing values are reasonable and non-negative
- Upgrade measures still calculate correctly

- [ ] **Step 8: Run backend tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass. The model manager loads new models transparently — baseline models now have ensemble bundles (3 sub-models), sizing models have new features but same XGB-only structure.

- [ ] **Step 9: Commit retrained models**

```bash
git add XGB_Models/ComStock_Upgrades_2025_R3/XGB_upgrade0_* \
       XGB_Models/ComStock_Upgrades_2025_R3/LGBM_upgrade0_* \
       XGB_Models/ComStock_Upgrades_2025_R3/CB_upgrade0_* \
       XGB_Models/ResStock_Upgrades_2025_R1/XGB_upgrade0_* \
       XGB_Models/ResStock_Upgrades_2025_R1/LGBM_upgrade0_* \
       XGB_Models/ResStock_Upgrades_2025_R1/CB_upgrade0_* \
       XGB_Models/ComStock_Sizing/ \
       XGB_Models/ResStock_Sizing/
git commit -m "feat: retrained baseline (ensemble) + sizing models with new features"
```

---

## Task 6: Model Manager Sizing Ensemble Support (Optional/Future)

**Scope:** This task is optional. Only pursue if sizing model accuracy needs improvement.

Currently `predict_sizing()` calls `_predict_single()` (XGB-only). If sizing models were trained with ensemble, the model manager's `_index_directory` for sizing would need to detect `LGBM_sizing_*` and `CB_sizing_*` files. The `_RE_SIZING` regex (`^XGB_(.+)\.pkl$`) would need updating.

**Decision:** Skip for now. Sizing R² is already 0.97+ for ComStock. Revisit only if accuracy is insufficient.

---

## Execution Order and Dependencies

```
Task 1 (ComStock baseline script)
    │                                  Task 3 (ComStock sizing update)
    │                                      │
Task 2 (ResStock baseline script)      Task 4 (ResStock sizing update)
    │                                      │
    └──────────────┬───────────────────────┘
                   │
             Task 5 (Full retrain + validate)
                   │
             Task 6 (Optional: sizing ensemble)
```

**Tasks 1-4 are independent** and can be developed in parallel.
**Task 5** depends on all of Tasks 1-4.
**Task 6** is optional and independent.
