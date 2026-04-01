import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def test_enduse_grouping_loads():
    """Config file is valid JSON and has expected structure."""
    path = DATA_DIR / "enduse_grouping.json"
    with open(path) as f:
        cfg = json.load(f)

    assert "display_categories" in cfg
    assert "display_colors" in cfg
    for ds in ("comstock", "resstock"):
        assert "trained_enduses" in cfg[ds]
        assert "grouping" in cfg[ds]


def test_grouping_covers_all_trained_enduses():
    """Every trained end use appears in exactly one display category."""
    path = DATA_DIR / "enduse_grouping.json"
    with open(path) as f:
        cfg = json.load(f)

    for ds in ("comstock", "resstock"):
        trained = set(cfg[ds]["trained_enduses"])
        all_grouped = []
        for enduses in cfg[ds]["grouping"].values():
            all_grouped.extend(enduses)
        assert len(all_grouped) == len(set(all_grouped)), f"{ds}: duplicate end use in grouping"
        assert set(all_grouped) == trained, f"{ds}: grouped {set(all_grouped)} != trained {trained}"


def test_display_categories_match_grouping_keys():
    """Grouping keys match the display_categories list for both datasets."""
    path = DATA_DIR / "enduse_grouping.json"
    with open(path) as f:
        cfg = json.load(f)

    expected = set(cfg["display_categories"])
    for ds in ("comstock", "resstock"):
        keys = set(cfg[ds]["grouping"].keys())
        assert keys == expected, f"{ds}: grouping keys {keys} != display {expected}"


def test_display_colors_match_categories():
    """Every display category has a color."""
    path = DATA_DIR / "enduse_grouping.json"
    with open(path) as f:
        cfg = json.load(f)

    for cat in cfg["display_categories"]:
        assert cat in cfg["display_colors"], f"Missing color for {cat}"


import numpy as np
from unittest.mock import patch, MagicMock
from app.inference.model_manager import ModelManager


def test_model_manager_indexes_enduse_directory(tmp_path):
    """ModelManager discovers end-use model files in ComStock_EndUse/ dir."""
    # Create mock model files
    enduse_dir = tmp_path / "ComStock_EndUse"
    enduse_dir.mkdir()
    for prefix in ("XGB", "LGBM", "CB"):
        for eu in ("heating", "cooling"):
            stem = f"{prefix}_enduse_{eu}"
            (enduse_dir / f"{stem}.pkl").write_bytes(b"mock")
            (enduse_dir / f"{stem}_encoders.pkl").write_bytes(b"mock")
            (enduse_dir / f"{stem}_meta.json").write_text('{"feature_columns": []}')

    mm = ModelManager(model_dir=str(tmp_path))
    count = mm.index_all()

    assert count >= 6  # 3 prefixes x 2 end uses
    assert "heating" in mm._index["comstock"]["enduse"]
    assert "cooling" in mm._index["comstock"]["enduse"]
    assert "XGB" in mm._index["comstock"]["enduse"]["heating"]


def test_predict_enduse_returns_shares(tmp_path):
    """predict_enduse returns dict of enduse_name -> predicted EUI."""
    mm = ModelManager(model_dir=str(tmp_path))

    # Mock loaded enduse models
    mock_bundle = {
        "model": MagicMock(predict=MagicMock(return_value=np.array([5.0]))),
        "encoders": {},
        "meta": {"feature_columns": ["in.sqft..ft2"], "log_target": False},
    }
    mm._loaded["comstock"]["enduse"] = {
        "heating": {"XGB": mock_bundle},
        "cooling": {"XGB": mock_bundle},
    }
    mm._dataset_initialised["comstock"] = True

    result = mm.predict_enduse({"in.sqft..ft2": 50000}, "comstock")

    assert "heating" in result
    assert "cooling" in result
    assert result["heating"] == 5.0
    assert result["cooling"] == 5.0
