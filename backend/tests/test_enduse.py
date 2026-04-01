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


from app.services.assessment import _compute_enduse_breakdown


def test_compute_enduse_breakdown_sums_to_100():
    """Grouped percentages must sum to ~100%."""
    raw_enduse_eui = {
        "heating": 3.0,
        "cooling": 2.0,
        "interior_lighting": 1.5,
        "exterior_lighting": 0.5,
        "fans": 1.0,
        "pumps": 0.2,
        "interior_equipment": 2.0,
        "water_systems": 0.8,
        "refrigeration": 0.5,
        "heat_recovery": 0.1,
        "heat_rejection": 0.05,
    }
    total_baseline_kbtu = 40.0

    result = _compute_enduse_breakdown(raw_enduse_eui, total_baseline_kbtu, "comstock")

    assert result is not None
    total_pct = sum(result.values())
    assert abs(total_pct - total_baseline_kbtu) < 0.1, f"Sum is {total_pct}, expected ~{total_baseline_kbtu}"


def test_compute_enduse_breakdown_returns_none_when_empty():
    """Returns None when no end-use predictions available."""
    result = _compute_enduse_breakdown({}, 40.0, "comstock")
    assert result is None


def test_compute_enduse_breakdown_scales_to_baseline():
    """kBtu/sf values scale proportionally to baseline total."""
    raw = {"heating": 6.0, "cooling": 4.0}
    total_baseline_kbtu = 50.0
    result = _compute_enduse_breakdown(raw, total_baseline_kbtu, "comstock")

    # heating is 60% of raw total, so 60% of 50 = 30 kBtu/sf
    assert result is not None
    heating_kbtu = result.get("Heating", 0)
    # Heating group only contains "heating" for comstock
    assert abs(heating_kbtu - 30.0) < 0.1
