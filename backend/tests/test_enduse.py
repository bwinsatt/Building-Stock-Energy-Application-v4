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
