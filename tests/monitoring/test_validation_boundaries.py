"""Reject malformed monitoring evidence at contract and metric boundaries."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd
import pytest
from phase7_support import prediction_frame, telemetry_frame

from predictive_maintenance.monitoring.metrics import (
    degradation_status,
    delayed_performance_signal,
    feature_shift_signal,
    population_stability_index,
    prediction_shift_signal,
)
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    ReferenceProfile,
    SignalResult,
    canonical_json_bytes,
)
from predictive_maintenance.monitoring.reference import (
    engine_balanced_sample,
    lifecycle_mix,
    validate_feature_frame,
)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_canonical_json_rejects_nonfinite_and_unserializable(value: object) -> None:
    with pytest.raises(MonitoringError, match=r"monitoring\.invalid_json"):
        canonical_json_bytes({"value": value})


@pytest.mark.parametrize(
    "change, code",
    [
        ({"minimum_rows": 0}, "invalid_adequacy"),
        ({"minimum_engines": 0}, "invalid_adequacy"),
        ({"max_rows_per_engine": 0}, "invalid_sampling"),
        ({"alert_psi": float("nan")}, "invalid_threshold"),
        ({"warning_location_shift": 2.0}, "invalid_threshold"),
        ({"persistent_drift_windows": 1}, "invalid_persistence"),
    ],
)
def test_policy_rejects_unsafe_thresholds(change: dict[str, Any], code: str) -> None:
    with pytest.raises(MonitoringError, match=code):
        MonitoringPolicy(**change)


@pytest.mark.parametrize(
    "change, code",
    [
        ({"name": "unknown"}, "unknown_feature"),
        ({"median": float("inf")}, "nonfinite"),
        ({"quantile_edges": (2.0, 1.0)}, "invalid_bins"),
        ({"bin_probabilities": (1.0,)}, "invalid_bins"),
        ({"bin_probabilities": (0.0,) * 10}, "invalid_bins"),
    ],
)
def test_feature_reference_rejects_invalid_bins(
    reference: ReferenceProfile, change: dict[str, Any], code: str
) -> None:
    with pytest.raises(MonitoringError, match=code):
        replace(reference.features[0], **change)


@pytest.mark.parametrize(
    "change, code",
    [
        ({"features": ()}, "feature_order"),
        ({"row_count": 1}, "invalid_counts"),
        ({"code_revision": ""}, "invalid_revision"),
    ],
)
def test_reference_rejects_inconsistent_metadata(
    reference: ReferenceProfile, change: dict[str, Any], code: str
) -> None:
    with pytest.raises(MonitoringError, match=code):
        replace(reference, **change)


@pytest.mark.parametrize(
    "change, code",
    [
        ({"status": "healthy"}, "invalid_status"),
        ({"reason_codes": ("private/url",)}, "invalid_reason"),
        ({"reason_codes": ("test.reason",) * 51}, "invalid_reason"),
        ({"summary": {"payload": "a" * 256_001}}, "summary_too_large"),
    ],
)
def test_signal_bounds(change: dict[str, Any], code: str) -> None:
    with pytest.raises(MonitoringError, match=code):
        replace(SignalResult("pass", {}), **change)


def test_error_codes_are_identifiers_and_messages_are_bounded() -> None:
    with pytest.raises(ValueError, match="stable identifiers"):
        MonitoringError("https://private", "bad")
    error = MonitoringError("test.bounded", "a" * 2000)
    assert len(error.to_dict()["message"]) == 1000


@pytest.mark.parametrize("column,value", [("engine_id", 0), ("cycle", 1.5)])
def test_nonpositive_and_fractional_row_keys_fail(column: str, value: float) -> None:
    frame = telemetry_frame().astype({column: "float64"})
    frame.loc[0, column] = value
    with pytest.raises(MonitoringError, match=r"quality\.invalid_key"):
        validate_feature_frame(frame)


def test_empty_nonfinite_and_invalid_sample_size_fail() -> None:
    frame = telemetry_frame()
    with pytest.raises(MonitoringError, match=r"quality\.empty_window"):
        validate_feature_frame(frame.iloc[:0])
    with pytest.raises(MonitoringError, match=r"quality\.nonfinite"):
        validate_feature_frame(frame.assign(sensor_1=np.inf))
    with pytest.raises(MonitoringError, match=r"reference\.invalid_sampling"):
        engine_balanced_sample(frame, 0)
    with pytest.raises(MonitoringError, match=r"quality\.nonfinite_label"):
        lifecycle_mix(frame.assign(rul=np.inf))


@pytest.mark.parametrize(
    "left,right,code",
    [([1.0], [0.5, 0.5], "shape_mismatch"), ([np.nan], [1.0], "nonfinite")],
)
def test_psi_rejects_unaligned_or_nonfinite_inputs(
    left: list[float], right: list[float], code: str
) -> None:
    with pytest.raises(MonitoringError, match=code):
        population_stability_index(left, right)


def test_insufficient_windows_do_not_report_shift(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    small = telemetry_frame().iloc[:1]
    assert feature_shift_signal(small, reference, policy).status == "insufficient_data"
    predictions = prediction_frame(small)
    assert (
        prediction_shift_signal(predictions, predictions, policy).status
        == "insufficient_data"
    )
    assert (
        prediction_shift_signal(predictions, pd.DataFrame(), policy).status == "invalid"
    )
    assert (
        prediction_shift_signal(
            predictions, predictions.assign(rul_cycles=np.inf), policy
        ).status
        == "invalid"
    )


@pytest.mark.parametrize(
    "case,reason",
    [
        ("keys", "invalid_prediction_keys"),
        ("contract", "invalid_label_contract"),
        ("duplicate", "duplicate_label_key"),
        ("prediction", "prediction_key_mismatch"),
        ("nonfinite", "nonfinite"),
        ("single_class", "single_class"),
    ],
)
def test_delayed_labels_reject_incomplete_or_misaligned_evidence(
    case: str, reason: str
) -> None:
    frame = telemetry_frame()
    predictions = prediction_frame(frame)
    keys = frame.loc[:, ["engine_id", "cycle"]].copy()
    labels = keys.assign(
        rul=predictions.rul_cycles, failure_risk_30=predictions.failure_risk_label
    )
    if case == "keys":
        keys = keys.rename(columns={"cycle": "wrong"})
    elif case == "contract":
        labels = labels.drop(columns="rul")
    elif case == "duplicate":
        labels.at[1, "engine_id"] = labels.at[0, "engine_id"]
        labels.at[1, "cycle"] = labels.at[0, "cycle"]
    elif case == "prediction":
        predictions.loc[0, "cycle"] = 999
    elif case == "nonfinite":
        labels.loc[0, "rul"] = np.inf
    else:
        labels["failure_risk_30"] = 0
    signal = delayed_performance_signal(keys, labels, predictions)
    assert signal.reason_codes == (f"performance.{reason}",)
    assert signal.status in {"invalid", "insufficient_data"}


def test_degradation_requires_fixed_baselines_and_available_labels() -> None:
    policy = MonitoringPolicy()
    available = SignalResult(
        "pass",
        {
            "regression": {"engine_balanced_rmse": 12.0},
            "classification": {"engine_balanced_brier_score": 0.1},
        },
    )
    assert (
        degradation_status(SignalResult("unavailable", {}), {}, policy) == "unavailable"
    )
    assert degradation_status(available, {}, policy) == "invalid"
    assert (
        degradation_status(
            available,
            {"engine_balanced_rmse": 10.0, "engine_balanced_brier_score": 0.1},
            policy,
        )
        == "alert"
    )
    assert (
        degradation_status(
            available,
            {"engine_balanced_rmse": 12.0, "engine_balanced_brier_score": 0.1},
            policy,
        )
        == "pass"
    )
