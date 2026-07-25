from __future__ import annotations

import json
from pathlib import Path

import pytest

from predictive_maintenance.data.cli import main
from predictive_maintenance.data.contract import ContractError
from predictive_maintenance.data.pipeline import ingest_fd001


@pytest.mark.integration
def test_valid_pipeline_is_idempotent(valid_source: Path, tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"

    first = ingest_fd001(valid_source, raw_root, code_revision="test")
    second = ingest_fd001(valid_source, raw_root, code_revision="test")

    assert first.validation.accepted is True
    assert first.snapshot.reused is False
    assert second.snapshot.reused is True
    assert first.snapshot.manifest == second.snapshot.manifest
    assert first.exploration == second.exploration
    assert "rul" in first.train
    assert "failure_risk_30" in first.test


@pytest.mark.integration
def test_invalid_pipeline_never_returns_accepted_result(
    valid_source: Path, tmp_path: Path
) -> None:
    path = valid_source / "train_FD001.txt"
    lines = path.read_text(encoding="ascii").splitlines()
    lines[1] = lines[0]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")

    with pytest.raises(ContractError, match="validation.snapshot_rejected") as error:
        ingest_fd001(valid_source, tmp_path / "raw")

    assert "semantic.duplicate_engine_cycle" in error.value.details["issues"]  # type: ignore[index]


@pytest.mark.integration
def test_cli_writes_only_sanitized_aggregate_reports(
    valid_source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_dir = tmp_path / "reports"

    status = main(
        [
            "--source-dir",
            str(valid_source),
            "--raw-root",
            str(tmp_path / "raw"),
            "--report-dir",
            str(report_dir),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert status == 0
    assert output["accepted"] is True
    assert {path.name for path in report_dir.iterdir()} == {
        "manifest.json",
        "validation.json",
        "exploration.json",
    }
    combined = "".join(
        path.read_text(encoding="utf-8") for path in report_dir.iterdir()
    )
    assert str(valid_source.resolve()) not in combined


@pytest.mark.integration
def test_cli_returns_structured_rejection(
    valid_source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (valid_source / "RUL_FD001.txt").write_text("1 2\n", encoding="ascii")

    status = main(
        [
            "--source-dir",
            str(valid_source),
            "--raw-root",
            str(tmp_path / "raw"),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert status == 1
    assert output["accepted"] is False
    assert output["error"]["rule_id"] == "parser.wrong_column_count"
    assert not (tmp_path / "reports").exists()
