"""Shared local object-store contract and failure behavior."""

from __future__ import annotations

import hashlib
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    ObjectIdentity,
)
from predictive_maintenance.cloud.object_store import (
    MAX_STANDARD_OBJECT_BYTES,
    FilesystemObjectRepository,
)


def _identity(
    payload: bytes, *, key: str = "fd001/snapshot/file.txt"
) -> ObjectIdentity:
    return ObjectIdentity(
        bucket_name="pm-raw",
        object_key=key,
        zone="raw",
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        content_type="text/plain",
    )


def test_filesystem_first_put_and_exact_reuse(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    repository = FilesystemObjectRepository(tmp_path / "objects")
    identity = _identity(b"telemetry")

    first = repository.put_verified(source, identity)
    second = repository.put_verified(source, identity)

    assert first.reused is False
    assert second.reused is True
    assert repository.read(identity.bucket_name, identity.object_key) == b"telemetry"
    assert repository.list_keys("pm-raw", "fd001/snapshot") == (
        "fd001/snapshot/file.txt",
    )


def test_exact_reuse_does_not_require_a_temporary_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    repository = FilesystemObjectRepository(tmp_path / "objects")
    identity = _identity(b"telemetry")
    repository.put_verified(source, identity)

    def reject_temporary_write(*args: object, **kwargs: object) -> None:
        raise AssertionError("exact reuse must not create a temporary file")

    monkeypatch.setattr(tempfile, "mkstemp", reject_temporary_write)

    assert repository.put_verified(source, identity).reused is True


def test_first_put_sets_shared_runtime_read_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    repository = FilesystemObjectRepository(tmp_path / "objects")
    chmod_modes: list[int] = []
    original_chmod = Path.chmod

    def record_chmod(path: Path, mode: int, *, follow_symlinks: bool = True) -> None:
        chmod_modes.append(mode)
        original_chmod(path, mode, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "chmod", record_chmod)

    repository.put_verified(source, _identity(b"telemetry"))

    assert chmod_modes == [0o644]


def test_existing_different_bytes_fail_closed(tmp_path: Path) -> None:
    first_source = tmp_path / "first.txt"
    first_source.write_bytes(b"first")
    second_source = tmp_path / "second.txt"
    second_source.write_bytes(b"second")
    repository = FilesystemObjectRepository(tmp_path / "objects")
    first = _identity(b"first")
    repository.put_verified(first_source, first)

    conflict = _identity(b"second")
    with pytest.raises(
        CloudFoundationError,
        match=r"object\.identity_conflict",
    ):
        repository.put_verified(second_source, conflict)


def test_source_identity_must_match_before_write(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"actual")
    repository = FilesystemObjectRepository(tmp_path / "objects")
    with pytest.raises(
        CloudFoundationError,
        match=r"object\.identity_conflict",
    ):
        repository.put_verified(source, _identity(b"expected"))
    assert repository.list_keys("pm-raw", "fd001/snapshot") == ()


def test_concurrent_same_key_has_one_creator(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"concurrent")
    repository = FilesystemObjectRepository(tmp_path / "objects")
    identity = _identity(b"concurrent")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: repository.put_verified(source, identity),
                range(2),
            )
        )
    assert sorted(result.reused for result in results) == [False, True]


def test_read_missing_object_has_stable_error(tmp_path: Path) -> None:
    repository = FilesystemObjectRepository(tmp_path / "objects")
    with pytest.raises(CloudFoundationError, match=r"object\.not_found"):
        repository.read("pm-raw", "fd001/missing/file.txt")


def test_read_enforces_phase_two_size_limit(tmp_path: Path) -> None:
    root = tmp_path / "objects"
    path = root / "pm-raw/fd001/snapshot/large.bin"
    path.parent.mkdir(parents=True)
    with path.open("wb") as stream:
        stream.truncate(MAX_STANDARD_OBJECT_BYTES + 1)
    repository = FilesystemObjectRepository(root)
    with pytest.raises(
        CloudFoundationError,
        match=r"object\.size_limit_exceeded",
    ):
        repository.read("pm-raw", "fd001/snapshot/large.bin")


def test_normal_interface_has_no_update_or_delete_method(tmp_path: Path) -> None:
    repository = FilesystemObjectRepository(tmp_path / "objects")
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
