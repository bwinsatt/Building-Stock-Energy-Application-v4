"""
ComStock 2025 R3 Exploratory Analysis
Phase 1: Understand savings data, validate model architecture, identify key features.

Key questions:
1. How do duplicate bldg_ids with different weights work? (Same simulation, different geographic representation)
2. Weighted vs unweighted training - which is better for single-building prediction?
3. What features drive savings variation?
4. Single multi-measure model vs per-measure models?
5. Predict post-upgrade EUI vs % savings?
"""

import pandas as pd
import pyarrow.parquet as pq
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "ComStock", "raw_data")

# ── 1. Load upgrades lookup ──────────────────────────────────────────────────
with open(os.path.join(RAW_DIR, "upgrades_lookup.json")) as f:
    upgrades = json.load(f)

print("=" * 80)
print("COMSTOCK 2025 R3 EXPLORATORY ANALYSIS")
print("=" * 80)
print(f"\nTotal upgrades: {len(upgrades)} (including baseline)")

# ── 2. Define columns of interest ───────────────────────────────────────────
INPUT_COLS = [
    "bldg_id", "upgrade", "weight", "applicability",
    # Core
    "in.comstock_building_type", "in.sqft..ft2", "in.number_of_stories",
    "in.as_simulated_ashrae_iecc_climate_zone_2006", "in.year_built", "in.vintage",
    # HVAC
    "in.heating_fuel", "in.service_water_heating_fuel", "in.hvac_category",
    "in.hvac_cool_type", "in.hvac_heat_type", "in.hvac_system_type", "in.hvac_vent_type",
    # Envelope
    "in.wall_construction_type", "in.window_type", "in.window_to_wall_ratio_category",
    "in.airtightness..m3_per_m2_h",
    # Lighting / Operations
    "in.interior_lighting_generation", "in.weekday_operating_hours..hr",
    # Detail
    "in.building_subtype", "in.aspect_ratio",
    # Energy code history
    "in.energy_code_followed_during_last_hvac_replacement",
    "in.energy_code_followed_during_last_roof_replacement",
    "in.energy_code_followed_during_last_walls_replacement",
    "in.energy_code_followed_during_last_svc_water_htg_replacement",
    # Geographic (for cluster mapping)
    "in.as_simulated_nhgis_county_gisjoin",
]

OUTPUT_COLS = [
    "out.site_energy.total.energy_consumption_intensity..kwh_per_ft2",
    "out.site_energy.total.energy_savings_intensity..kwh_per_ft2",
    "out.site_energy.total.energy_consumption..kwh",
    "out.site_energy.total.energy_savings..kwh",
    "out.electricity.total.energy_consumption..kwh",
    "out.electricity.total.energy_savings..kwh",
    "out.natural_gas.total.energy_consumption..kwh",
    "out.natural_gas.total.energy_savings..kwh",
    "out.propane.total.energy_consumption..kwh",
    "out.propane.total.energy_savings..kwh",
    "out.fuel_oil.total.energy_consumption..kwh",
    "out.fuel_oil.total.energy_savings..kwh",
    "out.district_heating.total.energy_consumption..kwh",
    "out.district_heating.total.energy_savings..kwh",
]

ALL_COLS = INPUT_COLS + OUTPUT_COLS

EUI_COL = "out.site_energy.total.energy_consumption_intensity..kwh_per_ft2"
SAVINGS_COL = "out.site_energy.total.energy_savings_intensity..kwh_per_ft2"

FEATURE_COLS = [
    "in.comstock_building_type", "in.sqft..ft2", "in.number_of_stories",
    "in.as_simulated_ashrae_iecc_climate_zone_2006", "in.vintage",
    "in.heating_fuel", "in.service_water_heating_fuel", "in.hvac_category",
    "in.hvac_cool_type", "in.hvac_heat_type", "in.hvac_system_type", "in.hvac_vent_type",
    "in.wall_construction_type", "in.window_type", "in.window_to_wall_ratio_category",
    "in.airtightness..m3_per_m2_h",
    "in.interior_lighting_generation", "in.weekday_operating_hours..hr",
    "in.building_subtype", "in.aspect_ratio",
    "in.energy_code_followed_during_last_hvac_replacement",
    "in.energy_code_followed_during_last_roof_replacement",
    "in.energy_code_followed_during_last_walls_replacement",
    "in.energy_code_followed_during_last_svc_water_htg_replacement",
]

# ── 3. Load baseline and understand weight/dedup structure ──────────────────
print("\n── Loading baseline (upgrade0) ──")
baseline_raw = pd.read_parquet(os.path.join(RAW_DIR, "upgrade0_agg.parquet"), columns=ALL_COLS)
print(f"Raw baseline rows: {len(baseline_raw):,}")
print(f"Unique bldg_ids: {baseline_raw['bldg_id'].nunique():,}")
print(f"Duplicates: {baseline_raw['bldg_id'].duplicated().sum():,}")

# Deduplicate: same bldg_id has identical features/EUI, only weight differs.
# Sum weights for training, keep one row for features.
baseline = baseline_raw.groupby('bldg_id', as_index=False).agg(
    {**{col: 'first' for col in ALL_COLS if col not in ['bldg_id', 'weight']},
     'weight': 'sum'}
)
print(f"After dedup (summed weights): {len(baseline):,} rows")

print(f"\nBuilding type distribution:")
print(baseline['in.comstock_building_type'].value_counts().to_string())

print(f"\n── Baseline EUI Statistics (kWh/ft2) ──")
print(baseline[EUI_COL].describe())

# Create lookup for fast baseline EUI access
baseline_eui_lookup = baseline.set_index('bldg_id')[EUI_COL]
baseline_weight_lookup = baseline.set_index('bldg_id')['weight']

# ── 4. Helper to load and prep an upgrade file ──────────────────────────────
def load_upgrade(uid):
    """Load upgrade file, dedup, merge baseline EUI, compute savings %."""
    fname = f"upgrade{uid}_agg.parquet"
    df = pd.read_parquet(os.path.join(RAW_DIR, fname), columns=ALL_COLS)
    # Dedup same as baseline
    df = df.groupby('bldg_id', as_index=False).agg(
        {**{col: 'first' for col in ALL_COLS if col not in ['bldg_id', 'weight']},
         'weight': 'sum'}
    )
    df['baseline_eui'] = df['bldg_id'].map(baseline_eui_lookup)
    df['weight'] = df['bldg_id'].map(baseline_weight_lookup)  # Use consistent weights
    df['pct_savings'] = (df[SAVINGS_COL] / df['baseline_eui']) * 100
    return df

# ── 5. Savings analysis by measure ──────────────────────────────────────────
SAMPLE_UPGRADES = [1, 43, 48, 49, 55]

print("\n" + "=" * 80)
print("SAVINGS ANALYSIS BY MEASURE")
print("=" * 80)

for uid in SAMPLE_UPGRADES:
    df = load_upgrade(uid)
    applicable = df[df['applicability'] == True]

    print(f"\n── Upgrade {uid}: {upgrades[str(uid)]} ──")
    print(f"  Applicable: {len(applicable):,} / {len(df):,} ({100*len(applicable)/len(df):.1f}%)")
    print(f"  EUI Savings (kWh/ft2):  mean={applicable[SAVINGS_COL].mean():.2f}, median={applicable[SAVINGS_COL].median():.2f}")
    print(f"  % Savings:              mean={applicable['pct_savings'].mean():.1f}%, median={applicable['pct_savings'].median():.1f}%")
    print(f"  Post-upgrade EUI:       mean={applicable[EUI_COL].mean():.2f}, median={applicable[EUI_COL].median():.2f}")

    print(f"\n  Savings by building type (mean % savings):")
    by_type = applicable.groupby('in.comstock_building_type')['pct_savings'].agg(['mean', 'std', 'count'])
    by_type = by_type.sort_values('mean', ascending=False)
    for idx, row in by_type.iterrows():
        print(f"    {idx:30s}  {row['mean']:6.1f}% +/- {row['std']:5.1f}%  (n={int(row['count']):,})")

# ── 6. Variance analysis: What drives savings variation? ────────────────────
print("\n" + "=" * 80)
print("VARIANCE ANALYSIS: WHAT DRIVES SAVINGS DIFFERENCES?")
print("=" * 80)

for uid, name in [(43, "LED Lighting"), (1, "HP-RTU")]:
    df = load_upgrade(uid)
    applicable = df[df['applicability'] == True].copy()

    print(f"\n── {name} (upgrade {uid}) - Eta-squared by feature ──")
    print("(Higher = more important for predicting savings)\n")

    total_var = applicable['pct_savings'].var()
    eta_squared = {}

    for col in FEATURE_COLS:
        if col not in applicable.columns:
            continue
        groups = applicable.groupby(col)['pct_savings']
        group_means = groups.mean()
        group_counts = groups.count()
        grand_mean = applicable['pct_savings'].mean()
        ss_between = sum(group_counts[g] * (group_means[g] - grand_mean)**2 for g in group_means.index)
        ss_total = total_var * (len(applicable) - 1)
        eta2 = ss_between / ss_total if ss_total > 0 else 0
        eta_squared[col] = eta2

    for col, eta2 in sorted(eta_squared.items(), key=lambda x: -x[1]):
        bar = "#" * int(eta2 * 50)
        print(f"  {col:60s}  {eta2:.4f}  {bar}")

# ── 7. Model comparison: Weighted vs Unweighted ─────────────────────────────
print("\n" + "=" * 80)
print("WEIGHTED vs UNWEIGHTED TRAINING COMPARISON")
print("=" * 80)

led = load_upgrade(43)
led_applicable = led[led['applicability'] == True].copy().reset_index(drop=True)

# Encode features
def encode_features(df, feature_cols):
    """Label-encode string columns, return encoded df."""
    df_enc = df[feature_cols].copy()
    encoders = {}
    for col in feature_cols:
        if df_enc[col].dtype == 'object' or str(df_enc[col].dtype) == 'large_string':
            le = LabelEncoder()
            df_enc[col] = le.fit_transform(df_enc[col].astype(str))
            encoders[col] = le
    return df_enc, encoders

X_enc, encoders = encode_features(led_applicable, FEATURE_COLS)
y = led_applicable['pct_savings'].values
w = led_applicable['weight'].values
btypes = led_applicable['in.comstock_building_type'].values

X_train, X_test, y_train, y_test, w_train, w_test, bt_train, bt_test = train_test_split(
    X_enc, y, w, btypes, test_size=0.2, random_state=42
)

# Unweighted
model_uw = xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
model_uw.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
pred_uw = model_uw.predict(X_test)

# Weighted
model_w = xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
model_w.fit(X_train, y_train, sample_weight=w_train, eval_set=[(X_test, y_test)], verbose=False)
pred_w = model_w.predict(X_test)

print(f"\nLED Savings prediction (% savings):")
print(f"  {'Metric':<25s} {'Unweighted':>12s} {'Weighted':>12s}")
print(f"  {'MAE (unweighted eval)':<25s} {mean_absolute_error(y_test, pred_uw):>12.2f} {mean_absolute_error(y_test, pred_w):>12.2f}")
print(f"  {'R² (unweighted eval)':<25s} {r2_score(y_test, pred_uw):>12.4f} {r2_score(y_test, pred_w):>12.4f}")
wmae_uw = np.average(np.abs(y_test - pred_uw), weights=w_test)
wmae_w = np.average(np.abs(y_test - pred_w), weights=w_test)
print(f"  {'MAE (weighted eval)':<25s} {wmae_uw:>12.2f} {wmae_w:>12.2f}")

print(f"\n  Per building-type MAE:")
test_df = pd.DataFrame({
    'actual': y_test,
    'pred_uw': pred_uw,
    'pred_w': pred_w,
    'btype': bt_test,
})

for btype in sorted(test_df['btype'].unique()):
    mask = test_df['btype'] == btype
    mae_uw_bt = mean_absolute_error(test_df.loc[mask, 'actual'], test_df.loc[mask, 'pred_uw'])
    mae_w_bt = mean_absolute_error(test_df.loc[mask, 'actual'], test_df.loc[mask, 'pred_w'])
    n = mask.sum()
    print(f"    {btype:30s}  UW={mae_uw_bt:.2f}%  W={mae_w_bt:.2f}%  (n={n:,})")

# ── 7.5. Stacking experiment: baseline EUI as feature ─────────────────────
print("\n" + "=" * 80)
print("STACKING EXPERIMENT: BASELINE EUI AS FEATURE")
print("=" * 80)
print("Does adding predicted baseline EUI as a feature improve upgrade model accuracy?")

from sklearn.model_selection import KFold

# Step 1: Train baseline model with out-of-fold predictions to avoid leakage
print("\n── Step 1: Generate out-of-fold baseline EUI predictions ──")
baseline_enc, _ = encode_features(baseline, FEATURE_COLS)
baseline_eui_values = baseline[EUI_COL].values
baseline_bldg_ids = baseline['bldg_id'].values

oof_predictions = np.zeros(len(baseline))
kf = KFold(n_splits=5, shuffle=True, random_state=42)

for fold, (train_idx, val_idx) in enumerate(kf.split(baseline_enc)):
    fold_model = xgb.XGBRegressor(
        n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1
    )
    fold_model.fit(baseline_enc.iloc[train_idx], baseline_eui_values[train_idx], verbose=False)
    oof_predictions[val_idx] = fold_model.predict(baseline_enc.iloc[val_idx])
    fold_r2 = r2_score(baseline_eui_values[val_idx], oof_predictions[val_idx])
    print(f"  Fold {fold+1}: R²={fold_r2:.4f}")

overall_r2 = r2_score(baseline_eui_values, oof_predictions)
overall_mae = mean_absolute_error(baseline_eui_values, oof_predictions)
print(f"  Overall OOF: R²={overall_r2:.4f}, MAE={overall_mae:.2f} kWh/ft²")

# Create lookup: bldg_id -> predicted baseline EUI
oof_lookup = dict(zip(baseline_bldg_ids, oof_predictions))

# Step 2: Add predicted baseline EUI to LED upgrade data and compare
print("\n── Step 2: Compare LED upgrade models with/without baseline EUI feature ──")

led_applicable['predicted_baseline_eui'] = led_applicable['bldg_id'].map(oof_lookup)
# Drop any rows where we couldn't map (shouldn't happen, but be safe)
led_stack = led_applicable.dropna(subset=['predicted_baseline_eui']).reset_index(drop=True)

FEATURE_COLS_STACKED = FEATURE_COLS + ['predicted_baseline_eui']

X_base, _ = encode_features(led_stack, FEATURE_COLS)
X_stacked, _ = encode_features(led_stack, FEATURE_COLS_STACKED)
y_stack = led_stack['pct_savings'].values
bt_stack = led_stack['in.comstock_building_type'].values

X_tr_b, X_te_b, X_tr_s, X_te_s, y_tr, y_te, bt_tr, bt_te = train_test_split(
    X_base, X_stacked, y_stack, bt_stack, test_size=0.2, random_state=42
)

# Without baseline EUI feature
model_no_stack = xgb.XGBRegressor(
    n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1
)
model_no_stack.fit(X_tr_b, y_tr, eval_set=[(X_te_b, y_te)], verbose=False)
pred_no_stack = model_no_stack.predict(X_te_b)

# With baseline EUI feature
model_stack = xgb.XGBRegressor(
    n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1
)
model_stack.fit(X_tr_s, y_tr, eval_set=[(X_te_s, y_te)], verbose=False)
pred_stack = model_stack.predict(X_te_s)

print(f"\n  LED Savings prediction (% savings):")
print(f"  {'Metric':<25s} {'Without BL EUI':>14s} {'With BL EUI':>14s} {'Delta':>10s}")
mae_no = mean_absolute_error(y_te, pred_no_stack)
mae_yes = mean_absolute_error(y_te, pred_stack)
r2_no = r2_score(y_te, pred_no_stack)
r2_yes = r2_score(y_te, pred_stack)
print(f"  {'MAE':<25s} {mae_no:>14.4f} {mae_yes:>14.4f} {mae_yes-mae_no:>+10.4f}")
print(f"  {'R²':<25s} {r2_no:>14.4f} {r2_yes:>14.4f} {r2_yes-r2_no:>+10.4f}")

print(f"\n  Per building-type MAE:")
for btype in sorted(set(bt_te)):
    mask = bt_te == btype
    if mask.sum() < 10:
        continue
    mae_b = mean_absolute_error(y_te[mask], pred_no_stack[mask])
    mae_s = mean_absolute_error(y_te[mask], pred_stack[mask])
    n = mask.sum()
    print(f"    {btype:30s}  Without={mae_b:.4f}%  With={mae_s:.4f}%  Delta={mae_s-mae_b:+.4f}%  (n={n:,})")

# Feature importance comparison
print(f"\n  Feature importance (with stacked baseline EUI, top 10):")
importances_s = dict(zip(FEATURE_COLS_STACKED, model_stack.feature_importances_))
for col, imp in sorted(importances_s.items(), key=lambda x: -x[1])[:10]:
    marker = " ← STACKED" if col == 'predicted_baseline_eui' else ""
    bar = "#" * int(imp * 100)
    print(f"    {col:60s}  {imp:.4f}  {bar}{marker}")

# Step 3: Test on additional upgrades
print(f"\n── Step 3: Stacking test across multiple upgrades ──")
print(f"  {'Upgrade':<55s} {'MAE (base)':>10s} {'MAE (stack)':>11s} {'R² (base)':>10s} {'R² (stack)':>11s}")

for uid in SAMPLE_UPGRADES:
    df = load_upgrade(uid)
    applicable = df[df['applicability'] == True].copy()
    applicable['predicted_baseline_eui'] = applicable['bldg_id'].map(oof_lookup)
    applicable = applicable.dropna(subset=['predicted_baseline_eui']).reset_index(drop=True)

    X_b, _ = encode_features(applicable, FEATURE_COLS)
    X_s, _ = encode_features(applicable, FEATURE_COLS_STACKED)
    y_u = applicable['pct_savings'].values

    Xtr_b, Xte_b, Xtr_s, Xte_s, ytr, yte = train_test_split(
        X_b, X_s, y_u, test_size=0.2, random_state=42
    )

    m_b = xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
    m_b.fit(Xtr_b, ytr, eval_set=[(Xte_b, yte)], verbose=False)
    p_b = m_b.predict(Xte_b)

    m_s = xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
    m_s.fit(Xtr_s, ytr, eval_set=[(Xte_s, yte)], verbose=False)
    p_s = m_s.predict(Xte_s)

    name = upgrades[str(uid)][:50]
    print(f"  {uid:2d}: {name:50s} {mean_absolute_error(yte, p_b):>10.4f} {mean_absolute_error(yte, p_s):>11.4f} {r2_score(yte, p_b):>10.4f} {r2_score(yte, p_s):>11.4f}")

print()

# ── 8. Multi-measure model (Option 3 validation) ───────────────────────────
print("\n" + "=" * 80)
print("MULTI-MEASURE MODEL TEST (Option 3 validation)")
print("=" * 80)
print("Loading upgrades 1, 43, 48, 49, 55 into one training set...")

frames = []
for uid in SAMPLE_UPGRADES:
    df = load_upgrade(uid)
    applicable = df[df['applicability'] == True].copy()
    applicable['upgrade_id'] = uid
    frames.append(applicable)

multi = pd.concat(frames, ignore_index=True)
print(f"Combined applicable rows: {len(multi):,}")

multi_feature_cols = FEATURE_COLS + ['upgrade_id']
X_multi_enc, _ = encode_features(multi, multi_feature_cols)
y_multi = multi['pct_savings'].values
w_multi = multi['weight'].values

X_train_m, X_test_m, y_train_m, y_test_m, w_train_m, w_test_m = train_test_split(
    X_multi_enc, y_multi, w_multi, test_size=0.2, random_state=42
)

# Test both weighted and unweighted for multi-measure
model_multi_uw = xgb.XGBRegressor(n_estimators=300, max_depth=8, learning_rate=0.1, random_state=42, n_jobs=-1)
model_multi_uw.fit(X_train_m, y_train_m, eval_set=[(X_test_m, y_test_m)], verbose=False)
pred_multi_uw = model_multi_uw.predict(X_test_m)

model_multi_w = xgb.XGBRegressor(n_estimators=300, max_depth=8, learning_rate=0.1, random_state=42, n_jobs=-1)
model_multi_w.fit(X_train_m, y_train_m, sample_weight=w_train_m, eval_set=[(X_test_m, y_test_m)], verbose=False)
pred_multi_w = model_multi_w.predict(X_test_m)

print(f"\nMulti-measure model (% savings):")
print(f"  {'Metric':<25s} {'Unweighted':>12s} {'Weighted':>12s}")
print(f"  {'MAE':<25s} {mean_absolute_error(y_test_m, pred_multi_uw):>12.2f} {mean_absolute_error(y_test_m, pred_multi_w):>12.2f}")
print(f"  {'R²':<25s} {r2_score(y_test_m, pred_multi_uw):>12.4f} {r2_score(y_test_m, pred_multi_w):>12.4f}")

# Per-measure accuracy (unweighted model)
print(f"\nPer-measure accuracy (unweighted model):")
# Store raw upgrade_ids before encoding
multi_upgrade_ids_raw = multi['upgrade_id'].values
test_m_indices = X_test_m.index
test_multi_df = pd.DataFrame({
    'actual': y_test_m,
    'predicted': pred_multi_uw,
    'upgrade_id_raw': [multi_upgrade_ids_raw[i] for i in test_m_indices],
})

for uid in SAMPLE_UPGRADES:
    mask = test_multi_df['upgrade_id_raw'] == uid
    if mask.sum() > 0:
        mae_sub = mean_absolute_error(test_multi_df.loc[mask, 'actual'], test_multi_df.loc[mask, 'predicted'])
        r2_sub = r2_score(test_multi_df.loc[mask, 'actual'], test_multi_df.loc[mask, 'predicted'])
        print(f"  Upgrade {uid:2d} ({upgrades[str(uid)][:50]:50s}): MAE={mae_sub:.2f}%, R²={r2_sub:.4f}, n={mask.sum():,}")

print(f"\nFeature importance (multi-measure unweighted, top 15):")
importances_m = dict(zip(multi_feature_cols, model_multi_uw.feature_importances_))
for col, imp in sorted(importances_m.items(), key=lambda x: -x[1])[:15]:
    bar = "#" * int(imp * 100)
    print(f"  {col:60s}  {imp:.4f}  {bar}")

# ── 9. Compare targets: post-upgrade EUI vs % savings ───────────────────────
print("\n" + "=" * 80)
print("TARGET COMPARISON: Post-upgrade EUI vs % Savings")
print("=" * 80)

# Post-upgrade EUI model
X_eui_enc, _ = encode_features(multi, multi_feature_cols)
y_eui = multi[EUI_COL].values

X_train_e, X_test_e, y_train_e, y_test_e = train_test_split(X_eui_enc, y_eui, test_size=0.2, random_state=42)

model_eui = xgb.XGBRegressor(n_estimators=300, max_depth=8, learning_rate=0.1, random_state=42, n_jobs=-1)
model_eui.fit(X_train_e, y_train_e, eval_set=[(X_test_e, y_test_e)], verbose=False)
pred_eui = model_eui.predict(X_test_e)

print(f"\n  {'Target':<30s} {'MAE':>10s} {'R²':>10s} {'Mean Actual':>12s}")
print(f"  {'Post-upgrade EUI (kWh/ft2)':<30s} {mean_absolute_error(y_test_e, pred_eui):>10.2f} {r2_score(y_test_e, pred_eui):>10.4f} {y_test_e.mean():>12.2f}")
print(f"  {'% Savings':<30s} {mean_absolute_error(y_test_m, pred_multi_uw):>10.2f} {r2_score(y_test_m, pred_multi_uw):>10.4f} {y_test_m.mean():>12.2f}")

# ── 10. Summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("ANALYSIS COMPLETE - KEY FINDINGS")
print("=" * 80)
print("""
Review the results above to determine:
1. Weighted vs unweighted: Which performs better for per-building prediction?
2. Multi-measure model: Does a single model with upgrade_id as feature work well?
3. Post-upgrade EUI vs % savings: Which target gives better predictive accuracy?
4. Feature importance: Which features matter most for savings prediction?
5. Per-measure accuracy: Does accuracy vary significantly across measure types?
""")
