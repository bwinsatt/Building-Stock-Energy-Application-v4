"""Runtime imputation service that predicts missing building characteristics."""
from __future__ import annotations

import logging
import os

import joblib
import numpy as np

from app.services.preprocessor import year_to_vintage

logger = logging.getLogger(__name__)


class ImputationService:
    """Loads pre-trained imputation models and predicts missing fields."""

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.models: dict[str, dict] = {}

    def load(self) -> None:
        """Load all imputation models from model_dir."""
        if not os.path.isdir(self.model_dir):
            logger.warning("Imputation model dir not found: %s", self.model_dir)
            return

        for filename in os.listdir(self.model_dir):
            if filename.startswith("impute_") and filename.endswith(".pkl"):
                field_name = filename[len("impute_"):-len(".pkl")]
                path = os.path.join(self.model_dir, filename)
                try:
                    bundle = joblib.load(path)
                    self.models[field_name] = bundle
                    logger.info("Loaded imputation model: %s", field_name)
                except Exception:
                    logger.exception("Failed to load imputation model: %s", path)

        logger.info("Loaded %d imputation models", len(self.models))

    def predict(
        self,
        known_fields: dict,
        fields_to_predict: list[str] | None = None,
    ) -> dict[str, dict]:
        """Predict missing field values with confidence.

        Args:
            known_fields: Dict with keys like building_type, climate_zone,
                year_built, sqft, num_stories, state.
            fields_to_predict: Which fields to impute. If None, predicts all
                fields that have models loaded.

        Returns:
            Dict of {field_name: {value, source, confidence}}.
        """
        if fields_to_predict is None:
            fields_to_predict = list(self.models.keys())

        results = {}

        for field in fields_to_predict:
            if field not in self.models:
                results[field] = {"value": None, "source": None, "confidence": None}
                continue

            bundle = self.models[field]
            model = bundle["model"]
            feature_encoders = bundle["feature_encoders"]
            target_encoder = bundle["target_encoder"]
            input_columns = bundle["input_columns"]

            try:
                # Build input feature vector
                raw_values = self._map_known_to_input(known_fields, input_columns)
                encoded = self._encode_features(raw_values, input_columns, feature_encoders)

                X = np.array([encoded])
                proba = model.predict_proba(X)
                pred_idx = np.argmax(proba[0])
                confidence = float(proba[0][pred_idx])
                predicted_value = target_encoder.inverse_transform([pred_idx])[0]

                results[field] = {
                    "value": predicted_value,
                    "source": "imputed",
                    "confidence": round(confidence, 3),
                }
            except Exception:
                logger.exception("Imputation failed for field: %s", field)
                results[field] = {"value": None, "source": None, "confidence": None}

        return results

    def _map_known_to_input(
        self, known_fields: dict, input_columns: list[str]
    ) -> list:
        """Map user-friendly known_fields to the model's input column order."""
        key_to_col = {
            "building_type": "in.comstock_building_type_group",
            "climate_zone": "in.as_simulated_ashrae_iecc_climate_zone_2006",
            "year_built": "in.vintage",
            "sqft": "in.sqft..ft2",
            "num_stories": "in.number_stories",
            "state": "in.state",
        }
        col_to_key = {v: k for k, v in key_to_col.items()}

        values = []
        for col in input_columns:
            key = col_to_key.get(col)
            if key is None:
                values.append(0)
                continue
            val = known_fields.get(key)
            # Convert year_built to vintage string
            if key == "year_built" and isinstance(val, (int, float)):
                val = year_to_vintage(int(val))
            elif key == "year_built" and val is None:
                val = "1980-1989"  # Default vintage
            values.append(val)
        return values

    def _encode_features(
        self,
        raw_values: list,
        input_columns: list[str],
        feature_encoders: dict,
    ) -> list:
        """Encode categorical values using the saved label encoders."""
        encoded = []
        for col, val in zip(input_columns, raw_values):
            if col in feature_encoders:
                le = feature_encoders[col]
                val_str = str(val)
                if val_str in le.classes_:
                    encoded.append(le.transform([val_str])[0])
                else:
                    # Unknown category: use 0 (most common)
                    encoded.append(0)
            else:
                encoded.append(val if isinstance(val, (int, float)) else 0)
        return encoded
