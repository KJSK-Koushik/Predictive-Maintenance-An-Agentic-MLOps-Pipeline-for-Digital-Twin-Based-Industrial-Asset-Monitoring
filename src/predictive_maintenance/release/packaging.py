"""Deterministic, approval-gated release bundle creation and loading."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from predictive_maintenance.release.gates import require_current_approval
from predictive_maintenance.release.models import (
    ApprovalDecision,
    ModelReference,
    ReleaseError,
    ReleaseManifest,
    canonical_json_bytes,
    sha256_bytes,
)

MANIFEST_FILENAME = "release-manifest.json"
FIXTURE_FILENAME = "verification-fixture.json"


def _verify_file(path: Path, expected_sha256: str, code: str) -> bytes:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ReleaseError(
            code, "A required release file could not be read."
        ) from error
    if sha256_bytes(payload) != expected_sha256:
        raise ReleaseError(code, "A required release file digest does not match.")
    return payload


def package_release(
    manifest: ReleaseManifest,
    approval: ApprovalDecision,
    *,
    regression_model: Path,
    classification_model: Path,
    verification_fixture: bytes,
    output_root: Path,
    now: datetime,
) -> Path:
    """Create one immutable bundle only after exact, current human approval."""
    require_current_approval(manifest, approval, now=now)
    regression_bytes = _verify_file(
        regression_model,
        manifest.regression.artifact_sha256,
        "package.regression_digest_mismatch",
    )
    classification_bytes = _verify_file(
        classification_model,
        manifest.classification.artifact_sha256,
        "package.classification_digest_mismatch",
    )
    if sha256_bytes(verification_fixture) != manifest.verification_fixture_sha256:
        raise ReleaseError(
            "package.fixture_digest_mismatch",
            "The verification fixture digest does not match.",
        )
    destination = output_root / manifest.release_id
    if destination.exists():
        verify_release_bundle(destination, expected_release_id=manifest.release_id)
        return destination
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".phase6-", dir=output_root))
    try:
        (temporary / "rul").mkdir()
        (temporary / "risk").mkdir()
        (temporary / MANIFEST_FILENAME).write_bytes(manifest.canonical_bytes())
        (temporary / FIXTURE_FILENAME).write_bytes(verification_fixture)
        (temporary / "rul" / "model.skops").write_bytes(regression_bytes)
        (temporary / "risk" / "model.skops").write_bytes(classification_bytes)
        try:
            os.rename(temporary, destination)
        except FileExistsError:
            verify_release_bundle(destination, expected_release_id=manifest.release_id)
        return destination
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def parse_manifest(payload: bytes) -> ReleaseManifest:
    """Parse canonical manifest JSON into validated immutable contracts."""
    try:
        value: dict[str, Any] = json.loads(payload)
        release_id = str(value.pop("release_id"))
        for key in ("regression", "classification"):
            reference = value[key]
            reference["feature_columns"] = tuple(reference["feature_columns"])
            reference["trusted_types"] = tuple(reference["trusted_types"])
            value[key] = ModelReference(**reference)
        manifest = ReleaseManifest(**value)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ReleaseError(
            "release.invalid_manifest", "Release manifest is invalid."
        ) from error
    if manifest.release_id != release_id or manifest.canonical_bytes() != payload:
        raise ReleaseError(
            "release.manifest_identity_mismatch",
            "Release manifest identity or canonical bytes do not match.",
        )
    return manifest


def verify_release_bundle(
    bundle: Path, *, expected_release_id: str | None = None
) -> ReleaseManifest:
    """Verify the complete immutable bundle before any model is loaded."""
    manifest = parse_manifest(_verify_file_unhashed(bundle / MANIFEST_FILENAME))
    if expected_release_id is not None and manifest.release_id != expected_release_id:
        raise ReleaseError("release.unexpected_id", "The release ID is not expected.")
    _verify_file(
        bundle / "rul" / "model.skops",
        manifest.regression.artifact_sha256,
        "release.regression_digest_mismatch",
    )
    _verify_file(
        bundle / "risk" / "model.skops",
        manifest.classification.artifact_sha256,
        "release.classification_digest_mismatch",
    )
    _verify_file(
        bundle / FIXTURE_FILENAME,
        manifest.verification_fixture_sha256,
        "release.fixture_digest_mismatch",
    )
    return manifest


def _verify_file_unhashed(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise ReleaseError(
            "release.file_unreadable", "A required release file could not be read."
        ) from error


def fixture_bytes(
    observations: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> bytes:
    """Return canonical startup-parity evidence."""
    return canonical_json_bytes(
        {
            "contract_version": "fd001-startup-parity-v1",
            "observations": observations,
            "expected": expected,
        }
    )
