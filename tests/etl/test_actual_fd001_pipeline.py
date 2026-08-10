"""Owner-provided FD001 direct Phase 3 pipeline evidence."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.pipeline import run_pipeline


@pytest.mark.dataset
@pytest.mark.integration
@pytest.mark.postgres
def test_actual_fd001_direct_pipeline_is_deterministic(tmp_path: Path) -> None:
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
        pytest.fail("Use only the disposable local Phase 3 PostgreSQL database.")
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
        code_revision="phase3-actual-dataset-test",
    )
    objects = FilesystemObjectRepository(tmp_path / "objects")
    raw_metadata = PostgresMetadataRepository(dsn)
    derived_metadata = PostgresDerivedMetadataRepository(dsn)
    raw = publish_snapshot(ingestion.snapshot, "pm-raw", objects, raw_metadata)
    first = run_pipeline(
        raw.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase3-actual-dataset-test",
    )
    second = run_pipeline(
        raw.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase3-actual-dataset-test",
    )

    assert first.source_snapshot_id == (
        "17d1db8dd823266b58b9c8d5b6da8edace17220980b733188756cd6b630e453d"
    )
    assert first.reused is False
    assert second.reused is True
    assert first.processed_snapshot_id == second.processed_snapshot_id
    assert first.feature_snapshot_id == second.feature_snapshot_id
    assert first.quality_snapshot_id == second.quality_snapshot_id
    assert len(objects.list_keys("pm-derived", "processed/fd001")) == 3
    assert len(objects.list_keys("pm-derived", "features/fd001")) == 5
    assert len(objects.list_keys("pm-derived", "reports/data-quality")) == 2
