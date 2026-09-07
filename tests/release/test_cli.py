"""Candidate CLI orchestration tests without running the expensive actual protocol."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

import predictive_maintenance.release.cli as cli
from predictive_maintenance.release.models import (
    CLASSIFICATION_REGISTERED_NAME,
    FEATURE_COLUMNS,
    REGRESSION_REGISTERED_NAME,
    ModelReference,
    ReleaseError,
)


class _Regression:
    def predict(self, frame: pd.DataFrame) -> np.ndarray[Any, Any]:
        return np.full(len(frame), 12.5)


class _Classification:
    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray[Any, Any]:
        return np.tile(np.array([[0.25, 0.75]]), (len(frame), 1))


class _ReleaseRepository:
    recorded: object | None = None

    def __init__(self, _: str) -> None:
        pass

    def record_candidate(self, manifest: object) -> None:
        self.recorded = manifest


def _reference(task: str) -> ModelReference:
    if task == "regression":
        return ModelReference(
            "regression",
            REGRESSION_REGISTERED_NAME,
            "1",
            "regression-run",
            "1" * 64,
            "histogram_gradient_boosting",
            {},
            (),
        )
    return ModelReference(
        "classification",
        CLASSIFICATION_REGISTERED_NAME,
        "1",
        "classification-run",
        "2" * 64,
        "class_balanced_logistic_regression",
        {},
        (),
    )


def test_prepare_writes_candidate_only(monkeypatch: Any, tmp_path: Path) -> None:
    row: dict[str, int | float] = {"engine_id": 1, "cycle": 1}
    row.update({name: float(index) for index, name in enumerate(FEATURE_COLUMNS)})
    dataset = SimpleNamespace(test_features=pd.DataFrame([row]))
    selection = SimpleNamespace(
        selection_id=cli.APPROVED_ACTUAL_SELECTION_ID,
        regression_parameters={},
        classification_parameters={},
    )
    result = SimpleNamespace(
        development=SimpleNamespace(
            manifest=SimpleNamespace(comparison_id=cli.APPROVED_ACTUAL_COMPARISON_ID),
            selection=selection,
        ),
        benchmark=SimpleNamespace(
            models={
                "regression_selected": _Regression(),
                "classification_selected": _Classification(),
            }
        ),
    )
    monkeypatch.setattr(
        cli,
        "ingest_fd001",
        lambda *args, **kwargs: SimpleNamespace(snapshot=object()),
    )
    monkeypatch.setattr(cli, "PostgresMetadataRepository", lambda _: object())
    monkeypatch.setattr(cli, "PostgresDerivedMetadataRepository", lambda _: object())
    monkeypatch.setattr(
        cli,
        "publish_snapshot",
        lambda *args, **kwargs: SimpleNamespace(snapshot_id="3" * 64),
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *args, **kwargs: SimpleNamespace(
            feature_snapshot_id=cli.APPROVED_ACTUAL_FEATURE_SNAPSHOT_ID,
            processed_snapshot_id="6" * 64,
        ),
    )
    monkeypatch.setattr(cli, "load_training_dataset", lambda *args: dataset)
    monkeypatch.setattr(
        cli,
        "create_split_manifest",
        lambda _: SimpleNamespace(split_id=cli.APPROVED_ACTUAL_SPLIT_ID),
    )
    monkeypatch.setattr(cli, "run_phase5", lambda *args, **kwargs: result)
    monkeypatch.setattr(
        cli,
        "log_phase5_result",
        lambda *args, **kwargs: SimpleNamespace(
            parent_run_id="parent",
            child_run_ids={
                "regression_selected": "regression-run",
                "classification_selected": "classification-run",
            },
        ),
    )
    monkeypatch.setattr(
        cli,
        "register_candidate",
        lambda **kwargs: _reference(str(kwargs["task"])),
    )
    monkeypatch.setattr(cli, "PostgresReleaseRepository", _ReleaseRepository)
    lock = tmp_path / "uv.lock"
    lock.write_text("locked", encoding="ascii")
    arguments = argparse.Namespace(
        data_dir=tmp_path / "Data",
        workspace=tmp_path / "actual",
        tracking_uri="http://127.0.0.1:5000",
        postgres_dsn="local",
        code_revision="abc123",
        dependency_lock=lock,
    )
    output = cli.prepare(arguments)
    candidate = arguments.workspace / "candidates" / output["release_id"]
    assert (candidate / "candidate-manifest.json").is_file()
    assert (candidate / "verification-fixture.json").is_file()
    assert (candidate / "candidate-evidence.json").is_file()
    assert not (candidate / "rul" / "model.skops").exists()
    assert output["state"] == "candidate_waiting_for_exact_owner_approval"


def test_approved_phase5_result_gate_rejects_identity_mismatch() -> None:
    result = SimpleNamespace(
        development=SimpleNamespace(
            manifest=SimpleNamespace(comparison_id="4" * 64),
            selection=SimpleNamespace(selection_id=cli.APPROVED_ACTUAL_SELECTION_ID),
        )
    )
    with pytest.raises(ReleaseError, match=r"candidate\.comparison_mismatch"):
        cli._require_approved_phase5_result(result)


def test_main_returns_sanitized_release_error(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(
        cli,
        "prepare",
        lambda _: (_ for _ in ()).throw(ReleaseError("candidate.failed", "Safe.")),
    )
    result = cli.main(
        [
            "--data-dir",
            "Data",
            "--workspace",
            "artifacts/test",
            "--tracking-uri",
            "http://127.0.0.1:5000",
            "--postgres-dsn",
            "local",
            "--code-revision",
            "abc",
        ]
    )
    assert result == 2
    assert "candidate.failed" in capsys.readouterr().err
