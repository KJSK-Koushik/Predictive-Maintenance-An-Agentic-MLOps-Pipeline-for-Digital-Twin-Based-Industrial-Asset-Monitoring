"""Direct Phase 4 CLI and environment-adapter tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import predictive_maintenance.modeling.cli as cli
import predictive_maintenance.modeling.runtime as runtime
from predictive_maintenance.cloud.config import Phase2Settings, SecretValue
from predictive_maintenance.modeling.models import (
    ModelingError,
    TrackingResult,
    TrainingDataset,
)
from predictive_maintenance.modeling.pipeline import run_baselines


def _settings(tmp_path: Path, *, app_env: str, dsn: str) -> Phase2Settings:
    return Phase2Settings(
        app_env,
        "pm-raw",
        "pm-derived",
        tmp_path / "objects",
        SecretValue(dsn),
        SecretValue("https://example.invalid" if app_env == "cloud" else ""),
        SecretValue("test-secret" if app_env == "cloud" else ""),
    )


def test_cli_logs_and_prints_bounded_identifiers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    synthetic_dataset: TrainingDataset,
) -> None:
    result = run_baselines(synthetic_dataset)
    tracked = TrackingResult("1", "parent", {"regression_candidate": "child"})
    monkeypatch.setattr(cli, "run_from_environment", lambda _snapshot_id: result)
    monkeypatch.setattr(cli, "log_baseline_result", lambda *args, **kwargs: tracked)

    status = cli.main(
        [
            "--feature-snapshot-id",
            synthetic_dataset.feature_snapshot_id,
            "--code-revision",
            "test-revision",
            "--dirty-worktree",
        ]
    )

    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["parent_run_id"] == "parent"
    assert payload["split_id"] == result.split_manifest.split_id
    assert payload["eligible"] == {"classification": True, "regression": True}


def test_cli_returns_sanitized_modeling_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_snapshot_id: str) -> Any:
        raise ModelingError("input.failed", "safe failure")

    monkeypatch.setattr(cli, "run_from_environment", fail)
    status = cli.main(
        [
            "--feature-snapshot-id",
            "f" * 64,
            "--code-revision",
            "test-revision",
        ]
    )
    assert status == 2
    assert json.loads(capsys.readouterr().err) == {
        "error": {"code": "input.failed", "message": "safe failure"}
    }


def test_runtime_rejects_missing_database_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, app_env="local", dsn="")
    monkeypatch.setattr(Phase2Settings, "from_env", lambda: settings)
    with pytest.raises(ModelingError, match="PM_POSTGRES_DSN"):
        runtime.run_from_environment("f" * 64)


@pytest.mark.parametrize("app_env", ["local", "cloud"])
def test_runtime_builds_read_only_adapters(
    app_env: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_dataset: TrainingDataset,
) -> None:
    settings = _settings(tmp_path, app_env=app_env, dsn="postgresql://local")
    raw_repository = object()
    derived_repository = object()
    object_repository = object()
    client = object()
    observed: dict[str, Any] = {}
    monkeypatch.setattr(Phase2Settings, "from_env", lambda: settings)
    monkeypatch.setattr(
        runtime, "PostgresMetadataRepository", lambda _dsn: raw_repository
    )
    monkeypatch.setattr(
        runtime, "PostgresDerivedMetadataRepository", lambda _dsn: derived_repository
    )
    monkeypatch.setattr(runtime, "create_client", lambda *_values: client)
    monkeypatch.setattr(
        runtime, "FilesystemObjectRepository", lambda _root: object_repository
    )
    monkeypatch.setattr(
        runtime, "SupabaseObjectRepository", lambda _client: object_repository
    )

    def load(snapshot_id: str, objects: Any, raw: Any, derived: Any) -> TrainingDataset:
        observed.update(
            snapshot_id=snapshot_id,
            objects=objects,
            raw=raw,
            derived=derived,
        )
        return synthetic_dataset

    monkeypatch.setattr(runtime, "load_training_dataset", load)
    monkeypatch.setattr(runtime, "run_baselines", lambda dataset: dataset)

    returned: Any = runtime.run_from_environment(synthetic_dataset.feature_snapshot_id)

    assert returned is synthetic_dataset
    assert observed == {
        "snapshot_id": synthetic_dataset.feature_snapshot_id,
        "objects": object_repository,
        "raw": raw_repository,
        "derived": derived_repository,
    }
