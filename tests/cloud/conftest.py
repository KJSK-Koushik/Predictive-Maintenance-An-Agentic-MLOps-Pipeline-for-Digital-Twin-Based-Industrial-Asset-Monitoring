"""Shared Phase 2 test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from predictive_maintenance.data.integrity import Snapshot, create_snapshot

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def accepted_snapshot(tmp_path: Path) -> Snapshot:
    """Create the accepted synthetic FD001 snapshot."""
    return create_snapshot(
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw",
        code_revision="phase2-test",
    )
