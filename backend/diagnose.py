"""
Cross-machine diagnostic script.
Run on BOTH machines and compare output:
    cd backend && python diagnose.py > diag_output.txt
"""
import sys, os, json, hashlib, platform

sys.path.insert(0, ".")

print("=" * 60)
print("SECTION 1: ENVIRONMENT")
print("=" * 60)
import xgboost, numpy, pandas, sklearn, joblib

print(f"Python:       {sys.version}")
print(f"Platform:     {platform.platform()}")
print(f"Machine:      {platform.machine()}")
print(f"XGBoost:      {xgboost.__version__}")
print(f"NumPy:        {numpy.__version__}")
print(f"Pandas:       {pandas.__version__}")
print(f"Scikit-learn: {sklearn.__version__}")
print(f"Joblib:       {joblib.__version__}")

print("\n" + "=" * 60)
print("SECTION 2: MODEL FILE CHECKSUMS")
print("=" * 60)
model_base = os.path.abspath(os.path.join(os.getcwd(), "..", "XGB_Models"))
print(f"Model dir: {model_base}")
print(f"Exists: {os.path.exists(model_base)}")

for subdir in sorted(os.listdir(model_base)):
    subdir_path = os.path.join(model_base, subdir)
    if not os.path.isdir(subdir_path):
        continue
    files = sorted(os.listdir(subdir_path))
    # Hash all files in directory combined
    combined = hashlib.md5()
    for f in files:
        combined.update(open(os.path.join(subdir_path, f), "rb").read())
    print(f"  {subdir}/: {len(files)} files, combined_md5={combined.hexdigest()}")

# Specific model files for upgrade 41 (worst offender)
print("\nKey individual model checksums:")
upgrade_dir = os.path.join(model_base, "ComStock_Upgrades_2025_R3")
for uid in [0, 1, 18, 41, 47]:
    for suffix in ["electricity.pkl", "natural_gas.pkl", "electricity_encoders.pkl",
                   "natural_gas_encoders.pkl", "electricity_meta.json", "natural_gas_meta.json"]:
        fname = f"XGB_upgrade{uid}_{suffix}"
        fpath = os.path.join(upgrade_dir, fname)
        if os.path.exists(fpath):
            h = hashlib.md5(open(fpath, "rb").read()).hexdigest()
            print(f"  {fname}: {h}")

print("\n" + "=" * 60)
print("SECTION 3: DATA FILE CHECKSUMS")
print("=" * 60)
data_dir = os.path.join(os.getcwd(), "app", "data")
for fname in sorted(os.listdir(data_dir)):
    fpath = os.path.join(data_dir, fname)
    if os.path.isfile(fpath):
        h = hashlib.md5(open(fpath, "rb").read()).hexdigest()
        print(f"  {fname}: {h}")

print("\n" + "=" * 60)
print("SECTION 4: PREPROCESSING OUTPUT")
print("=" * 60)
from app.schemas.request import BuildingInput
from app.services.preprocessor import preprocess

building = BuildingInput(
    building_type="Office", sqft=500000, num_stories=39,
    zipcode="10019", year_built=1985,
)
features, imputed, dataset, climate_zone, state = preprocess(building)
print(f"Dataset: {dataset}, Climate: {climate_zone}, State: {state}")
print(f"Features ({len(features)} keys):")
for k in sorted(features.keys()):
    print(f"  {k}: {features[k]!r}")
print(f"Imputed fields:")
for k, v in sorted(imputed.items()):
    print(f"  {k}: {v['value']!r} (source={v['source']})")

print("\n" + "=" * 60)
print("SECTION 5: ENCODED FEATURES (upgrade 41 electricity)")
print("=" * 60)
from app.inference.model_manager import ModelManager, encode_features
import numpy as np

mm = ModelManager(model_base)
mm.index_all()
mm._ensure_dataset_core("comstock")

u41_bundle = mm._get_upgrade_bundle("comstock", 41, "electricity")
u41_cols = u41_bundle["meta"]["feature_columns"]
u41_enc = u41_bundle["encoders"]

row = {col: features.get(col, np.nan) for col in u41_cols}
df = pandas.DataFrame([row])
df_enc, _ = encode_features(df, u41_cols, encoders=u41_enc)

for col in u41_cols:
    raw = features.get(col, "MISSING")
    enc_val = df_enc[col].iloc[0]
    dtype = df_enc[col].dtype
    # For categoricals, also show the integer code
    if hasattr(df_enc[col], "cat"):
        code = df_enc[col].cat.codes.iloc[0]
        cats = list(df_enc[col].cat.categories)
        print(f"  {col}: raw={raw!r} -> val={enc_val} code={code} dtype={dtype} n_cats={len(cats)}")
    else:
        print(f"  {col}: raw={raw!r} -> val={enc_val} dtype={dtype}")

print("\n" + "=" * 60)
print("SECTION 6: RAW PREDICTIONS (per-fuel)")
print("=" * 60)

enc_cache = {}
baseline = mm.predict_baseline(features, dataset, enc_cache)
print(f"Baseline EUI (kWh/sf):")
for fuel in sorted(baseline.keys()):
    print(f"  {fuel}: {baseline[fuel]:.10f}")
total_bl = sum(v * 3.412 for v in baseline.values())
print(f"  TOTAL (kBtu/sf): {total_bl:.10f}")

for uid in [41, 18, 47, 11, 1]:
    try:
        delta = mm.predict_delta(features, uid, dataset, enc_cache)
        print(f"\nUpgrade {uid} delta (kWh/sf):")
        for fuel in sorted(delta.keys()):
            print(f"  {fuel}: {delta[fuel]:.10f}")
        savings = {fuel: max(0, d) for fuel, d in delta.items()}
        total_sav = sum(v * 3.412 for v in savings.values())
        pct = total_sav / total_bl * 100 if total_bl > 0 else 0
        print(f"  savings_pct: {pct:.10f}")
    except Exception as e:
        print(f"\nUpgrade {uid}: ERROR - {e}")

print("\n" + "=" * 60)
print("SECTION 7: XGBOOST INTERNAL MODEL CHECK")
print("=" * 60)
# Check tree count and config for upgrade 41 electricity
booster = u41_bundle["model"].get_booster()
config = json.loads(booster.save_config())
print(f"XGB version in model: {config.get('version')}")
print(f"Num trees: {booster.num_boosted_rounds()}")
learner = config.get("learner", {})
params = learner.get("learner_model_param", {})
print(f"base_score: {params.get('base_score')}")
print(f"num_feature: {params.get('num_feature')}")
gp = learner.get("gradient_booster", {}).get("gbtree_model_param", {})
print(f"num_trees: {gp.get('num_trees')}")

# Dump first tree split info as fingerprint
trees = booster.get_dump(dump_format="json")
first_tree = json.loads(trees[0])
def get_splits(node, depth=0):
    if "split" in node and depth < 3:
        print(f"  {'  '*depth}split: {node['split']} < {node.get('split_condition', '?')}")
        if "children" in node:
            for child in node["children"]:
                get_splits(child, depth+1)
    elif "leaf" in node and depth < 3:
        print(f"  {'  '*depth}leaf: {node['leaf']:.10f}")

print(f"\nFirst tree structure (depth<=2):")
get_splits(first_tree)

print("\nDONE")
