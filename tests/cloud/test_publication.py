"""Publication, retry, and reconciliation tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from predictive_maintenance.cloud.metadata import MetadataRepository
from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    SnapshotPublication,
    StoredSnapshot,
)
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import (
    build_publication,
    publish_snapshot,
    reconcile_snapshot,
)
from predictive_maintenance.data.integrity import Snapshot


@dataclass
class FakeMetadataRepository(MetadataRepository):
    """Small deterministic metadata substitute for application tests."""

    stored: StoredSnapshot | None = None
    fail_commit_once: bool = False
    run_state: str | None = None
    failure_code: str | None = None

    def begin_run(self, snapshot_id: str, started_at: datetime) -> None:
        del snapshot_id, started_at
        if self.stored is None:
            self.run_state = "started"

    def get_snapshot(self, snapshot_id: str) -> StoredSnapshot | None:
        if self.stored is not None and self.stored.snapshot_id == snapshot_id:
            return self.stored
        return None

    def commit_publication(self, publication: SnapshotPublication) -> StoredSnapshot:
        if self.fail_commit_once:
            self.fail_commit_once = False
            raise CloudFoundationError(
                "metadata.commit_failed",
                "Injected metadata failure.",
            )
        expected = StoredSnapshot(
            publication.snapshot_id,
            "available",
            publication.manifest.sha256,
            len(publication.files),
            publication.identities,
        )
        if self.stored is not None and self.stored != expected:
            raise CloudFoundationError(
                "metadata.snapshot_conflict",
                "Injected metadata conflict.",
            )
        self.stored = expected
        self.run_state = "available"
        return expected

    def record_failure(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        del snapshot_id, error_detail, finished_at
        self.run_state = "failed"
        self.failure_code = error_code

    def mark_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        del error_detail, detected_at
        if self.stored is None or self.stored.snapshot_id != snapshot_id:
            raise AssertionError("Unknown fake snapshot")
        self.stored = StoredSnapshot(
            self.stored.snapshot_id,
            "inconsistent",
            self.stored.manifest_sha256,
            self.stored.required_file_count,
            self.stored.identities,
        )
        self.run_state = "inconsistent"
        self.failure_code = error_code


def test_publication_reuses_exact_objects_and_metadata(
    tmp_path: Path,
    accepted_snapshot: Snapshot,
) -> None:
    objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = FakeMetadataRepository()
    timestamp = datetime(2026, 7, 26, tzinfo=UTC)

    first = publish_snapshot(
        accepted_snapshot,
        "pm-raw",
        objects,
        metadata,
        verified_at=timestamp,
    )
    second = publish_snapshot(
        accepted_snapshot,
        "pm-raw",
        objects,
        metadata,
        verified_at=timestamp,
    )

    assert first.reused is False
    assert second.reused is True
    assert first.object_count == 5
    assert metadata.run_state == "available"
    assert reconcile_snapshot(first.snapshot_id, objects, metadata).consistent


def test_storage_success_database_failure_converges_on_retry(
    tmp_path: Path,
    accepted_snapshot: Snapshot,
) -> None:
    objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = FakeMetadataRepository(fail_commit_once=True)
    timestamp = datetime(2026, 7, 26, tzinfo=UTC)

    with pytest.raises(CloudFoundationError, match=r"metadata\.commit_failed"):
        publish_snapshot(
            accepted_snapshot,
            "pm-raw",
            objects,
            metadata,
            verified_at=timestamp,
        )
    assert metadata.run_state == "failed"
    assert metadata.stored is None

    recovered = publish_snapshot(
        accepted_snapshot,
        "pm-raw",
        objects,
        metadata,
        verified_at=timestamp,
    )
    assert recovered.state == "available"
    assert metadata.stored is not None


def test_missing_referenced_object_marks_snapshot_inconsistent(
    tmp_path: Path,
    accepted_snapshot: Snapshot,
) -> None:
    root = tmp_path / "objects"
    objects = FilesystemObjectRepository(root)
    metadata = FakeMetadataRepository()
    result = publish_snapshot(accepted_snapshot, "pm-raw", objects, metadata)
    assert metadata.stored is not None
    missing = metadata.stored.identities[1]
    (root / missing.bucket_name / missing.object_key).unlink()

    report = reconcile_snapshot(result.snapshot_id, objects, metadata)

    assert [finding.kind for finding in report.findings] == ["missing"]
    assert metadata.stored is not None
    assert metadata.stored.state == "inconsistent"


def test_mismatched_referenced_object_marks_snapshot_inconsistent(
    tmp_path: Path,
    accepted_snapshot: Snapshot,
) -> None:
    root = tmp_path / "objects"
    objects = FilesystemObjectRepository(root)
    metadata = FakeMetadataRepository()
    result = publish_snapshot(accepted_snapshot, "pm-raw", objects, metadata)
    assert metadata.stored is not None
    changed = metadata.stored.identities[1]
    (root / changed.bucket_name / changed.object_key).write_bytes(b"tampered")

    report = reconcile_snapshot(result.snapshot_id, objects, metadata)

    assert [finding.kind for finding in report.findings] == ["mismatched"]
    assert metadata.stored is not None
    assert metadata.stored.state == "inconsistent"


def test_orphan_is_reported_without_automatic_deletion(
    tmp_path: Path,
    accepted_snapshot: Snapshot,
) -> None:
    root = tmp_path / "objects"
    objects = FilesystemObjectRepository(root)
    metadata = FakeMetadataRepository()
    result = publish_snapshot(accepted_snapshot, "pm-raw", objects, metadata)
    orphan = root / "pm-raw" / f"fd001/{result.snapshot_id}/orphan.bin"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan")

    report = reconcile_snapshot(result.snapshot_id, objects, metadata)

    assert [finding.kind for finding in report.findings] == ["orphaned"]
    assert orphan.exists()
    assert metadata.stored is not None
    assert metadata.stored.state == "available"


def test_publication_keeps_phase_one_snapshot_identity(
    accepted_snapshot: Snapshot,
) -> None:
    publication = build_publication(accepted_snapshot, "pm-raw")
    assert publication.snapshot_id == accepted_snapshot.manifest.snapshot_id
    assert [item.logical_filename for item in publication.files] == [
        record.filename for record in accepted_snapshot.manifest.files
    ]
    assert publication.manifest.object_key.endswith("/manifest.json")
