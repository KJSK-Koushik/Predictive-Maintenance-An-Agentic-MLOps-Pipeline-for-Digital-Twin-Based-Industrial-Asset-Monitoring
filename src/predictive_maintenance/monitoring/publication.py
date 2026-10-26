"""Put-if-absent publication for bounded monitoring evidence."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Protocol

from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    ObjectIdentity,
    ObjectPutResult,
    ReconciliationFinding,
)
from predictive_maintenance.cloud.object_store import ObjectRepository
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringReport,
    ReferenceProfile,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.retraining.evaluation import ChallengerEvaluation


class ReportMetadataWriter(Protocol):
    """Narrow metadata side of the recoverable publication boundary."""

    def record_report(
        self,
        report: MonitoringReport,
        object_identity: ObjectIdentity,
        *,
        verified_at: datetime,
    ) -> None:
        """Record an already verified immutable report object."""
        ...


def monitoring_report_key(report: MonitoringReport) -> str:
    """Return the private content-addressed Storage key."""
    return (
        f"reports/monitoring/{report.window.release_id}/"
        f"{report.window.window_id}/{report.report_id}.json"
    )


def publish_monitoring_report(
    report: MonitoringReport,
    *,
    bucket: str,
    repository: ObjectRepository,
) -> ObjectPutResult:
    """Publish canonical bytes without overwrite and verify the download."""
    return _publish_bytes(
        report.canonical_bytes(),
        bucket=bucket,
        object_key=monitoring_report_key(report),
        repository=repository,
    )


def publish_and_record_monitoring_report(
    report: MonitoringReport,
    *,
    bucket: str,
    repository: ObjectRepository,
    metadata: ReportMetadataWriter,
    verified_at: datetime,
) -> ObjectPutResult:
    """Publish first, then record metadata so retry can reuse verified bytes."""
    result = publish_monitoring_report(
        report,
        bucket=bucket,
        repository=repository,
    )
    metadata.record_report(report, result.identity, verified_at=verified_at)
    return result


def reconcile_monitoring_objects(
    expected: tuple[ObjectIdentity, ...],
    *,
    bucket: str,
    prefix: str,
    repository: ObjectRepository,
) -> tuple[ReconciliationFinding, ...]:
    """Report missing, mismatched, and orphan objects without repairing them."""
    expected_by_key = {item.object_key: item for item in expected}
    if any(item.bucket_name != bucket for item in expected):
        raise MonitoringError(
            "reconciliation.bucket_mismatch",
            "Expected monitoring objects must use the requested bucket.",
        )
    findings: list[ReconciliationFinding] = []
    for identity in expected:
        try:
            payload = repository.read(bucket, identity.object_key)
        except CloudFoundationError as error:
            if error.code != "object.not_found":
                raise
            findings.append(
                ReconciliationFinding(
                    "missing",
                    bucket,
                    identity.object_key,
                    expected_sha256=identity.sha256,
                )
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != identity.sha256 or len(payload) != identity.byte_size:
            findings.append(
                ReconciliationFinding(
                    "mismatched",
                    bucket,
                    identity.object_key,
                    expected_sha256=identity.sha256,
                    actual_sha256=actual_sha256,
                )
            )
    for key in repository.list_keys(bucket, prefix):
        if key not in expected_by_key:
            findings.append(ReconciliationFinding("orphaned", bucket, key))
    return tuple(findings)


def publish_reference_profile(
    reference: ReferenceProfile,
    *,
    bucket: str,
    repository: ObjectRepository,
) -> ObjectPutResult:
    """Publish one private immutable reference profile."""
    return _publish_bytes(
        reference.canonical_bytes(),
        bucket=bucket,
        object_key=f"reports/monitoring/{reference.release_id}/references/{reference.reference_id}.json",
        repository=repository,
    )


def publish_challenger_evaluation(
    evaluation: ChallengerEvaluation,
    *,
    bucket: str,
    repository: ObjectRepository,
) -> ObjectPutResult:
    """Publish one private immutable challenger evaluation."""
    return _publish_bytes(
        canonical_json_bytes(evaluation.to_dict()),
        bucket=bucket,
        object_key=(
            f"reports/retraining/{evaluation.request_id}/"
            f"{evaluation.evaluation_id}.json"
        ),
        repository=repository,
    )


def _publish_bytes(
    payload: bytes,
    *,
    bucket: str,
    object_key: str,
    repository: ObjectRepository,
) -> ObjectPutResult:
    """Publish and download-verify bounded canonical JSON bytes."""
    identity = ObjectIdentity(
        bucket_name=bucket,
        object_key=object_key,
        zone="derived",
        sha256=sha256_bytes(payload),
        byte_size=len(payload),
        content_type="application/json",
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="phase7-monitor-", suffix=".json", delete=False
        ) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        result = repository.put_verified(temporary, identity)
        if repository.read(bucket, object_key) != payload:
            raise MonitoringError(
                "publication.download_mismatch",
                "Published monitoring report failed byte verification.",
            )
        return result
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
