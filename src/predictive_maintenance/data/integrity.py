"""Byte-level provenance and content-addressed local raw snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import BinaryIO

from predictive_maintenance.data.contract import (
    CONTRACT_VERSION,
    DATASET_FAMILY,
    DATASET_SUBSET,
    PARSER_VERSION,
    REQUIRED_FILENAMES,
    SOURCE_CITATION,
    SOURCE_URL,
    ContractError,
)

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileRecord:
    """Content identity for one required logical file."""

    filename: str
    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """Canonical, path-sanitized identity for one FD001 source set."""

    dataset_family: str
    dataset_subset: str
    snapshot_id: str
    contract_version: str
    parser_version: str
    code_revision: str
    source_url: str
    source_citation: str
    original_archive_checksum_available: bool
    files: tuple[FileRecord, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe dictionary with stable file ordering."""
        return asdict(self)

    def canonical_json(self) -> str:
        """Serialize deterministically for repeatable evidence."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Verified local raw snapshot."""

    path: Path
    manifest: SnapshotManifest
    reused: bool


def _digest_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    while chunk := stream.read(_CHUNK_SIZE):
        digest.update(chunk)
        byte_size += len(chunk)
    return digest.hexdigest(), byte_size


def inspect_file(path: Path, logical_file: str | None = None) -> FileRecord:
    """Calculate SHA-256 and byte size with bounded memory."""
    try:
        with path.open("rb") as stream:
            digest, byte_size = _digest_stream(stream)
    except OSError as error:
        raise ContractError(
            "source.file_unreadable",
            "Required source file could not be read.",
            logical_file or path.name,
        ) from error
    return FileRecord(logical_file or path.name, byte_size, digest)


def inspect_source_set(source_dir: Path) -> tuple[FileRecord, ...]:
    """Inspect exactly the owner-confirmed FD001 logical source set."""
    if not source_dir.is_dir():
        raise ContractError(
            "source.directory_missing",
            "The FD001 source directory does not exist.",
        )
    records: list[FileRecord] = []
    for filename in REQUIRED_FILENAMES:
        path = source_dir / filename
        if not path.is_file():
            raise ContractError(
                "source.required_file_missing",
                "A required FD001 source file is missing.",
                filename,
            )
        records.append(inspect_file(path, filename))
    return tuple(records)


def _snapshot_id(records: tuple[FileRecord, ...]) -> str:
    identity = {
        "contract_version": CONTRACT_VERSION,
        "dataset_subset": DATASET_SUBSET,
        "files": [asdict(record) for record in records],
        "parser_version": PARSER_VERSION,
        "source_citation": SOURCE_CITATION,
        "source_url": SOURCE_URL,
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def build_manifest(
    records: tuple[FileRecord, ...], code_revision: str = "unknown"
) -> SnapshotManifest:
    """Build the deterministic, sanitized manifest."""
    return SnapshotManifest(
        dataset_family=DATASET_FAMILY,
        dataset_subset=DATASET_SUBSET,
        snapshot_id=_snapshot_id(records),
        contract_version=CONTRACT_VERSION,
        parser_version=PARSER_VERSION,
        code_revision=code_revision,
        source_url=SOURCE_URL,
        source_citation=SOURCE_CITATION,
        original_archive_checksum_available=False,
        files=records,
    )


def _verify_existing(
    destination: Path, expected: SnapshotManifest
) -> SnapshotManifest:
    manifest_path = destination / "manifest.json"
    try:
        current_manifest = manifest_path.read_text(encoding="utf-8")
        payload = json.loads(current_manifest)
        persisted = SnapshotManifest(
            **{
                **payload,
                "files": tuple(FileRecord(**record) for record in payload["files"]),
            }
        )
    except OSError as error:
        raise ContractError(
            "snapshot.existing_incomplete",
            "An existing snapshot is missing its readable manifest.",
        ) from error
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ContractError(
            "snapshot.manifest_invalid",
            "An existing snapshot manifest is not valid canonical metadata.",
        ) from error
    if current_manifest != persisted.canonical_json() + "\n":
        raise ContractError(
            "snapshot.manifest_not_canonical",
            "An existing snapshot manifest is not canonical JSON.",
        )
    comparable_expected = replace(
        expected,
        code_revision=persisted.code_revision,
    )
    if persisted != comparable_expected:
        raise ContractError(
            "snapshot.manifest_mismatch",
            "An existing snapshot manifest does not match the expected identity.",
        )
    for expected_file in persisted.files:
        if not (destination / expected_file.filename).is_file():
            raise ContractError(
                "snapshot.existing_incomplete",
                "An existing snapshot is missing a required file.",
                expected_file.filename,
            )
        actual = inspect_file(
            destination / expected_file.filename,
            expected_file.filename,
        )
        if actual != expected_file:
            raise ContractError(
                "snapshot.content_mismatch",
                "An existing snapshot file failed byte-level verification.",
                expected_file.filename,
            )
    return persisted


def _exclusive_verified_copy(
    source: Path, destination: Path, expected: FileRecord
) -> None:
    try:
        with source.open("rb") as source_stream:
            with destination.open("xb") as destination_stream:
                shutil.copyfileobj(source_stream, destination_stream, _CHUNK_SIZE)
    except FileExistsError as error:
        raise ContractError(
            "snapshot.overwrite_denied",
            "Snapshot files are created exclusively and cannot be overwritten.",
            expected.filename,
        ) from error
    copied = inspect_file(destination, expected.filename)
    if copied != expected:
        raise ContractError(
            "snapshot.copy_verification_failed",
            "Copied bytes did not match the inspected source bytes.",
            expected.filename,
        )
    source_after_copy = inspect_file(source, expected.filename)
    if source_after_copy != expected:
        raise ContractError(
            "source.changed_during_copy",
            "Source bytes changed while the snapshot was being created.",
            expected.filename,
        )


def create_snapshot(
    source_dir: Path,
    raw_root: Path,
    *,
    code_revision: str = "unknown",
) -> Snapshot:
    """Create or verify an idempotent content-addressed FD001 snapshot."""
    records = inspect_source_set(source_dir)
    manifest = build_manifest(records, code_revision)
    subset_root = raw_root / DATASET_SUBSET.lower()
    destination = subset_root / manifest.snapshot_id

    if destination.exists():
        persisted = _verify_existing(destination, manifest)
        return Snapshot(destination, persisted, reused=True)

    subset_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=subset_root) as temporary:
        staging = Path(temporary)
        for record in records:
            _exclusive_verified_copy(
                source_dir / record.filename,
                staging / record.filename,
                record,
            )
        (staging / "manifest.json").write_text(
            manifest.canonical_json() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        try:
            os.replace(staging, destination)
        except OSError:
            if not destination.exists():
                raise
            _verify_existing(destination, manifest)

    manifest = _verify_existing(destination, manifest)
    return Snapshot(destination, manifest, reused=False)
