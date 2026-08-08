"""Shared Phase 3 synthetic FD001 fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from predictive_maintenance.data.pipeline import IngestionResult, ingest_fd001

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ingestion(tmp_path: Path) -> IngestionResult:
    """Return the accepted committed synthetic FD001 ingestion."""
    return ingest_fd001(
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw",
        code_revision="phase3-test",
    )
