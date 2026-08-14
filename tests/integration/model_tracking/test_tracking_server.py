"""Real SQLite-backed MLflow log, retrieve, trusted-load, and restore evidence."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from mlflow.tracking import MlflowClient

from predictive_maintenance.modeling.models import FEATURE_COLUMNS, TrainingDataset
from predictive_maintenance.modeling.pipeline import run_baselines
from predictive_maintenance.modeling.tracking import (
    EXPERIMENT_NAME,
    load_verified_model,
    log_baseline_result,
    schema_only_input_example,
)


@pytest.mark.integration
@pytest.mark.mlflow
def test_real_mlflow_round_trip_and_stopped_server_restore(
    tmp_path: Path,
    synthetic_dataset: TrainingDataset,
    mlflow_server_factory: Any,
) -> None:
    original_root = tmp_path / "original"
    server = mlflow_server_factory(original_root)
    result = run_baselines(synthetic_dataset)
    try:
        os.environ.pop("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", None)
        tracked = log_baseline_result(
            result,
            tracking_uri=server.uri,
            code_revision="phase4-mlflow-test",
            dirty_worktree=False,
        )
        assert os.environ["MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT"] == "true"
        client = MlflowClient(tracking_uri=server.uri)
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        assert experiment is not None
        assert experiment.experiment_id == tracked.experiment_id
        runs = client.search_runs(
            [tracked.experiment_id],
            filter_string=f"tags.split_id = '{result.split_manifest.split_id}'",
        )
        assert len(runs) == 5
        task_runs = client.search_runs(
            [tracked.experiment_id],
            filter_string=(
                f"tags.split_id = '{result.split_manifest.split_id}' "
                "and tags.task = 'regression'"
            ),
        )
        assert len(task_runs) == 2
        assert client.search_registered_models() == []

        example = schema_only_input_example()
        for key in ("regression_candidate", "classification_candidate"):
            loaded = load_verified_model(
                tracked.child_run_ids[key],
                tracking_uri=server.uri,
                feature_snapshot_id=result.split_manifest.feature_snapshot_id,
                split_id=result.split_manifest.split_id,
                download_root=tmp_path / f"download-{key}",
            )
            np.testing.assert_allclose(
                loaded.predict(example), result.models[key].predict(example)
            )
            assert tuple(loaded.feature_names_in_) == FEATURE_COLUMNS
    finally:
        server.stop()

    restore_root = tmp_path / "restored"
    restore_root.mkdir()
    shutil.copy2(original_root / "mlflow.db", restore_root / "mlflow.db")
    shutil.copytree(original_root / "artifacts", restore_root / "artifacts")
    restored = mlflow_server_factory(restore_root)
    try:
        restored_client = MlflowClient(tracking_uri=restored.uri)
        assert (
            restored_client.get_run(tracked.parent_run_id).info.run_id
            == tracked.parent_run_id
        )
        loaded = load_verified_model(
            tracked.child_run_ids["regression_candidate"],
            tracking_uri=restored.uri,
            feature_snapshot_id=result.split_manifest.feature_snapshot_id,
            split_id=result.split_manifest.split_id,
            download_root=tmp_path / "restored-download",
        )
        np.testing.assert_allclose(
            loaded.predict(schema_only_input_example()),
            result.models["regression_candidate"].predict(schema_only_input_example()),
        )
    finally:
        restored.stop()
