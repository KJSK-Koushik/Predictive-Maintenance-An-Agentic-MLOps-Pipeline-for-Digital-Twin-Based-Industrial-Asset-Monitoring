"""Supabase Storage adapter contract tests using an in-memory SDK boundary."""

from __future__ import annotations

import hashlib
import io
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, BinaryIO, cast

import pytest
from storage3.exceptions import StorageApiError

from predictive_maintenance.cloud.models import CloudFoundationError, ObjectIdentity
from predictive_maintenance.cloud.object_store import (
    MAX_STANDARD_OBJECT_BYTES,
    SupabaseObjectRepository,
)
from supabase import Client


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


@dataclass
class _BucketRecord:
    id: str
    public: bool


class _FakeBucket:
    def __init__(self, storage: _FakeStorage, name: str) -> None:
        self._storage = storage
        self._name = name

    def upload(
        self,
        path: str,
        stream: BinaryIO,
        options: dict[str, str],
    ) -> None:
        self._storage.last_options = options
        if self._storage.upload_error is not None:
            raise self._storage.upload_error
        payload = stream.read()
        identity = (self._name, path)
        with self._storage.lock:
            if identity in self._storage.objects:
                raise StorageApiError("The resource already exists", "Duplicate", 400)
            self._storage.objects[identity] = payload

    def download(self, path: str) -> bytes:
        if self._storage.download_error is not None:
            raise self._storage.download_error
        try:
            return self._storage.objects[(self._name, path)]
        except KeyError as error:
            raise StorageApiError("Object not found", "not_found", 404) from error

    def list(self, prefix: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        children: dict[str, dict[str, Any]] = {}
        prefix_with_slash = f"{prefix}/"
        for bucket_name, key in self._storage.objects:
            if bucket_name != self._name or not key.startswith(prefix_with_slash):
                continue
            relative = key[len(prefix_with_slash) :]
            name, separator, _ = relative.partition("/")
            children[name] = {
                "name": name,
                "metadata": None if separator else {"size": len(self.download(key))},
            }
        ordered = [children[name] for name in sorted(children)]
        offset = int(options["offset"])
        limit = int(options["limit"])
        return ordered[offset : offset + limit]


class _FakeStorage:
    def __init__(self) -> None:
        self.buckets: dict[str, _BucketRecord] = {}
        self.objects: dict[tuple[str, str], bytes] = {}
        self.last_options: dict[str, str] | None = None
        self.upload_error: StorageApiError | None = None
        self.download_error: StorageApiError | None = None
        self.lock = threading.Lock()

    def list_buckets(self) -> list[_BucketRecord]:
        return list(self.buckets.values())

    def create_bucket(self, name: str, *, options: dict[str, Any]) -> None:
        self.buckets[name] = _BucketRecord(name, bool(options["public"]))

    def from_(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)


def _repository(storage: _FakeStorage) -> SupabaseObjectRepository:
    fake_client = SimpleNamespace(storage=storage)
    return SupabaseObjectRepository(cast(Client, fake_client))


def test_supabase_adapter_creates_private_buckets() -> None:
    storage = _FakeStorage()
    repository = _repository(storage)

    repository.ensure_private_buckets("pm-raw", "pm-derived")

    assert storage.buckets == {
        "pm-raw": _BucketRecord("pm-raw", False),
        "pm-derived": _BucketRecord("pm-derived", False),
    }


def test_supabase_adapter_rejects_public_existing_bucket() -> None:
    storage = _FakeStorage()
    storage.buckets["pm-raw"] = _BucketRecord("pm-raw", True)

    with pytest.raises(CloudFoundationError, match=r"storage\.public_bucket"):
        _repository(storage).ensure_private_buckets("pm-raw", "pm-derived")


def test_supabase_first_put_exact_reuse_and_recursive_listing(tmp_path: Path) -> None:
    storage = _FakeStorage()
    repository = _repository(storage)
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    identity = _identity(b"telemetry")

    first = repository.put_verified(source, identity)
    second = repository.put_verified(source, identity)
    nested = _identity(b"nested", key="fd001/snapshot/nested/second.txt")
    nested_source = tmp_path / "nested.txt"
    nested_source.write_bytes(b"nested")
    repository.put_verified(nested_source, nested)

    assert first.reused is False
    assert second.reused is True
    assert storage.last_options == {
        "content-type": "text/plain",
        "upsert": "false",
    }
    assert repository.read("pm-raw", identity.object_key) == b"telemetry"
    assert repository.list_keys("pm-raw", "fd001/snapshot") == (
        "fd001/snapshot/file.txt",
        "fd001/snapshot/nested/second.txt",
    )


def test_supabase_adapter_reuses_hosted_409_duplicate(tmp_path: Path) -> None:
    storage = _FakeStorage()
    repository = _repository(storage)
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    identity = _identity(b"telemetry")
    storage.objects[("pm-raw", identity.object_key)] = b"telemetry"
    storage.upload_error = StorageApiError(
        "The resource already exists",
        "Duplicate",
        409,
    )

    result = repository.put_verified(source, identity)

    assert result.reused is True


def test_supabase_existing_different_bytes_fail_closed(tmp_path: Path) -> None:
    storage = _FakeStorage()
    repository = _repository(storage)
    source = tmp_path / "source.txt"
    source.write_bytes(b"expected")
    identity = _identity(b"expected")
    storage.objects[("pm-raw", identity.object_key)] = b"different"

    with pytest.raises(CloudFoundationError, match=r"object\.identity_conflict"):
        repository.put_verified(source, identity)


def test_supabase_upload_and_download_errors_are_sanitized(tmp_path: Path) -> None:
    storage = _FakeStorage()
    repository = _repository(storage)
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    identity = _identity(b"telemetry")
    storage.upload_error = StorageApiError("private endpoint detail", "boom", 500)

    with pytest.raises(CloudFoundationError, match=r"storage\.upload_failed"):
        repository.put_verified(source, identity)

    storage.upload_error = None
    storage.download_error = StorageApiError("private endpoint detail", "boom", 500)
    with pytest.raises(CloudFoundationError, match=r"storage\.download_failed"):
        repository.read("pm-raw", identity.object_key)


def test_supabase_missing_and_oversized_downloads_fail_closed() -> None:
    storage = _FakeStorage()
    repository = _repository(storage)
    with pytest.raises(CloudFoundationError, match=r"object\.not_found"):
        repository.read("pm-raw", "fd001/missing.txt")

    storage.objects[("pm-raw", "fd001/large.bin")] = b"x" * (
        MAX_STANDARD_OBJECT_BYTES + 1
    )
    with pytest.raises(CloudFoundationError, match=r"object\.size_limit_exceeded"):
        repository.read("pm-raw", "fd001/large.bin")


def test_supabase_put_checks_size_and_source_identity(tmp_path: Path) -> None:
    storage = _FakeStorage()
    repository = _repository(storage)
    source = tmp_path / "source.txt"
    source.write_bytes(b"actual")

    with pytest.raises(CloudFoundationError, match=r"object\.size_limit_exceeded"):
        repository.put_verified(
            source,
            ObjectIdentity(
                bucket_name="pm-raw",
                object_key="fd001/large.bin",
                zone="raw",
                sha256=hashlib.sha256(b"actual").hexdigest(),
                byte_size=MAX_STANDARD_OBJECT_BYTES + 1,
                content_type="application/octet-stream",
            ),
        )

    with pytest.raises(CloudFoundationError, match=r"object\.identity_conflict"):
        repository.put_verified(source, _identity(b"expected"))


def test_supabase_source_open_failure_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"telemetry")
    identity = _identity(b"telemetry")
    repository = _repository(_FakeStorage())
    original_open = Path.open
    calls = 0

    def fail_second_open(path: Path, *args: Any, **kwargs: Any) -> io.BytesIO:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("private local path")
        return cast(io.BytesIO, original_open(path, *args, **kwargs))

    monkeypatch.setattr(Path, "open", fail_second_open)
    with pytest.raises(CloudFoundationError, match=r"object\.source_unreadable"):
        repository.put_verified(source, identity)
