"""Fixed Phase 4 scikit-learn baseline estimators."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.dummy import (  # type: ignore[import-untyped]
    DummyClassifier,
    DummyRegressor,
)
from sklearn.linear_model import (  # type: ignore[import-untyped]
    LogisticRegression,
    Ridge,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from predictive_maintenance.modeling.models import RANDOM_SEED


def regression_models() -> dict[str, Any]:
    """Create unfitted median and fixed scaled Ridge baselines."""
    return {
        "dummy": DummyRegressor(strategy="median"),
        "candidate": Pipeline(
            [("scaler", StandardScaler()), ("estimator", Ridge(alpha=1.0))]
        ),
    }


def classification_models() -> dict[str, Any]:
    """Create unfitted prior and fixed class-balanced logistic baselines."""
    return {
        "dummy": DummyClassifier(strategy="prior", random_state=RANDOM_SEED),
        "candidate": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "estimator",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=1000,
                        random_state=RANDOM_SEED,
                        solver="liblinear",
                    ),
                ),
            ]
        ),
    }


def non_negative_predictions(model: Any, features: Any) -> tuple[np.ndarray, int]:
    """Apply the only allowed RUL output transformation: a floor at zero."""
    raw = np.asarray(model.predict(features), dtype="float64")
    clipped = np.maximum(raw, 0.0)
    return clipped, int((raw < 0.0).sum())


def positive_probabilities(model: Any, features: Any) -> np.ndarray:
    """Return the probability for class one using the model's class mapping."""
    classes = np.asarray(model.classes_)
    matches = np.flatnonzero(classes == 1)
    if len(matches) != 1:
        raise ValueError("Classification training must contain class one.")
    return np.asarray(
        model.predict_proba(features)[:, int(matches[0])], dtype="float64"
    )
