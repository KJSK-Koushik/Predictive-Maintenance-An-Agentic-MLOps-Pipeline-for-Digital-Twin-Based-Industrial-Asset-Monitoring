"""Deterministic aggregate monitoring metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from predictive_maintenance.modeling.metrics import (
    classification_metrics,
    regression_metrics,
)
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    ReferenceProfile,
    SignalResult,
    SignalStatus,
)
from predictive_maintenance.monitoring.reference import validate_feature_frame

_EPSILON = 1e-6


def _worst_status(statuses: Sequence[SignalStatus]) -> SignalStatus:
    order = {
        "pass": 0,
        "unavailable": 1,
        "insufficient_data": 2,
        "warning": 3,
        "alert": 4,
        "invalid": 5,
    }
    return max(statuses, key=order.__getitem__)


def data_quality_signal(frame: pd.DataFrame, policy: MonitoringPolicy) -> SignalResult:
    """Check quality and adequacy before any distribution metric."""
    try:
        validate_feature_frame(frame)
    except MonitoringError as error:
        return SignalResult("invalid", {}, (error.code,))
    row_count = len(frame)
    engine_count = int(frame["engine_id"].nunique())
    summary = {"row_count": row_count, "engine_count": engine_count}
    if row_count < policy.minimum_rows or engine_count < policy.minimum_engines:
        return SignalResult(
            "insufficient_data", summary, ("quality.insufficient_sample",)
        )
    return SignalResult("pass", summary)


def population_stability_index(
    reference_probabilities: Sequence[float], current_probabilities: Sequence[float]
) -> float:
    """Calculate finite PSI with a fixed small smoothing value."""
    reference = np.asarray(reference_probabilities, dtype="float64")
    current = np.asarray(current_probabilities, dtype="float64")
    if reference.shape != current.shape or reference.ndim != 1:
        raise MonitoringError("metric.shape_mismatch", "PSI vectors must align.")
    if not bool(np.isfinite(reference).all() and np.isfinite(current).all()):
        raise MonitoringError("metric.nonfinite", "PSI inputs must be finite.")
    reference = np.maximum(reference, _EPSILON)
    current = np.maximum(current, _EPSILON)
    reference /= reference.sum()
    current /= current.sum()
    return float(np.sum((current - reference) * np.log(current / reference)))


def _metric_status(
    psi: float, location: float, policy: MonitoringPolicy
) -> SignalStatus:
    if psi >= policy.alert_psi or location >= policy.alert_location_shift:
        return "alert"
    if psi >= policy.warning_psi or location >= policy.warning_location_shift:
        return "warning"
    return "pass"


def feature_shift_signal(
    frame: pd.DataFrame,
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
) -> SignalResult:
    """Measure all ordered inputs against bins fixed by the reference."""
    quality = data_quality_signal(frame, policy)
    if quality.status == "invalid":
        return SignalResult("invalid", {}, ("shift.blocked_by_quality",))
    if quality.status == "insufficient_data":
        return SignalResult("insufficient_data", {}, ("shift.insufficient_sample",))
    rows: list[dict[str, Any]] = []
    statuses: list[SignalStatus] = []
    for feature in reference.features:
        values = frame[feature.name].to_numpy(dtype="float64")
        counts, _ = np.histogram(
            values, bins=(-np.inf, *feature.quantile_edges, np.inf)
        )
        probabilities = counts.astype("float64") / counts.sum()
        psi = population_stability_index(feature.bin_probabilities, probabilities)
        scale = max(feature.iqr, _EPSILON)
        location = abs(float(np.median(values)) - feature.median) / scale
        outside = float(
            np.mean((values < feature.minimum) | (values > feature.maximum))
        )
        status = _metric_status(psi, location, policy)
        statuses.append(status)
        rows.append(
            {
                "feature": feature.name,
                "status": status,
                "psi": psi,
                "robust_location_shift": location,
                "outside_reference_range_fraction": outside,
            }
        )
    status = _worst_status(statuses)
    reasons = () if status == "pass" else (f"shift.feature_{status}",)
    return SignalResult(status, {"features": rows}, reasons)


def _distribution_summary(
    name: str,
    reference_values: np.ndarray,
    current_values: np.ndarray,
    policy: MonitoringPolicy,
) -> dict[str, Any]:
    edges = tuple(
        float(item)
        for item in np.unique(np.quantile(reference_values, np.linspace(0.1, 0.9, 9)))
    )
    reference_counts, _ = np.histogram(reference_values, bins=(-np.inf, *edges, np.inf))
    current_counts, _ = np.histogram(current_values, bins=(-np.inf, *edges, np.inf))
    reference_probabilities = reference_counts / reference_counts.sum()
    current_probabilities = current_counts / current_counts.sum()
    psi = population_stability_index(reference_probabilities, current_probabilities)
    iqr = float(
        np.quantile(reference_values, 0.75) - np.quantile(reference_values, 0.25)
    )
    location = abs(
        float(np.median(current_values)) - float(np.median(reference_values))
    ) / max(iqr, _EPSILON)
    return {
        "output": name,
        "status": _metric_status(psi, location, policy),
        "psi": psi,
        "robust_location_shift": location,
        "reference_median": float(np.median(reference_values)),
        "current_median": float(np.median(current_values)),
    }


def prediction_shift_signal(
    reference_predictions: pd.DataFrame,
    current_predictions: pd.DataFrame,
    policy: MonitoringPolicy,
) -> SignalResult:
    """Measure RUL, risk probability, and risk prevalence separately."""
    columns = (
        "engine_id",
        "cycle",
        "rul_cycles",
        "failure_risk_probability",
        "failure_risk_label",
    )
    for frame in (reference_predictions, current_predictions):
        if tuple(frame.columns) != columns or frame.empty:
            return SignalResult("invalid", {}, ("prediction.invalid_contract",))
        values = frame.loc[:, list(columns[2:])].to_numpy(dtype="float64")
        if not bool(np.isfinite(values).all()):
            return SignalResult("invalid", {}, ("prediction.nonfinite",))
    if (
        len(current_predictions) < policy.minimum_rows
        or current_predictions["engine_id"].nunique() < policy.minimum_engines
    ):
        return SignalResult(
            "insufficient_data", {}, ("prediction.insufficient_sample",)
        )
    summaries = [
        _distribution_summary(
            name,
            reference_predictions[name].to_numpy(dtype="float64"),
            current_predictions[name].to_numpy(dtype="float64"),
            policy,
        )
        for name in ("rul_cycles", "failure_risk_probability")
    ]
    prevalence_delta = abs(
        float(current_predictions["failure_risk_label"].mean())
        - float(reference_predictions["failure_risk_label"].mean())
    )
    prevalence_status: SignalStatus = (
        "alert"
        if prevalence_delta >= 0.25
        else "warning"
        if prevalence_delta >= 0.10
        else "pass"
    )
    summaries.append(
        {
            "output": "failure_risk_prevalence",
            "status": prevalence_status,
            "absolute_change": prevalence_delta,
        }
    )
    status = _worst_status([item["status"] for item in summaries])
    reasons = () if status == "pass" else (f"shift.prediction_{status}",)
    return SignalResult(status, {"outputs": summaries}, reasons)


def service_health_signal(
    *,
    readiness: bool,
    status_codes: Sequence[int],
    latencies_ms: Sequence[float],
) -> SignalResult:
    """Summarize bounded loopback probe evidence without an SLA claim."""
    if len(status_codes) != len(latencies_ms) or not status_codes:
        return SignalResult("unavailable", {}, ("service.no_probe_evidence",))
    latencies = np.asarray(latencies_ms, dtype="float64")
    if not bool(np.isfinite(latencies).all()) or bool((latencies < 0).any()):
        return SignalResult("invalid", {}, ("service.invalid_latency",))
    counts = {
        "2xx": sum(200 <= value < 300 for value in status_codes),
        "4xx": sum(400 <= value < 500 for value in status_codes),
        "5xx": sum(500 <= value < 600 for value in status_codes),
        "other": sum(not 200 <= value < 600 for value in status_codes),
    }
    summary: dict[str, Any] = {
        "scope": "bounded_loopback_probe_not_sla",
        "ready": readiness,
        "request_count": len(status_codes),
        "status_counts": counts,
        "latency_ms": {
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
            "max": float(np.max(latencies)),
        },
    }
    status: SignalStatus = "pass"
    reasons: tuple[str, ...] = ()
    if not readiness or counts["5xx"] or counts["other"]:
        status, reasons = "alert", ("service.probe_failed",)
    elif counts["4xx"]:
        status, reasons = "warning", ("service.client_error",)
    return SignalResult(status, summary, reasons)


def delayed_performance_signal(
    keys: pd.DataFrame,
    labels: pd.DataFrame | None,
    predictions: pd.DataFrame,
) -> SignalResult:
    """Calculate approved metrics only after exact key-aligned labels exist."""
    if labels is None:
        return SignalResult("unavailable", {}, ("performance.labels_unavailable",))
    expected_keys = ("engine_id", "cycle")
    if tuple(keys.columns) != expected_keys or bool(keys.duplicated().any()):
        return SignalResult("invalid", {}, ("performance.invalid_prediction_keys",))
    if tuple(labels.columns) != (*expected_keys, "rul", "failure_risk_30"):
        return SignalResult("invalid", {}, ("performance.invalid_label_contract",))
    if bool(labels.loc[:, list(expected_keys)].duplicated().any()):
        return SignalResult("invalid", {}, ("performance.duplicate_label_key",))
    if not keys.reset_index(drop=True).equals(
        labels.loc[:, list(expected_keys)].reset_index(drop=True)
    ):
        return SignalResult("invalid", {}, ("performance.label_key_mismatch",))
    if not keys.reset_index(drop=True).equals(
        predictions.loc[:, list(expected_keys)].reset_index(drop=True)
    ):
        return SignalResult("invalid", {}, ("performance.prediction_key_mismatch",))
    true_rul = labels["rul"].to_numpy(dtype="float64")
    true_risk = labels["failure_risk_30"].to_numpy(dtype="int64")
    predicted_rul = predictions["rul_cycles"].to_numpy(dtype="float64")
    probability = predictions["failure_risk_probability"].to_numpy(dtype="float64")
    if not bool(
        np.isfinite(true_rul).all()
        and np.isfinite(predicted_rul).all()
        and np.isfinite(probability).all()
    ):
        return SignalResult("invalid", {}, ("performance.nonfinite",))
    if len(np.unique(true_risk)) < 2:
        return SignalResult("insufficient_data", {}, ("performance.single_class",))
    try:
        regression = regression_metrics(
            keys, true_rul, predicted_rul, clipped_count=int((predicted_rul <= 0).sum())
        )
        classification = classification_metrics(keys, true_risk, probability)
    except ValueError:
        return SignalResult("invalid", {}, ("performance.invalid_prediction",))
    return SignalResult(
        "pass", {"regression": regression, "classification": classification}
    )


def degradation_status(
    performance: SignalResult,
    baseline: dict[str, float],
    policy: MonitoringPolicy,
) -> SignalStatus:
    """Compare available aggregate performance with fixed champion baselines."""
    if performance.status != "pass":
        return performance.status
    regression = performance.summary["regression"]
    classification = performance.summary["classification"]
    rmse_baseline = baseline.get("engine_balanced_rmse", math.nan)
    brier_baseline = baseline.get("engine_balanced_brier_score", math.nan)
    if not math.isfinite(rmse_baseline) or not math.isfinite(brier_baseline):
        return "invalid"
    rmse_ratio = regression["engine_balanced_rmse"] / max(rmse_baseline, _EPSILON)
    brier_delta = classification["engine_balanced_brier_score"] - brier_baseline
    if (
        rmse_ratio >= policy.performance_rmse_ratio_alert
        or brier_delta >= policy.performance_brier_delta_alert
    ):
        return "alert"
    return "pass"
