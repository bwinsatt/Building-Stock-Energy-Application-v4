# Delta Savings Models — Design Plan

**Date:** 2026-03-08
**Status:** Validation phase

## Problem

Baseline (upgrade 0) and upgrade XGBoost models are trained independently on different building populations. They predict absolute EUI, not deltas. Subtracting two independent predictions compounds noise, producing "negative savings" for measures like duct sealing that physically cannot increase total energy use.

Current mitigation: per-fuel clamping in `_CLAMP_NEGATIVE_CATEGORIES` — works but is blunt and potentially too aggressive (e.g., low-SHGC windows in cold climates can legitimately increase heating load).

## Solution: Delta/Savings Models

Train models to predict `baseline_EUI - upgrade_EUI` (the savings) directly, rather than absolute post-upgrade EUI. The model learns the *relationship* between baseline and upgrade states.

### Why This Works

- Paired parquet files exist with the same `bldg_id` across baseline and each upgrade
- Inner join gives true per-building deltas as training targets
- Model directly learns "duct sealing saves X in climate zone Y" rather than two unrelated absolute values
- Negative savings are handled with a simple `max(0, delta)` clamp — principled and minimal

### What Doesn't Change

- **Preprocessor / imputation** — runs before any model prediction, fully independent
- **Baseline models** (upgrade 0) — still predict absolute EUI per fuel
- **Sizing models** — separate pipeline, predict heating/cooling capacity for cost calc
- **Rate models** — separate pipeline, predict $/kWh per fuel
- **Cost calculator** — consumes sizing predictions, not EUI predictions

### What Changes

- **Upgrade models** — replaced by delta models (predict savings, not absolute EUI)
- **`ModelManager.predict_upgrade()`** — replaced by `predict_delta()` returning savings per fuel
- **`assessment.py`** — savings = delta prediction (clamped at 0); post-upgrade EUI = baseline - savings
- **`_CLAMP_NEGATIVE_CATEGORIES`** — deleted entirely
- **Training script** — `train_resstock_deltas.py` replaces `train_resstock_upgrades.py`

### Rollout

Hard cutover. No conditional logic or backwards compatibility with absolute upgrade models.

## Validation Plan

### Script: `scripts/validate_delta_models.py`

Test on upgrade 13 (Duct Sealing) first. Compares delta approach vs. current absolute-subtraction approach head-to-head on the same held-out test set.

**Data prep:**
1. Load `upgrade0.parquet` and `upgrade13.parquet`
2. Inner join on `bldg_id` (buildings present in both AND applicable in upgrade 13)
3. Compute ground-truth delta per fuel: `baseline_eui - upgrade_eui`
4. Same MF 4+ occupied filter, same cluster lookup join as current training
5. 80/20 train/test split (`random_state=42`)

**Models trained:**
- 4 delta models (electricity, natural_gas, fuel_oil, propane)
- Same XGBoost setup, same feature columns, same hyperparameters as existing training

**Evaluation (on held-out test set):**
- MAE of total savings (kBtu/sf) — both approaches
- % of buildings with negative total savings — both approaches
- % of buildings with negative per-fuel savings — both approaches
- R² of predicted savings vs. true simulation savings — both approaches
- Per-building comparison CSV for deeper analysis

**CLI:**
```bash
python scripts/validate_delta_models.py                  # Default: upgrade 13
python scripts/validate_delta_models.py --upgrade 11     # Test another upgrade
```

### Success Criteria

- Delta approach has lower MAE on total savings than absolute subtraction
- Delta approach produces fewer physically impossible (negative) savings predictions
- R² of delta predictions is meaningfully positive (model is learning real patterns)

## Production Integration (after validation)

### ModelManager
- `predict_delta(features, upgrade_id, dataset) -> dict[fuel, savings_kwh_sf]`
- Replaces `predict_upgrade()`
- Models stored in same `XGB_Models/ResStock_Upgrades_2025_R1/` directory

### assessment.py
```python
# New flow
delta = model_manager.predict_delta(features, uid, dataset)
savings_kwh = {fuel: max(0.0, d) for fuel, d in delta.items()}
post_eui = {fuel: baseline_eui[fuel] - savings_kwh[fuel] for fuel in baseline_eui}
```

### Training
- `train_resstock_deltas.py` — joins each upgrade parquet with upgrade 0 on `bldg_id`
- Targets: `delta_{fuel} = baseline_{fuel} - upgrade_{fuel}`
- Same feature columns, hyperparameter groups, and evaluation as current script
