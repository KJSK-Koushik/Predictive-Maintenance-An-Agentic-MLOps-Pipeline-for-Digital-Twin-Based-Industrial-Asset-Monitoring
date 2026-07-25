from __future__ import annotations

from pathlib import Path

import pytest

from predictive_maintenance.data.pipeline import ingest_fd001


@pytest.mark.dataset
def test_owner_provided_fd001_passes_contract(tmp_path: Path) -> None:
    source = Path("Data")
    required = (
        "train_FD001.txt",
        "test_FD001.txt",
        "RUL_FD001.txt",
        "readme.txt",
    )
    if not all((source / filename).is_file() for filename in required):
        pytest.fail(
            "Owner-provided FD001 files are required for the local dataset test."
        )

    result = ingest_fd001(source, tmp_path / "raw", code_revision="dataset-test")

    assert result.validation.accepted is True
    assert len(result.train) == 20_631
    assert len(result.test) == 13_096
    assert result.train["engine_id"].nunique() == 100
    assert result.test["engine_id"].nunique() == 100
