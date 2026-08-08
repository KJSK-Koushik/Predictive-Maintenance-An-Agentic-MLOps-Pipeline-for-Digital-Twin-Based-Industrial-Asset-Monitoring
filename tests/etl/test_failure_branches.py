"""Fail-closed branches for extraction and publication boundaries."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.data.contract import CONTRACT_VERSION, PARSER_VERSION
from predictive_maintenance.etl import extraction
from predictive_maintenance.etl.models import (
    ColumnContract,
    DerivedManifest,
    EtlError,
    ManifestFile,
    canonical_json_bytes,
)
from predictive_maintenance.etl.publication import (
    build_batch_publication,
    reconcile_derived_snapshot,
)


class StaticObjects:
    """Small object adapter used to exercise byte-verification failures."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self, bucket_name: str, object_key: str) -> bytes:
        del bucket_name, object_key
        return self.payload


def _identity(
    payload: bytes, *, size: int | None = None, sha: str | None = None
) -> ObjectIdentity:
    return ObjectIdentity(
        bucket_name="pm-raw",
        object_key="fd001/" + "a" * 64 + "/manifest.json",
        zone="raw",
        sha256=sha or hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload) if size is None else size,
        content_type="application/json",
    )


def test_verified_read_rejects_size_limit_size_and_hash_mismatch() -> None:
    oversized = b"x" * 5
    with pytest.raises(EtlError, match=r"source\.object_too_large"):
        extraction._read_verified(
            cast(Any, StaticObjects(oversized)),
            _identity(oversized),
            size_limit=4,
        )

    payload = b"payload"
    with pytest.raises(EtlError, match=r"source\.object_size_mismatch"):
        extraction._read_verified(
            cast(Any, StaticObjects(payload)),
            _identity(payload, size=len(payload) + 1),
        )
    with pytest.raises(EtlError, match=r"source\.object_hash_mismatch"):
        extraction._read_verified(
            cast(Any, StaticObjects(payload)),
            _identity(payload, sha="0" * 64),
        )


@pytest.mark.parametrize(
    "payload,code",
    [
        (b"\xff", "source.manifest_invalid"),
        (b'{"broken"\n', "source.manifest_invalid"),
        (b'{ "snapshot_id": "value" }\n', "source.manifest_not_canonical"),
        (
            canonical_json_bytes(
                {
                    "snapshot_id": "a" * 64,
                    "contract_version": CONTRACT_VERSION,
                    "parser_version": "unexpected-parser",
                }
            ),
            "source.manifest_contract_mismatch",
        ),
    ],
)
def test_manifest_parser_rejects_invalid_noncanonical_or_wrong_contract(
    payload: bytes,
    code: str,
) -> None:
    with pytest.raises(EtlError, match=code.replace(".", r"\.")):
        extraction._manifest_payload(payload, "a" * 64)


def test_manifest_parser_accepts_canonical_identity() -> None:
    value = {
        "snapshot_id": "a" * 64,
        "contract_version": CONTRACT_VERSION,
        "parser_version": PARSER_VERSION,
        "files": [],
    }
    assert extraction._manifest_payload(canonical_json_bytes(value), "a" * 64) == value


def test_extraction_rejects_invalid_snapshot_before_adapter_access(
    tmp_path: Path,
) -> None:
    with pytest.raises(EtlError, match=r"source\.invalid_snapshot_id"):
        extraction.extract_validated_source(
            "invalid",
            cast(Any, object()),
            cast(Any, object()),
            tmp_path,
            code_revision="phase3-test",
        )


def test_publication_rejects_naive_time_and_unknown_reconciliation_target() -> None:
    with pytest.raises(EtlError, match=r"publication\.naive_timestamp"):
        build_batch_publication(
            "a" * 64,
            "phase3-test",
            (),
            verified_at=datetime(2026, 1, 1),
        )

    class MissingMetadata:
        def get_derived_snapshot(self, snapshot_id: str) -> None:
            del snapshot_id
            return None

    with pytest.raises(EtlError, match=r"reconciliation\.derived_not_found"):
        reconcile_derived_snapshot(
            "a" * 64,
            cast(Any, object()),
            cast(Any, MissingMetadata()),
        )


def _manifest_file(
    *,
    name: str = "data.parquet",
    position: int = 1,
    size: int = 1,
    sha: str = "a" * 64,
    rows: int | None = 1,
) -> ManifestFile:
    return ManifestFile(
        name,
        position,
        size,
        sha,
        "application/vnd.apache.parquet",
        rows,
        (ColumnContract("engine_id", "int64", "key"),),
    )


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"name": "../data.parquet"}, "identity.invalid_filename"),
        ({"position": 0}, "identity.invalid_file_metadata"),
        ({"sha": "invalid"}, "identity.invalid_sha256"),
        ({"rows": -1}, "identity.invalid_row_count"),
    ],
)
def test_manifest_file_rejects_invalid_identity_fields(
    kwargs: dict[str, Any], code: str
) -> None:
    with pytest.raises(EtlError, match=code.replace(".", r"\.")):
        _manifest_file(**kwargs)


def _derived_manifest(
    files: tuple[ManifestFile, ...], *, source: str = "a" * 64
) -> DerivedManifest:
    return DerivedManifest(
        artifact_kind="processed",
        source_snapshot_id=source,
        parent_snapshot_id="a" * 64,
        contract_version="test-contract",
        transformation_version="test-transform",
        serializer_version="test-serializer",
        code_revision="phase3-test",
        files=files,
    )


def test_derived_manifest_rejects_invalid_empty_noncontiguous_and_duplicate() -> None:
    with pytest.raises(EtlError, match=r"identity\.invalid_snapshot_id"):
        _derived_manifest((_manifest_file(),), source="invalid")
    with pytest.raises(EtlError, match=r"identity\.empty_artifact"):
        _derived_manifest(())
    with pytest.raises(EtlError, match=r"identity\.non_contiguous_files"):
        _derived_manifest((_manifest_file(position=2),))
    with pytest.raises(EtlError, match=r"identity\.duplicate_filename"):
        _derived_manifest((_manifest_file(position=1), _manifest_file(position=2)))


def test_etl_error_rejects_unstable_error_code() -> None:
    with pytest.raises(ValueError, match="stable lowercase"):
        EtlError("INVALID", "message")
