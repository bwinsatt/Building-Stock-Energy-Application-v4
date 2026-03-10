"""Tests for the runtime imputation service."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
import joblib
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder

from app.inference.imputation_service import ImputationService


@pytest.fixture
def mock_imputation_models(tmp_path):
    """Create minimal mock imputation models for testing."""
    model_dir = tmp_path / "Imputation"
    model_dir.mkdir()

    # Create a simple model for heating_fuel
    X = np.array([[0, 0, 0, 50000, 3, 0]] * 50 + [[1, 1, 1, 20000, 1, 1]] * 50)
    y = np.array(["NaturalGas"] * 50 + ["Electricity"] * 50)

    feature_cols = [
        "in.comstock_building_type_group",
        "in.as_simulated_ashrae_iecc_climate_zone_2006",
        "in.vintage",
        "in.sqft..ft2",
        "in.number_stories",
        "in.state",
    ]

    target_enc = LabelEncoder()
    y_enc = target_enc.fit_transform(y)

    model = XGBClassifier(n_estimators=10, random_state=42, eval_metric="mlogloss")
    model.fit(X, y_enc)

    # Save with empty feature encoders (inputs are already numeric in test)
    bundle = {
        "model": model,
        "feature_encoders": {},
        "target_encoder": target_enc,
        "input_columns": feature_cols,
        "feature_names": ["building_type", "climate_zone", "vintage", "sqft", "num_stories", "state"],
    }
    joblib.dump(bundle, str(model_dir / "impute_heating_fuel.pkl"))

    return str(model_dir)


class TestImputationService:
    def test_loads_models(self, mock_imputation_models):
        svc = ImputationService(mock_imputation_models)
        svc.load()
        assert "heating_fuel" in svc.models

    def test_predicts_with_confidence(self, mock_imputation_models):
        svc = ImputationService(mock_imputation_models)
        svc.load()

        known_fields = {
            "building_type": "Office",
            "climate_zone": "4A",
            "year_built": 1985,
            "sqft": 50000,
            "num_stories": 3,
            "state": "NY",
        }

        results = svc.predict(known_fields, fields_to_predict=["heating_fuel"])
        assert "heating_fuel" in results
        assert "value" in results["heating_fuel"]
        assert "confidence" in results["heating_fuel"]
        assert results["heating_fuel"]["source"] == "imputed"
        assert 0 <= results["heating_fuel"]["confidence"] <= 1.0

    def test_skips_fields_without_models(self, mock_imputation_models):
        svc = ImputationService(mock_imputation_models)
        svc.load()

        known_fields = {
            "building_type": "Office",
            "climate_zone": "4A",
            "sqft": 50000,
            "num_stories": 3,
            "state": "NY",
        }

        results = svc.predict(known_fields, fields_to_predict=["wall_construction"])
        # No model for wall_construction in our mock, should not error
        assert "wall_construction" not in results or results["wall_construction"]["value"] is None


def test_map_known_to_input_state_column():
    """State should map to 'in.state', not 'in.state_abbreviation'."""
    service = ImputationService.__new__(ImputationService)
    input_columns = [
        "in.comstock_building_type_group",
        "in.state",
    ]
    known = {"building_type": "Office", "state": "CA"}
    result = service._map_known_to_input(known, input_columns)
    assert result[1] == "CA", f"Expected 'CA', got {result[1]}"
