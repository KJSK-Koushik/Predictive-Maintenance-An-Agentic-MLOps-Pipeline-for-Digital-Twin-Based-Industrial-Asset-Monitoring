"""Challenger evaluation and promotion-denial tests."""

from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from predictive_maintenance.monitoring.models import MonitoringError
from predictive_maintenance.monitoring.triggers import CandidateRequest
from predictive_maintenance.retraining.evaluation import (
    blocked_no_new_training_data,
    evaluate_challenger,
)


def _identity(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _request() -> CandidateRequest:
    return CandidateRequest(
        release_id=_identity("release"),
        policy_id=_identity("policy"),
        requested_task="both",
        data_cutoff_window_id=_identity("window"),
        evidence_report_ids=(_identity("report-one"), _identity("report-two")),
        reason="persistent_shift",
    )


def _evidence(challenger_factor: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "engine_id": [1, 2, 3, 4],
            "champion_regression_loss": [10.0, 12.0, 8.0, 9.0],
            "challenger_regression_loss": [
                value * challenger_factor for value in [10.0, 12.0, 8.0, 9.0]
            ],
            "champion_classification_loss": [0.20, 0.25, 0.18, 0.22],
            "challenger_classification_loss": [
                value * challenger_factor for value in [0.20, 0.25, 0.18, 0.22]
            ],
        }
    )


def test_passing_challenger_is_reviewable_not_promoted() -> None:
    result = evaluate_challenger(
        _request(),
        _evidence(0.8),
        challenger_artifact_sha256=_identity("challenger"),
        source_partition="validation",
    )
    assert result.outcome == "eligible_for_human_review"
    assert result.promotion_authority == "none"
    assert result.checks["promotion_path_absent"]
    assert result.regression_interval is not None
    assert result.regression_interval[0] >= 0.01
    assert result.evaluation_id == result.evaluation_id


def test_failing_and_identical_challengers_retain_champion() -> None:
    failing = evaluate_challenger(
        _request(),
        _evidence(1.2),
        challenger_artifact_sha256=_identity("bad"),
        source_partition="validation",
    )
    unchanged = evaluate_challenger(
        _request(),
        _evidence(1.0),
        challenger_artifact_sha256=_identity("same"),
        source_partition="validation",
    )
    assert failing.outcome == "retain_champion"
    assert unchanged.outcome == "no_change"
    assert failing.champion_release_id == _request().release_id


def test_whole_engine_bootstrap_is_reproducible_and_gate_failure_is_contained() -> None:
    first = evaluate_challenger(
        _request(),
        _evidence(0.8),
        challenger_artifact_sha256=_identity("challenger"),
        source_partition="validation",
    )
    repeated = evaluate_challenger(
        _request(),
        _evidence(0.8),
        challenger_artifact_sha256=_identity("challenger"),
        source_partition="validation",
    )
    contained = evaluate_challenger(
        _request(),
        _evidence(0.8),
        challenger_artifact_sha256=_identity("challenger"),
        source_partition="validation",
        gate_checks={"security": False},
    )
    assert first.regression_interval == repeated.regression_interval
    assert first.classification_interval == repeated.classification_interval
    assert first.evaluation_id == repeated.evaluation_id
    assert contained.outcome == "retain_champion"
    assert contained.promotion_authority == "none"
    assert not contained.checks["security"]


def test_nasa_test_rows_are_prohibited_from_fitting() -> None:
    with pytest.raises(MonitoringError, match=r"evaluation\.test_fit_prohibited"):
        evaluate_challenger(
            _request(),
            _evidence(0.8),
            challenger_artifact_sha256=_identity("challenger"),
            source_partition="test",
        )


def test_actual_path_can_block_without_new_training_data() -> None:
    result = blocked_no_new_training_data(_request())
    assert result.outcome == "blocked_no_new_training_data"
    assert result.challenger_artifact_sha256 is None
    assert not result.checks["new_training_population"]
    assert result.promotion_authority == "none"
