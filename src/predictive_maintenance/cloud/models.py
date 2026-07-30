"""Vendor-independent identities and results for Phase 2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ObjectZone = Literal["raw", "derived"]
SnapshotState = Literal["available", "inconsistent"]
FindingKind = Literal["missing", "mismatched", "orphaned"]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BUCKET = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.]{2,99}$")


class CloudFoundationError(Exception):
    """Stable, sanitized Phase 2 failure."""

    def __init__(self, code: str, message: str) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError("Cloud error codes must be stable lowercase identifiers.")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        """Return bounded details safe for reports."""
        return {"code": self.code, "message": self.message[:1000]}


def validate_sha256(value: str, *, field: str = "sha256") -> None:
    """Reject a value that is not a lowercase SHA-256 digest."""
    if not _SHA256.fullmatch(value):
        raise CloudFoundationError(
            "identity.invalid_sha256",
            f"{field} must contain 64 lowercase hexadecimal characters.",
        )


def validate_bucket_name(value: str) -> None:
    """Apply the project's conservative Storage bucket-name contract."""
    if not _BUCKET.fullmatch(value) or "--" in value:
        raise CloudFoundationError(
            "identity.invalid_bucket",
            "Bucket names must use 3-63 lowercase letters, digits, or single hyphens.",
        )


def validate_object_key(value: str) -> None:
    """Reject empty, ambiguous, or traversal-capable object keys."""
    if not value or len(value) > 1024 or value.startswith("/") or value.endswith("/"):
        raise CloudFoundationError(
            "identity.invalid_object_key",
            "Object keys must be relative non-empty paths of at most 1024 characters.",
        )
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise CloudFoundationError(
            "identity.invalid_object_key",
            "Object keys cannot contain empty or traversal path segments.",
        )
    if any("\\" in segment or "\x00" in segment for segment in segments):
        raise CloudFoundationError(
            "identity.invalid_object_key",
            "Object keys must use forward slashes and cannot contain null bytes.",
        )


def validate_logical_filename(value: str) -> None:
    """Reject path-like values where a simple logical filename is required."""
    if (
        not value
        or len(value) > 255
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise CloudFoundationError(
            "identity.invalid_logical_filename",
            "Logical filenames must be simple basename values.",
        )


@dataclass(frozen=True, slots=True)
class ObjectIdentity:
    """Expected and verified identity for one stored object."""

    bucket_name: str
    object_key: str
    zone: ObjectZone
    sha256: str
    byte_size: int
    content_type: str

    def __post_init__(self) -> None:
        validate_bucket_name(self.bucket_name)
        validate_object_key(self.object_key)
        validate_sha256(self.sha256)
        if self.byte_size < 0:
            raise CloudFoundationError(
                "identity.invalid_byte_size",
                "Object byte size cannot be negative.",
            )
        if not 1 <= len(self.content_type) <= 255:
            raise CloudFoundationError(
                "identity.invalid_content_type",
                "Object content type must contain 1-255 characters.",
            )


@dataclass(frozen=True, slots=True)
class ObjectPutResult:
    """Result of a verified put-if-absent operation."""

    identity: ObjectIdentity
    reused: bool


@dataclass(frozen=True, slots=True)
class SnapshotFile:
    """One ordered logical file in a dataset snapshot."""

    logical_filename: str
    file_position: int
    identity: ObjectIdentity

    def __post_init__(self) -> None:
        validate_logical_filename(self.logical_filename)
        if self.file_position <= 0:
            raise CloudFoundationError(
                "identity.invalid_file_position",
                "Snapshot file positions must be positive.",
            )


@dataclass(frozen=True, slots=True)
class SnapshotPublication:
    """Complete metadata transaction input after object verification."""

    snapshot_id: str
    dataset_family: str
    dataset_subset: str
    contract_version: str
    parser_version: str
    code_revision: str
    manifest: ObjectIdentity
    files: tuple[SnapshotFile, ...]
    verified_at: datetime

    def __post_init__(self) -> None:
        validate_sha256(self.snapshot_id, field="snapshot_id")
        if not self.files:
            raise CloudFoundationError(
                "publication.empty_snapshot",
                "A snapshot publication requires at least one logical file.",
            )
        positions = [item.file_position for item in self.files]
        filenames = [item.logical_filename for item in self.files]
        if len(set(positions)) != len(positions) or len(set(filenames)) != len(
            filenames
        ):
            raise CloudFoundationError(
                "publication.duplicate_file",
                "Snapshot filenames and positions must be unique.",
            )
        if sorted(positions) != list(range(1, len(self.files) + 1)):
            raise CloudFoundationError(
                "publication.non_contiguous_positions",
                "Snapshot file positions must form a contiguous sequence from one.",
            )

    @property
    def identities(self) -> tuple[ObjectIdentity, ...]:
        """Return manifest and files in deterministic order."""
        return (self.manifest, *(item.identity for item in self.files))


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    """Authoritative snapshot state returned by metadata storage."""

    snapshot_id: str
    state: SnapshotState
    manifest_sha256: str
    required_file_count: int
    identities: tuple[ObjectIdentity, ...]


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Sanitized publication outcome."""

    snapshot_id: str
    state: SnapshotState
    object_count: int
    reused: bool


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    """One deterministic difference between metadata and object storage."""

    kind: FindingKind
    bucket_name: str
    object_key: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Read-only reconciliation outcome."""

    snapshot_id: str
    findings: tuple[ReconciliationFinding, ...]

    @property
    def consistent(self) -> bool:
        """Return true only when no finding exists."""
        return not self.findings


def raw_file_key(snapshot_id: str, sha256: str, logical_filename: str) -> str:
    """Build a content-addressed FD001 raw file key."""
    validate_sha256(snapshot_id, field="snapshot_id")
    validate_sha256(sha256)
    validate_logical_filename(logical_filename)
    return f"fd001/{snapshot_id}/{sha256}/{logical_filename}"


def raw_manifest_key(snapshot_id: str) -> str:
    """Build the fixed manifest key for one FD001 snapshot."""
    validate_sha256(snapshot_id, field="snapshot_id")
    return f"fd001/{snapshot_id}/manifest.json"
