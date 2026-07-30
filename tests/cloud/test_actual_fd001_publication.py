"""Owner-provided FD001 local publication evidence."""

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


@pytest.mark.dataset
@pytest.mark.integration
@pytest.mark.postgres
def test_actual_fd001_publishes_locally_and_idempotently(tmp_path: Path) -> None:
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
        pytest.fail("Use only the disposable local Phase 2 PostgreSQL database.")
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(
            """
            truncate table
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
        code_revision="phase-2-actual-dataset-test",
    )
    objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = PostgresMetadataRepository(dsn)
    first = publish_snapshot(ingestion.snapshot, "pm-raw", objects, metadata)
    second = publish_snapshot(ingestion.snapshot, "pm-raw", objects, metadata)

    assert first.snapshot_id == (
        "17d1db8dd823266b58b9c8d5b6da8edace17220980b733188756cd6b630e453d"
    )
    assert first.state == "available"
    assert first.object_count == 5
    assert first.reused is False
    assert second.reused is True
