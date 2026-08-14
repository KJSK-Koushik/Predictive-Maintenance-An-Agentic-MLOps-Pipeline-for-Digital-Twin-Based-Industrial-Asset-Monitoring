"""Known-vector metric and contract tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from predictive_maintenance.modeling.metrics import (
    classification_metrics,
    engine_balanced_weights,
    final_cycle_mask,
    nasa_asymmetric_score,
    prediction_digest,
    regression_metrics,
)
from predictive_maintenance.modeling.models import (
    ModelingError,
    canonical_json_bytes,
)


def test_modeling_error_is_bounded_and_serializable() -> None:
    error = ModelingError("input.invalid", "x" * 2000)
    assert len(error.message) == 1000
    assert error.to_dict()["code"] == "input.invalid"
    with pytest.raises(ValueError, match="codes"):
        ModelingError("BAD", "message")


def test_canonical_json_rejects_non_finite() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}\n'
    with pytest.raises(ModelingError, match="finite JSON"):
        canonical_json_bytes({"bad": float("nan")})


def test_engine_balanced_weights_equalize_trajectory_totals() -> None:
    weights = engine_balanced_weights([1, 1, 1, 2])
    assert weights[:3].sum() == pytest.approx(1.0)
    assert weights[3:].sum() == pytest.approx(1.0)


def test_nasa_score_covers_early_late_and_zero() -> None:
    score = nasa_asymmetric_score(
        np.array([10.0, 10.0, 10.0]), np.array([0.0, 10.0, 20.0])
    )
    expected = np.expm1(10 / 13) + np.expm1(10 / 10)
    assert score == pytest.approx(expected)
    assert np.isfinite(nasa_asymmetric_score(np.array([0.0]), np.array([100_000.0])))


def test_regression_metrics_known_values_and_bands() -> None:
    keys = pd.DataFrame({"engine_id": [1, 1, 2], "cycle": [1, 2, 1]})
    metrics = regression_metrics(
        keys,
        np.array([120.0, 20.0, 50.0]),
        np.array([110.0, 20.0, 60.0]),
        clipped_count=2,
    )
    assert metrics["pooled_mae"] == pytest.approx(20 / 3)
    assert metrics["clipped_prediction_count"] == 2
    assert set(metrics["lifecycle_bands"]) == {
        "early_over_100",
        "middle_31_100",
        "near_0_30",
    }
    assert metrics["final_cycle"]["mae"] == pytest.approx(5.0)


def test_final_cycle_returns_one_row_per_engine() -> None:
    keys = pd.DataFrame({"engine_id": [1, 1, 2, 2], "cycle": [1, 2, 4, 5]})
    assert final_cycle_mask(keys).tolist() == [False, True, False, True]


def test_classification_metrics_known_confusion_and_threshold() -> None:
    keys = pd.DataFrame({"engine_id": [1, 1, 2, 2], "cycle": [1, 2, 1, 2]})
    metrics = classification_metrics(
        keys, np.array([0, 1, 0, 1]), np.array([0.1, 0.5, 0.9, 0.8])
    )
    assert metrics["confusion"] == {
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 0,
        "true_positive": 2,
    }
    assert metrics["recall"] == 1.0
    assert metrics["calibration"]["bins"]


def test_single_class_roc_is_explicitly_unavailable() -> None:
    keys = pd.DataFrame({"engine_id": [1, 2], "cycle": [1, 1]})
    metrics = classification_metrics(keys, np.array([1, 1]), np.array([0.8, 0.9]))
    assert metrics["pooled_roc_auc"] is None
    assert metrics["final_cycle"]["roc_auc"] is None


def test_invalid_classification_probabilities_fail() -> None:
    keys = pd.DataFrame({"engine_id": [1, 2], "cycle": [1, 1]})
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        classification_metrics(keys, np.array([0, 1]), np.array([-0.1, 1.1]))


def test_prediction_digest_binds_keys_order_value_and_kind() -> None:
    keys = pd.DataFrame({"engine_id": [1, 2], "cycle": [1, 1]})
    values = np.array([0.1, 0.2])
    first = prediction_digest(keys, values)
    assert first == prediction_digest(keys, values)
    assert first != prediction_digest(keys.iloc[::-1], values)
    assert first != prediction_digest(keys, values, probability=True)
