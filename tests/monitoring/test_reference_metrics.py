"""Reference, quality, shift, service, and delayed-label tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from phase7_support import identity, prediction_frame, telemetry_frame

from predictive_maintenance.monitoring.metrics import (
    data_quality_signal,
    delayed_performance_signal,
    feature_shift_signal,
    population_stability_index,
    prediction_shift_signal,
    service_health_signal,
)
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    ReferenceProfile,
)
from predictive_maintenance.monitoring.reference import (
    build_reference_profile,
    engine_balanced_sample,
    reference_from_dict,
    validate_feature_frame,
)
from predictive_maintenance.release.models import FEATURE_COLUMNS


def test_reference_is_deterministic_and_round_trips(
    reference_frame: pd.DataFrame, policy: MonitoringPolicy, reference: ReferenceProfile
) -> None:
    repeated = build_reference_profile(
        reference_frame,
        release_id=identity("release"),
        feature_snapshot_id=identity("feature"),
        policy=policy,
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
    assert repeated.reference_id == reference.reference_id
    assert repeated.canonical_bytes() == reference.canonical_bytes()
    assert reference_from_dict(reference.to_dict()) == reference
    assert tuple(item.name for item in reference.features) == FEATURE_COLUMNS


def test_reference_identity_changes_with_policy(reference_frame: pd.DataFrame) -> None:
    first = MonitoringPolicy()
    second = replace(first, alert_psi=0.30)
    one = build_reference_profile(
        reference_frame,
        release_id=identity("release"),
        feature_snapshot_id=identity("feature"),
        policy=first,
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
    two = build_reference_profile(
        reference_frame,
        release_id=identity("release"),
        feature_snapshot_id=identity("feature"),
        policy=second,
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
    assert one.reference_id != two.reference_id


def test_engine_balanced_sample_bounds_each_engine() -> None:
    frame = telemetry_frame()
    sample = engine_balanced_sample(frame, 4)
    assert sample.groupby("engine_id").size().to_dict() == {1: 4, 2: 4, 3: 4}
    assert sample.groupby("engine_id")["cycle"].agg(list).to_dict() == {
        1: [1, 7, 13, 20],
        2: [1, 7, 13, 20],
        3: [1, 7, 13, 20],
    }


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda frame: frame.drop(columns="sensor_21"), "quality.schema_mismatch"),
        (
            lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            "quality.duplicate_key",
        ),
        (
            lambda frame: frame.assign(sensor_1=np.nan),
            "quality.missing_value",
        ),
        (
            lambda frame: frame.sort_values("cycle", ascending=False),
            "quality.cycle_order",
        ),
    ],
)
def test_feature_contract_fails_closed(
    mutator: Callable[[pd.DataFrame], pd.DataFrame], code: str
) -> None:
    with pytest.raises(MonitoringError, match=code):
        validate_feature_frame(mutator(telemetry_frame()))


def test_quality_distinguishes_invalid_insufficient_and_pass(
    policy: MonitoringPolicy,
) -> None:
    assert data_quality_signal(telemetry_frame(), policy).status == "pass"
    small = telemetry_frame().query("engine_id == 1").iloc[:2]
    assert data_quality_signal(small, policy).status == "insufficient_data"
    assert (
        data_quality_signal(telemetry_frame().drop(columns="sensor_1"), policy).status
        == "invalid"
    )


def test_known_psi_matches_formula() -> None:
    result = population_stability_index([0.5, 0.5], [0.75, 0.25])
    expected = 0.25 * np.log(1.5) - 0.25 * np.log(0.5)
    assert result == pytest.approx(expected)


def test_feature_and_prediction_shift_are_separate(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    unchanged = telemetry_frame()
    shifted = telemetry_frame(shift=5.0)
    assert feature_shift_signal(unchanged, reference, policy).status == "pass"
    feature_result = feature_shift_signal(shifted, reference, policy)
    assert feature_result.status == "alert"
    assert len(feature_result.summary["features"]) == 24
    reference_predictions = prediction_frame(unchanged)
    current_predictions = prediction_frame(unchanged, shift=15.0)
    prediction_result = prediction_shift_signal(
        reference_predictions, current_predictions, policy
    )
    assert prediction_result.status in {"warning", "alert"}
    assert {item["output"] for item in prediction_result.summary["outputs"]} == {
        "rul_cycles",
        "failure_risk_probability",
        "failure_risk_prevalence",
    }


def test_invalid_quality_blocks_feature_shift(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    invalid = telemetry_frame().drop(columns="sensor_1")
    result = feature_shift_signal(invalid, reference, policy)
    assert result.status == "invalid"
    assert result.reason_codes == ("shift.blocked_by_quality",)


def test_service_probe_summary_and_failure() -> None:
    passing = service_health_signal(
        readiness=True, status_codes=[200, 200, 204], latencies_ms=[1, 3, 2]
    )
    assert passing.status == "pass"
    assert passing.summary["latency_ms"] == {"p50": 2.0, "p95": 2.9, "max": 3.0}
    assert "sla" in passing.summary["scope"]
    assert (
        service_health_signal(
            readiness=False, status_codes=[503], latencies_ms=[4]
        ).status
        == "alert"
    )
    assert (
        service_health_signal(readiness=True, status_codes=[], latencies_ms=[]).status
        == "unavailable"
    )
    assert (
        service_health_signal(
            readiness=True, status_codes=[422], latencies_ms=[2.0]
        ).status
        == "warning"
    )
    assert (
        service_health_signal(
            readiness=True, status_codes=[200], latencies_ms=[float("nan")]
        ).status
        == "invalid"
    )


def test_delayed_performance_requires_exact_aligned_labels() -> None:
    frame = telemetry_frame()
    predictions = prediction_frame(frame)
    keys = frame.loc[:, ["engine_id", "cycle"]]
    assert delayed_performance_signal(keys, None, predictions).status == "unavailable"
    labels = keys.copy()
    labels["rul"] = predictions["rul_cycles"]
    labels["failure_risk_30"] = predictions["failure_risk_label"]
    available = delayed_performance_signal(keys, labels, predictions)
    assert available.status == "pass"
    assert available.summary["regression"]["engine_balanced_rmse"] == 0.0
    mismatched = labels.copy()
    mismatched.loc[0, "cycle"] = 999
    assert delayed_performance_signal(keys, mismatched, predictions).status == "invalid"


def test_invalid_policies_and_reference_identity_fail() -> None:
    with pytest.raises(MonitoringError, match=r"policy\.invalid_threshold"):
        MonitoringPolicy(warning_psi=0.5, alert_psi=0.2)
    reference = build_reference_profile(
        telemetry_frame(),
        release_id=identity("release"),
        feature_snapshot_id=identity("feature"),
        policy=MonitoringPolicy(),
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
    value = reference.to_dict()
    value["reference_id"] = identity("wrong")
    with pytest.raises(MonitoringError, match=r"reference\.identity_mismatch"):
        reference_from_dict(value)
