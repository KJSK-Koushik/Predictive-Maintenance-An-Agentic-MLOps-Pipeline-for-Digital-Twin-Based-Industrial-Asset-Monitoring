"""Put-if-absent object repositories for local and Supabase Storage."""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Protocol

from storage3.exceptions import StorageApiError
from storage3.types import (
    CreateOrUpdateBucketOptions,
    FileOptions,
    ListBucketFilesOptions,
)

from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    ObjectIdentity,
    ObjectPutResult,
    validate_bucket_name,
    validate_object_key,
)
from supabase import Client

_CHUNK_SIZE = 1024 * 1024
MAX_STANDARD_OBJECT_BYTES = 6 * 1024 * 1024


class ObjectRepository(Protocol):
    """Narrow object boundary without update or delete operations."""

    def put_verified(self, source: Path, expected: ObjectIdentity) -> ObjectPutResult:
        """Create an object or verify exact existing bytes."""
        ...

    def read(self, bucket_name: str, object_key: str) -> bytes:
        """Read one bounded object or fail with a stable not-found code."""
        ...

    def list_keys(self, bucket_name: str, prefix: str) -> tuple[str, ...]:
        """List object keys below a controlled prefix."""
        ...


def _digest_chunks(chunks: Iterator[bytes]) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    for chunk in chunks:
        digest.update(chunk)
        byte_size += len(chunk)
    return digest.hexdigest(), byte_size


def _file_chunks(stream: BinaryIO) -> Iterator[bytes]:
    while chunk := stream.read(_CHUNK_SIZE):
        yield chunk


def inspect_path(path: Path) -> tuple[str, int]:
    """Hash one file with bounded memory."""
    try:
        with path.open("rb") as stream:
            return _digest_chunks(_file_chunks(stream))
    except OSError as error:
        raise CloudFoundationError(
            "object.source_unreadable",
            "The source object could not be read.",
        ) from error


def _verify_expected_bytes(
    actual_sha256: str, actual_size: int, expected: ObjectIdentity
) -> None:
    if actual_sha256 != expected.sha256 or actual_size != expected.byte_size:
        raise CloudFoundationError(
            "object.identity_conflict",
            "Stored bytes do not match the expected SHA-256 and byte size.",
        )


class FilesystemObjectRepository:
    """Local object substitute with exclusive creation."""

    def __init__(self, root: Path) -> None:
        resolved = root.resolve()
        if os.name == "nt" and not str(resolved).startswith("\\\\?\\"):
            resolved = Path("\\\\?\\" + str(resolved))
        self._root = resolved

    def _path(self, bucket_name: str, object_key: str) -> Path:
        validate_bucket_name(bucket_name)
        validate_object_key(object_key)
        candidate = (self._root / bucket_name / Path(*object_key.split("/"))).resolve()
        bucket_root = (self._root / bucket_name).resolve()
        if candidate == bucket_root or bucket_root not in candidate.parents:
            raise CloudFoundationError(
                "identity.object_path_escape",
                "The object key escaped its bucket root.",
            )
        return candidate

    def put_verified(self, source: Path, expected: ObjectIdentity) -> ObjectPutResult:
        """Copy exact bytes once and verify a concurrent existing winner."""
        source_sha256, source_size = inspect_path(source)
        _verify_expected_bytes(source_sha256, source_size, expected)
        destination = self._path(expected.bucket_name, expected.object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        created = False
        try:
            with (
                source.open("rb") as source_stream,
                destination.open("xb") as destination_stream,
            ):
                created = True
                shutil.copyfileobj(
                    source_stream,
                    destination_stream,
                    _CHUNK_SIZE,
                )
        except FileExistsError:
            created = False
        except OSError as error:
            if created:
                destination.unlink(missing_ok=True)
            raise CloudFoundationError(
                "object.write_failed",
                "The local object could not be written.",
            ) from error

        actual_sha256, actual_size = inspect_path(destination)
        _verify_expected_bytes(actual_sha256, actual_size, expected)
        source_after_sha256, source_after_size = inspect_path(source)
        _verify_expected_bytes(source_after_sha256, source_after_size, expected)
        return ObjectPutResult(expected, reused=not created)

    def read(self, bucket_name: str, object_key: str) -> bytes:
        """Read a bounded local object."""
        path = self._path(bucket_name, object_key)
        try:
            size = path.stat().st_size
            if size > MAX_STANDARD_OBJECT_BYTES:
                raise CloudFoundationError(
                    "object.size_limit_exceeded",
                    "The object exceeds the Phase 2 standard-upload size limit.",
                )
            return path.read_bytes()
        except FileNotFoundError as error:
            raise CloudFoundationError(
                "object.not_found",
                "The requested object does not exist.",
            ) from error
        except OSError as error:
            raise CloudFoundationError(
                "object.read_failed",
                "The requested object could not be read.",
            ) from error

    def list_keys(self, bucket_name: str, prefix: str) -> tuple[str, ...]:
        """Return deterministic keys under a safe local prefix."""
        validate_bucket_name(bucket_name)
        validate_object_key(prefix)
        bucket_root = (self._root / bucket_name).resolve()
        prefix_root = self._path(bucket_name, prefix)
        if prefix_root.is_file():
            return (prefix,)
        if not prefix_root.exists():
            return ()
        keys = [
            path.relative_to(bucket_root).as_posix()
            for path in prefix_root.rglob("*")
            if path.is_file()
        ]
        return tuple(sorted(keys))


class SupabaseObjectRepository:
    """Supabase Storage adapter using non-upsert standard uploads."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def ensure_private_buckets(
        self,
        raw_bucket: str,
        derived_bucket: str,
    ) -> None:
        """Create missing private buckets and reject public existing buckets."""
        for bucket_name in (raw_bucket, derived_bucket):
            validate_bucket_name(bucket_name)
        existing = {bucket.id: bucket for bucket in self._client.storage.list_buckets()}
        for bucket_name in (raw_bucket, derived_bucket):
            bucket = existing.get(bucket_name)
            if bucket is None:
                options: CreateOrUpdateBucketOptions = {
                    "public": False,
                    "file_size_limit": MAX_STANDARD_OBJECT_BYTES,
                }
                self._client.storage.create_bucket(bucket_name, options=options)
            elif bucket.public:
                raise CloudFoundationError(
                    "storage.public_bucket",
                    "An approved Phase 2 bucket is public.",
                )

    @staticmethod
    def _is_existing_object(error: StorageApiError) -> bool:
        status = str(error.status)
        message = error.message.lower()
        code = error.code.lower()
        return status == "400" and (
            "already exists" in message or "duplicate" in message or "duplicate" in code
        )

    def put_verified(self, source: Path, expected: ObjectIdentity) -> ObjectPutResult:
        """Upload without upsert, then download and rehash."""
        if expected.byte_size > MAX_STANDARD_OBJECT_BYTES:
            raise CloudFoundationError(
                "object.size_limit_exceeded",
                "The object exceeds the Phase 2 standard-upload size limit.",
            )
        source_sha256, source_size = inspect_path(source)
        _verify_expected_bytes(source_sha256, source_size, expected)
        options: FileOptions = {
            "content-type": expected.content_type,
            "upsert": "false",
        }
        reused = False
        try:
            with source.open("rb") as stream:
                self._client.storage.from_(expected.bucket_name).upload(
                    expected.object_key,
                    stream,
                    options,
                )
        except StorageApiError as error:
            if not self._is_existing_object(error):
                raise CloudFoundationError(
                    "storage.upload_failed",
                    "Supabase Storage rejected the object upload.",
                ) from error
            reused = True
        except OSError as error:
            raise CloudFoundationError(
                "object.source_unreadable",
                "The source object could not be read.",
            ) from error

        downloaded = self.read(expected.bucket_name, expected.object_key)
        actual_sha256 = hashlib.sha256(downloaded).hexdigest()
        _verify_expected_bytes(actual_sha256, len(downloaded), expected)
        source_after_sha256, source_after_size = inspect_path(source)
        _verify_expected_bytes(source_after_sha256, source_after_size, expected)
        return ObjectPutResult(expected, reused=reused)

    def read(self, bucket_name: str, object_key: str) -> bytes:
        """Download one bounded Storage object."""
        validate_bucket_name(bucket_name)
        validate_object_key(object_key)
        try:
            payload = self._client.storage.from_(bucket_name).download(object_key)
        except StorageApiError as error:
            if str(error.status) == "404":
                raise CloudFoundationError(
                    "object.not_found",
                    "The requested object does not exist.",
                ) from error
            raise CloudFoundationError(
                "storage.download_failed",
                "Supabase Storage rejected the object download.",
            ) from error
        if len(payload) > MAX_STANDARD_OBJECT_BYTES:
            raise CloudFoundationError(
                "object.size_limit_exceeded",
                "The object exceeds the Phase 2 standard-upload size limit.",
            )
        return payload

    def list_keys(self, bucket_name: str, prefix: str) -> tuple[str, ...]:
        """Recursively list Storage keys below a controlled prefix."""
        validate_bucket_name(bucket_name)
        validate_object_key(prefix)
        bucket = self._client.storage.from_(bucket_name)
        keys: list[str] = []
        pending = [prefix]
        while pending:
            current = pending.pop()
            offset = 0
            while True:
                options: ListBucketFilesOptions = {
                    "limit": 1000,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                }
                rows = bucket.list(current, options)
                for row in rows:
                    name = str(row["name"])
                    child = f"{current}/{name}"
                    if row.get("metadata") is None:
                        pending.append(child)
                    else:
                        validate_object_key(child)
                        keys.append(child)
                if len(rows) < 1000:
                    break
                offset += len(rows)
        return tuple(sorted(keys))
