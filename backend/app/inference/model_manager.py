"""
Model Manager — indexes all XGBoost models at startup but loads them lazily.

Models are organised in nested dicts keyed by dataset ('comstock' / 'resstock'),
model category ('baseline', 'sizing', 'rates', 'upgrades'), and target name.

Loading strategy:
  - Startup: scan directories and build a path index (no deserialization).
  - First request for a dataset: eagerly load baseline + sizing + rates (~11
    small models).
  - Upgrade models: loaded on-demand with an LRU cache to cap memory usage.
"""

import json
import logging
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default model directory (relative to *this* file → backend/app/inference/)
# Override with the MODEL_DIR environment variable.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_DEFAULT_MODEL_DIR = _THIS_DIR.parent.parent.parent / "XGB_Models"

# Known sub-directories and which dataset / category they map to.
_DIR_MAP = {
    "ComStock_Upgrades_2025_R3": ("comstock", "upgrades"),
    "ResStock_Upgrades_2025_R1": ("resstock", "upgrades"),
    "ComStock_Sizing":           ("comstock", "sizing"),
    "ComStock_Rates":            ("comstock", "rates"),
    "ResStock_Sizing":           ("resstock", "sizing"),
    "ResStock_Rates":            ("resstock", "rates"),
}

# Regex patterns for model file naming conventions
_RE_UPGRADE = re.compile(r"^XGB_upgrade(\d+)_(.+)\.pkl$")
_RE_SIZING  = re.compile(r"^XGB_(.+)\.pkl$")
_RE_RATE    = re.compile(r"^XGB_rate_(.+)\.pkl$")

# Default max upgrade bundles kept in memory per dataset
_DEFAULT_LRU_CAP = 80


# ---------------------------------------------------------------------------
# encode_features  (copied from scripts/training_utils.py — kept in sync)
# ---------------------------------------------------------------------------

def encode_features(df, feature_cols, encoders=None):
    """Convert string/categorical columns to pandas Categorical for XGBoost."""
    df_enc = df[feature_cols].copy()
    if encoders is None:
        encoders = {}
        fit = True
    else:
        fit = False

    for col in feature_cols:
        # When applying saved encoders (inference), check encoders first:
        # a column may have been categorical during training even if the
        # current dtype is numeric (e.g. number_stories stored as int but
        # trained as categorical string).
        if not fit and col in encoders:
            enc = encoders[col]
            df_enc[col] = df_enc[col].astype(str)
            if isinstance(enc, list):
                categories = enc
                known = set(categories)
                df_enc[col] = df_enc[col].apply(
                    lambda x, _k=known, _c=categories: x if x in _k else _c[0]
                )
                df_enc[col] = pd.Categorical(
                    df_enc[col], categories=categories
                )
            else:
                # Legacy LabelEncoder from old models
                known = set(enc.classes_)
                df_enc[col] = df_enc[col].apply(
                    lambda x, _k=known, _e=enc: x if x in _k else _e.classes_[0]
                )
                df_enc[col] = enc.transform(df_enc[col])
        elif df_enc[col].dtype == "object" or str(df_enc[col].dtype) in (
            "large_string",
            "string",
        ):
            df_enc[col] = df_enc[col].astype(str)
            if fit:
                categories = sorted(df_enc[col].unique().tolist())
                encoders[col] = categories
                df_enc[col] = pd.Categorical(df_enc[col], categories=categories)
            else:
                # Column is string but not in encoders — treat as numeric
                df_enc[col] = pd.to_numeric(df_enc[col], errors="coerce").fillna(0)
        else:
            df_enc[col] = pd.to_numeric(df_enc[col], errors="coerce").fillna(0)

    return df_enc, encoders


# ---------------------------------------------------------------------------
# ModelManager
# ---------------------------------------------------------------------------

class ModelManager:
    """Indexes XGBoost models at startup; loads them lazily on first use."""

    def __init__(self, model_dir: Optional[str] = None, lru_cap: int = _DEFAULT_LRU_CAP):
        self.model_dir = Path(
            model_dir or os.environ.get("MODEL_DIR", str(_DEFAULT_MODEL_DIR))
        ).resolve()
        self._lru_cap = lru_cap

        # --- Path index (populated at startup, no deserialization) ---
        # dataset -> category -> key -> Path
        #   baseline/sizing/rates: key = fuel_or_target_name
        #   upgrades:              key = (upgrade_id, fuel_name)
        self._index: Dict[str, Dict[str, dict]] = {
            "comstock": {"baseline": {}, "sizing": {}, "rates": {}, "upgrades": {}},
            "resstock": {"baseline": {}, "sizing": {}, "rates": {}, "upgrades": {}},
        }

        # --- Loaded bundles (populated lazily) ---
        # baseline/sizing/rates: same structure as old self.models
        self._loaded: Dict[str, Dict[str, dict]] = {
            "comstock": {"baseline": {}, "sizing": {}, "rates": {}},
            "resstock": {"baseline": {}, "sizing": {}, "rates": {}},
        }

        # upgrades use a per-dataset LRU cache: (upgrade_id, fuel) -> bundle
        self._upgrade_cache: Dict[str, OrderedDict] = {
            "comstock": OrderedDict(),
            "resstock": OrderedDict(),
        }

        # Track which datasets have had their core models loaded
        self._dataset_initialised: Dict[str, bool] = {
            "comstock": False,
            "resstock": False,
        }

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Indexing (startup — fast, no deserialization)
    # ------------------------------------------------------------------

    def index_all(self) -> int:
        """Scan model directories and build a path index.

        Returns the total number of model bundles indexed.
        """
        total = 0
        for dir_name, (dataset, category) in _DIR_MAP.items():
            dir_path = self.model_dir / dir_name
            if not dir_path.is_dir():
                logger.warning("Model directory not found, skipping: %s", dir_path)
                continue
            indexed = self._index_directory(dir_path, dataset, category)
            total += indexed
            logger.info(
                "Indexed %d models from %s (%s/%s)", indexed, dir_name, dataset, category
            )
        logger.info("Total models indexed: %d", total)
        return total

    # Keep load_all as an alias so existing code doesn't break
    def load_all(self) -> int:
        """Alias for index_all — scans directories without loading."""
        return self.index_all()

    def _index_directory(self, dir_path: Path, dataset: str, category: str) -> int:
        """Scan *dir_path* for model .pkl files and record their paths."""
        indexed = 0
        for pkl_path in sorted(dir_path.glob("*.pkl")):
            name = pkl_path.name
            if name.endswith("_encoders.pkl"):
                continue

            if category == "upgrades":
                m = _RE_UPGRADE.match(name)
                if not m:
                    continue
                upgrade_id = int(m.group(1))
                fuel_name = m.group(2)
                if upgrade_id == 0:
                    self._index[dataset]["baseline"][fuel_name] = pkl_path
                else:
                    self._index[dataset]["upgrades"][(upgrade_id, fuel_name)] = pkl_path
                indexed += 1

            elif category == "sizing":
                m = _RE_SIZING.match(name)
                if not m:
                    continue
                self._index[dataset]["sizing"][m.group(1)] = pkl_path
                indexed += 1

            elif category == "rates":
                m = _RE_RATE.match(name)
                if not m:
                    continue
                self._index[dataset]["rates"][m.group(1)] = pkl_path
                indexed += 1

        return indexed

    # ------------------------------------------------------------------
    # Lazy loading helpers
    # ------------------------------------------------------------------

    def _ensure_dataset_core(self, dataset: str) -> None:
        """Load baseline + sizing + rates for *dataset* on first access."""
        if self._dataset_initialised[dataset]:
            return
        with self._lock:
            if self._dataset_initialised[dataset]:
                return  # double-check after acquiring lock
            for category in ("baseline", "sizing", "rates"):
                for key, pkl_path in self._index[dataset][category].items():
                    bundle = self._load_bundle(pkl_path)
                    if bundle:
                        self._loaded[dataset][category][key] = bundle
            count = sum(
                len(self._loaded[dataset][c]) for c in ("baseline", "sizing", "rates")
            )
            logger.info(
                "Loaded %d core models (baseline/sizing/rates) for %s", count, dataset
            )
            self._dataset_initialised[dataset] = True

    def _get_upgrade_bundle(self, dataset: str, upgrade_id: int, fuel: str) -> Optional[dict]:
        """Get an upgrade bundle, loading from disk if not cached."""
        cache = self._upgrade_cache[dataset]
        cache_key = (upgrade_id, fuel)

        # Fast path: already cached
        if cache_key in cache:
            cache.move_to_end(cache_key)
            return cache[cache_key]

        # Slow path: load from disk
        pkl_path = self._index[dataset]["upgrades"].get(cache_key)
        if pkl_path is None:
            return None

        bundle = self._load_bundle(pkl_path)
        if bundle is None:
            return None

        with self._lock:
            cache[cache_key] = bundle
            cache.move_to_end(cache_key)
            # Evict oldest if over cap
            while len(cache) > self._lru_cap:
                evicted_key, _ = cache.popitem(last=False)
                logger.debug("Evicted upgrade model %s/%s from cache", dataset, evicted_key)

        return bundle

    # -- generic bundle loader --

    @staticmethod
    def _load_bundle(pkl_path: Path) -> Optional[dict]:
        """Load model, encoders, and meta for a single model file.

        Expected companion files:
            {stem}_encoders.pkl
            {stem}_meta.json

        Returns a dict with keys 'model', 'encoders', 'meta', or None on
        failure.
        """
        stem = pkl_path.stem  # e.g. "XGB_upgrade0_electricity"
        parent = pkl_path.parent

        enc_path = parent / f"{stem}_encoders.pkl"
        meta_path = parent / f"{stem}_meta.json"

        if not enc_path.exists():
            logger.warning("Encoder file missing for %s, skipping", pkl_path.name)
            return None
        if not meta_path.exists():
            logger.warning("Meta file missing for %s, skipping", pkl_path.name)
            return None

        try:
            model = joblib.load(pkl_path)
            encoders = joblib.load(enc_path)
            with open(meta_path) as f:
                meta = json.load(f)
            return {"model": model, "encoders": encoders, "meta": meta}
        except Exception:
            logger.exception("Failed to load model bundle %s", pkl_path.name)
            return None

    # ------------------------------------------------------------------
    # Prediction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _predict_single(bundle: dict, features_dict: dict) -> float:
        """Run a single model on *features_dict* and return a scalar."""
        meta = bundle["meta"]
        feature_cols = meta["feature_columns"]
        log_target = meta.get("log_target", False)

        # Build single-row DataFrame
        row = {col: features_dict.get(col, np.nan) for col in feature_cols}
        df = pd.DataFrame([row])

        # Encode
        df_enc, _ = encode_features(df, feature_cols, encoders=bundle["encoders"])

        # Predict
        pred = bundle["model"].predict(df_enc)[0]

        # Inverse log1p if trained on log-transformed target
        if log_target:
            pred = float(np.expm1(pred))

        return float(pred)

    # ------------------------------------------------------------------
    # Public prediction methods
    # ------------------------------------------------------------------

    def predict_baseline(self, features_dict: dict, dataset: str) -> dict:
        """Run baseline (upgrade 0) EUI models.

        Returns dict of fuel -> predicted EUI (kWh/ft2).
        """
        dataset = dataset.lower()
        self._ensure_dataset_core(dataset)
        bundles = self._loaded[dataset]["baseline"]
        if not bundles:
            raise ValueError(
                f"No baseline models loaded for dataset '{dataset}'"
            )
        return {
            fuel: self._predict_single(bundle, features_dict)
            for fuel, bundle in bundles.items()
        }

    def predict_sizing(self, features_dict: dict, dataset: str) -> dict:
        """Run sizing models.

        Returns dict of target_name -> predicted value.
        """
        dataset = dataset.lower()
        self._ensure_dataset_core(dataset)
        bundles = self._loaded[dataset]["sizing"]
        if not bundles:
            raise ValueError(
                f"No sizing models loaded for dataset '{dataset}'"
            )
        return {
            target: self._predict_single(bundle, features_dict)
            for target, bundle in bundles.items()
        }

    def predict_rates(self, features_dict: dict, dataset: str) -> dict:
        """Run rate models.

        Returns dict of fuel -> predicted rate ($/kWh).
        """
        dataset = dataset.lower()
        self._ensure_dataset_core(dataset)
        bundles = self._loaded[dataset]["rates"]
        if not bundles:
            raise ValueError(
                f"No rate models loaded for dataset '{dataset}'"
            )
        return {
            fuel: self._predict_single(bundle, features_dict)
            for fuel, bundle in bundles.items()
        }

    def get_available_upgrades(self, dataset: str) -> list[int]:
        """Return sorted list of upgrade IDs that have trained models for *dataset*."""
        dataset = dataset.lower()
        # Derive from the index (no loading required)
        upgrade_ids = {uid for uid, _fuel in self._index[dataset]["upgrades"]}
        return sorted(upgrade_ids)

    def predict_delta(
        self, features_dict: dict, upgrade_id: int, dataset: str
    ) -> dict:
        """Run per-fuel delta/savings models for one upgrade.

        Returns dict of fuel -> predicted savings (kWh/ft2).
        Positive values mean the upgrade saves energy for that fuel.
        """
        dataset = dataset.lower()

        # Find all fuels for this upgrade from the index
        fuel_keys = [
            fuel for uid, fuel in self._index[dataset]["upgrades"]
            if uid == upgrade_id
        ]
        if not fuel_keys:
            raise ValueError(
                f"No models indexed for upgrade {upgrade_id} in dataset '{dataset}'"
            )

        results = {}
        for fuel in fuel_keys:
            bundle = self._get_upgrade_bundle(dataset, upgrade_id, fuel)
            if bundle is None:
                logger.warning(
                    "Failed to load upgrade %d/%s for %s", upgrade_id, fuel, dataset
                )
                continue
            results[fuel] = self._predict_single(bundle, features_dict)

        return results
