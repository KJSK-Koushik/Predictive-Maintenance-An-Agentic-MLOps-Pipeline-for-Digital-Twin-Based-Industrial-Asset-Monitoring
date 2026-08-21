"""Deterministic nested engine folds and bounded Phase 5 model search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
import sklearn  # type: ignore[import-untyped]
from sklearn.ensemble import (  # type: ignore[import-untyped]
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.model_selection import GroupKFold  # type: ignore[import-untyped]

from predictive_maintenance.modeling.baselines import (
    classification_models,
    non_negative_predictions,
    positive_probabilities,
    regression_models,
)
from predictive_maintenance.modeling.metrics import (
    classification_metrics,
    regression_metrics,
)
from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    RANDOM_SEED,
    TARGET_COLUMNS,
    ModelingError,
    canonical_json_bytes,
)
from predictive_maintenance.modeling.phase5_models import (
    INNER_FOLDS,
    OUTER_FOLDS,
    SEARCH_SPACE_VERSION,
    ComparisonManifest,
    InnerFold,
    OuterFold,
)

Task = Literal["regression", "classification"]
_ALLOWED_PARAMETERS = {
    "learning_rate",
    "max_iter",
    "max_leaf_nodes",
    "min_samples_leaf",
    "l2_regularization",
}


def _grid() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "learning_rate": learning_rate,
            "max_iter": 100,
            "max_leaf_nodes": leaves,
            "min_samples_leaf": 20,
            "l2_regularization": regularization,
        }
        for learning_rate in (0.05, 0.1)
        for leaves in (15, 31)
        for regularization in (0.0, 1.0)
    )


REGRESSION_GRID = _grid()
CLASSIFICATION_GRID = _grid()


@dataclass(frozen=True, slots=True)
class DevelopmentInput:
    """Source-training-only input; it cannot carry NASA benchmark rows."""

    raw_snapshot_id: str
    processed_snapshot_id: str
    feature_snapshot_id: str
    phase4_split_id: str
    features: pd.DataFrame
    targets: pd.DataFrame


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Select only the exact ordered Phase 4 model inputs."""
    if any(column not in frame.columns for column in FEATURE_COLUMNS):
        raise ModelingError(
            "comparison.feature_columns", "Required model input columns are missing."
        )
    selected: pd.DataFrame = frame.loc[:, list(FEATURE_COLUMNS)]
    result = selected.astype("float64").copy()
    if result.empty or not bool(np.isfinite(result.to_numpy()).all()):
        raise ModelingError(
            "comparison.feature_values", "Model inputs must be finite and non-empty."
        )
    return result


def parameter_grid(task: Task) -> tuple[dict[str, Any], ...]:
    """Return one checked-in finite search space."""
    grid = REGRESSION_GRID if task == "regression" else CLASSIFICATION_GRID
    if len(grid) > 12 or any(set(item) != _ALLOWED_PARAMETERS for item in grid):
        raise ModelingError(
            "comparison.search_space", "Advanced search space is not approved."
        )
    return tuple(dict(item) for item in grid)


def baseline_model(task: Task) -> Any:
    """Return the exact unchanged Phase 4 linear candidate."""
    return (
        regression_models()["candidate"]
        if task == "regression"
        else classification_models()["candidate"]
    )


def advanced_model(task: Task, parameters: dict[str, Any]) -> Any:
    """Create one deterministic histogram-gradient-boosting estimator."""
    if set(parameters) != _ALLOWED_PARAMETERS:
        raise ModelingError(
            "comparison.search_parameters", "Advanced model parameters are invalid."
        )
    common = {
        **parameters,
        "early_stopping": False,
        "random_state": RANDOM_SEED,
    }
    if task == "regression":
        return HistGradientBoostingRegressor(loss="squared_error", **common)
    return HistGradientBoostingClassifier(
        loss="log_loss", class_weight="balanced", **common
    )


def _engine_folds(engine_ids: tuple[int, ...], count: int) -> tuple[InnerFold, ...]:
    if len(engine_ids) < count:
        raise ModelingError(
            "comparison.insufficient_engines",
            "Not enough source-training engines for the approved fold count.",
        )
    values = np.asarray(sorted(engine_ids), dtype="int64")
    splitter = GroupKFold(n_splits=count)
    folds: list[InnerFold] = []
    for train_index, validation_index in splitter.split(values, groups=values):
        train = tuple(sorted(int(value) for value in values[train_index]))
        validation = tuple(sorted(int(value) for value in values[validation_index]))
        if set(train) & set(validation) or set(train) | set(validation) != set(values):
            raise ModelingError(
                "comparison.fold_overlap", "Engine fold coverage is invalid."
            )
        folds.append(InnerFold(train, validation))
    return tuple(folds)


def create_comparison_manifest(
    data: DevelopmentInput,
    *,
    outer_count: int = OUTER_FOLDS,
    inner_count: int = INNER_FOLDS,
    seed: int = RANDOM_SEED,
) -> ComparisonManifest:
    """Create deterministic nested folds from source-training engines only."""
    if data.features.empty or len(data.features) != len(data.targets):
        raise ModelingError(
            "comparison.input_rows", "Development feature and target rows differ."
        )
    keys = data.features.loc[:, ["engine_id", "cycle"]].reset_index(drop=True)
    target_keys = data.targets.loc[:, ["engine_id", "cycle"]].reset_index(drop=True)
    if not keys.equals(target_keys):
        raise ModelingError(
            "comparison.input_keys", "Development feature and target keys differ."
        )
    feature_matrix(data.features)
    engines = tuple(sorted(int(value) for value in keys["engine_id"].unique()))
    outer_base = _engine_folds(engines, outer_count)
    outer = tuple(
        OuterFold(
            index=index,
            train_engine_ids=fold.train_engine_ids,
            validation_engine_ids=fold.validation_engine_ids,
            inner_folds=_engine_folds(fold.train_engine_ids, inner_count),
        )
        for index, fold in enumerate(outer_base)
    )
    validation_engines = [
        engine for fold in outer for engine in fold.validation_engine_ids
    ]
    if sorted(validation_engines) != list(engines):
        raise ModelingError(
            "comparison.outer_coverage",
            "Every source-training engine must be held out exactly once.",
        )
    return ComparisonManifest(
        feature_snapshot_id=data.feature_snapshot_id,
        processed_snapshot_id=data.processed_snapshot_id,
        raw_snapshot_id=data.raw_snapshot_id,
        phase4_split_id=data.phase4_split_id,
        seed=seed,
        feature_columns=FEATURE_COLUMNS,
        target_columns=TARGET_COLUMNS,
        engine_ids=engines,
        row_count=len(data.features),
        numpy_version=np.__version__,
        sklearn_version=sklearn.__version__,
        search_space_version=SEARCH_SPACE_VERSION,
        outer_folds=outer,
        final_inner_folds=_engine_folds(engines, inner_count),
    )


def _mask(frame: pd.DataFrame, engines: tuple[int, ...]) -> np.ndarray:
    return frame["engine_id"].isin(engines).to_numpy()


def predict(model: Any, task: Task, matrix: pd.DataFrame) -> np.ndarray:
    """Return task output under the existing Phase 4 output rules."""
    return prediction_with_metadata(model, task, matrix)[0]


def prediction_with_metadata(
    model: Any, task: Task, matrix: pd.DataFrame
) -> tuple[np.ndarray, int]:
    """Return task output plus the truthful regression clipping count."""
    if task == "regression":
        return non_negative_predictions(model, matrix)
    return positive_probabilities(model, matrix), 0


def primary_metric(
    task: Task,
    keys: pd.DataFrame,
    targets: np.ndarray,
    predictions: np.ndarray,
) -> float:
    """Return the approved engine-balanced primary metric."""
    if task == "regression":
        return float(
            regression_metrics(keys, targets, predictions, clipped_count=0)[
                "engine_balanced_rmse"
            ]
        )
    return float(
        classification_metrics(keys, targets, predictions)[
            "engine_balanced_average_precision"
        ]
    )


def tune_parameters(
    data: DevelopmentInput,
    task: Task,
    folds: tuple[InnerFold, ...],
) -> dict[str, Any]:
    """Choose one configuration from inner engine folds with stable tie-breaking."""
    x = feature_matrix(data.features)
    target_name = "rul" if task == "regression" else "failure_risk_30"
    y = data.targets[target_name].to_numpy(
        dtype="float64" if task == "regression" else "int64"
    )
    scored: list[tuple[float, bytes, dict[str, Any]]] = []
    for parameters in parameter_grid(task):
        fold_scores: list[float] = []
        for fold in folds:
            train_mask = _mask(data.features, fold.train_engine_ids)
            validation_mask = _mask(data.features, fold.validation_engine_ids)
            if bool((train_mask & validation_mask).any()):
                raise ModelingError(
                    "comparison.fold_overlap", "Inner fold rows overlap."
                )
            model = advanced_model(task, parameters)
            model.fit(x.loc[train_mask], y[train_mask])
            prediction = predict(model, task, x.loc[validation_mask])
            keys = data.features.loc[
                validation_mask, ["engine_id", "cycle"]
            ].reset_index(drop=True)
            fold_scores.append(
                primary_metric(task, keys, y[validation_mask], prediction)
            )
        mean_score = float(np.mean(fold_scores))
        ordering_score = mean_score if task == "regression" else -mean_score
        scored.append((ordering_score, canonical_json_bytes(parameters), parameters))
    return dict(min(scored, key=lambda item: (item[0], item[1]))[2])
