"""Stable identities and errors for deterministic Phase 3 artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from predictive_maintenance.cloud.models import ObjectIdentity

PROCESSED_CONTRACT_VERSION = "fd001-processed-v1"
FEATURE_SPEC_VERSION = "fd001-candidate-features-v1"
QUALITY_CONTRACT_VERSION = "fd001-data-quality-v1"
TRANSFORMATION_VERSION = "fd001-etl-v1"
PIPELINE_VERSION = "fd001-derived-pipeline-v1"
SERIALIZER_VERSION = "pyarrow-25.0.0-parquet-v1"
MANIFEST_VERSION = "derived-manifest-v1"

ArtifactKind = Literal["processed", "feature", "quality_report"]
ColumnRole = Literal["key", "feature", "target"]
LineageType = Literal["derived_from", "reported_by"]

_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.]{2,99}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EtlError(Exception):
    """Stable, bounded ETL failure safe for logs and reports."""

    def __init__(self, code: str, message: str) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError("ETL error codes must be stable lowercase identifiers.")
        bounded = message[:1000]
        super().__init__(f"{code}: {bounded}")
        self.code = code
        self.message = bounded

    def to_dict(self) -> dict[str, str]:
        """Return a sanitized JSON representation."""
        return {"code": self.code, "message": self.message}


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON with one canonical project-owned representation."""
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise EtlError(
            "serialization.invalid_json",
            "Artifact metadata is not valid finite JSON.",
        ) from error
    return (payload + "\n").encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ColumnContract:
    """One ordered column in a derived file."""

    name: str
    dtype: str
    role: ColumnRole


@dataclass(frozen=True, slots=True)
class ManifestFile:
    """Content and schema identity for one output file."""

    logical_filename: str
    file_position: int
    byte_size: int
    sha256: str
    content_type: str
    row_count: int | None
    columns: tuple[ColumnContract, ...]

    def __post_init__(self) -> None:
        if (
            not self.logical_filename
            or "/" in self.logical_filename
            or "\\" in self.logical_filename
            or self.logical_filename in {".", ".."}
        ):
            raise EtlError(
                "identity.invalid_filename",
                "Derived logical filenames must be simple basename values.",
            )
        if self.file_position <= 0 or self.byte_size < 0:
            raise EtlError(
                "identity.invalid_file_metadata",
                "Derived file positions must be positive and sizes non-negative.",
            )
        if not _SHA256.fullmatch(self.sha256):
            raise EtlError(
                "identity.invalid_sha256",
                "Derived file SHA-256 values must be lowercase hexadecimal digests.",
            )
        if self.row_count is not None and self.row_count < 0:
            raise EtlError(
                "identity.invalid_row_count",
                "Derived row counts cannot be negative.",
            )

    def to_dict(self) -> dict[str, Any]:
        """Return canonical JSON-ready metadata."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DerivedManifest:
    """Canonical content identity for a processed, feature, or report snapshot."""

    artifact_kind: ArtifactKind
    source_snapshot_id: str
    parent_snapshot_id: str
    contract_version: str
    transformation_version: str
    serializer_version: str
    code_revision: str
    files: tuple[ManifestFile, ...]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("source_snapshot_id", self.source_snapshot_id),
            ("parent_snapshot_id", self.parent_snapshot_id),
        ):
            if not _SHA256.fullmatch(value):
                raise EtlError(
                    "identity.invalid_snapshot_id",
                    f"{field_name} must be a lowercase SHA-256 digest.",
                )
        if not self.files:
            raise EtlError(
                "identity.empty_artifact",
                "A derived artifact requires at least one output file.",
            )
        positions = [item.file_position for item in self.files]
        names = [item.logical_filename for item in self.files]
        if positions != list(range(1, len(self.files) + 1)):
            raise EtlError(
                "identity.non_contiguous_files",
                "Derived file positions must be ordered from one without gaps.",
            )
        if len(names) != len(set(names)):
            raise EtlError(
                "identity.duplicate_filename",
                "Derived logical filenames must be unique.",
            )

    def identity_dict(self) -> dict[str, Any]:
        """Return fields that determine the derived snapshot ID."""
        return {
            "artifact_kind": self.artifact_kind,
            "code_revision": self.code_revision,
            "contract_version": self.contract_version,
            "files": [item.to_dict() for item in self.files],
            "manifest_version": MANIFEST_VERSION,
            "parent_snapshot_id": self.parent_snapshot_id,
            "serializer_version": self.serializer_version,
            "source_snapshot_id": self.source_snapshot_id,
            "transformation_version": self.transformation_version,
        }

    @property
    def snapshot_id(self) -> str:
        """Hash the canonical identity without execution timestamps."""
        return sha256_bytes(canonical_json_bytes(self.identity_dict()))

    def to_dict(self) -> dict[str, Any]:
        """Return the stored manifest with its derived ID."""
        return {"derived_snapshot_id": self.snapshot_id, **self.identity_dict()}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored manifest bytes."""
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class MaterializedFile:
    """One local file and the metadata that identifies it."""

    path: Path
    record: ManifestFile


@dataclass(frozen=True, slots=True)
class MaterializedArtifact:
    """Complete local artifact ready for immutable publication."""

    manifest: DerivedManifest
    manifest_path: Path
    files: tuple[MaterializedFile, ...]

    @property
    def snapshot_id(self) -> str:
        """Expose the content-derived snapshot identifier."""
        return self.manifest.snapshot_id


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Bounded identifiers returned by direct and orchestrated runs."""

    source_snapshot_id: str
    processed_snapshot_id: str
    feature_snapshot_id: str
    quality_snapshot_id: str
    reused: bool

    def to_dict(self) -> dict[str, str | bool]:
        """Return an identifier-only payload suitable for CLI output or XCom."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DerivedFilePublication:
    """One verified output file and its object-level lineage."""

    logical_filename: str
    file_position: int
    identity: ObjectIdentity
    schema: tuple[dict[str, str], ...]
    column_roles: dict[str, str]
    parents: tuple[ObjectIdentity, ...]
    relationship_type: LineageType


@dataclass(frozen=True, slots=True)
class DerivedSnapshotPublication:
    """Complete metadata for one materialized artifact."""

    derived_snapshot_id: str
    source_snapshot_id: str
    parent_derived_snapshot_id: str | None
    artifact_kind: ArtifactKind
    contract_version: str
    transformation_version: str
    serializer_version: str
    code_revision: str
    manifest: ObjectIdentity
    files: tuple[DerivedFilePublication, ...]

    @property
    def identities(self) -> tuple[ObjectIdentity, ...]:
        """Return the manifest followed by ordered output objects."""
        return (self.manifest, *(item.identity for item in self.files))


@dataclass(frozen=True, slots=True)
class DerivedBatchPublication:
    """One all-or-nothing metadata transaction after object publication."""

    idempotency_key: str
    source_snapshot_id: str
    pipeline_version: str
    code_revision: str
    artifacts: tuple[DerivedSnapshotPublication, ...]
    verified_at: datetime


@dataclass(frozen=True, slots=True)
class StoredDerivedSnapshot:
    """Authoritative derived snapshot returned by PostgreSQL."""

    derived_snapshot_id: str
    source_snapshot_id: str
    parent_derived_snapshot_id: str | None
    artifact_kind: ArtifactKind
    contract_version: str
    state: Literal["available", "inconsistent"]
    manifest_sha256: str
    identities: tuple[ObjectIdentity, ...]
