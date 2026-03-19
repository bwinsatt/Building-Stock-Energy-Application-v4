"""Tests for ensemble blending in model_manager."""
import pytest
import numpy as np


def test_blend_predictions_simple_average():
    """Blend should average predictions from available models."""
    from app.inference.model_manager import _blend_predictions

    preds = {'xgb': 10.0, 'lgbm': 12.0, 'catboost': 11.0}
    result = _blend_predictions(preds)
    assert result == pytest.approx(11.0)


def test_blend_predictions_missing_model():
    """Blend should work with fewer than 3 models (graceful degradation)."""
    from app.inference.model_manager import _blend_predictions

    preds = {'xgb': 10.0}
    result = _blend_predictions(preds)
    assert result == pytest.approx(10.0)


def test_blend_predictions_empty_raises():
    """Blend should raise on empty predictions."""
    from app.inference.model_manager import _blend_predictions

    with pytest.raises(ValueError, match="No predictions"):
        _blend_predictions({})
