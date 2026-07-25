from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from predictive_maintenance.data.contract import ContractError, REQUIRED_FILENAMES
from predictive_maintenance.data.integrity import (
    build_manifest,
    create_snapshot,
    inspect_file,
    inspect_source_set,
)


def test_inspect_file_matches_known_sha256(tmp_path: Path) -> None:
    path = tmp_path / "known.txt"
    path.write_bytes(b"abc")

    record = inspect_file(path)

    assert record.byte_size == 3
    assert record.sha256 == hashlib.sha256(b"abc").hexdigest()


def test_missing_required_file_has_stable_error(valid_source: Path) -> None:
    (valid_source / "readme.txt").unlink()

    with pytest.raises(ContractError, match="source.required_file_missing") as error:
        inspect_source_set(valid_source)

    assert error.value.logical_file == "readme.txt"


def test_manifest_is_deterministic_and_sanitized(valid_source: Path) -> None:
    records = inspect_source_set(valid_source)

    first = build_manifest(records, "revision")
    second = build_manifest(records, "revision")

    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert str(valid_source.resolve()) not in first.canonical_json()
    assert list(json.loads(first.canonical_json())) == sorted(
        json.loads(first.canonical_json())
    )
    assert first.original_archive_checksum_available is False


def test_snapshot_copies_exact_bytes_and_reuses(valid_source: Path, tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"

    first = create_snapshot(valid_source, raw_root, code_revision="revision")
    second = create_snapshot(valid_source, raw_root, code_revision="new-revision")

    assert first.reused is False
    assert second.reused is True
    assert first.path == second.path
    assert second.manifest.code_revision == "revision"
    for filename in REQUIRED_FILENAMES:
        assert (first.path / filename).read_bytes() == (
            valid_source / filename
        ).read_bytes()


def test_changed_source_bytes_create_a_new_identity(
    valid_source: Path, tmp_path: Path
) -> None:
    raw_root = tmp_path / "raw"
    first = create_snapshot(valid_source, raw_root)
    readme = valid_source / "readme.txt"
    readme.write_bytes(readme.read_bytes() + b"changed\n")

    second = create_snapshot(valid_source, raw_root)

    assert first.path != second.path
    assert first.manifest.snapshot_id != second.manifest.snapshot_id


def test_tampered_existing_snapshot_is_rejected(
    valid_source: Path, tmp_path: Path
) -> None:
    snapshot = create_snapshot(valid_source, tmp_path / "raw")
    (snapshot.path / "train_FD001.txt").write_text("tampered\n", encoding="ascii")

    with pytest.raises(ContractError, match="snapshot.content_mismatch"):
        create_snapshot(valid_source, tmp_path / "raw")


def test_manifest_tampering_is_rejected(valid_source: Path, tmp_path: Path) -> None:
    snapshot = create_snapshot(valid_source, tmp_path / "raw")
    (snapshot.path / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ContractError, match="snapshot.manifest_invalid"):
        create_snapshot(valid_source, tmp_path / "raw")


def test_incomplete_existing_snapshot_is_rejected(
    valid_source: Path, tmp_path: Path
) -> None:
    snapshot = create_snapshot(valid_source, tmp_path / "raw")
    (snapshot.path / "test_FD001.txt").unlink()

    with pytest.raises(ContractError, match="snapshot.existing_incomplete"):
        create_snapshot(valid_source, tmp_path / "raw")


def test_non_directory_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="source.directory_missing"):
        inspect_source_set(tmp_path / "missing")
