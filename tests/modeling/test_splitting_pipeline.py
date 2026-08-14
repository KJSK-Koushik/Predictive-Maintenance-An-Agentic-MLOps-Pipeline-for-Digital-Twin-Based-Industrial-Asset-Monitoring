"""Split, leakage, model, and reproducibility tests."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]

from predictive_maintenance.modeling.baselines import (
    classification_models,
    non_negative_predictions,
    positive_probabilities,
    regression_models,
)
from predictive_maintenance.modeling.models import FEATURE_COLUMNS, TrainingDataset
from predictive_maintenance.modeling.pipeline import run_baselines
from predictive_maintenance.modeling.splitting import apply_split, create_split_manifest


def test_split_is_engine_disjoint_complete_and_deterministic(
    synthetic_dataset: TrainingDataset,
) -> None:
    first = create_split_manifest(synthetic_dataset)
    second = create_split_manifest(synthetic_dataset)

    assert len(first.train.engine_ids) == 8
    assert len(first.validation.engine_ids) == 2
    assert not set(first.train.engine_ids) & set(first.validation.engine_ids)
    assert first.train.row_count + first.validation.row_count == 400
    assert first.test.row_count == 140
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.split_id == second.split_id


def test_split_membership_ignores_row_order(synthetic_dataset: TrainingDataset) -> None:
    shuffled = replace(
        synthetic_dataset,
        train_features=synthetic_dataset.train_features.sample(frac=1, random_state=7),
        train_targets=synthetic_dataset.train_targets.sample(frac=1, random_state=7),
    )
    assert (
        create_split_manifest(shuffled).split_id
        == create_split_manifest(synthetic_dataset).split_id
    )


def test_source_partition_keeps_repeated_numeric_ids_distinct(
    synthetic_dataset: TrainingDataset,
) -> None:
    manifest = create_split_manifest(synthetic_dataset)
    assert set(manifest.test.engine_ids) & set(manifest.train.engine_ids)
    assert manifest.test.source_partition == "test"
    assert manifest.train.source_partition == "train"


def test_split_requires_enough_engines(synthetic_dataset: TrainingDataset) -> None:
    small_features = synthetic_dataset.train_features.query("engine_id < 5")
    small_targets = synthetic_dataset.train_targets.query("engine_id < 5")
    with pytest.raises(ValueError, match="five"):
        create_split_manifest(
            replace(
                synthetic_dataset,
                train_features=small_features,
                train_targets=small_targets,
            )
        )


def test_apply_split_rejects_wrong_lineage(synthetic_dataset: TrainingDataset) -> None:
    manifest = replace(
        create_split_manifest(synthetic_dataset), feature_snapshot_id="f" * 64
    )
    with pytest.raises(ValueError, match="does not belong"):
        apply_split(synthetic_dataset, manifest)


def test_fixed_model_configurations() -> None:
    regression = regression_models()
    classification = classification_models()
    ridge = regression["candidate"]
    logistic = classification["candidate"]

    assert regression["dummy"].strategy == "median"
    assert isinstance(ridge, Pipeline)
    assert ridge["estimator"].alpha == 1.0
    assert classification["dummy"].strategy == "prior"
    assert logistic["estimator"].class_weight == "balanced"
    assert logistic["estimator"].solver == "liblinear"
    assert logistic["estimator"].max_iter == 1000


def test_non_negative_floor_and_positive_class_mapping() -> None:
    class Regression:
        def predict(self, _features: np.ndarray) -> np.ndarray:
            return np.array([-2.0, 3.0])

    class Classification:
        classes_ = np.array([1, 0])

        def predict_proba(self, _features: np.ndarray) -> np.ndarray:
            return np.array([[0.8, 0.2], [0.3, 0.7]])

    predictions, clipped = non_negative_predictions(Regression(), np.zeros((2, 1)))
    assert predictions.tolist() == [0.0, 3.0]
    assert clipped == 1
    assert positive_probabilities(Classification(), np.zeros((2, 1))).tolist() == [
        0.8,
        0.3,
    ]


def test_full_synthetic_pipeline_beats_both_dummies(
    synthetic_dataset: TrainingDataset,
) -> None:
    result = run_baselines(synthetic_dataset)

    regression_dummy = result.evaluation("regression", "dummy")
    regression_candidate = result.evaluation("regression", "candidate")
    classification_dummy = result.evaluation("classification", "dummy")
    classification_candidate = result.evaluation("classification", "candidate")
    assert regression_candidate.eligible
    assert classification_candidate.eligible
    assert (
        regression_candidate.validation_metrics["engine_balanced_rmse"]
        < regression_dummy.validation_metrics["engine_balanced_rmse"]
    )
    assert (
        classification_candidate.validation_metrics["engine_balanced_average_precision"]
        > classification_dummy.validation_metrics["engine_balanced_average_precision"]
    )
    assert set(result.models) == {
        "regression_dummy",
        "regression_candidate",
        "classification_dummy",
        "classification_candidate",
    }


def test_repeated_training_is_behaviorally_reproducible(
    synthetic_dataset: TrainingDataset,
) -> None:
    first = run_baselines(synthetic_dataset)
    second = run_baselines(synthetic_dataset)

    assert first.split_manifest.split_id == second.split_manifest.split_id
    assert [item.validation_prediction_digest for item in first.evaluations] == [
        item.validation_prediction_digest for item in second.evaluations
    ]
    for left, right in zip(first.evaluations, second.evaluations, strict=True):
        assert left.validation_metrics == right.validation_metrics
        assert left.test_metrics == right.test_metrics


def test_validation_and_test_changes_do_not_change_fitted_candidate(
    synthetic_dataset: TrainingDataset,
) -> None:
    baseline = run_baselines(synthetic_dataset)
    manifest = baseline.split_manifest
    changed_train = synthetic_dataset.train_features.copy()
    validation_mask = changed_train["engine_id"].isin(manifest.validation.engine_ids)
    changed_train.loc[validation_mask, list(FEATURE_COLUMNS)] += 10_000.0
    changed_test = synthetic_dataset.test_features.copy()
    changed_test.loc[:, list(FEATURE_COLUMNS)] -= 10_000.0
    changed = replace(
        synthetic_dataset,
        train_features=changed_train,
        test_features=changed_test,
    )
    repeated = run_baselines(changed)

    for key in ("regression_candidate", "classification_candidate"):
        first_model = baseline.models[key]
        second_model = repeated.models[key]
        np.testing.assert_allclose(
            first_model["scaler"].mean_, second_model["scaler"].mean_
        )
        np.testing.assert_allclose(
            first_model["estimator"].coef_, second_model["estimator"].coef_
        )


def test_only_declared_features_reach_estimators(
    synthetic_dataset: TrainingDataset,
) -> None:
    result = run_baselines(synthetic_dataset)
    for key in ("regression_candidate", "classification_candidate"):
        assert tuple(result.models[key].feature_names_in_) == FEATURE_COLUMNS
        assert "engine_id" not in result.models[key].feature_names_in_
        assert "cycle" not in result.models[key].feature_names_in_


def test_classification_rejects_one_class_training(
    synthetic_dataset: TrainingDataset,
) -> None:
    targets = synthetic_dataset.train_targets.copy()
    targets["failure_risk_30"] = np.int8(1)
    with pytest.raises(ValueError, match="both classes"):
        run_baselines(replace(synthetic_dataset, train_targets=targets))


def test_model_input_frame_is_float64(synthetic_dataset: TrainingDataset) -> None:
    result = run_baselines(synthetic_dataset)
    example = synthetic_dataset.test_features.loc[:, list(FEATURE_COLUMNS)].copy()
    assert all(dtype == np.dtype("float64") for dtype in example.dtypes)
    assert np.isfinite(result.models["regression_candidate"].predict(example)).all()
