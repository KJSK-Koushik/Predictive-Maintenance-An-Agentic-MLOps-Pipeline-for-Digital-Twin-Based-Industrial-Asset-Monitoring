"""Fail-safe staging switch and rollback objective tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from predictive_maintenance.release.deployment import LocalStagingController
from predictive_maintenance.release.models import ReleaseError


def test_bad_candidate_does_not_replace_previous_and_rollback_is_bounded(
    tmp_path: Path,
) -> None:
    controller = LocalStagingController(tmp_path / "active-release")
    first = "1" * 64
    second = "2" * 64
    controller.activate(first, smoke=lambda _: True)
    with pytest.raises(ReleaseError, match=r"deployment\.candidate_smoke_failed"):
        controller.activate(second, smoke=lambda _: False)
    assert controller.active_release_id() == first
    controller.activate(second, smoke=lambda _: True)
    rollback = controller.rollback(first, smoke=lambda _: True)
    assert rollback.active_release_id == first
    assert rollback.previous_release_id == second
    assert rollback.elapsed_seconds < 300
