"""Owner-provided FD001 Phase 5 research-comparison evidence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import psycopg
import pytest
from mlflow.tracking import MlflowClient

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.pipeline import run_pipeline
from predictive_maintenance.modeling.loading import load_training_dataset
from predictive_maintenance.modeling.phase5_pipeline import run_phase5
from predictive_maintenance.modeling.phase5_tracking import (
    load_verified_phase5_model,
    log_phase5_result,
)
from predictive_maintenance.modeling.splitting import create_split_manifest
from predictive_maintenance.modeling.tracking import schema_only_input_example


@pytest.mark.dataset
@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.mlflow
def test_actual_fd001_complete_phase5_path(
    tmp_path: Path, mlflow_server_factory: Any
) -> None:
    """Exercise the bounded protocol on simulated FD001 telemetry."""
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
        pytest.fail("Use only the disposable local Phase 5 PostgreSQL database.")
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
        code_revision="phase5-actual-dataset-test",
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
        code_revision="phase5-actual-dataset-test",
    )
    dataset = load_training_dataset(
        etl.feature_snapshot_id, objects, raw_metadata, derived_metadata
    )
    assert len(dataset.train_features) == 20_631
    assert dataset.train_features["engine_id"].nunique() == 100
    assert len(dataset.test_features) == 13_096
    assert dataset.test_features["engine_id"].nunique() == 100

    split_id = create_split_manifest(dataset).split_id
    first = run_phase5(dataset, phase4_split_id=split_id)
    second = run_phase5(dataset, phase4_split_id=split_id)
    assert first.development.manifest.canonical_bytes() == (
        second.development.manifest.canonical_bytes()
    )
    assert first.development.selection.canonical_bytes() == (
        second.development.selection.canonical_bytes()
    )
    assert first.development.comparisons == second.development.comparisons
    assert first.development.clustering == second.development.clustering
    assert first.development.novelty == second.development.novelty
    assert first.benchmark.evaluations == second.benchmark.evaluations
    assert first.benchmark.test_exposure_status == "previously_observed_in_phase_4"

    server = mlflow_server_factory(tmp_path / "phase5-actual-mlflow")
    try:
        tracked = log_phase5_result(
            first,
            tracking_uri=server.uri,
            code_revision="phase5-actual-dataset-test",
            dirty_worktree=False,
        )
        client = MlflowClient(tracking_uri=server.uri)
        assert client.search_registered_models() == []
        example = schema_only_input_example()
        for task in ("regression", "classification"):
            key = f"{task}_selected"
            loaded = load_verified_phase5_model(
                tracked.child_run_ids[key],
                tracking_uri=server.uri,
                feature_snapshot_id=first.development.manifest.feature_snapshot_id,
                comparison_id=first.development.manifest.comparison_id,
                selection_id=first.development.selection.selection_id,
                download_root=tmp_path / f"actual-{key}",
            )
            np.testing.assert_allclose(
                loaded.predict(example), first.benchmark.models[key].predict(example)
            )
        artifacts = client.list_artifacts(tracked.parent_run_id, "evidence")
        assert artifacts
        assert all(
            item.file_size is None or item.file_size < 1_000_000 for item in artifacts
        )
    finally:
        server.stop()
