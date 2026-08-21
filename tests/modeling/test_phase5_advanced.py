"""Phase 5 nested-fold and bounded-search contract tests."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from predictive_maintenance.modeling.advanced import (
    DevelopmentInput,
    advanced_model,
    create_comparison_manifest,
    feature_matrix,
    parameter_grid,
    tune_parameters,
)
from predictive_maintenance.modeling.models import FEATURE_COLUMNS, TrainingDataset
from predictive_maintenance.modeling.splitting import create_split_manifest


def _development(dataset: TrainingDataset) -> DevelopmentInput:
    return DevelopmentInput(
        dataset.raw_snapshot_id,
        dataset.processed_snapshot_id,
        dataset.feature_snapshot_id,
        create_split_manifest(dataset).split_id,
        dataset.train_features.copy(),
        dataset.train_targets.copy(),
    )


def test_nested_manifest_is_deterministic_disjoint_and_complete(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _development(synthetic_dataset)
    first = create_comparison_manifest(data)
    second = create_comparison_manifest(data)

    assert first.canonical_bytes() == second.canonical_bytes()
    assert len(first.outer_folds) == 5
    assert len(first.final_inner_folds) == 4
    held_out: list[int] = []
    for outer in first.outer_folds:
        assert not set(outer.train_engine_ids) & set(outer.validation_engine_ids)
        assert len(outer.inner_folds) == 4
        held_out.extend(outer.validation_engine_ids)
        for inner in outer.inner_folds:
            assert not set(inner.train_engine_ids) & set(inner.validation_engine_ids)
            assert set(inner.train_engine_ids) | set(
                inner.validation_engine_ids
            ) == set(outer.train_engine_ids)
    assert sorted(held_out) == list(first.engine_ids)


def test_manifest_membership_ignores_row_order(
    synthetic_dataset: TrainingDataset,
) -> None:
    original = _development(synthetic_dataset)
    shuffled = replace(
        original,
        features=original.features.sample(frac=1, random_state=9).reset_index(
            drop=True
        ),
        targets=original.targets.sample(frac=1, random_state=9).reset_index(drop=True),
    )
    assert (
        create_comparison_manifest(original).comparison_id
        == create_comparison_manifest(shuffled).comparison_id
    )


def test_development_boundary_has_no_benchmark_fields(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _development(synthetic_dataset)
    assert not hasattr(data, "test_features")
    assert not hasattr(data, "test_targets")
    assert tuple(feature_matrix(data.features).columns) == FEATURE_COLUMNS


def test_search_spaces_are_finite_and_estimators_reject_unknown_parameters() -> None:
    for task in ("regression", "classification"):
        grid = parameter_grid(task)
        assert len(grid) == 8
        assert len(grid) <= 12
        assert advanced_model(task, grid[0]).get_params()["early_stopping"] is False
        with pytest.raises(Exception, match="parameters are invalid"):
            advanced_model(task, {"unknown": 1})


def test_tuning_is_deterministic(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _development(synthetic_dataset)
    manifest = create_comparison_manifest(data)
    first = tune_parameters(data, "regression", manifest.final_inner_folds)
    second = tune_parameters(data, "regression", manifest.final_inner_folds)
    assert first == second


def test_manifest_rejects_key_mismatch_and_insufficient_engines(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _development(synthetic_dataset)
    wrong_targets = data.targets.copy()
    wrong_targets.loc[0, "cycle"] = 999
    with pytest.raises(Exception, match="keys differ"):
        create_comparison_manifest(replace(data, targets=wrong_targets))

    small_features = data.features.query("engine_id <= 4").reset_index(drop=True)
    small_targets = data.targets.query("engine_id <= 4").reset_index(drop=True)
    with pytest.raises(Exception, match="Not enough"):
        create_comparison_manifest(
            replace(data, features=small_features, targets=small_targets)
        )


def test_feature_matrix_rejects_missing_and_non_finite_values(
    synthetic_dataset: TrainingDataset,
) -> None:
    frame = synthetic_dataset.train_features.copy()
    with pytest.raises(Exception, match="columns are missing"):
        feature_matrix(frame.drop(columns=[FEATURE_COLUMNS[0]]))
    frame.loc[0, FEATURE_COLUMNS[0]] = float("inf")
    with pytest.raises(Exception, match="finite"):
        feature_matrix(frame)


def test_manifest_identity_changes_with_parent_split(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _development(synthetic_dataset)
    changed = replace(data, phase4_split_id="f" * 64)
    assert (
        create_comparison_manifest(data).comparison_id
        != create_comparison_manifest(changed).comparison_id
    )


def test_row_order_change_must_keep_feature_target_keys_aligned(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _development(synthetic_dataset)
    features = data.features.sort_values(["cycle", "engine_id"]).reset_index(drop=True)
    targets = data.targets.sort_values(["cycle", "engine_id"]).reset_index(drop=True)
    reordered = replace(data, features=features, targets=targets)
    assert isinstance(create_comparison_manifest(reordered).to_dict(), dict)
    assert isinstance(feature_matrix(features), pd.DataFrame)
