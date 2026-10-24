"""Monitoring pipeline, trigger, and report publication tests."""

from __future__ import annotations

import io
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from phase7_support import identity, prediction_frame, telemetry_frame

from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.etl.models import (
    FEATURE_SPEC_VERSION,
    DerivedManifest,
    ManifestFile,
)
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    MonitoringReport,
    ReferenceProfile,
    SignalResult,
    sha256_bytes,
)
from predictive_maintenance.monitoring.pipeline import (
    attach_delayed_labels,
    build_monitoring_report,
    create_window,
)
from predictive_maintenance.monitoring.publication import (
    monitoring_report_key,
    publish_and_record_monitoring_report,
    publish_challenger_evaluation,
    publish_monitoring_report,
    publish_reference_profile,
    reconcile_monitoring_objects,
)
from predictive_maintenance.monitoring.triggers import (
    CandidateRequest,
    evaluate_triggers,
)
from predictive_maintenance.release.models import ReleaseError
from predictive_maintenance.retraining.evaluation import blocked_no_new_training_data


def _report(
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
    *,
    telemetry_shift: float = 0.0,
    prediction_shift: float = 0.0,
    sequence: int = 1,
    ready: bool = True,
) -> MonitoringReport:
    frame = telemetry_frame(shift=telemetry_shift)
    window = create_window(
        frame,
        reference=reference,
        policy=policy,
        raw_snapshot_id=identity("raw"),
        processed_snapshot_id=identity("processed"),
        feature_snapshot_id=identity("feature-window"),
        source_partition="synthetic",
        replay_sequence=sequence,
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
    return build_monitoring_report(
        frame,
        prediction_frame(frame, shift=prediction_shift),
        prediction_frame(telemetry_frame()),
        window=window,
        reference=reference,
        policy=policy,
        service_evidence={
            "readiness": ready,
            "status_codes": [200] if ready else [503],
            "latencies_ms": [2.0],
        },
    )


def _label_evidence(
    report: MonitoringReport,
    targets: pd.DataFrame | None = None,
) -> tuple[MonitoringReport, bytes, DerivedManifest]:
    if targets is None:
        targets = telemetry_frame().loc[:, ["engine_id", "cycle"]].copy()
        targets["rul"] = 40 - targets["cycle"]
        targets["failure_risk_30"] = (targets["rul"] <= 30).astype("int8")
    stream = io.BytesIO()
    targets.to_parquet(stream, index=False)
    payload = stream.getvalue()
    manifest = DerivedManifest(
        artifact_kind="feature",
        source_snapshot_id=report.window.raw_snapshot_id,
        parent_snapshot_id=report.window.processed_snapshot_id,
        contract_version=FEATURE_SPEC_VERSION,
        transformation_version="test",
        serializer_version="test",
        code_revision="phase7-tests",
        files=(
            ManifestFile(
                logical_filename="synthetic_targets.parquet",
                file_position=1,
                byte_size=len(payload),
                sha256=sha256_bytes(payload),
                content_type="application/vnd.apache.parquet",
                row_count=len(targets),
                columns=(),
            ),
        ),
    )
    return (
        replace(
            report,
            window=replace(report.window, feature_snapshot_id=manifest.snapshot_id),
        ),
        payload,
        manifest,
    )


@pytest.mark.parametrize(
    "change",
    [
        "values",
        "keys",
        "partition",
        "snapshot",
        "bytes",
        "missing_digest",
        "membership",
    ],
)
def test_label_attachment_rejects_changed_prediction_or_label_evidence(
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
    change: str,
) -> None:
    report, payload, manifest = _label_evidence(_report(reference, policy))
    predictions = prediction_frame(telemetry_frame())
    partition = "synthetic"
    if change == "values":
        predictions.loc[0, "rul_cycles"] = 999.0
    elif change == "keys":
        predictions.loc[0, "cycle"] = 999
    elif change == "partition":
        partition = "test"
    elif change == "snapshot":
        manifest = replace(manifest, source_snapshot_id=identity("wrong"))
    elif change == "bytes":
        payload += b"changed"
    elif change == "membership":
        report = replace(report, window=replace(report.window, row_count=1))
    else:
        report = replace(report, prediction_sha256=None)
    with pytest.raises(MonitoringError):
        attach_delayed_labels(
            report,
            predictions,
            label_payload=payload,
            feature_manifest=manifest,
            expected_source_partition=partition,
        )


@pytest.mark.parametrize("change", ["duplicate", "missing", "semantics", "schema"])
def test_label_attachment_validates_snapshot_targets(
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
    change: str,
) -> None:
    targets = telemetry_frame().loc[:, ["engine_id", "cycle"]].copy()
    targets["rul"] = 40 - targets["cycle"]
    targets["failure_risk_30"] = (targets["rul"] <= 30).astype("int8")
    if change == "duplicate":
        targets.iloc[1] = targets.iloc[0]
    elif change == "missing":
        targets = targets.iloc[1:]
    elif change == "schema":
        targets = targets.drop(columns="rul")
    else:
        targets.loc[0, "failure_risk_30"] = 1
    report, payload, manifest = _label_evidence(_report(reference, policy), targets)
    with pytest.raises(MonitoringError, match="invalid_label_snapshot"):
        attach_delayed_labels(
            report,
            prediction_frame(telemetry_frame()),
            label_payload=payload,
            feature_manifest=manifest,
            expected_source_partition="synthetic",
        )


@pytest.mark.parametrize(
    "change", ["release", "reference", "partition", "order", "duplicate"]
)
def test_trigger_history_rejects_mixed_or_repeated_windows(
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
    change: str,
) -> None:
    first = _report(reference, policy, telemetry_shift=5, sequence=1)
    second = _report(reference, policy, telemetry_shift=5, sequence=2)
    if change == "release":
        second = replace(
            second, window=replace(second.window, release_id=identity("wrong"))
        )
    elif change == "reference":
        second = replace(
            second,
            reference_id=identity("wrong"),
            window=replace(second.window, reference_id=identity("wrong")),
        )
    elif change == "partition":
        second = replace(second, window=replace(second.window, source_partition="test"))
    elif change == "order":
        first, second = second, first
    else:
        second = first
    with pytest.raises(MonitoringError, match=r"trigger\.history_"):
        evaluate_triggers((first, second), policy=policy)


def test_unhealthy_historical_window_cannot_prove_persistent_drift(
    reference: ReferenceProfile,
    policy: MonitoringPolicy,
) -> None:
    first = _report(reference, policy, telemetry_shift=5, sequence=1, ready=False)
    second = _report(reference, policy, telemetry_shift=5, sequence=2)
    assert evaluate_triggers((first, second), policy=policy).candidate_request is None


def test_report_identity_is_deterministic_and_has_no_processing_time(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    first = _report(reference, policy)
    second = _report(reference, policy)
    assert first.report_id == second.report_id
    assert first.canonical_bytes() == second.canonical_bytes()
    assert b"processing_time" not in first.canonical_bytes()
    assert first.delayed_performance.status == "unavailable"
    assert first.feature_shift.status == "pass"


def test_window_membership_and_policy_change_identity(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    first = _report(reference, policy)
    second = _report(reference, policy, sequence=2)
    assert first.window.window_id != second.window.window_id
    assert first.report_id != second.report_id
    with pytest.raises(MonitoringError, match=r"pipeline\.membership_mismatch"):
        build_monitoring_report(
            telemetry_frame().iloc[:-1],
            prediction_frame(telemetry_frame().iloc[:-1]),
            prediction_frame(telemetry_frame()),
            window=first.window,
            reference=reference,
            policy=policy,
        )


def test_invalid_quality_blocks_downstream_signals(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    valid = telemetry_frame()
    window = create_window(
        valid.drop(columns="sensor_21"),
        reference=reference,
        policy=policy,
        raw_snapshot_id=identity("raw"),
        processed_snapshot_id=identity("processed"),
        feature_snapshot_id=identity("feature-window"),
        source_partition="synthetic",
        replay_sequence=1,
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
    report = build_monitoring_report(
        valid.drop(columns="sensor_21"),
        prediction_frame(valid),
        prediction_frame(valid),
        window=window,
        reference=reference,
        policy=policy,
    )
    assert report.data_quality.status == "invalid"
    assert report.feature_shift.status == "invalid"
    assert report.prediction_shift.status == "invalid"
    assert report.delayed_performance.status == "unavailable"


def test_label_attachment_creates_child_without_overwrite(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    original, payload, manifest = _label_evidence(_report(reference, policy))
    frame = telemetry_frame()
    predictions = prediction_frame(frame)
    attached = attach_delayed_labels(
        original,
        predictions,
        label_payload=payload,
        feature_manifest=manifest,
        expected_source_partition="synthetic",
    )
    assert original.delayed_performance.status == "unavailable"
    assert attached.delayed_performance.status == "pass"
    assert attached.parent_report_id == original.report_id
    assert attached.report_id != original.report_id
    with pytest.raises(MonitoringError, match=r"performance\.already_attached"):
        attach_delayed_labels(
            attached,
            predictions,
            label_payload=payload,
            feature_manifest=manifest,
            expected_source_partition="synthetic",
        )


def test_quality_and_service_alerts_only_investigate(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    service_failure = _report(reference, policy, ready=False)
    service_decision = evaluate_triggers((service_failure,), policy=policy)
    assert service_decision.status == "investigate"
    assert service_decision.candidate_request is None
    invalid_quality = replace(
        service_failure,
        data_quality=SignalResult("invalid", {}, ("quality.invalid",)),
        feature_shift=SignalResult("invalid", {}, ("monitoring.blocked",)),
        prediction_shift=SignalResult("invalid", {}, ("monitoring.blocked",)),
    )
    quality_decision = evaluate_triggers((invalid_quality,), policy=policy)
    assert quality_decision.investigations[0].category == "data_quality"
    assert quality_decision.candidate_request is None


def test_persistent_shift_creates_one_deterministic_candidate(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    first = _report(reference, policy, telemetry_shift=5, sequence=1)
    second = _report(reference, policy, telemetry_shift=5, sequence=2)
    single = evaluate_triggers((first,), policy=policy)
    assert single.status == "investigate"
    assert single.candidate_request is None
    decision = evaluate_triggers((first, second), policy=policy)
    repeated = evaluate_triggers((first, second), policy=policy)
    assert decision.status == "candidate_requested"
    assert decision.candidate_request is not None
    assert repeated.candidate_request is not None
    assert (
        decision.candidate_request.request_id == repeated.candidate_request.request_id
    )
    assert decision.candidate_request.authority == "evaluation_only"


def test_unavailable_performance_cannot_trigger_candidate(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    report = _report(reference, policy)
    decision = evaluate_triggers((report,), policy=policy, performance_degraded=True)
    assert decision.status == "no_action"
    assert decision.candidate_request is None


def test_available_degraded_performance_can_request_evaluation(
    reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    original, payload, manifest = _label_evidence(_report(reference, policy))
    frame = telemetry_frame()
    predictions = prediction_frame(frame)
    attached = attach_delayed_labels(
        original,
        predictions,
        label_payload=payload,
        feature_manifest=manifest,
        expected_source_partition="synthetic",
    )
    decision = evaluate_triggers((attached,), policy=policy, performance_degraded=True)
    assert decision.status == "candidate_requested"
    assert decision.candidate_request is not None
    assert decision.candidate_request.reason == "performance_degradation"
    assert decision.candidate_request.authority == "evaluation_only"


def test_candidate_request_rejects_duplicate_or_invalid_evidence() -> None:
    kwargs: dict[str, Any] = {
        "release_id": identity("release"),
        "policy_id": identity("policy"),
        "requested_task": "both",
        "data_cutoff_window_id": identity("window"),
        "reason": "persistent_shift",
    }
    with pytest.raises(ReleaseError, match=r"release\.invalid_identity"):
        CandidateRequest(evidence_report_ids=("not-a-digest",), **kwargs)
    report_id = identity("report")
    with pytest.raises(MonitoringError, match=r"trigger\.duplicate_evidence"):
        CandidateRequest(
            evidence_report_ids=(report_id, report_id),
            **kwargs,
        )


def test_publication_is_put_if_absent_and_conflict_safe(
    tmp_path: Path, reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    report = _report(reference, policy)
    repository = FilesystemObjectRepository(tmp_path / "objects")
    first = publish_monitoring_report(
        report, bucket="pm-derived-test", repository=repository
    )
    second = publish_monitoring_report(
        report, bucket="pm-derived-test", repository=repository
    )
    assert not first.reused
    assert second.reused
    assert monitoring_report_key(report).endswith(f"/{report.report_id}.json")
    stored = repository.read("pm-derived-test", monitoring_report_key(report))
    assert stored == report.canonical_bytes()


def test_reference_and_evaluation_publication_are_content_addressed(
    tmp_path: Path, reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    first_report = _report(reference, policy, telemetry_shift=5.0, sequence=1)
    second_report = _report(reference, policy, telemetry_shift=5.0, sequence=2)
    decision = evaluate_triggers((first_report, second_report), policy=policy)
    assert decision.candidate_request is not None
    evaluation = blocked_no_new_training_data(decision.candidate_request)
    repository = FilesystemObjectRepository(tmp_path / "objects")
    reference_result = publish_reference_profile(
        reference, bucket="pm-derived-test", repository=repository
    )
    evaluation_result = publish_challenger_evaluation(
        evaluation, bucket="pm-derived-test", repository=repository
    )
    assert not reference_result.reused
    assert not evaluation_result.reused
    assert reference.reference_id in reference_result.identity.object_key
    assert evaluation.evaluation_id in evaluation_result.identity.object_key


def test_partial_metadata_failure_retry_and_reconciliation_report_gaps(
    tmp_path: Path, reference: ReferenceProfile, policy: MonitoringPolicy
) -> None:
    report = _report(reference, policy)
    object_root = tmp_path / "objects"
    repository = FilesystemObjectRepository(object_root)

    class FailOnceMetadata:
        attempts = 0
        recorded: ObjectIdentity | None = None

        def record_report(
            self,
            _: MonitoringReport,
            object_identity: ObjectIdentity,
            *,
            verified_at: datetime,
        ) -> None:
            assert verified_at.tzinfo is not None
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("controlled metadata failure")
            self.recorded = object_identity

    metadata = FailOnceMetadata()
    with pytest.raises(RuntimeError, match="controlled metadata failure"):
        publish_and_record_monitoring_report(
            report,
            bucket="pm-derived-test",
            repository=repository,
            metadata=metadata,
            verified_at=datetime.now(UTC),
        )
    recovered = publish_and_record_monitoring_report(
        report,
        bucket="pm-derived-test",
        repository=repository,
        metadata=metadata,
        verified_at=datetime.now(UTC),
    )
    assert recovered.reused
    assert metadata.recorded == recovered.identity

    stored_path = (
        object_root
        / "pm-derived-test"
        / Path(*recovered.identity.object_key.split("/"))
    )
    if os.name == "nt" and not str(stored_path).startswith("\\\\?\\"):
        stored_path = Path("\\\\?\\" + str(stored_path.resolve()))
    stored_path.write_bytes(b"different bytes")
    prefix = f"reports/monitoring/{report.window.release_id}/{report.window.window_id}"
    orphan_key = f"{prefix}/orphan.json"
    orphan_path = object_root / "pm-derived-test" / Path(*orphan_key.split("/"))
    if os.name == "nt" and not str(orphan_path).startswith("\\\\?\\"):
        orphan_path = Path("\\\\?\\" + str(orphan_path.resolve()))
    orphan_path.write_bytes(b"orphan")
    missing = ObjectIdentity(
        bucket_name="pm-derived-test",
        object_key=f"{prefix}/missing.json",
        zone="derived",
        sha256=identity("missing"),
        byte_size=7,
        content_type="application/json",
    )
    findings = reconcile_monitoring_objects(
        (recovered.identity, missing),
        bucket="pm-derived-test",
        prefix=prefix,
        repository=repository,
    )
    assert {finding.kind for finding in findings} == {
        "missing",
        "mismatched",
        "orphaned",
    }
