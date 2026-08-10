"""Immutable object preparation, publication, and derived reconciliation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from predictive_maintenance.cloud.models import (
    ObjectIdentity,
    ObjectPutResult,
    ReconciliationFinding,
    ReconciliationReport,
)
from predictive_maintenance.cloud.object_store import ObjectRepository, inspect_path
from predictive_maintenance.etl.metadata import DerivedMetadataRepository
from predictive_maintenance.etl.models import (
    PIPELINE_VERSION,
    DerivedBatchPublication,
    DerivedFilePublication,
    DerivedSnapshotPublication,
    EtlError,
    LineageType,
    MaterializedArtifact,
    PipelineResult,
    StoredDerivedSnapshot,
    canonical_json_bytes,
    sha256_bytes,
)


@dataclass(frozen=True, slots=True)
class PreparedObject:
    """A local source path paired with its immutable object identity."""

    path: Path
    identity: ObjectIdentity


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    """Storage writes and metadata for one derived artifact."""

    publication: DerivedSnapshotPublication
    objects: tuple[PreparedObject, ...]


def _artifact_prefix(artifact: MaterializedArtifact) -> str:
    manifest = artifact.manifest
    if manifest.artifact_kind == "processed":
        return (
            f"processed/fd001/{manifest.contract_version}/{manifest.source_snapshot_id}"
        )
    if manifest.artifact_kind == "feature":
        return (
            f"features/fd001/{manifest.contract_version}/{manifest.parent_snapshot_id}"
        )
    return (
        f"reports/data-quality/{manifest.contract_version}/"
        f"{manifest.source_snapshot_id}"
    )


def prepare_artifact(
    artifact: MaterializedArtifact,
    derived_bucket: str,
    *,
    parents_by_filename: dict[str, tuple[ObjectIdentity, ...]],
    relationship_type: LineageType,
) -> PreparedArtifact:
    """Build content-addressed keys and publication metadata."""
    prefix = _artifact_prefix(artifact)
    prepared: list[PreparedObject] = []
    files: list[DerivedFilePublication] = []
    for materialized in artifact.files:
        record = materialized.record
        identity = ObjectIdentity(
            bucket_name=derived_bucket,
            object_key=(f"{prefix}/{record.sha256}/{record.logical_filename}"),
            zone="derived",
            sha256=record.sha256,
            byte_size=record.byte_size,
            content_type=record.content_type,
        )
        parents = parents_by_filename.get(record.logical_filename, ())
        if not parents:
            raise EtlError(
                "lineage.parent_missing",
                "Every derived data or report file requires object-level lineage.",
            )
        files.append(
            DerivedFilePublication(
                logical_filename=record.logical_filename,
                file_position=record.file_position,
                identity=identity,
                schema=tuple(
                    {"name": column.name, "dtype": column.dtype}
                    for column in record.columns
                ),
                column_roles={column.name: column.role for column in record.columns},
                parents=parents,
                relationship_type=relationship_type,
            )
        )
        prepared.append(PreparedObject(materialized.path, identity))

    manifest_sha, manifest_size = inspect_path(artifact.manifest_path)
    manifest_identity = ObjectIdentity(
        bucket_name=derived_bucket,
        object_key=f"{prefix}/{artifact.snapshot_id}/manifest.json",
        zone="derived",
        sha256=manifest_sha,
        byte_size=manifest_size,
        content_type="application/json",
    )
    prepared.append(PreparedObject(artifact.manifest_path, manifest_identity))
    parent_derived = (
        None
        if artifact.manifest.artifact_kind == "processed"
        else artifact.manifest.parent_snapshot_id
    )
    publication = DerivedSnapshotPublication(
        derived_snapshot_id=artifact.snapshot_id,
        source_snapshot_id=artifact.manifest.source_snapshot_id,
        parent_derived_snapshot_id=parent_derived,
        artifact_kind=artifact.manifest.artifact_kind,
        contract_version=artifact.manifest.contract_version,
        transformation_version=artifact.manifest.transformation_version,
        serializer_version=artifact.manifest.serializer_version,
        code_revision=artifact.manifest.code_revision,
        manifest=manifest_identity,
        files=tuple(files),
    )
    return PreparedArtifact(publication, tuple(prepared))


def build_batch_publication(
    source_snapshot_id: str,
    code_revision: str,
    artifacts: tuple[PreparedArtifact, ...],
    *,
    verified_at: datetime | None = None,
) -> DerivedBatchPublication:
    """Create an Airflow-date-independent transformation idempotency key."""
    timestamp = datetime.now(UTC) if verified_at is None else verified_at
    if timestamp.tzinfo is None:
        raise EtlError(
            "publication.naive_timestamp",
            "Transformation timestamps must include a timezone.",
        )
    identity = {
        "artifacts": [item.publication.derived_snapshot_id for item in artifacts],
        "code_revision": code_revision,
        "pipeline_version": PIPELINE_VERSION,
        "source_snapshot_id": source_snapshot_id,
    }
    return DerivedBatchPublication(
        idempotency_key=sha256_bytes(canonical_json_bytes(identity)),
        source_snapshot_id=source_snapshot_id,
        pipeline_version=PIPELINE_VERSION,
        code_revision=code_revision,
        artifacts=tuple(item.publication for item in artifacts),
        verified_at=timestamp,
    )


def _reconciliation_prefix(stored: StoredDerivedSnapshot) -> str:
    if stored.artifact_kind == "processed":
        return f"processed/fd001/{stored.contract_version}/{stored.source_snapshot_id}"
    if stored.artifact_kind == "feature":
        return (
            f"features/fd001/{stored.contract_version}/"
            f"{stored.parent_derived_snapshot_id}"
        )
    return f"reports/data-quality/{stored.contract_version}/{stored.source_snapshot_id}"


def reconcile_derived_snapshot(
    snapshot_id: str,
    objects: ObjectRepository,
    metadata: DerivedMetadataRepository,
    *,
    detected_at: datetime | None = None,
) -> ReconciliationReport:
    """Report missing, mismatched, and orphan objects without deleting them."""
    stored = metadata.get_derived_snapshot(snapshot_id)
    if stored is None:
        raise EtlError(
            "reconciliation.derived_not_found",
            "No derived metadata exists for the requested snapshot.",
        )
    expected = {
        (identity.bucket_name, identity.object_key): identity
        for identity in stored.identities
    }
    findings: list[ReconciliationFinding] = []
    for identity in stored.identities:
        try:
            payload = objects.read(identity.bucket_name, identity.object_key)
        except Exception as error:
            code = getattr(error, "code", "")
            if code != "object.not_found":
                raise
            findings.append(
                ReconciliationFinding(
                    "missing",
                    identity.bucket_name,
                    identity.object_key,
                    expected_sha256=identity.sha256,
                )
            )
            continue
        actual = hashlib.sha256(payload).hexdigest()
        if actual != identity.sha256 or len(payload) != identity.byte_size:
            findings.append(
                ReconciliationFinding(
                    "mismatched",
                    identity.bucket_name,
                    identity.object_key,
                    expected_sha256=identity.sha256,
                    actual_sha256=actual,
                )
            )
    bucket = stored.identities[0].bucket_name
    for object_key in objects.list_keys(bucket, _reconciliation_prefix(stored)):
        if (bucket, object_key) not in expected:
            findings.append(ReconciliationFinding("orphaned", bucket, object_key))
    blocking = [item for item in findings if item.kind in {"missing", "mismatched"}]
    if blocking and stored.state == "available":
        metadata.mark_derived_inconsistent(
            snapshot_id,
            "reconciliation.derived_object_invalid",
            f"{len(blocking)} referenced derived object(s) are invalid.",
            datetime.now(UTC) if detected_at is None else detected_at,
        )
    return ReconciliationReport(snapshot_id, tuple(findings))


def publish_batch(
    source_snapshot_id: str,
    prepared: tuple[PreparedArtifact, ...],
    batch: DerivedBatchPublication,
    objects: ObjectRepository,
    metadata: DerivedMetadataRepository,
) -> PipelineResult:
    """Publish all bytes, atomically commit metadata, and reconcile references."""
    metadata.begin_transformation(batch)
    put_results: list[ObjectPutResult] = []
    try:
        for prepared_artifact in prepared:
            for item in prepared_artifact.objects:
                put_results.append(objects.put_verified(item.path, item.identity))
        reused_metadata = metadata.commit_derived_batch(batch)
        for published_artifact in batch.artifacts:
            report = reconcile_derived_snapshot(
                published_artifact.derived_snapshot_id,
                objects,
                metadata,
                detected_at=batch.verified_at,
            )
            if any(item.kind in {"missing", "mismatched"} for item in report.findings):
                raise EtlError(
                    "publication.reconciliation_failed",
                    "A referenced derived object failed post-commit verification.",
                )
    except EtlError as error:
        metadata.record_transformation_failure(
            batch.idempotency_key,
            error.code,
            error.message,
            datetime.now(UTC),
        )
        raise
    except Exception as error:
        metadata.record_transformation_failure(
            batch.idempotency_key,
            "publication.unexpected_failure",
            "The derived publication failed without exposing infrastructure details.",
            datetime.now(UTC),
        )
        raise EtlError(
            "publication.unexpected_failure",
            "The derived publication failed without exposing infrastructure details.",
        ) from error

    by_kind = {item.publication.artifact_kind: item for item in prepared}
    return PipelineResult(
        source_snapshot_id=source_snapshot_id,
        processed_snapshot_id=by_kind["processed"].publication.derived_snapshot_id,
        feature_snapshot_id=by_kind["feature"].publication.derived_snapshot_id,
        quality_snapshot_id=by_kind["quality_report"].publication.derived_snapshot_id,
        reused=reused_metadata and all(item.reused for item in put_results),
    )
