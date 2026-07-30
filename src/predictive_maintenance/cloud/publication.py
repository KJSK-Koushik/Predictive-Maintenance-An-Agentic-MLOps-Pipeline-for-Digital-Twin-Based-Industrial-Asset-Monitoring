"""Idempotent object and metadata publication with reconciliation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from predictive_maintenance.cloud.metadata import MetadataRepository
from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    ObjectIdentity,
    PublicationResult,
    ReconciliationFinding,
    ReconciliationReport,
    SnapshotFile,
    SnapshotPublication,
    raw_file_key,
    raw_manifest_key,
)
from predictive_maintenance.cloud.object_store import (
    ObjectRepository,
    inspect_path,
)
from predictive_maintenance.data.integrity import Snapshot


def build_publication(
    snapshot: Snapshot,
    raw_bucket: str,
    *,
    verified_at: datetime | None = None,
) -> SnapshotPublication:
    """Translate the accepted Phase 1 snapshot without redefining identity."""
    manifest = snapshot.manifest
    timestamp = datetime.now(UTC) if verified_at is None else verified_at
    if timestamp.tzinfo is None:
        raise CloudFoundationError(
            "publication.naive_timestamp",
            "Publication timestamps must include a timezone.",
        )

    files: list[SnapshotFile] = []
    for position, record in enumerate(manifest.files, start=1):
        files.append(
            SnapshotFile(
                logical_filename=record.filename,
                file_position=position,
                identity=ObjectIdentity(
                    bucket_name=raw_bucket,
                    object_key=raw_file_key(
                        manifest.snapshot_id,
                        record.sha256,
                        record.filename,
                    ),
                    zone="raw",
                    sha256=record.sha256,
                    byte_size=record.byte_size,
                    content_type="text/plain",
                ),
            )
        )

    manifest_path = snapshot.path / "manifest.json"
    manifest_sha256, manifest_size = inspect_path(manifest_path)
    manifest_identity = ObjectIdentity(
        bucket_name=raw_bucket,
        object_key=raw_manifest_key(manifest.snapshot_id),
        zone="raw",
        sha256=manifest_sha256,
        byte_size=manifest_size,
        content_type="application/json",
    )
    return SnapshotPublication(
        snapshot_id=manifest.snapshot_id,
        dataset_family=manifest.dataset_family,
        dataset_subset=manifest.dataset_subset,
        contract_version=manifest.contract_version,
        parser_version=manifest.parser_version,
        code_revision=manifest.code_revision,
        manifest=manifest_identity,
        files=tuple(files),
        verified_at=timestamp,
    )


def _source_paths(
    snapshot: Snapshot,
    publication: SnapshotPublication,
) -> tuple[tuple[Path, ObjectIdentity], ...]:
    paths = [
        (snapshot.path / item.logical_filename, item.identity)
        for item in publication.files
    ]
    paths.append((snapshot.path / "manifest.json", publication.manifest))
    return tuple(paths)


def reconcile_snapshot(
    snapshot_id: str,
    object_repository: ObjectRepository,
    metadata_repository: MetadataRepository,
    *,
    detected_at: datetime | None = None,
) -> ReconciliationReport:
    """Report storage/metadata differences without deleting or repairing."""
    stored = metadata_repository.get_snapshot(snapshot_id)
    if stored is None:
        raise CloudFoundationError(
            "reconciliation.snapshot_not_found",
            "No metadata exists for the requested snapshot.",
        )

    findings: list[ReconciliationFinding] = []
    expected_keys: dict[tuple[str, str], ObjectIdentity] = {
        (identity.bucket_name, identity.object_key): identity
        for identity in stored.identities
    }
    for identity in stored.identities:
        try:
            payload = object_repository.read(
                identity.bucket_name,
                identity.object_key,
            )
        except CloudFoundationError as error:
            if error.code != "object.not_found":
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
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != identity.sha256 or len(payload) != identity.byte_size:
            findings.append(
                ReconciliationFinding(
                    "mismatched",
                    identity.bucket_name,
                    identity.object_key,
                    expected_sha256=identity.sha256,
                    actual_sha256=actual_sha256,
                )
            )

    prefixes = {
        (identity.bucket_name, f"fd001/{snapshot_id}") for identity in stored.identities
    }
    for bucket_name, prefix in sorted(prefixes):
        for object_key in object_repository.list_keys(bucket_name, prefix):
            if (bucket_name, object_key) not in expected_keys:
                findings.append(
                    ReconciliationFinding(
                        "orphaned",
                        bucket_name,
                        object_key,
                    )
                )

    blocking = [
        finding for finding in findings if finding.kind in {"missing", "mismatched"}
    ]
    if blocking and stored.state != "inconsistent":
        timestamp = datetime.now(UTC) if detected_at is None else detected_at
        metadata_repository.mark_inconsistent(
            snapshot_id,
            "reconciliation.referenced_object_invalid",
            f"{len(blocking)} referenced object(s) missing or mismatched.",
            timestamp,
        )
    return ReconciliationReport(snapshot_id, tuple(findings))


def publish_snapshot(
    snapshot: Snapshot,
    raw_bucket: str,
    object_repository: ObjectRepository,
    metadata_repository: MetadataRepository,
    *,
    verified_at: datetime | None = None,
) -> PublicationResult:
    """Publish verified objects followed by one PostgreSQL metadata commit."""
    publication = build_publication(
        snapshot,
        raw_bucket,
        verified_at=verified_at,
    )
    started_at = publication.verified_at
    metadata_repository.begin_run(publication.snapshot_id, started_at)
    existing = metadata_repository.get_snapshot(publication.snapshot_id)
    put_results = []
    try:
        for source, identity in _source_paths(snapshot, publication):
            put_results.append(object_repository.put_verified(source, identity))
        stored = metadata_repository.commit_publication(publication)
    except CloudFoundationError as error:
        now = datetime.now(UTC)
        if existing is not None and existing.state == "available":
            metadata_repository.mark_inconsistent(
                publication.snapshot_id,
                error.code,
                error.message,
                now,
            )
        else:
            metadata_repository.record_failure(
                publication.snapshot_id,
                error.code,
                error.message,
                now,
            )
        raise

    report = reconcile_snapshot(
        publication.snapshot_id,
        object_repository,
        metadata_repository,
        detected_at=publication.verified_at,
    )
    if any(finding.kind in {"missing", "mismatched"} for finding in report.findings):
        raise CloudFoundationError(
            "publication.reconciliation_failed",
            "Referenced objects failed reconciliation after metadata commit.",
        )
    return PublicationResult(
        snapshot_id=stored.snapshot_id,
        state=stored.state,
        object_count=len(stored.identities),
        reused=existing is not None and all(result.reused for result in put_results),
    )
