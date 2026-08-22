"""Phase 6 release fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from phase6_support import SyntheticRelease, build_synthetic_release


@pytest.fixture
def synthetic_release(tmp_path: Path) -> SyntheticRelease:
    """Create one fully approved synthetic bundle."""
    return build_synthetic_release(tmp_path)
