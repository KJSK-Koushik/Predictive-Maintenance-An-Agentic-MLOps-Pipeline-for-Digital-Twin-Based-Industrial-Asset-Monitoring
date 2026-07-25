from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def valid_source(tmp_path: Path) -> Path:
    fixture = Path(__file__).parents[1] / "fixtures" / "cmapss" / "valid"
    destination = tmp_path / "source"
    shutil.copytree(fixture, destination)
    return destination
