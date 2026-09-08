"""Direct deterministic monitoring workflow without cloud or Airflow dependencies."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from predictive_maintenance.monitoring.metrics import (
    data_quality_signal,
    delayed_performance_signal,
    feature_shift_signal,
    prediction_shift_signal,
    service_health_signal,
)
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    MonitoringReport,
    MonitoringWindow,
    ReferenceProfile,
    SignalResult,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.monitoring.reference import (
    KEY_COLUMNS,
    lifecycle_mix,
    operating_setting_summary,
)

DEFAULT_LIMITATIONS = (
    "FD001 is static simulated telemetry replay, not live or field telemetry.",
    "Distribution shift does not by itself prove model degradation or a fault.",
    "Loopback probes are bounded service evidence, not production availability.",
)


def membership_sha256(frame: pd.DataFrame, source_partition: str) -> str:
    """Hash ordered partition, engine, and cycle membership without telemetry values."""
    rows = [
        {
            "source_partition": source_partition,
            "engine_id": int(engine_id),
            "cycle": int(cycle),
            "replay_position": position,
        }
        for position, (engine_id, cycle) in enumerate(
            frame.loc[:, list(KEY_COLUMNS)].itertuples(index=False, name=None), start=1
        )
    ]
    return sha256_bytes(canonical_json_bytes(rows))


def create_window(
    frame: pd.DataFrame,
    *,
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
    raw_snapshot_id: str,
    processed_snapshot_id: str,
    feature_snapshot_id: str,
    source_partition: str,
    replay_sequence: int,
    code_revision: str,
    dependency_lock_sha256: str,
) -> MonitoringWindow:
    """Create immutable window lineage independently of processing time."""
    if source_partition not in {"train", "validation", "test", "synthetic"}:
        raise MonitoringError(
            "window.invalid_partition", "Source partition is not supported."
        )
    return MonitoringWindow(
        release_id=reference.release_id,
        reference_id=reference.reference_id,
        policy_id=policy.policy_id,
        raw_snapshot_id=raw_snapshot_id,
        processed_snapshot_id=processed_snapshot_id,
        feature_snapshot_id=feature_snapshot_id,
        source_partition=source_partition,  # type: ignore[arg-type]
        membership_sha256=membership_sha256(frame, source_partition),
        row_count=len(frame),
        engine_count=int(frame["engine_id"].nunique()),
        replay_sequence=replay_sequence,
        code_revision=code_revision,
        dependency_lock_sha256=dependency_lock_sha256,
    )


def build_monitoring_report(
    frame: pd.DataFrame,
    current_predictions: pd.DataFrame,
    reference_predictions: pd.DataFrame,
    *,
    window: MonitoringWindow,
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
    service_evidence: dict[str, Any] | None = None,
) -> MonitoringReport:
    """Evaluate a window while keeping every signal class separate."""
    if (
        window.reference_id != reference.reference_id
        or window.policy_id != policy.policy_id
    ):
        raise MonitoringError(
            "pipeline.lineage_mismatch", "Window, reference, and policy do not align."
        )
    expected_membership = membership_sha256(frame, window.source_partition)
    if expected_membership != window.membership_sha256:
        raise MonitoringError(
            "pipeline.membership_mismatch", "Window membership changed after creation."
        )
    quality = data_quality_signal(frame, policy)
    if quality.status == "invalid":
        blocked = SignalResult("invalid", {}, ("monitoring.blocked_by_quality",))
        feature_shift = blocked
        prediction_shift = blocked
        performance = SignalResult(
            "unavailable", {}, ("performance.blocked_by_quality",)
        )
    else:
        feature_shift = feature_shift_signal(frame, reference, policy)
        current_keys = (
            current_predictions.loc[:, list(KEY_COLUMNS)]
            if all(name in current_predictions for name in KEY_COLUMNS)
            else pd.DataFrame()
        )
        expected_keys = frame.loc[:, list(KEY_COLUMNS)].reset_index(drop=True)
        if current_keys.empty or not expected_keys.equals(
            current_keys.reset_index(drop=True)
        ):
            prediction_shift = SignalResult("invalid", {}, ("prediction.key_mismatch",))
        else:
            prediction_shift = prediction_shift_signal(
                reference_predictions, current_predictions, policy
            )
        performance = SignalResult(
            "unavailable", {}, ("performance.labels_unavailable",)
        )
    service = (
        SignalResult("unavailable", {}, ("service.no_probe_evidence",))
        if service_evidence is None
        else service_health_signal(
            readiness=bool(service_evidence["readiness"]),
            status_codes=service_evidence["status_codes"],
            latencies_ms=service_evidence["latencies_ms"],
        )
    )
    return MonitoringReport(
        window=window,
        reference_id=reference.reference_id,
        policy_id=policy.policy_id,
        data_quality=quality,
        feature_shift=feature_shift,
        prediction_shift=prediction_shift,
        service_health=service,
        delayed_performance=performance,
        lifecycle_mix=(lifecycle_mix(frame) if quality.status != "invalid" else {}),
        operating_setting_summary=(
            operating_setting_summary(frame) if quality.status != "invalid" else {}
        ),
        limitations=DEFAULT_LIMITATIONS,
    )


def attach_delayed_labels(
    report: MonitoringReport,
    labels: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    label_snapshot_id: str,
    expected_source_partition: str,
) -> MonitoringReport:
    """Create new immutable performance evidence after prediction evidence is fixed."""
    if report.parent_report_id is not None or report.label_snapshot_id is not None:
        raise MonitoringError(
            "performance.already_attached",
            "Labels are already attached to this report.",
        )
    if report.window.source_partition != expected_source_partition:
        raise MonitoringError(
            "performance.partition_mismatch", "Label source partition does not align."
        )
    keys = predictions.loc[:, list(KEY_COLUMNS)]
    signal = delayed_performance_signal(keys, labels, predictions)
    if signal.status == "invalid":
        raise MonitoringError(
            "performance.attachment_rejected",
            "Delayed labels failed exact key and contract validation.",
        )
    return replace(
        report,
        delayed_performance=signal,
        lifecycle_mix=lifecycle_mix(labels),
        parent_report_id=report.report_id,
        label_snapshot_id=label_snapshot_id,
    )
