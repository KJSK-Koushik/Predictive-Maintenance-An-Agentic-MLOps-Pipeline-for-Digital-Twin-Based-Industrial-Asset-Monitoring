"""Owner-provided FD001 end-to-end Phase 4 and MLflow evidence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import psycopg
import pytest

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.pipeline import run_pipeline
from predictive_maintenance.modeling.loading import load_training_dataset
from predictive_maintenance.modeling.pipeline import run_baselines
from predictive_maintenance.modeling.tracking import (
    load_verified_model,
    log_baseline_result,
    schema_only_input_example,
)


@pytest.mark.dataset
@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.mlflow
def test_actual_fd001_complete_baseline_path(
    tmp_path: Path, mlflow_server_factory: Any
) -> None:
    """Exercise actual simulated FD001 without changing the fixed protocol."""
    source = Path("Data")
    required = (
        "train_FD001.txt",
        "test_FD001.txt",
        "RUL_FD001.txt",
        "readme.txt",
    )
    if not all((source / filename).is_file() for filename in required):
        pytest.fail("Owner-provided FD001 files are required.")
    dsn = os.environ.get("PM_POSTGRES_DSN", "")
    parsed = urlsplit(dsn)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail("Use only the disposable local Phase 4 PostgreSQL database.")
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(
            """
            truncate table
                ops.transformation_runs,
                ops.derived_snapshot_files,
                ops.derived_snapshots,
                ops.lineage_edges,
                ops.snapshot_files,
                ops.dataset_snapshots,
                ops.data_objects,
                ops.ingestion_runs
            restart identity cascade
            """
        )

    ingestion = ingest_fd001(
        source,
        tmp_path / "raw",
        code_revision="phase4-actual-dataset-test",
    )
    objects = FilesystemObjectRepository(tmp_path / "objects")
    raw_metadata = PostgresMetadataRepository(dsn)
    derived_metadata = PostgresDerivedMetadataRepository(dsn)
    raw = publish_snapshot(ingestion.snapshot, "pm-raw", objects, raw_metadata)
    etl = run_pipeline(
        raw.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase4-actual-dataset-test",
    )
    dataset = load_training_dataset(
        etl.feature_snapshot_id, objects, raw_metadata, derived_metadata
    )
    assert len(dataset.train_features) == 20_631
    assert dataset.train_features["engine_id"].nunique() == 100
    assert len(dataset.test_features) == 13_096
    assert dataset.test_features["engine_id"].nunique() == 100

    first = run_baselines(dataset)
    second = run_baselines(dataset)
    assert first.split_manifest.split_id == second.split_manifest.split_id
    assert [item.test_prediction_digest for item in first.evaluations] == [
        item.test_prediction_digest for item in second.evaluations
    ]
    assert first.evaluation("regression", "candidate").eligible
    assert first.evaluation("classification", "candidate").eligible

    server = mlflow_server_factory(tmp_path / "mlflow")
    try:
        tracked = log_baseline_result(
            first,
            tracking_uri=server.uri,
            code_revision="phase4-actual-dataset-test",
            dirty_worktree=False,
        )
        example = schema_only_input_example()
        for key in ("regression_candidate", "classification_candidate"):
            loaded = load_verified_model(
                tracked.child_run_ids[key],
                tracking_uri=server.uri,
                feature_snapshot_id=first.split_manifest.feature_snapshot_id,
                split_id=first.split_manifest.split_id,
                download_root=tmp_path / f"actual-{key}",
            )
            np.testing.assert_allclose(
                loaded.predict(example), first.models[key].predict(example)
            )
    finally:
        server.stop()
