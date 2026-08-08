"""LocalExecutor execution, retry, idempotency, and backfill evidence."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_SOURCE_ID = "7ac4dc6568b3968e18cec98dd0162a640838f062183989a658dc40bc3c831cca"
pytestmark = [pytest.mark.integration, pytest.mark.airflow]


def _application_dsn() -> str:
    value = os.environ.get("PM_POSTGRES_DSN", "")
    parsed = urlsplit(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail(
            "Airflow integration requires the disposable local PostgreSQL port."
        )
    return value


def _airflow_dsn() -> str:
    parsed = urlsplit(_application_dsn())
    return urlunsplit(
        parsed._replace(
            netloc=f"postgres:phase2-local-only@{parsed.hostname}:{parsed.port}",
            path="/airflow",
        )
    )


def _airflow(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "airflow", "airflow", *arguments],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=240,
    )


def _wait_for_backfill() -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        with psycopg.connect(_airflow_dsn()) as connection:
            rows = connection.execute(
                """
                select logical_date, state
                from dag_run
                where dag_id = 'fd001_derived_pipeline'
                  and run_type = 'backfill'
                  and logical_date in (%s, %s)
                order by logical_date
                """,
                ("2026-03-03T00:00:00+00:00", "2026-03-04T00:00:00+00:00"),
            ).fetchall()
        if len(rows) == 2 and all(row[1] == "success" for row in rows):
            return
        if any(row[1] == "failed" for row in rows):
            pytest.fail(f"Backfill failed: {rows}")
        time.sleep(1)
    pytest.fail("The two-date Airflow backfill did not finish within 120 seconds.")


def test_localexecutor_retry_and_backfill_reuse_one_artifact_set(
    tmp_path: Path,
) -> None:
    dsn = _application_dsn()
    raw_bucket = os.environ.get("PM_RAW_BUCKET", "pm-raw")
    derived_bucket = os.environ.get("PM_DERIVED_BUCKET", "pm-derived")
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
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw",
        code_revision="phase3-airflow-test",
    )
    assert ingestion.snapshot.manifest.snapshot_id == EXPECTED_SOURCE_ID
    objects = FilesystemObjectRepository(ROOT / "artifacts/cloud-objects")
    raw_metadata = PostgresMetadataRepository(dsn)
    derived_metadata = PostgresDerivedMetadataRepository(dsn)
    publish_snapshot(ingestion.snapshot, raw_bucket, objects, raw_metadata)
    direct = run_pipeline(
        EXPECTED_SOURCE_ID,
        derived_bucket,
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase3-local",
    )

    configured_source = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "airflow",
            "printenv",
            "PM_SOURCE_SNAPSHOT_ID",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    assert configured_source == EXPECTED_SOURCE_ID
    for name, expected in (
        ("PM_RAW_BUCKET", raw_bucket),
        ("PM_DERIVED_BUCKET", derived_bucket),
    ):
        configured = subprocess.run(
            ["docker", "compose", "exec", "-T", "airflow", "printenv", name],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        assert configured == expected

    normal_conf = json.dumps({"source_snapshot_id": EXPECTED_SOURCE_ID})
    _airflow(
        "dags",
        "test",
        "fd001_derived_pipeline",
        "2026-03-01T00:00:00+00:00",
        "--use-executor",
        "--conf",
        normal_conf,
    )
    retry_conf = json.dumps(
        {
            "source_snapshot_id": EXPECTED_SOURCE_ID,
            "inject_retryable_failure": True,
        }
    )
    _airflow(
        "dags",
        "test",
        "fd001_derived_pipeline",
        "2026-03-02T00:00:00+00:00",
        "--use-executor",
        "--conf",
        retry_conf,
    )

    _airflow(
        "backfill",
        "create",
        "--dag-id",
        "fd001_derived_pipeline",
        "--from-date",
        "2026-03-03",
        "--to-date",
        "2026-03-04",
        "--max-active-runs",
        "1",
        "--dag-run-conf",
        normal_conf,
    )
    _airflow("dags", "unpause", "fd001_derived_pipeline")
    _wait_for_backfill()

    with psycopg.connect(dsn) as connection:
        snapshot_rows = connection.execute(
            """
            select artifact_kind, derived_snapshot_id
            from ops.derived_snapshots
            order by artifact_kind
            """
        ).fetchall()
        run_rows = connection.execute(
            """
            select processed_snapshot_id, feature_snapshot_id, quality_snapshot_id
            from ops.transformation_runs
            """
        ).fetchall()
    assert snapshot_rows == [
        ("feature", direct.feature_snapshot_id),
        ("processed", direct.processed_snapshot_id),
        ("quality_report", direct.quality_snapshot_id),
    ]
    assert run_rows == [
        (
            direct.processed_snapshot_id,
            direct.feature_snapshot_id,
            direct.quality_snapshot_id,
        )
    ]

    with psycopg.connect(_airflow_dsn()) as connection:
        retry_attempt = connection.execute(
            """
            select ti.try_number
            from task_instance ti
            join dag_run dr on dr.run_id = ti.run_id and dr.dag_id = ti.dag_id
            where dr.dag_id = 'fd001_derived_pipeline'
              and dr.logical_date = %s
              and ti.task_id = 'publish_processed'
            """,
            ("2026-03-02T00:00:00+00:00",),
        ).fetchone()
        max_xcom_bytes = connection.execute(
            """
            select max(octet_length(value::text))
            from xcom
            where dag_id = 'fd001_derived_pipeline'
            """
        ).fetchone()
    assert retry_attempt == (2,)
    assert max_xcom_bytes is not None
    assert max_xcom_bytes[0] <= 512
