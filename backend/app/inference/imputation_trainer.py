"""
Train XGBoost classifiers for imputing missing building characteristics.

Usage:
    python -m app.inference.imputation_trainer \
        --comstock-path ../../ComStock/raw_data/comstock.parquet \
        --resstock-path ../../ResStock/raw_data/resstock.parquet \
        --output-dir ../../XGB_Models/Imputation

Each model predicts one target field given:
    building_type, climate_zone, year_built (vintage), sqft, num_stories, state
"""
from __future__ import annotations

import argparse
import json
import os
import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

# Target fields to train imputation models for
TARGET_FIELDS_COMSTOCK = {
    "heating_fuel": "in.heating_fuel",
    "dhw_fuel": "in.service_water_heating_fuel",
    "hvac_system_type": "in.hvac_system_type",
    "wall_construction": "in.wall_construction_type",
    "window_type": "in.window_type",
    "window_to_wall_ratio": "in.window_to_wall_ratio_category",
    "lighting_type": "in.interior_lighting_generation",
}

# Input feature columns used for prediction
INPUT_FEATURES_COMSTOCK = [
    "in.comstock_building_type_group",
    "in.as_simulated_ashrae_iecc_climate_zone_2006",
    "in.vintage",
    "in.sqft..ft2",
    "in.number_stories",
    "in.state",
]

# Friendly names for features (used in model metadata)
FEATURE_NAMES = [
    "building_type",
    "climate_zone",
    "vintage",
    "sqft",
    "num_stories",
    "state",
]


def train_imputation_models(
    data_path: str,
    output_dir: str,
    dataset: str = "comstock",
) -> dict[str, str]:
    """Train and save imputation models.

    Args:
        data_path: Path to raw parquet data file.
        output_dir: Directory to save trained models.
        dataset: 'comstock' or 'resstock'.

    Returns:
        Dict of {field_name: model_path} for successfully trained models.
    """
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Loading data from %s", data_path)
    df = pd.read_parquet(data_path)

    target_fields = TARGET_FIELDS_COMSTOCK  # Expand for resstock later
    input_features = INPUT_FEATURES_COMSTOCK

    # Check which columns actually exist
    available_inputs = [c for c in input_features if c in df.columns]
    if len(available_inputs) < len(input_features):
        missing = set(input_features) - set(available_inputs)
        logger.warning("Missing input columns: %s", missing)

    trained = {}
    metadata = {}

    for field_name, col_name in target_fields.items():
        if col_name not in df.columns:
            logger.warning("Target column %s not found, skipping %s", col_name, field_name)
            continue

        logger.info("Training imputation model for: %s (%s)", field_name, col_name)

        # Prepare data: drop rows where target or any input is missing
        subset = df[available_inputs + [col_name]].dropna()
        if len(subset) < 100:
            logger.warning("Too few samples for %s (%d), skipping", field_name, len(subset))
            continue

        X = subset[available_inputs].copy()
        y = subset[col_name].copy()

        # Encode categorical features
        encoders = {}
        for col in X.columns:
            if X[col].dtype == object:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                encoders[col] = le

        # Encode target
        target_encoder = LabelEncoder()
        y_encoded = target_encoder.fit_transform(y.astype(str))

        # Train XGBoost
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric="mlogloss",
        )
        model.fit(X, y_encoded)

        # Save model + encoders + metadata
        model_path = os.path.join(output_dir, f"impute_{field_name}.pkl")
        joblib.dump({
            "model": model,
            "feature_encoders": encoders,
            "target_encoder": target_encoder,
            "input_columns": available_inputs,
            "feature_names": FEATURE_NAMES[:len(available_inputs)],
        }, model_path)

        trained[field_name] = model_path
        metadata[field_name] = {
            "n_samples": len(subset),
            "n_classes": len(target_encoder.classes_),
            "classes": target_encoder.classes_.tolist(),
        }
        logger.info("  Saved %s (%d samples, %d classes)",
                     model_path, len(subset), len(target_encoder.classes_))

    # Save metadata summary
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return trained


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Train imputation models")
    parser.add_argument("--comstock-path", required=True, help="Path to ComStock parquet")
    parser.add_argument("--output-dir", default="../../XGB_Models/Imputation")
    args = parser.parse_args()

    train_imputation_models(args.comstock_path, args.output_dir, dataset="comstock")
