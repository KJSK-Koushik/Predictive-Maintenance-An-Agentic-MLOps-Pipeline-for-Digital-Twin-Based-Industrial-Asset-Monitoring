"""Direct deterministic monitoring workflow without cloud or Airflow dependencies."""

from __future__ import annotations

import io
from dataclasses import replace
from typing import Any

import pandas as pd

from predictive_maintenance.etl.models import FEATURE_SPEC_VERSION, DerivedManifest
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

PREDICTION_COLUMNS = (
    "engine_id",
    "cycle",
    "rul_cycles",
    "failure_risk_probability",
    "failure_risk_label",
)


def prediction_sha256(predictions: pd.DataFrame) -> str:
    """Bind exact ordered prediction values without storing the row dump."""
    if tuple(predictions.columns) != PREDICTION_COLUMNS:
        raise MonitoringError(
            "prediction.invalid_contract",
            "Prediction columns do not match the contract.",
        )
    return sha256_bytes(canonical_json_bytes(predictions.to_dict(orient="records")))


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
        or window.release_id != reference.release_id
        or reference.policy_id != policy.policy_id
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
        prediction_sha256=(
            prediction_sha256(current_predictions)
            if quality.status != "invalid" and prediction_shift.status != "invalid"
            else None
        ),
    )


def attach_delayed_labels(
    report: MonitoringReport,
    predictions: pd.DataFrame,
    *,
    label_payload: bytes,
    feature_manifest: DerivedManifest,
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
    if (
        report.data_quality.status != "pass"
        or report.prediction_shift.status in {"invalid", "insufficient_data"}
        or report.prediction_sha256 is None
        or prediction_sha256(predictions) != report.prediction_sha256
    ):
        raise MonitoringError(
            "performance.prediction_evidence_mismatch",
            "Performance requires the exact valid predictions in the parent report.",
        )
    if (
        len(predictions) != report.window.row_count
        or membership_sha256(predictions, expected_source_partition)
        != report.window.membership_sha256
    ):
        raise MonitoringError(
            "performance.membership_mismatch", "Predictions do not match the window."
        )
    if (
        feature_manifest.snapshot_id != report.window.feature_snapshot_id
        or feature_manifest.source_snapshot_id != report.window.raw_snapshot_id
        or feature_manifest.parent_snapshot_id != report.window.processed_snapshot_id
        or feature_manifest.artifact_kind != "feature"
        or feature_manifest.contract_version != FEATURE_SPEC_VERSION
    ):
        raise MonitoringError(
            "performance.snapshot_mismatch",
            "Label manifest does not match window lineage.",
        )
    files = [
        item
        for item in feature_manifest.files
        if item.logical_filename == f"{expected_source_partition}_targets.parquet"
    ]
    if (
        len(files) != 1
        or files[0].sha256 != sha256_bytes(label_payload)
        or files[0].byte_size != len(label_payload)
    ):
        raise MonitoringError(
            "performance.label_integrity",
            "Label bytes do not match the fixed manifest.",
        )
    try:
        targets = pd.read_parquet(io.BytesIO(label_payload))
        if (
            tuple(targets.columns) != (*KEY_COLUMNS, "rul", "failure_risk_30")
            or len(targets) != files[0].row_count
            or targets.duplicated(list(KEY_COLUMNS)).any()
            or targets.isna().any().any()
            or (targets["rul"] < 0).any()
            or not (targets["failure_risk_30"] == (targets["rul"] <= 30)).all()
        ):
            raise ValueError
        keys = predictions.loc[:, list(KEY_COLUMNS)]
        labels = keys.merge(
            targets, on=list(KEY_COLUMNS), how="left", validate="one_to_one"
        )
        if labels.isna().any().any():
            raise ValueError
    except (OSError, ValueError, KeyError) as error:
        raise MonitoringError(
            "performance.invalid_label_snapshot",
            "Label snapshot cannot supply valid targets.",
        ) from error
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
        label_snapshot_id=files[0].sha256,
    )
