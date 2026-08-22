"""Deterministic gates separating candidate creation from human approval."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from predictive_maintenance.release.models import (
    ApprovalDecision,
    ModelReference,
    ReleaseError,
    ReleaseManifest,
    approval_request_id,
)


def build_candidate_manifest(
    *,
    feature_snapshot_id: str,
    processed_snapshot_id: str,
    raw_snapshot_id: str,
    split_id: str,
    comparison_id: str,
    selection_id: str,
    regression: ModelReference,
    classification: ModelReference,
    verification_fixture_sha256: str,
    code_revision: str,
    python_version: str,
    dependency_lock_sha256: str,
    previous_release_id: str | None = None,
) -> ReleaseManifest:
    """Build one deterministic candidate without creating approval or aliases."""
    request: dict[str, Any] = {
        "feature_snapshot_id": feature_snapshot_id,
        "processed_snapshot_id": processed_snapshot_id,
        "raw_snapshot_id": raw_snapshot_id,
        "split_id": split_id,
        "comparison_id": comparison_id,
        "selection_id": selection_id,
        "regression": asdict(regression),
        "classification": asdict(classification),
        "verification_fixture_sha256": verification_fixture_sha256,
        "code_revision": code_revision,
        "python_version": python_version,
        "dependency_lock_sha256": dependency_lock_sha256,
        "previous_release_id": previous_release_id,
    }
    request_id = approval_request_id(request)
    return ReleaseManifest(
        approval_request_id=request_id,
        feature_snapshot_id=feature_snapshot_id,
        processed_snapshot_id=processed_snapshot_id,
        raw_snapshot_id=raw_snapshot_id,
        split_id=split_id,
        comparison_id=comparison_id,
        selection_id=selection_id,
        regression=regression,
        classification=classification,
        verification_fixture_sha256=verification_fixture_sha256,
        code_revision=code_revision,
        python_version=python_version,
        dependency_lock_sha256=dependency_lock_sha256,
        previous_release_id=previous_release_id,
    )


def require_current_approval(
    manifest: ReleaseManifest,
    approval: ApprovalDecision | None,
    *,
    now: datetime,
) -> None:
    """Fail closed unless one current human approval matches the exact release."""
    if approval is None:
        raise ReleaseError("approval.missing", "This release has no human approval.")
    if approval.approval_request_id != manifest.approval_request_id:
        raise ReleaseError(
            "approval.request_mismatch", "Approval request does not match the release."
        )
    if approval.release_id != manifest.release_id:
        raise ReleaseError(
            "approval.release_mismatch", "Approval does not match the release ID."
        )
    if approval.decision != "approved":
        raise ReleaseError("approval.rejected", "The release was not approved.")
    if now.tzinfo is None:
        raise ReleaseError("approval.naive_timestamp", "Current time needs a timezone.")
    if now > approval.expires_at:
        raise ReleaseError("approval.expired", "The release approval has expired.")
