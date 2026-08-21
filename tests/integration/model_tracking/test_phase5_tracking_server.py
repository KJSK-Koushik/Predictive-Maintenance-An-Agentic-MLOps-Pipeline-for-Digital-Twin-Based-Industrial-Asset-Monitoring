"""Real local MLflow evidence for the complete synthetic Phase 5 path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from mlflow.tracking import MlflowClient

from predictive_maintenance.modeling.models import TrainingDataset
from predictive_maintenance.modeling.phase5_pipeline import run_phase5
from predictive_maintenance.modeling.phase5_tracking import (
    EXPERIMENT_NAME,
    load_verified_phase5_model,
    log_phase5_result,
)
from predictive_maintenance.modeling.splitting import create_split_manifest
from predictive_maintenance.modeling.tracking import schema_only_input_example


@pytest.mark.integration
@pytest.mark.mlflow
def test_complete_phase5_path_logs_and_loads_selected_models(
    tmp_path: Path,
    synthetic_dataset: TrainingDataset,
    mlflow_server_factory: Any,
) -> None:
    split_id = create_split_manifest(synthetic_dataset).split_id
    result = run_phase5(synthetic_dataset, phase4_split_id=split_id)
    server = mlflow_server_factory(tmp_path / "phase5-mlflow")
    try:
        tracked = log_phase5_result(
            result,
            tracking_uri=server.uri,
            code_revision="phase5-synthetic-integration",
            dirty_worktree=False,
        )
        client = MlflowClient(tracking_uri=server.uri)
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        assert experiment is not None
        assert experiment.experiment_id == tracked.experiment_id
        runs = client.search_runs(
            [tracked.experiment_id],
            filter_string=(
                f"tags.selection_id = '{result.development.selection.selection_id}'"
            ),
        )
        assert len(runs) == 3
        assert client.search_registered_models() == []
        parent = client.get_run(tracked.parent_run_id)
        assert len(parent.data.tags["development_evidence_sha256"]) == 64
        assert len(parent.data.tags["benchmark_evidence_sha256"]) == 64

        example = schema_only_input_example()
        for task in ("regression", "classification"):
            key = f"{task}_selected"
            loaded = load_verified_phase5_model(
                tracked.child_run_ids[key],
                tracking_uri=server.uri,
                feature_snapshot_id=result.development.manifest.feature_snapshot_id,
                comparison_id=result.development.manifest.comparison_id,
                selection_id=result.development.selection.selection_id,
                download_root=tmp_path / f"download-{key}",
            )
            np.testing.assert_allclose(
                loaded.predict(example), result.benchmark.models[key].predict(example)
            )

        with pytest.raises(Exception, match="provenance"):
            load_verified_phase5_model(
                tracked.child_run_ids["regression_selected"],
                tracking_uri=server.uri,
                feature_snapshot_id=result.development.manifest.feature_snapshot_id,
                comparison_id=result.development.manifest.comparison_id,
                selection_id="f" * 64,
                download_root=tmp_path / "wrong-selection",
            )
    finally:
        server.stop()
