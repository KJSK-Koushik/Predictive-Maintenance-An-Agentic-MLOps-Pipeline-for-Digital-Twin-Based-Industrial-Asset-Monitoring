"""Phase 5 comparison, uncertainty, selection, and benchmark tests."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from predictive_maintenance.modeling.comparison import (
    SupervisedDevelopment,
    _complexity_gate,
    _whole_engine_bootstrap,
    development_input_from_dataset,
    run_locked_benchmark,
    run_supervised_development,
    selection_from_bytes,
)
from predictive_maintenance.modeling.models import TrainingDataset
from predictive_maintenance.modeling.phase5_models import (
    BOOTSTRAP_SAMPLES,
    BootstrapInterval,
)
from predictive_maintenance.modeling.splitting import create_split_manifest


@pytest.fixture(scope="module")
def supervised_result(
    synthetic_dataset: TrainingDataset,
) -> tuple[str, SupervisedDevelopment]:
    split_id = create_split_manifest(synthetic_dataset).split_id
    data = development_input_from_dataset(synthetic_dataset, phase4_split_id=split_id)
    return split_id, run_supervised_development(data)


def test_whole_engine_bootstrap_detects_clear_regression_improvement(
    synthetic_dataset: TrainingDataset,
) -> None:
    keys = synthetic_dataset.train_features.loc[:, ["engine_id", "cycle"]]
    target = synthetic_dataset.train_targets["rul"].to_numpy(dtype="float64")
    baseline = target + 10.0
    advanced = target.copy()
    interval = _whole_engine_bootstrap("regression", keys, target, baseline, advanced)
    assert interval.samples == BOOTSTRAP_SAMPLES
    assert interval.point_improvement == pytest.approx(10.0)
    assert interval.lower_95 > 0.0
    assert "evaluation_uncertainty" in interval.uncertainty_kind


def test_complete_development_retains_baseline_when_complexity_is_not_justified(
    synthetic_dataset: TrainingDataset,
    supervised_result: tuple[str, SupervisedDevelopment],
) -> None:
    split_id, result = supervised_result

    assert result.manifest.row_count == len(synthetic_dataset.train_features)
    assert result.selection.locked
    assert result.selection.test_exposure_status == "previously_observed_in_phase_4"
    assert len(result.comparisons) == 2
    for comparison in result.comparisons:
        assert len(comparison.outer_selected_parameters) == 5
        assert comparison.preferred_model in {"baseline", "advanced"}
        assert len(comparison.baseline_coefficients) == 24
        assert len(comparison.advanced_permutation_importance) == 24
        assert len(comparison.error_analysis["worst_engines"]) <= 5
        assert comparison.error_analysis["lifecycle_bands"]
        assert comparison.interval.samples == 2_000
    assert any(item.preferred_model == "baseline" for item in result.comparisons)

    benchmark = run_locked_benchmark(
        synthetic_dataset, result.selection, phase4_split_id=split_id
    )
    assert benchmark.selection_id == result.selection.selection_id
    assert len(benchmark.evaluations) == 2
    assert set(benchmark.models) == {
        "regression_selected",
        "classification_selected",
    }


def test_selection_round_trip_and_tamper_detection(
    supervised_result: tuple[str, SupervisedDevelopment],
) -> None:
    _, result = supervised_result
    restored = selection_from_bytes(result.selection.canonical_bytes())
    assert restored.selection_id == result.selection.selection_id

    tampered = json.loads(result.selection.canonical_bytes())
    tampered["regression_model"] = "advanced"
    with pytest.raises(Exception, match="identity"):
        selection_from_bytes(json.dumps(tampered).encode())
    with pytest.raises(Exception, match="valid JSON"):
        selection_from_bytes(b"not-json")


def test_complexity_gates_apply_exact_boundaries() -> None:
    regression = _complexity_gate(
        "regression",
        {
            "engine_balanced_rmse": 10.0,
            "engine_balanced_mae": 8.0,
            "engine_balanced_nasa_score": 20.0,
        },
        {
            "engine_balanced_mae": 8.4,
            "engine_balanced_nasa_score": 21.0,
        },
        BootstrapInterval(0.3, 0.001, 0.6),
    )
    assert all(regression.values())

    classification = _complexity_gate(
        "classification",
        {"engine_balanced_brier_score": 0.20},
        {"engine_balanced_brier_score": 0.21},
        BootstrapInterval(0.005, 0.001, 0.01),
    )
    assert all(classification.values())
    failed = _complexity_gate(
        "classification",
        {"engine_balanced_brier_score": 0.20},
        {"engine_balanced_brier_score": 0.211},
        BootstrapInterval(0.005, 0.0, 0.01),
    )
    assert not failed["interval_above_zero"]
    assert not failed["brier_non_inferior"]


def test_benchmark_rejects_unlocked_or_wrong_provenance(
    synthetic_dataset: TrainingDataset,
    supervised_result: tuple[str, SupervisedDevelopment],
) -> None:
    split_id, result = supervised_result
    with pytest.raises(Exception, match="locked"):
        run_locked_benchmark(
            synthetic_dataset,
            replace(result.selection, locked=False),
            phase4_split_id=split_id,
        )
    with pytest.raises(Exception, match="does not match"):
        run_locked_benchmark(
            synthetic_dataset,
            replace(result.selection, feature_snapshot_id="f" * 64),
            phase4_split_id=split_id,
        )
    with pytest.raises(Exception, match="comparison manifest"):
        run_locked_benchmark(
            synthetic_dataset,
            replace(result.selection, comparison_id="f" * 64),
            phase4_split_id=split_id,
        )


def test_development_selection_does_not_depend_on_changed_benchmark_targets(
    synthetic_dataset: TrainingDataset,
) -> None:
    split_id = create_split_manifest(synthetic_dataset).split_id
    first_input = development_input_from_dataset(
        synthetic_dataset, phase4_split_id=split_id
    )
    changed_test = synthetic_dataset.test_targets.copy()
    changed_test["rul"] = changed_test["rul"] + 100
    changed_test["failure_risk_30"] = np.int8(0)
    changed_dataset = replace(synthetic_dataset, test_targets=changed_test)
    second_input = development_input_from_dataset(
        changed_dataset, phase4_split_id=split_id
    )
    assert first_input.features.equals(second_input.features)
    assert first_input.targets.equals(second_input.targets)
