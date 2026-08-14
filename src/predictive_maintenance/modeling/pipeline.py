"""One fixed, leakage-safe baseline training workflow."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from predictive_maintenance.modeling.baselines import (
    classification_models,
    non_negative_predictions,
    positive_probabilities,
    regression_models,
)
from predictive_maintenance.modeling.metrics import (
    classification_metrics,
    prediction_digest,
    regression_metrics,
)
from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    BaselineResult,
    Evaluation,
    TrainingDataset,
)
from predictive_maintenance.modeling.splitting import apply_split, create_split_manifest


def _matrix(frame: pd.DataFrame) -> pd.DataFrame:
    selected: pd.DataFrame = frame.loc[:, list(FEATURE_COLUMNS)]
    return selected.astype("float64").copy()


def run_baselines(dataset: TrainingDataset) -> BaselineResult:
    """Fit four fixed models, gate on validation, then report final holdout."""
    manifest = create_split_manifest(dataset)
    split = apply_split(dataset, manifest)
    train_x = _matrix(split.train_features)
    validation_x = _matrix(split.validation_features)
    test_x = _matrix(split.test_features)
    evaluations: list[Evaluation] = []
    fitted: dict[str, Any] = {}

    regression = regression_models()
    regression_validation_metrics: dict[str, dict[str, Any]] = {}
    regression_pending: list[tuple[str, dict[str, Any], dict[str, Any], str, str]] = []
    train_rul = split.train_targets["rul"].to_numpy(dtype="float64")
    for name, model in regression.items():
        model.fit(train_x, train_rul)
        validation_prediction, validation_clipped = non_negative_predictions(
            model, validation_x
        )
        test_prediction, test_clipped = non_negative_predictions(model, test_x)
        validation_metrics = regression_metrics(
            split.validation_features.loc[:, ["engine_id", "cycle"]],
            split.validation_targets["rul"].to_numpy(),
            validation_prediction,
            clipped_count=validation_clipped,
        )
        test_metrics = regression_metrics(
            split.test_features.loc[:, ["engine_id", "cycle"]],
            split.test_targets["rul"].to_numpy(),
            test_prediction,
            clipped_count=test_clipped,
        )
        regression_validation_metrics[name] = validation_metrics
        regression_pending.append(
            (
                name,
                validation_metrics,
                test_metrics,
                prediction_digest(split.validation_features, validation_prediction),
                prediction_digest(split.test_features, test_prediction),
            )
        )
        fitted[f"regression_{name}"] = model
    regression_eligible = (
        regression_validation_metrics["candidate"]["engine_balanced_rmse"]
        < regression_validation_metrics["dummy"]["engine_balanced_rmse"]
    )
    for (
        name,
        validation_metrics,
        test_metrics,
        validation_digest,
        test_digest,
    ) in regression_pending:
        evaluations.append(
            Evaluation(
                "regression",
                name,  # type: ignore[arg-type]
                validation_metrics,
                test_metrics,
                validation_digest,
                test_digest,
                bool(regression_eligible) if name == "candidate" else False,
            )
        )

    classification = classification_models()
    classification_validation_metrics: dict[str, dict[str, Any]] = {}
    classification_pending: list[
        tuple[str, dict[str, Any], dict[str, Any], str, str]
    ] = []
    train_risk = split.train_targets["failure_risk_30"].to_numpy(dtype="int64")
    if len(np.unique(train_risk)) != 2:
        raise ValueError("Classification training split must contain both classes.")
    for name, model in classification.items():
        model.fit(train_x, train_risk)
        validation_probability = positive_probabilities(model, validation_x)
        test_probability = positive_probabilities(model, test_x)
        validation_metrics = classification_metrics(
            split.validation_features.loc[:, ["engine_id", "cycle"]],
            split.validation_targets["failure_risk_30"].to_numpy(),
            validation_probability,
        )
        test_metrics = classification_metrics(
            split.test_features.loc[:, ["engine_id", "cycle"]],
            split.test_targets["failure_risk_30"].to_numpy(),
            test_probability,
        )
        classification_validation_metrics[name] = validation_metrics
        classification_pending.append(
            (
                name,
                validation_metrics,
                test_metrics,
                prediction_digest(
                    split.validation_features, validation_probability, probability=True
                ),
                prediction_digest(
                    split.test_features, test_probability, probability=True
                ),
            )
        )
        fitted[f"classification_{name}"] = model
    classification_eligible = (
        classification_validation_metrics["candidate"][
            "engine_balanced_average_precision"
        ]
        > classification_validation_metrics["dummy"][
            "engine_balanced_average_precision"
        ]
    )
    for (
        name,
        validation_metrics,
        test_metrics,
        validation_digest,
        test_digest,
    ) in classification_pending:
        evaluations.append(
            Evaluation(
                "classification",
                name,  # type: ignore[arg-type]
                validation_metrics,
                test_metrics,
                validation_digest,
                test_digest,
                bool(classification_eligible) if name == "candidate" else False,
            )
        )
    return BaselineResult(manifest, tuple(evaluations), fitted)
