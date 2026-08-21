"""Phase 5 two-step CLI and local-only runtime tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import predictive_maintenance.modeling.phase5_cli as cli
import predictive_maintenance.modeling.phase5_runtime as runtime
from predictive_maintenance.cloud.config import Phase2Settings, SecretValue
from predictive_maintenance.modeling.models import ModelingError, TrainingDataset


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


def test_develop_cli_writes_immutable_selection_and_bounded_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    synthetic_dataset: TrainingDataset,
) -> None:
    selection_path = tmp_path / "selection.json"
    selection = SimpleNamespace(
        selection_id="s" * 64,
        canonical_bytes=lambda: b'{"selection_id":"safe"}\n',
    )
    result = SimpleNamespace(
        manifest=SimpleNamespace(
            feature_snapshot_id=synthetic_dataset.feature_snapshot_id,
            comparison_id="c" * 64,
        ),
        selection=selection,
        comparisons=(
            SimpleNamespace(task="regression", preferred_model="baseline"),
            SimpleNamespace(task="classification", preferred_model="advanced"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_phase5_input",
        lambda _snapshot: (synthetic_dataset, "p" * 64),
    )
    monkeypatch.setattr(cli, "run_phase5_development", lambda _data: result)

    status = cli.main(
        [
            "develop",
            "--feature-snapshot-id",
            synthetic_dataset.feature_snapshot_id,
            "--selection-path",
            str(selection_path),
        ]
    )

    assert status == 0
    assert selection_path.read_bytes() == selection.canonical_bytes()
    payload = json.loads(capsys.readouterr().out)
    assert payload["step"] == "development_locked"
    assert payload["selection_id"] == "s" * 64
    assert payload["preferred_models"] == {
        "regression": "baseline",
        "classification": "advanced",
    }

    selection_path.write_bytes(b"different")
    assert (
        cli.main(
            [
                "develop",
                "--feature-snapshot-id",
                synthetic_dataset.feature_snapshot_id,
                "--selection-path",
                str(selection_path),
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().err)["error"]["code"] == (
        "selection.conflict"
    )


def test_benchmark_cli_reuses_locked_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    synthetic_dataset: TrainingDataset,
) -> None:
    path = tmp_path / "selection.json"
    path.write_bytes(b"locked")
    selection = object()
    benchmark = SimpleNamespace(
        feature_snapshot_id=synthetic_dataset.feature_snapshot_id,
        selection_id="s" * 64,
        test_exposure_status="previously_observed_in_phase_4",
        evaluations=(
            SimpleNamespace(task="regression", prediction_digest="r" * 64),
            SimpleNamespace(task="classification", prediction_digest="c" * 64),
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_phase5_input",
        lambda _snapshot: (synthetic_dataset, "p" * 64),
    )
    monkeypatch.setattr(cli, "selection_from_bytes", lambda _payload: selection)
    monkeypatch.setattr(
        cli,
        "run_locked_benchmark",
        lambda *_args, **_kwargs: benchmark,
    )

    assert (
        cli.main(
            [
                "benchmark",
                "--feature-snapshot-id",
                synthetic_dataset.feature_snapshot_id,
                "--selection-path",
                str(path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["step"] == "known_benchmark_complete"
    assert payload["test_exposure_status"] == "previously_observed_in_phase_4"


@pytest.mark.parametrize(
    "app_env, dsn, message",
    [
        ("cloud", "postgresql://local", "local-only"),
        ("local", "", "PM_POSTGRES_DSN"),
    ],
)
def test_runtime_fails_closed_before_adapters(
    app_env: str,
    dsn: str,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Phase2Settings,
        "from_env",
        lambda: _settings(tmp_path, app_env=app_env, dsn=dsn),
    )
    with pytest.raises(ModelingError, match=message):
        runtime.load_phase5_input("f" * 64)


def test_runtime_loads_verified_snapshot_through_local_read_only_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_dataset: TrainingDataset,
) -> None:
    settings = _settings(tmp_path, app_env="local", dsn="postgresql://local")
    observed: dict[str, Any] = {}
    monkeypatch.setattr(Phase2Settings, "from_env", lambda: settings)
    monkeypatch.setattr(runtime, "PostgresMetadataRepository", lambda _dsn: "raw")
    monkeypatch.setattr(
        runtime, "PostgresDerivedMetadataRepository", lambda _dsn: "derived"
    )
    monkeypatch.setattr(runtime, "FilesystemObjectRepository", lambda _root: "objects")

    def load(snapshot_id: str, objects: Any, raw: Any, derived: Any) -> TrainingDataset:
        observed.update(
            snapshot_id=snapshot_id,
            objects=objects,
            raw=raw,
            derived=derived,
        )
        return synthetic_dataset

    monkeypatch.setattr(runtime, "load_training_dataset", load)
    dataset, split_id = runtime.load_phase5_input(synthetic_dataset.feature_snapshot_id)
    assert dataset is synthetic_dataset
    assert len(split_id) == 64
    assert observed == {
        "snapshot_id": synthetic_dataset.feature_snapshot_id,
        "objects": "objects",
        "raw": "raw",
        "derived": "derived",
    }
