"""Challenger evaluation and promotion-denial tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

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
    rows = []
    for engine in range(1, 5):
        for cycle, rul in enumerate([70, 60, 50, 40, 30, 20, 10, 0], start=1):
            risk = int(rul <= 30)
            probability = [0.1, 0.2, 0.65, 0.7, 0.5, 0.6, 0.8, 0.9][cycle - 1]
            challenger_probability = max(
                0.0,
                min(
                    1.0,
                    probability + 3 * (1 - challenger_factor) * (risk - probability),
                ),
            )
            rows.append(
                {
                    "engine_id": engine,
                    "cycle": cycle,
                    "rul": float(rul),
                    "failure_risk_30": risk,
                    "champion_rul_cycles": rul + 10.0,
                    "challenger_rul_cycles": rul + 10.0 * challenger_factor,
                    "champion_failure_risk_probability": probability,
                    "challenger_failure_risk_probability": challenger_probability,
                }
            )
    return pd.DataFrame(rows)


def _passing_checks() -> dict[str, bool]:
    """Explicit synthetic gate evidence; omitted checks must never pass."""
    return dict.fromkeys(
        (
            "data_contract",
            "leakage_control",
            "reproducibility",
            "feature_contract",
            "signature_contract",
            "trusted_type",
            "performance",
            "robustness",
            "security",
            "release_compatibility",
            "prediction_parity",
        ),
        True,
    )


def test_passing_challenger_is_reviewable_not_promoted() -> None:
    result = evaluate_challenger(
        _request(),
        _evidence(0.8),
        challenger_artifact_sha256=_identity("challenger"),
        source_partition="validation",
        gate_checks=_passing_checks(),
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


def test_missing_gate_evidence_cannot_make_improved_challenger_eligible() -> None:
    result = evaluate_challenger(
        _request(),
        _evidence(0.8),
        challenger_artifact_sha256=_identity("challenger"),
        source_partition="validation",
    )
    assert result.outcome == "retain_champion"
    assert not result.checks["security"]
    assert not result.checks["trusted_type"]


@pytest.mark.parametrize(
    "change,code",
    [
        ({"source_partition": "test"}, "invalid_partition"),
        ({"promotion_authority": "deploy"}, "invalid_authority"),
        ({"regression_improvement": float("inf")}, "nonfinite"),
        ({"regression_interval": (1.0, 0.0)}, "invalid_interval"),
        ({"classification_interval": (float("nan"), 0.0)}, "invalid_interval"),
        ({"checks": {}}, "invalid_checks"),
        ({"checks": {"security": 1}}, "invalid_checks"),
        ({"bootstrap_seed": 7}, "invalid_bootstrap"),
    ],
)
def test_evaluation_contract_rejects_invalid_handoffs(
    change: dict[str, Any], code: str
) -> None:
    with pytest.raises(MonitoringError, match=code):
        replace(blocked_no_new_training_data(_request()), **change)


@pytest.mark.parametrize(
    "case,code",
    [
        ("schema", "invalid_contract"),
        ("duplicate", "duplicate_key"),
        ("nonfinite", "invalid_loss"),
        ("negative", "invalid_loss"),
        ("unknown_check", "unknown_check"),
    ],
)
def test_invalid_challenger_evidence_fails_before_handoff(case: str, code: str) -> None:
    evidence = _evidence(0.8)
    checks: dict[str, bool] = {}
    if case == "schema":
        evidence = evidence.drop(columns="champion_rul_cycles")
    elif case == "duplicate":
        evidence.loc[1, "cycle"] = 1
    elif case == "nonfinite":
        evidence.loc[0, "champion_rul_cycles"] = float("inf")
    elif case == "negative":
        evidence.loc[0, "challenger_rul_cycles"] = -1
    else:
        checks["unknown"] = True
    with pytest.raises(MonitoringError, match=code):
        evaluate_challenger(
            _request(),
            evidence,
            challenger_artifact_sha256=_identity("challenger"),
            source_partition="validation",
            gate_checks=checks,
        )
