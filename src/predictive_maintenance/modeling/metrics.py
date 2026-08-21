"""Engine-balanced and pooled Phase 4 evaluation metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from predictive_maintenance.modeling.models import (
    RISK_THRESHOLD,
    canonical_json_bytes,
    sha256_bytes,
)


def engine_balanced_weights(engine_ids: Any) -> np.ndarray:
    """Give every engine equal total weight regardless of trajectory length."""
    values = np.asarray(engine_ids, dtype="int64")
    unique, counts = np.unique(values, return_counts=True)
    count_by_engine = dict(zip(unique.tolist(), counts.tolist(), strict=True))
    return np.asarray([1.0 / count_by_engine[int(value)] for value in values])


def _weighted_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    weights: np.ndarray,
    *,
    squared: bool,
) -> float:
    errors = y_pred - y_true
    values = errors**2 if squared else np.abs(errors)
    result = float(np.average(values, weights=weights))
    return float(np.sqrt(result)) if squared else result


def nasa_asymmetric_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Penalize late RUL predictions more strongly than early predictions."""
    error = np.asarray(y_pred, dtype="float64") - np.asarray(y_true, dtype="float64")
    exponent = np.where(error < 0.0, -error / 13.0, error / 10.0)
    exponent = np.minimum(exponent, 700.0)
    return float(np.sum(np.expm1(exponent)))


def engine_balanced_nasa_score(
    engine_ids: Any, y_true: np.ndarray, y_pred: np.ndarray
) -> float:
    """Average the mean NASA penalty of each engine trajectory."""
    engines = np.asarray(engine_ids, dtype="int64")
    true = np.asarray(y_true, dtype="float64")
    predicted = np.asarray(y_pred, dtype="float64")
    penalties: list[float] = []
    for engine in np.unique(engines):
        mask = engines == engine
        penalties.append(
            nasa_asymmetric_score(true[mask], predicted[mask]) / mask.sum()
        )
    return float(np.mean(penalties))


def _regression_subset(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(np.mean(np.abs(y_pred - y_true))),
        "rmse": float(np.sqrt(np.mean((y_pred - y_true) ** 2))),
    }


def final_cycle_mask(keys: pd.DataFrame) -> np.ndarray:
    """Select exactly the greatest cycle for each engine."""
    maximum = keys.groupby("engine_id")["cycle"].transform("max")
    return keys["cycle"].eq(maximum).to_numpy()


def regression_metrics(
    keys: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    clipped_count: int,
) -> dict[str, Any]:
    """Return bounded aggregate RUL evidence."""
    true = np.asarray(y_true, dtype="float64")
    predicted = np.asarray(y_pred, dtype="float64")
    weights = engine_balanced_weights(keys["engine_id"].to_numpy())
    residual = predicted - true
    lifecycle = {
        "near_0_30": true <= 30,
        "middle_31_100": (true >= 31) & (true <= 100),
        "early_over_100": true > 100,
    }
    bands = {
        name: {
            "row_count": int(mask.sum()),
            **_regression_subset(true[mask], predicted[mask]),
        }
        for name, mask in lifecycle.items()
        if bool(mask.any())
    }
    final = final_cycle_mask(keys)
    return {
        "engine_balanced_mae": _weighted_error(true, predicted, weights, squared=False),
        "engine_balanced_rmse": _weighted_error(true, predicted, weights, squared=True),
        "pooled_mae": float(np.mean(np.abs(residual))),
        "pooled_rmse": float(np.sqrt(np.mean(residual**2))),
        "nasa_asymmetric_score": nasa_asymmetric_score(true, predicted),
        "engine_balanced_nasa_score": engine_balanced_nasa_score(
            keys["engine_id"].to_numpy(), true, predicted
        ),
        "residual_mean": float(np.mean(residual)),
        "residual_std": float(np.std(residual)),
        "clipped_prediction_count": clipped_count,
        "lifecycle_bands": bands,
        "final_cycle": _regression_subset(true[final], predicted[final]),
    }


def _optional_roc_auc(
    y_true: np.ndarray, probability: np.ndarray, weights: np.ndarray | None = None
) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    return float(roc_auc_score(y_true, probability, sample_weight=weights))


def _balanced_accuracy(y_true: np.ndarray, predicted: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float(np.mean(predicted == y_true))
    return float(balanced_accuracy_score(y_true, predicted))


def _calibration(
    y_true: np.ndarray, probability: np.ndarray, bins: int = 10
) -> dict[str, Any]:
    indexes = np.minimum((probability * bins).astype("int64"), bins - 1)
    rows: list[dict[str, float | int]] = []
    ece = 0.0
    for index in range(bins):
        mask = indexes == index
        if not bool(mask.any()):
            continue
        mean_probability = float(np.mean(probability[mask]))
        event_rate = float(np.mean(y_true[mask]))
        count = int(mask.sum())
        ece += count / len(y_true) * abs(mean_probability - event_rate)
        rows.append(
            {
                "bin": index,
                "count": count,
                "mean_probability": mean_probability,
                "event_rate": event_rate,
            }
        )
    return {"expected_calibration_error": float(ece), "bins": rows}


def classification_metrics(
    keys: pd.DataFrame,
    y_true: np.ndarray,
    probability: np.ndarray,
) -> dict[str, Any]:
    """Return bounded aggregate 30-cycle risk evidence."""
    true = np.asarray(y_true, dtype="int64")
    probabilities = np.asarray(probability, dtype="float64")
    if not bool(np.isfinite(probabilities).all()) or bool(
        ((probabilities < 0.0) | (probabilities > 1.0)).any()
    ):
        raise ValueError("Classification probabilities must be finite in [0, 1].")
    predicted = (probabilities >= RISK_THRESHOLD).astype("int64")
    weights = engine_balanced_weights(keys["engine_id"].to_numpy())
    matrix = confusion_matrix(true, predicted, labels=[0, 1])
    final = final_cycle_mask(keys)
    final_true = true[final]
    final_probability = probabilities[final]
    return {
        "engine_balanced_average_precision": float(
            average_precision_score(true, probabilities, sample_weight=weights)
        ),
        "pooled_average_precision": float(average_precision_score(true, probabilities)),
        "engine_balanced_roc_auc": _optional_roc_auc(true, probabilities, weights),
        "pooled_roc_auc": _optional_roc_auc(true, probabilities),
        "engine_balanced_brier_score": float(
            brier_score_loss(true, probabilities, sample_weight=weights)
        ),
        "brier_score": float(brier_score_loss(true, probabilities)),
        "balanced_accuracy": _balanced_accuracy(true, predicted),
        "precision": float(precision_score(true, predicted, zero_division=0)),
        "recall": float(recall_score(true, predicted, zero_division=0)),
        "f1": float(f1_score(true, predicted, zero_division=0)),
        "confusion": {
            "true_negative": int(matrix[0, 0]),
            "false_positive": int(matrix[0, 1]),
            "false_negative": int(matrix[1, 0]),
            "true_positive": int(matrix[1, 1]),
        },
        "calibration": _calibration(true, probabilities),
        "final_cycle": {
            "row_count": int(final.sum()),
            "average_precision": float(
                average_precision_score(final_true, final_probability)
            ),
            "roc_auc": _optional_roc_auc(final_true, final_probability),
            "brier_score": float(brier_score_loss(final_true, final_probability)),
        },
    }


def prediction_digest(
    keys: pd.DataFrame, predictions: np.ndarray, *, probability: bool = False
) -> str:
    """Hash ordered keys and rounded predictions as behavioral evidence."""
    values = np.asarray(predictions, dtype="float64")
    rows = [
        {
            "engine_id": int(engine_id),
            "cycle": int(cycle),
            "value": round(float(value), 12),
            "kind": "probability" if probability else "prediction",
        }
        for engine_id, cycle, value in zip(
            keys["engine_id"], keys["cycle"], values, strict=True
        )
    ]
    return sha256_bytes(canonical_json_bytes(rows))
