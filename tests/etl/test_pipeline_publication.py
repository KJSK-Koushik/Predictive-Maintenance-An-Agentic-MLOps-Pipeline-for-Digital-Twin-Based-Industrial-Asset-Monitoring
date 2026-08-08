"""Direct pipeline, retry, exact reuse, and reconciliation tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from predictive_maintenance.cloud.models import SnapshotPublication, StoredSnapshot
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import build_publication
from predictive_maintenance.data.pipeline import IngestionResult
from predictive_maintenance.etl.extraction import extract_validated_source
from predictive_maintenance.etl.models import (
    DerivedBatchPublication,
    EtlError,
    StoredDerivedSnapshot,
)
from predictive_maintenance.etl.pipeline import run_pipeline
from predictive_maintenance.etl.publication import reconcile_derived_snapshot


@dataclass
class FakeRawMetadata:
    """Read-only authoritative raw snapshot metadata."""

    stored: StoredSnapshot | None

    def get_snapshot(self, snapshot_id: str) -> StoredSnapshot | None:
        if self.stored is not None and self.stored.snapshot_id == snapshot_id:
            return self.stored
        return None

    def begin_run(self, snapshot_id: str, started_at: datetime) -> None:
        raise AssertionError("Phase 3 extraction must not open a raw ingestion run")

    def commit_publication(self, publication: SnapshotPublication) -> StoredSnapshot:
        raise AssertionError("Phase 3 extraction must not publish raw metadata")

    def record_failure(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        raise AssertionError("Phase 3 extraction must not mutate raw metadata")

    def mark_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        raise AssertionError("Phase 3 extraction must not mutate raw metadata")


@dataclass
class FakeDerivedMetadata:
    """Deterministic metadata substitute for application integration tests."""

    snapshots: dict[str, StoredDerivedSnapshot] = field(default_factory=dict)
    run_state: str | None = None
    failure_code: str | None = None
    fail_commit_once: bool = False
    last_batch: DerivedBatchPublication | None = None

    def begin_transformation(self, publication: DerivedBatchPublication) -> None:
        self.last_batch = publication
        if self.run_state != "available":
            self.run_state = "started"

    def get_derived_snapshot(self, snapshot_id: str) -> StoredDerivedSnapshot | None:
        return self.snapshots.get(snapshot_id)

    def commit_derived_batch(self, publication: DerivedBatchPublication) -> bool:
        if self.fail_commit_once:
            self.fail_commit_once = False
            raise EtlError("metadata.derived_commit_failed", "Injected failure.")
        reused = True
        for item in publication.artifacts:
            expected = StoredDerivedSnapshot(
                derived_snapshot_id=item.derived_snapshot_id,
                source_snapshot_id=item.source_snapshot_id,
                parent_derived_snapshot_id=item.parent_derived_snapshot_id,
                artifact_kind=item.artifact_kind,
                contract_version=item.contract_version,
                state="available",
                manifest_sha256=item.manifest.sha256,
                identities=item.identities,
            )
            current = self.snapshots.get(item.derived_snapshot_id)
            if current is None:
                self.snapshots[item.derived_snapshot_id] = expected
                reused = False
            elif current != expected:
                raise EtlError(
                    "metadata.derived_snapshot_conflict",
                    "Injected derived metadata conflict.",
                )
        self.run_state = "available"
        return reused

    def record_transformation_failure(
        self,
        idempotency_key: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        del idempotency_key, error_detail, finished_at
        if self.run_state != "available":
            self.run_state = "failed"
            self.failure_code = error_code

    def mark_derived_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        del error_detail, detected_at
        current = self.snapshots[snapshot_id]
        self.snapshots[snapshot_id] = StoredDerivedSnapshot(
            derived_snapshot_id=current.derived_snapshot_id,
            source_snapshot_id=current.source_snapshot_id,
            parent_derived_snapshot_id=current.parent_derived_snapshot_id,
            artifact_kind=current.artifact_kind,
            contract_version=current.contract_version,
            state="inconsistent",
            manifest_sha256=current.manifest_sha256,
            identities=current.identities,
        )
        self.run_state = "inconsistent"
        self.failure_code = error_code


def _published_raw(
    tmp_path: Path, ingestion: IngestionResult
) -> tuple[FilesystemObjectRepository, FakeRawMetadata]:
    objects = FilesystemObjectRepository(tmp_path / "objects")
    snapshot = ingestion.snapshot
    publication = build_publication(snapshot, "pm-raw")
    for item in publication.files:
        objects.put_verified(snapshot.path / item.logical_filename, item.identity)
    objects.put_verified(snapshot.path / "manifest.json", publication.manifest)
    stored = StoredSnapshot(
        snapshot_id=publication.snapshot_id,
        state="available",
        manifest_sha256=publication.manifest.sha256,
        required_file_count=len(publication.files),
        identities=publication.identities,
    )
    return objects, FakeRawMetadata(stored)


def test_direct_pipeline_publishes_all_artifacts_and_exactly_reuses(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    objects, raw = _published_raw(tmp_path, ingestion)
    derived = FakeDerivedMetadata()
    source_id = ingestion.snapshot.manifest.snapshot_id

    first = run_pipeline(
        source_id,
        "pm-derived",
        objects,
        raw,
        derived,
        code_revision="abc123",
    )
    second = run_pipeline(
        source_id,
        "pm-derived",
        objects,
        raw,
        derived,
        code_revision="abc123",
    )

    assert first.reused is False
    assert second == type(second)(
        source_id,
        first.processed_snapshot_id,
        first.feature_snapshot_id,
        first.quality_snapshot_id,
        True,
    )
    assert derived.run_state == "available"
    assert len(derived.snapshots) == 3
    assert len(objects.list_keys("pm-derived", "processed/fd001")) == 3
    assert len(objects.list_keys("pm-derived", "features/fd001")) == 5
    assert len(objects.list_keys("pm-derived", "reports/data-quality")) == 2


def test_storage_success_metadata_failure_converges_on_retry(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    objects, raw = _published_raw(tmp_path, ingestion)
    derived = FakeDerivedMetadata(fail_commit_once=True)
    source_id = ingestion.snapshot.manifest.snapshot_id

    with pytest.raises(EtlError, match=r"metadata\.derived_commit_failed"):
        run_pipeline(
            source_id,
            "pm-derived",
            objects,
            raw,
            derived,
            code_revision="abc123",
        )
    assert derived.run_state == "failed"
    assert not derived.snapshots

    recovered = run_pipeline(
        source_id,
        "pm-derived",
        objects,
        raw,
        derived,
        code_revision="abc123",
    )
    assert recovered.reused is False
    assert derived.run_state == "available"
    assert len(derived.snapshots) == 3


def test_unknown_or_inconsistent_raw_source_fails_before_artifacts(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    objects, raw = _published_raw(tmp_path, ingestion)
    derived = FakeDerivedMetadata()
    with pytest.raises(EtlError, match=r"source\.not_found"):
        run_pipeline(
            "f" * 64,
            "pm-derived",
            objects,
            raw,
            derived,
            code_revision="abc123",
        )
    assert not objects.list_keys("pm-derived", "processed/fd001")

    assert raw.stored is not None
    raw.stored = StoredSnapshot(
        raw.stored.snapshot_id,
        "inconsistent",
        raw.stored.manifest_sha256,
        raw.stored.required_file_count,
        raw.stored.identities,
    )
    with pytest.raises(EtlError, match=r"source\.not_available"):
        run_pipeline(
            raw.stored.snapshot_id,
            "pm-derived",
            objects,
            raw,
            derived,
            code_revision="abc123",
        )


def test_raw_object_tampering_is_rejected_before_transformation(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    objects, raw = _published_raw(tmp_path, ingestion)
    assert raw.stored is not None
    identity = raw.stored.identities[1]
    tampered = tmp_path / "objects" / identity.bucket_name / identity.object_key
    tampered.write_bytes(b"tampered")
    with pytest.raises(EtlError, match=r"source\.object_(size|hash)_mismatch"):
        extract_validated_source(
            raw.stored.snapshot_id,
            objects,
            raw,
            tmp_path / "extract",
            code_revision="abc123",
        )


def test_missing_derived_object_marks_snapshot_inconsistent(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    objects, raw = _published_raw(tmp_path, ingestion)
    derived = FakeDerivedMetadata()
    result = run_pipeline(
        ingestion.snapshot.manifest.snapshot_id,
        "pm-derived",
        objects,
        raw,
        derived,
        code_revision="abc123",
    )
    stored = derived.snapshots[result.processed_snapshot_id]
    missing = stored.identities[1]
    path = tmp_path / "objects" / missing.bucket_name / missing.object_key
    if path.drive:
        path = Path("\\\\?\\" + str(path))
    path.unlink()

    report = reconcile_derived_snapshot(
        result.processed_snapshot_id,
        objects,
        derived,
    )

    assert [item.kind for item in report.findings] == ["missing"]
    assert derived.snapshots[result.processed_snapshot_id].state == "inconsistent"
    assert derived.run_state == "inconsistent"


def test_raw_metadata_protocol_is_read_only_during_extraction(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    objects, raw = _published_raw(tmp_path, ingestion)
    validated = extract_validated_source(
        ingestion.snapshot.manifest.snapshot_id,
        objects,
        raw,
        tmp_path / "extract",
        code_revision="abc123",
    )
    assert validated.ingestion.snapshot.manifest.snapshot_id == (
        ingestion.snapshot.manifest.snapshot_id
    )
    assert set(validated.raw_files) == {
        "train_FD001.txt",
        "test_FD001.txt",
        "RUL_FD001.txt",
        "readme.txt",
    }
