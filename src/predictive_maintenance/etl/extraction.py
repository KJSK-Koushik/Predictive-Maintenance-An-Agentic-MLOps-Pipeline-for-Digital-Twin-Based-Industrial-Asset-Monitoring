"""Verified extraction of one available immutable Phase 2 raw snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from predictive_maintenance.cloud.metadata import MetadataRepository
from predictive_maintenance.cloud.models import (
    ObjectIdentity,
    validate_sha256,
)
from predictive_maintenance.cloud.object_store import ObjectRepository
from predictive_maintenance.data.contract import (
    CONTRACT_VERSION,
    PARSER_VERSION,
    REQUIRED_FILENAMES,
    ContractError,
)
from predictive_maintenance.data.pipeline import IngestionResult, ingest_fd001
from predictive_maintenance.etl.models import EtlError, canonical_json_bytes

_MAX_RAW_MANIFEST_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class ValidatedSource:
    """Accepted raw input plus verified object identities by logical filename."""

    ingestion: IngestionResult
    raw_files: dict[str, ObjectIdentity]
    raw_manifest: ObjectIdentity


def _read_verified(
    objects: ObjectRepository,
    identity: ObjectIdentity,
    *,
    size_limit: int | None = None,
) -> bytes:
    payload = objects.read(identity.bucket_name, identity.object_key)
    if size_limit is not None and len(payload) > size_limit:
        raise EtlError(
            "source.object_too_large",
            "A raw metadata object exceeded its approved size limit.",
        )
    if len(payload) != identity.byte_size:
        raise EtlError(
            "source.object_size_mismatch",
            "A referenced raw object has a different byte size.",
        )
    if hashlib.sha256(payload).hexdigest() != identity.sha256:
        raise EtlError(
            "source.object_hash_mismatch",
            "A referenced raw object failed SHA-256 verification.",
        )
    return payload


def _manifest_payload(payload: bytes, snapshot_id: str) -> dict[str, Any]:
    try:
        decoded = payload.decode("ascii")
        value = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EtlError(
            "source.manifest_invalid",
            "The raw snapshot manifest is not valid ASCII JSON.",
        ) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != payload:
        raise EtlError(
            "source.manifest_not_canonical",
            "The raw snapshot manifest is not canonical project JSON.",
        )
    expected = {
        "snapshot_id": snapshot_id,
        "contract_version": CONTRACT_VERSION,
        "parser_version": PARSER_VERSION,
    }
    if any(
        value.get(name) != expected_value for name, expected_value in expected.items()
    ):
        raise EtlError(
            "source.manifest_contract_mismatch",
            "The raw manifest identity or executable contract version is unexpected.",
        )
    return value


def extract_validated_source(
    snapshot_id: str,
    objects: ObjectRepository,
    metadata: MetadataRepository,
    workspace: Path,
    *,
    code_revision: str,
) -> ValidatedSource:
    """Download, rehash, parse, and revalidate one available raw snapshot."""
    try:
        validate_sha256(snapshot_id, field="source_snapshot_id")
    except Exception as error:
        raise EtlError(
            "source.invalid_snapshot_id",
            "The source snapshot ID must be a lowercase SHA-256 digest.",
        ) from error
    stored = metadata.get_snapshot(snapshot_id)
    if stored is None:
        raise EtlError("source.not_found", "The requested raw snapshot is unknown.")
    if stored.state != "available":
        raise EtlError(
            "source.not_available",
            "The requested raw snapshot is not available for transformation.",
        )
    manifest_candidates = [
        identity
        for identity in stored.identities
        if identity.object_key.endswith("/manifest.json")
    ]
    if len(manifest_candidates) != 1:
        raise EtlError(
            "source.manifest_count",
            "The raw snapshot must reference exactly one manifest object.",
        )
    manifest_identity = manifest_candidates[0]
    manifest = _manifest_payload(
        _read_verified(
            objects,
            manifest_identity,
            size_limit=_MAX_RAW_MANIFEST_BYTES,
        ),
        snapshot_id,
    )
    file_rows = manifest.get("files")
    if not isinstance(file_rows, list) or len(file_rows) != len(REQUIRED_FILENAMES):
        raise EtlError(
            "source.file_manifest_invalid",
            "The raw manifest does not declare the complete FD001 source set.",
        )
    extracted = workspace / "source"
    extracted.mkdir(parents=True, exist_ok=True)
    raw_files: dict[str, ObjectIdentity] = {}
    non_manifest = [
        identity for identity in stored.identities if identity != manifest_identity
    ]
    for position, filename in enumerate(REQUIRED_FILENAMES):
        row = file_rows[position]
        if not isinstance(row, dict) or row.get("filename") != filename:
            raise EtlError(
                "source.file_order_mismatch",
                "The raw manifest logical file order is unexpected.",
            )
        expected_sha = row.get("sha256")
        expected_size = row.get("byte_size")
        candidates = [
            identity
            for identity in non_manifest
            if identity.sha256 == expected_sha
            and identity.byte_size == expected_size
            and identity.object_key.endswith(f"/{filename}")
        ]
        if len(candidates) != 1:
            raise EtlError(
                "source.object_mapping_invalid",
                "A required raw logical file does not map to one verified object.",
            )
        identity = candidates[0]
        (extracted / filename).write_bytes(_read_verified(objects, identity))
        raw_files[filename] = identity

    try:
        ingestion = ingest_fd001(
            extracted,
            workspace / "verified-raw",
            code_revision=code_revision,
        )
    except ContractError as error:
        raise EtlError(
            "source.contract_rejected",
            "The extracted raw snapshot failed the executable FD001 contract.",
        ) from error
    if ingestion.snapshot.manifest.snapshot_id != snapshot_id:
        raise EtlError(
            "source.snapshot_identity_mismatch",
            "Revalidated raw bytes produced a different snapshot identity.",
        )
    return ValidatedSource(ingestion, raw_files, manifest_identity)
