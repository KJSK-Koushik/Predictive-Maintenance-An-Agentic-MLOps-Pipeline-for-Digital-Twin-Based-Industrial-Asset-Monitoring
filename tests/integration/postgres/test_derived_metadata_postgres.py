"""Phase 3 PostgreSQL derived publication, lineage, security, and isolation."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.integrity import create_snapshot
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[3]
pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture(autouse=True)
def clean_operational_tables() -> Iterator[None]:
    """Reset Phase 2 and Phase 3 rows in the disposable database."""
    with psycopg.connect(_dsn(), autocommit=True) as connection:
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
    yield


def _dsn() -> str:
    value = os.environ.get("PM_POSTGRES_DSN", "")
    if not value:
        pytest.skip("PM_POSTGRES_DSN is required for PostgreSQL integration tests.")
    parsed = urlsplit(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail("PostgreSQL integration tests require the disposable local port.")
    return value


def _airflow_dsn() -> str:
    parsed = urlsplit(_dsn())
    host = parsed.hostname or "127.0.0.1"
    netloc = f"airflow:phase3-airflow-local-only@{host}:{parsed.port}"
    return urlunsplit(parsed._replace(netloc=netloc, path="/airflow"))


def _publish_derived(tmp_path: Path) -> tuple[str, FilesystemObjectRepository]:
    snapshot = create_snapshot(
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw",
        code_revision="phase3-postgres-test",
    )
    objects = FilesystemObjectRepository(tmp_path / "objects")
    raw_metadata = PostgresMetadataRepository(_dsn())
    publish_snapshot(snapshot, "pm-raw", objects, raw_metadata)
    derived_metadata = PostgresDerivedMetadataRepository(_dsn())
    result = run_pipeline(
        snapshot.manifest.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase3-postgres-test",
    )
    return result.processed_snapshot_id, objects


def test_postgres_derived_pipeline_is_complete_and_idempotent(tmp_path: Path) -> None:
    snapshot = create_snapshot(
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw",
        code_revision="phase3-postgres-test",
    )
    objects = FilesystemObjectRepository(tmp_path / "objects")
    raw_metadata = PostgresMetadataRepository(_dsn())
    derived_metadata = PostgresDerivedMetadataRepository(_dsn())
    publish_snapshot(snapshot, "pm-raw", objects, raw_metadata)

    first = run_pipeline(
        snapshot.manifest.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase3-postgres-test",
    )
    second = run_pipeline(
        snapshot.manifest.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase3-postgres-test",
    )

    assert first.reused is False
    assert second.reused is True
    assert first.processed_snapshot_id == second.processed_snapshot_id
    with psycopg.connect(_dsn()) as connection:
        counts = {
            table: connection.execute(f"select count(*) from ops.{table}").fetchone()
            for table in (
                "data_objects",
                "derived_snapshots",
                "derived_snapshot_files",
                "transformation_runs",
            )
        }
        assert counts == {
            "data_objects": (15,),
            "derived_snapshots": (3,),
            "derived_snapshot_files": (7,),
            "transformation_runs": (1,),
        }
        lineage: dict[str, int] = dict(
            connection.execute(
                """
                select relationship_type, count(*)
                from ops.lineage_edges
                group by relationship_type
                """
            ).fetchall()
        )
        assert lineage == {
            "derived_from": 7,
            "documented_by_manifest": 11,
            "reported_by": 6,
        }


def test_runtime_grants_and_rls_cover_new_tables_independently(
    tmp_path: Path,
) -> None:
    processed_id, _ = _publish_derived(tmp_path)
    with psycopg.connect(_dsn()) as connection:
        connection.execute("set local role predictive_maintenance_runtime")
        assert connection.execute(
            "select count(*) from ops.derived_snapshots"
        ).fetchone() == (3,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("delete from ops.derived_snapshots")
    with psycopg.connect(_dsn()) as connection:
        connection.execute(
            """
            update ops.derived_snapshots
            set state = 'inconsistent', updated_at = now()
            where derived_snapshot_id = %s
            """,
            (processed_id,),
        )
    with psycopg.connect(_dsn()) as connection:
        connection.execute("set local role predictive_maintenance_runtime")
        updated = connection.execute(
            """
            update ops.derived_snapshots
            set state = 'available', updated_at = now()
            where derived_snapshot_id = %s
            returning derived_snapshot_id
            """,
            (processed_id,),
        ).fetchall()
        assert updated == []


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_data_api_roles_cannot_access_derived_metadata(role: str) -> None:
    with psycopg.connect(_dsn()) as connection:
        connection.execute(f"set local role {role}")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("select * from ops.derived_snapshots")


def test_airflow_metadata_database_and_user_are_isolated_from_ops() -> None:
    with psycopg.connect(_dsn()) as connection:
        row = connection.execute(
            """
            select database.datname, role.rolsuper, role.rolcreatedb
            from pg_database database
            join pg_roles role on role.oid = database.datdba
            where database.datname = 'airflow' and role.rolname = 'airflow'
            """
        ).fetchone()
        assert row == ("airflow", False, False)
    with psycopg.connect(_airflow_dsn()) as connection:
        assert connection.execute("select to_regnamespace('ops')").fetchone() == (None,)


def test_derived_constraints_reject_invalid_parent_and_file_metadata(
    tmp_path: Path,
) -> None:
    _publish_derived(tmp_path)
    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        connection.execute(
            """
            insert into ops.derived_snapshots (
                derived_snapshot_id, source_snapshot_id,
                parent_derived_snapshot_id, artifact_kind, contract_version,
                transformation_version, serializer_version, code_revision,
                manifest_sha256, manifest_object_id, required_file_count, state
            )
            select
                %s, source_snapshot_id, null, 'feature', contract_version,
                transformation_version, serializer_version, code_revision,
                %s, manifest_object_id, 1, 'available'
            from ops.derived_snapshots
            limit 1
            """,
            ("e" * 64, "d" * 64),
        )
