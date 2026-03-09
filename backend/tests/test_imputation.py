"""Tests for imputation model training and prediction."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
import joblib

from app.inference.imputation_trainer import train_imputation_models


@pytest.fixture
def synthetic_comstock_data(tmp_path):
    """Create a small synthetic dataset mimicking ComStock structure."""
    rng = np.random.default_rng(42)
    n = 500
    df = pd.DataFrame({
        "in.comstock_building_type_group": rng.choice(
            ["Office", "Education", "Mercantile"], n
        ),
        "in.as_simulated_ashrae_iecc_climate_zone_2006": rng.choice(
            ["3A", "4A", "5A"], n
        ),
        "in.vintage": rng.choice(
            ["1980-1989", "1990-1999", "2000-2004"], n
        ),
        "in.sqft..ft2": rng.uniform(5000, 100000, n),
        "in.number_stories": rng.choice([1, 2, 3, 5], n),
        "in.state_abbreviation": rng.choice(["NY", "CA", "TX"], n),
        "in.heating_fuel": rng.choice(["NaturalGas", "Electricity"], n),
        "in.service_water_heating_fuel": rng.choice(["NaturalGas", "Electricity"], n),
        "in.hvac_system_type": rng.choice(["PSZ-AC", "VAV_chiller_boiler"], n),
        "in.wall_construction_type": rng.choice(["Mass", "SteelFrame"], n),
        "in.window_type": rng.choice(
            ["Double, Clear, Metal", "Double, Low-E, Non-metal"], n
        ),
        "in.window_to_wall_ratio_category": rng.choice(["10-20%", "20-30%"], n),
        "in.interior_lighting_generation": rng.choice(["LED", "T8"], n),
    })
    path = tmp_path / "synthetic_comstock.parquet"
    df.to_parquet(path)
    return str(path)


class TestImputationTrainer:
    def test_trains_all_target_models(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        trained = train_imputation_models(
            synthetic_comstock_data, output_dir, dataset="comstock"
        )
        assert "heating_fuel" in trained
        assert "wall_construction" in trained
        assert len(trained) == 7  # All 7 target fields

    def test_saved_models_are_loadable(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        trained = train_imputation_models(
            synthetic_comstock_data, output_dir, dataset="comstock"
        )
        for field, path in trained.items():
            bundle = joblib.load(path)
            assert "model" in bundle
            assert "target_encoder" in bundle
            assert "feature_encoders" in bundle

    def test_model_predicts_with_probabilities(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        trained = train_imputation_models(
            synthetic_comstock_data, output_dir, dataset="comstock"
        )
        bundle = joblib.load(trained["heating_fuel"])
        model = bundle["model"]
        # Single sample prediction
        sample = np.array([[0, 1, 2, 50000, 3, 0]])
        proba = model.predict_proba(sample)
        assert proba.shape[1] == len(bundle["target_encoder"].classes_)
        assert abs(proba.sum() - 1.0) < 0.01

    def test_metadata_json_created(self, synthetic_comstock_data, tmp_path):
        output_dir = str(tmp_path / "models")
        train_imputation_models(synthetic_comstock_data, output_dir)
        import json
        with open(os.path.join(output_dir, "metadata.json")) as f:
            meta = json.load(f)
        assert "heating_fuel" in meta
        assert "n_classes" in meta["heating_fuel"]
