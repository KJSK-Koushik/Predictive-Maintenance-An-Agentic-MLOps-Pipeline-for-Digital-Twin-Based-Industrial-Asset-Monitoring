"""Approval-gated content-addressed release publication."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.cloud.object_store import ObjectRepository
from predictive_maintenance.release.gates import require_current_approval
from predictive_maintenance.release.models import (
    ApprovalDecision,
    ReleaseError,
    sha256_bytes,
)
from predictive_maintenance.release.packaging import verify_release_bundle

_RELEASE_FILES = (
    ("release-manifest.json", "application/json"),
    ("verification-fixture.json", "application/json"),
    ("rul/model.skops", "application/octet-stream"),
    ("risk/model.skops", "application/octet-stream"),
)


def publish_release(
    bundle: Path,
    approval: ApprovalDecision,
    *,
    bucket: str,
    repository: ObjectRepository,
    now: datetime,
) -> tuple[ObjectIdentity, ...]:
    """Publish exact approved bytes with put-if-absent and download verification."""
    manifest = verify_release_bundle(bundle)
    require_current_approval(manifest, approval, now=now)
    identities: list[ObjectIdentity] = []
    for relative, content_type in _RELEASE_FILES:
        source = bundle / Path(*relative.split("/"))
        payload = source.read_bytes()
        identity = ObjectIdentity(
            bucket_name=bucket,
            object_key=f"models/releases/{manifest.release_id}/{relative}",
            zone="derived",
            sha256=sha256_bytes(payload),
            byte_size=len(payload),
            content_type=content_type,
        )
        repository.put_verified(source, identity)
        downloaded = repository.read(bucket, identity.object_key)
        if downloaded != payload:
            raise ReleaseError(
                "publication.download_mismatch",
                "Published release bytes failed verification.",
            )
        identities.append(identity)
    return tuple(identities)
