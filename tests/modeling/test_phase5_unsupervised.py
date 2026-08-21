"""Exploratory telemetry-state and novelty-score tests."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from predictive_maintenance.modeling.comparison import development_input_from_dataset
from predictive_maintenance.modeling.models import TrainingDataset
from predictive_maintenance.modeling.splitting import create_split_manifest
from predictive_maintenance.modeling.unsupervised import (
    cluster_telemetry,
    run_unsupervised_analysis,
    score_novelty,
)


def _data(dataset: TrainingDataset):  # type: ignore[no-untyped-def]
    return development_input_from_dataset(
        dataset, phase4_split_id=create_split_manifest(dataset).split_id
    )


def test_clustering_is_bounded_stable_and_honestly_named(
    synthetic_dataset: TrainingDataset,
) -> None:
    result = cluster_telemetry(_data(synthetic_dataset))
    assert result.sampled_rows == len(synthetic_dataset.train_features)
    assert result.maximum_rows_per_engine == 100
    assert 1 <= result.pca_components <= 24
    assert {item["cluster_count"] for item in result.candidates} == {2, 3, 4, 5, 6}
    assert "not_ground_truth" in result.claim
    if result.supported:
        assert result.selected_cluster_count in {2, 3, 4, 5, 6}
        assert result.lifecycle_association


def test_labels_do_not_select_clusters_or_fit_novelty(
    synthetic_dataset: TrainingDataset,
) -> None:
    data = _data(synthetic_dataset)
    changed_targets = data.targets.copy()
    changed_targets["rul"] = changed_targets["rul"] + 500
    changed_targets["failure_risk_30"] = np.int8(0)
    changed = replace(data, targets=changed_targets)

    first_cluster, first_novelty = run_unsupervised_analysis(data)
    second_cluster, second_novelty = run_unsupervised_analysis(changed)
    assert first_cluster.selected_cluster_count == second_cluster.selected_cluster_count
    assert first_cluster.candidates == second_cluster.candidates
    assert first_novelty == second_novelty


def test_novelty_uses_first_twenty_percent_and_reports_no_fake_accuracy(
    synthetic_dataset: TrainingDataset,
) -> None:
    result = score_novelty(_data(synthetic_dataset))
    assert result.early_lifecycle_fraction == 0.20
    assert result.reference_rows == 80
    assert set(result.lifecycle_scores) == {
        "early_0_20",
        "middle_20_80",
        "late_80_100",
    }
    serialized = str(result)
    assert "precision" not in serialized
    assert "recall" not in serialized
    assert "without_ground_truth" in result.claim
