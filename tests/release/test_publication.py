"""Approval-gated local content-addressed publication tests."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from phase6_support import SyntheticRelease

from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.release.models import ReleaseError
from predictive_maintenance.release.publication import publish_release


def test_local_publication_is_content_addressed_and_reusable(
    synthetic_release: SyntheticRelease, tmp_path: Path
) -> None:
    repository = FilesystemObjectRepository(tmp_path / "objects")
    now = synthetic_release.approval.decided_at + timedelta(minutes=1)
    first = publish_release(
        synthetic_release.bundle,
        synthetic_release.approval,
        bucket="pm-derived",
        repository=repository,
        now=now,
    )
    second = publish_release(
        synthetic_release.bundle,
        synthetic_release.approval,
        bucket="pm-derived",
        repository=repository,
        now=now,
    )
    assert first == second
    assert len(first) == 4
    assert all(
        item.object_key.startswith(
            f"models/releases/{synthetic_release.manifest.release_id}/"
        )
        for item in first
    )


def test_publication_requires_current_exact_approval(
    synthetic_release: SyntheticRelease, tmp_path: Path
) -> None:
    with pytest.raises(ReleaseError, match=r"approval\.expired"):
        publish_release(
            synthetic_release.bundle,
            synthetic_release.approval,
            bucket="pm-derived",
            repository=FilesystemObjectRepository(tmp_path / "objects"),
            now=synthetic_release.approval.expires_at + timedelta(seconds=1),
        )
