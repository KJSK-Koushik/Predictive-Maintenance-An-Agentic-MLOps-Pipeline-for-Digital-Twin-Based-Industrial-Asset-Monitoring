"""Leakage-controlled Phase 5 comparison, uncertainty, and benchmark gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]

from predictive_maintenance.modeling.advanced import (
    DevelopmentInput,
    advanced_model,
    baseline_model,
    create_comparison_manifest,
    feature_matrix,
    predict,
    prediction_with_metadata,
    primary_metric,
    tune_parameters,
)
from predictive_maintenance.modeling.metrics import (
    classification_metrics,
    prediction_digest,
    regression_metrics,
)
from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    RANDOM_SEED,
    RISK_THRESHOLD,
    ModelingError,
    TrainingDataset,
)
from predictive_maintenance.modeling.phase5_models import (
    BOOTSTRAP_SAMPLES,
    SEARCH_SPACE_VERSION,
    SELECTION_CONTRACT_VERSION,
    BenchmarkResult,
    BenchmarkTaskResult,
    BootstrapInterval,
    ComparisonManifest,
    SelectionRecord,
    TaskComparison,
)

Task = Literal["regression", "classification"]


@dataclass(frozen=True, slots=True)
class SupervisedDevelopment:
    """Supervised evidence produced before NASA benchmark access."""

    manifest: ComparisonManifest
    comparisons: tuple[TaskComparison, ...]
    selection: SelectionRecord


def development_input_from_dataset(
    dataset: TrainingDataset, *, phase4_split_id: str
) -> DevelopmentInput:
    """Copy only source-training frames into the tuning boundary."""
    return DevelopmentInput(
        raw_snapshot_id=dataset.raw_snapshot_id,
        processed_snapshot_id=dataset.processed_snapshot_id,
        feature_snapshot_id=dataset.feature_snapshot_id,
        phase4_split_id=phase4_split_id,
        features=dataset.train_features.copy(),
        targets=dataset.train_targets.copy(),
    )


def _subset(data: DevelopmentInput, engines: tuple[int, ...]) -> DevelopmentInput:
    mask = data.features["engine_id"].isin(engines).to_numpy()
    return DevelopmentInput(
        data.raw_snapshot_id,
        data.processed_snapshot_id,
        data.feature_snapshot_id,
        data.phase4_split_id,
        data.features.loc[mask].reset_index(drop=True),
        data.targets.loc[mask].reset_index(drop=True),
    )


def _target(data: DevelopmentInput, task: Task) -> np.ndarray:
    name = "rul" if task == "regression" else "failure_risk_30"
    return data.targets[name].to_numpy(
        dtype="float64" if task == "regression" else "int64"
    )


def _linear_coefficients(model: Any) -> np.ndarray:
    estimator = model.named_steps["estimator"]
    values = np.asarray(estimator.coef_, dtype="float64")
    result: np.ndarray = np.abs(values.reshape(-1))
    return result


def _permutation_importance(
    model: Any,
    task: Task,
    features: pd.DataFrame,
    targets: np.ndarray,
    keys: pd.DataFrame,
    *,
    seed: int,
) -> np.ndarray:
    matrix = feature_matrix(features)
    baseline = primary_metric(task, keys, targets, predict(model, task, matrix))
    rng = np.random.default_rng(seed)
    output = np.zeros(len(FEATURE_COLUMNS), dtype="float64")
    for column_index, column in enumerate(FEATURE_COLUMNS):
        changes: list[float] = []
        for _ in range(2):
            permuted = matrix.copy()
            permuted[column] = rng.permutation(permuted[column].to_numpy())
            score = primary_metric(task, keys, targets, predict(model, task, permuted))
            changes.append(
                score - baseline if task == "regression" else baseline - score
            )
        output[column_index] = float(np.mean(changes))
    return output


def _rank_stability(values: list[np.ndarray]) -> float:
    correlations: list[float] = []
    for left in range(len(values)):
        for right in range(left + 1, len(values)):
            left_rank = pd.Series(values[left]).rank(method="average")
            right_rank = pd.Series(values[right]).rank(method="average")
            correlation = left_rank.corr(right_rank, method="pearson")
            correlations.append(0.0 if pd.isna(correlation) else float(correlation))
    return float(np.mean(correlations)) if correlations else 1.0


def _whole_engine_bootstrap(
    task: Task,
    keys: pd.DataFrame,
    targets: np.ndarray,
    baseline: np.ndarray,
    advanced: np.ndarray,
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = RANDOM_SEED,
) -> BootstrapInterval:
    if samples != BOOTSTRAP_SAMPLES:
        raise ModelingError(
            "comparison.bootstrap_samples",
            "Phase 5 requires exactly 2,000 bootstrap samples.",
        )
    engines = np.asarray(sorted(keys["engine_id"].unique()), dtype="int64")
    engine_values = keys["engine_id"].to_numpy(dtype="int64")
    rng = np.random.default_rng(seed)
    improvements = np.empty(samples, dtype="float64")
    if task == "regression":
        baseline_mse = np.asarray(
            [
                np.mean(
                    (
                        baseline[engine_values == engine]
                        - targets[engine_values == engine]
                    )
                    ** 2
                )
                for engine in engines
            ],
            dtype="float64",
        )
        advanced_mse = np.asarray(
            [
                np.mean(
                    (
                        advanced[engine_values == engine]
                        - targets[engine_values == engine]
                    )
                    ** 2
                )
                for engine in engines
            ],
            dtype="float64",
        )
        point = float(np.sqrt(np.mean(baseline_mse)) - np.sqrt(np.mean(advanced_mse)))
        for index in range(samples):
            selected = rng.integers(0, len(engines), size=len(engines))
            improvements[index] = np.sqrt(np.mean(baseline_mse[selected])) - np.sqrt(
                np.mean(advanced_mse[selected])
            )
    else:
        row_counts = np.asarray(
            [(engine_values == engine).sum() for engine in engines], dtype="float64"
        )
        weights_by_engine = {
            int(engine): 1.0 / row_counts[index] for index, engine in enumerate(engines)
        }
        equal_weights = np.asarray(
            [weights_by_engine[int(engine)] for engine in engine_values],
            dtype="float64",
        )
        point = float(
            average_precision_score(targets, advanced, sample_weight=equal_weights)
            - average_precision_score(targets, baseline, sample_weight=equal_weights)
        )
        for index in range(samples):
            counts = np.bincount(
                rng.integers(0, len(engines), size=len(engines)),
                minlength=len(engines),
            )
            count_by_engine = {
                int(engine): int(counts[position])
                for position, engine in enumerate(engines)
            }
            row_weights = np.asarray(
                [
                    count_by_engine[int(engine)] * weights_by_engine[int(engine)]
                    for engine in engine_values
                ],
                dtype="float64",
            )
            improvements[index] = average_precision_score(
                targets, advanced, sample_weight=row_weights
            ) - average_precision_score(targets, baseline, sample_weight=row_weights)
    lower, upper = np.percentile(improvements, [2.5, 97.5])
    return BootstrapInterval(point, float(lower), float(upper), samples)


def _error_analysis(
    task: Task,
    keys: pd.DataFrame,
    targets: np.ndarray,
    predictions: np.ndarray,
    rul: np.ndarray,
) -> dict[str, Any]:
    rows: list[dict[str, float | int]] = []
    for engine in sorted(keys["engine_id"].unique()):
        mask = keys["engine_id"].eq(engine).to_numpy()
        if task == "regression":
            score = float(np.sqrt(np.mean((predictions[mask] - targets[mask]) ** 2)))
            metric = "rmse"
        else:
            score = float(average_precision_score(targets[mask], predictions[mask]))
            metric = "average_precision"
        rows.append({"engine_id": int(engine), metric: score})
    metric = "rmse" if task == "regression" else "average_precision"
    reverse = task == "regression"
    worst = sorted(rows, key=lambda row: float(row[metric]), reverse=reverse)[:5]
    lifecycle_masks = {
        "near_0_30": rul <= 30,
        "middle_31_100": (rul >= 31) & (rul <= 100),
        "early_over_100": rul > 100,
    }
    lifecycle: dict[str, dict[str, float | int | None]] = {}
    for name, mask in lifecycle_masks.items():
        if not bool(mask.any()):
            continue
        if task == "regression":
            lifecycle[name] = {
                "row_count": int(mask.sum()),
                "rmse": float(
                    np.sqrt(np.mean((predictions[mask] - targets[mask]) ** 2))
                ),
                "mae": float(np.mean(np.abs(predictions[mask] - targets[mask]))),
            }
        else:
            band_targets = targets[mask]
            band_predictions = (predictions[mask] >= RISK_THRESHOLD).astype("int64")
            lifecycle[name] = {
                "row_count": int(mask.sum()),
                "average_precision": (
                    float(average_precision_score(band_targets, predictions[mask]))
                    if len(np.unique(band_targets)) > 1
                    else None
                ),
                "brier_score": float(np.mean((predictions[mask] - band_targets) ** 2)),
                "false_positive": int(
                    ((band_predictions == 1) & (band_targets == 0)).sum()
                ),
                "false_negative": int(
                    ((band_predictions == 0) & (band_targets == 1)).sum()
                ),
            }
    return {
        "worst_engines": worst,
        "maximum_examples": 5,
        "lifecycle_bands": lifecycle,
    }


def _complexity_gate(
    task: Task,
    baseline_metrics: dict[str, Any],
    advanced_metrics: dict[str, Any],
    interval: BootstrapInterval,
) -> dict[str, bool]:
    """Apply the predeclared practical, interval, and non-inferiority rules."""
    if task == "regression":
        baseline_rmse = float(baseline_metrics["engine_balanced_rmse"])
        relative_rmse = (
            interval.point_improvement / baseline_rmse if baseline_rmse > 0.0 else 0.0
        )
        return {
            "practical_improvement": relative_rmse >= 0.03,
            "interval_above_zero": interval.lower_95 > 0.0,
            "mae_non_inferior": float(advanced_metrics["engine_balanced_mae"])
            <= float(baseline_metrics["engine_balanced_mae"]) * 1.05,
            "nasa_non_inferior": float(advanced_metrics["engine_balanced_nasa_score"])
            <= float(baseline_metrics["engine_balanced_nasa_score"]) * 1.05,
        }
    return {
        "practical_improvement": interval.point_improvement >= 0.005,
        "interval_above_zero": interval.lower_95 > 0.0,
        "brier_non_inferior": float(advanced_metrics["engine_balanced_brier_score"])
        <= float(baseline_metrics["engine_balanced_brier_score"]) + 0.01,
    }


def _comparison_metrics(
    task: Task,
    data: DevelopmentInput,
    predictions: np.ndarray,
    *,
    clipped_count: int = 0,
) -> dict[str, Any]:
    keys = data.features.loc[:, ["engine_id", "cycle"]]
    targets = _target(data, task)
    if task == "regression":
        return regression_metrics(
            keys, targets, predictions, clipped_count=clipped_count
        )
    return classification_metrics(keys, targets, predictions)


def _run_task(
    data: DevelopmentInput, manifest: ComparisonManifest, task: Task
) -> TaskComparison:
    matrix = feature_matrix(data.features)
    targets = _target(data, task)
    baseline_oof = np.full(len(data.features), np.nan, dtype="float64")
    advanced_oof = np.full(len(data.features), np.nan, dtype="float64")
    selected_parameters: list[dict[str, Any]] = []
    coefficient_rows: list[np.ndarray] = []
    importance_rows: list[np.ndarray] = []
    baseline_clipped = 0
    advanced_clipped = 0
    for fold in manifest.outer_folds:
        train_mask = data.features["engine_id"].isin(fold.train_engine_ids).to_numpy()
        validation_mask = (
            data.features["engine_id"].isin(fold.validation_engine_ids).to_numpy()
        )
        outer_data = _subset(data, fold.train_engine_ids)
        parameters = tune_parameters(outer_data, task, fold.inner_folds)
        selected_parameters.append(parameters)

        reference = baseline_model(task)
        reference.fit(matrix.loc[train_mask], targets[train_mask])
        reference_output, clipped = prediction_with_metadata(
            reference, task, matrix.loc[validation_mask]
        )
        baseline_oof[validation_mask] = reference_output
        baseline_clipped += clipped
        coefficient_rows.append(_linear_coefficients(reference))

        candidate = advanced_model(task, parameters)
        candidate.fit(matrix.loc[train_mask], targets[train_mask])
        candidate_output, clipped = prediction_with_metadata(
            candidate, task, matrix.loc[validation_mask]
        )
        advanced_oof[validation_mask] = candidate_output
        advanced_clipped += clipped
        keys = data.features.loc[validation_mask, ["engine_id", "cycle"]].reset_index(
            drop=True
        )
        importance_rows.append(
            _permutation_importance(
                candidate,
                task,
                data.features.loc[validation_mask].reset_index(drop=True),
                targets[validation_mask],
                keys,
                seed=RANDOM_SEED + fold.index,
            )
        )
    if not bool(np.isfinite(baseline_oof).all()) or not bool(
        np.isfinite(advanced_oof).all()
    ):
        raise ModelingError(
            "comparison.oof_coverage", "Outer out-of-fold predictions are incomplete."
        )
    final_parameters = tune_parameters(data, task, manifest.final_inner_folds)
    baseline_metrics = _comparison_metrics(
        task, data, baseline_oof, clipped_count=baseline_clipped
    )
    advanced_metrics = _comparison_metrics(
        task, data, advanced_oof, clipped_count=advanced_clipped
    )
    keys = data.features.loc[:, ["engine_id", "cycle"]]
    interval = _whole_engine_bootstrap(task, keys, targets, baseline_oof, advanced_oof)
    guardrails = _complexity_gate(task, baseline_metrics, advanced_metrics, interval)
    preferred = bool(all(guardrails.values()))
    coefficients = np.mean(np.vstack(coefficient_rows), axis=0)
    importances = np.mean(np.vstack(importance_rows), axis=0)
    preferred_predictions = advanced_oof if preferred else baseline_oof
    return TaskComparison(
        task=task,
        baseline_metrics=baseline_metrics,
        advanced_metrics=advanced_metrics,
        baseline_prediction_digest=prediction_digest(
            keys, baseline_oof, probability=task == "classification"
        ),
        advanced_prediction_digest=prediction_digest(
            keys, advanced_oof, probability=task == "classification"
        ),
        outer_selected_parameters=tuple(selected_parameters),
        final_parameters=final_parameters,
        interval=interval,
        guardrails=guardrails,
        advanced_preferred=preferred,
        preferred_model="advanced" if preferred else "baseline",
        baseline_coefficients={
            name: float(value)
            for name, value in zip(FEATURE_COLUMNS, coefficients, strict=True)
        },
        advanced_permutation_importance={
            name: float(value)
            for name, value in zip(FEATURE_COLUMNS, importances, strict=True)
        },
        feature_rank_stability=_rank_stability(importance_rows),
        error_analysis=_error_analysis(
            task,
            keys,
            targets,
            preferred_predictions,
            data.targets["rul"].to_numpy(dtype="float64"),
        ),
    )


def run_supervised_development(data: DevelopmentInput) -> SupervisedDevelopment:
    """Run nested comparisons using source-training rows only."""
    manifest = create_comparison_manifest(data)
    regression = _run_task(data, manifest, "regression")
    classification = _run_task(data, manifest, "classification")
    selection = SelectionRecord(
        feature_snapshot_id=data.feature_snapshot_id,
        processed_snapshot_id=data.processed_snapshot_id,
        raw_snapshot_id=data.raw_snapshot_id,
        phase4_split_id=data.phase4_split_id,
        comparison_id=manifest.comparison_id,
        search_space_version=SEARCH_SPACE_VERSION,
        regression_model=regression.preferred_model,
        regression_parameters=(
            regression.final_parameters if regression.advanced_preferred else {}
        ),
        classification_model=classification.preferred_model,
        classification_parameters=(
            classification.final_parameters if classification.advanced_preferred else {}
        ),
        regression_prediction_digest=(
            regression.advanced_prediction_digest
            if regression.advanced_preferred
            else regression.baseline_prediction_digest
        ),
        classification_prediction_digest=(
            classification.advanced_prediction_digest
            if classification.advanced_preferred
            else classification.baseline_prediction_digest
        ),
    )
    return SupervisedDevelopment(manifest, (regression, classification), selection)


def selection_from_bytes(payload: bytes) -> SelectionRecord:
    """Load and verify one canonical locked-selection record."""
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ModelingError(
            "selection.invalid_json", "Selection record is not valid JSON."
        ) from error
    if not isinstance(value, dict):
        raise ModelingError("selection.invalid", "Selection record must be an object.")
    stored_id = value.pop("selection_id", None)
    try:
        record = SelectionRecord(**value)
    except TypeError as error:
        raise ModelingError(
            "selection.invalid", "Selection record fields are invalid."
        ) from error
    if stored_id != record.selection_id or not record.locked:
        raise ModelingError(
            "selection.identity", "Selection record identity or lock is invalid."
        )
    if (
        record.selection_contract_version != SELECTION_CONTRACT_VERSION
        or record.search_space_version != SEARCH_SPACE_VERSION
        or record.test_exposure_status != "previously_observed_in_phase_4"
        or record.regression_model not in {"baseline", "advanced"}
        or record.classification_model not in {"baseline", "advanced"}
        or (record.regression_model == "baseline" and record.regression_parameters)
        or (
            record.classification_model == "baseline"
            and record.classification_parameters
        )
    ):
        raise ModelingError(
            "selection.contract", "Selection record contract is not supported."
        )
    return record


def run_locked_benchmark(
    dataset: TrainingDataset,
    selection: SelectionRecord,
    *,
    phase4_split_id: str,
) -> BenchmarkResult:
    """Fit locked winners on source train and evaluate the known benchmark once."""
    if (
        not selection.locked
        or selection.test_exposure_status != "previously_observed_in_phase_4"
    ):
        raise ModelingError("selection.unlocked", "A locked selection is required.")
    expected = (
        dataset.feature_snapshot_id,
        dataset.processed_snapshot_id,
        dataset.raw_snapshot_id,
        phase4_split_id,
    )
    actual = (
        selection.feature_snapshot_id,
        selection.processed_snapshot_id,
        selection.raw_snapshot_id,
        selection.phase4_split_id,
    )
    if actual != expected:
        raise ModelingError(
            "selection.provenance", "Selection record does not match the dataset."
        )
    development = development_input_from_dataset(
        dataset, phase4_split_id=phase4_split_id
    )
    expected_comparison_id = create_comparison_manifest(development).comparison_id
    if selection.comparison_id != expected_comparison_id:
        raise ModelingError(
            "selection.comparison",
            "Selection record does not match the approved comparison manifest.",
        )
    train_x = feature_matrix(dataset.train_features)
    test_x = feature_matrix(dataset.test_features)
    keys = dataset.test_features.loc[:, ["engine_id", "cycle"]]
    evaluations: list[BenchmarkTaskResult] = []
    models: dict[str, Any] = {}
    for task in cast(tuple[Task, ...], ("regression", "classification")):
        selected_name = (
            selection.regression_model
            if task == "regression"
            else selection.classification_model
        )
        parameters = (
            selection.regression_parameters
            if task == "regression"
            else selection.classification_parameters
        )
        model = (
            baseline_model(task)
            if selected_name == "baseline"
            else advanced_model(task, parameters)
        )
        target_name = "rul" if task == "regression" else "failure_risk_30"
        train_target = dataset.train_targets[target_name].to_numpy(
            dtype="float64" if task == "regression" else "int64"
        )
        test_target = dataset.test_targets[target_name].to_numpy(
            dtype="float64" if task == "regression" else "int64"
        )
        model.fit(train_x, train_target)
        output, clipped_count = prediction_with_metadata(model, task, test_x)
        metrics = (
            regression_metrics(keys, test_target, output, clipped_count=clipped_count)
            if task == "regression"
            else classification_metrics(keys, test_target, output)
        )
        evaluations.append(
            BenchmarkTaskResult(
                task,
                selected_name,
                metrics,
                prediction_digest(keys, output, probability=task == "classification"),
            )
        )
        models[f"{task}_selected"] = model
    return BenchmarkResult(
        selection.selection_id,
        dataset.feature_snapshot_id,
        tuple(evaluations),
        models,
    )
