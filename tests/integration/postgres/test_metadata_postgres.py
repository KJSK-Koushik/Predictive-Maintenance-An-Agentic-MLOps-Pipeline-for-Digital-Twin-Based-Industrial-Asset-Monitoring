"""Migration, security, transaction, and recovery evidence for PostgreSQL."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import (
    publish_snapshot,
    reconcile_snapshot,
)
from predictive_maintenance.data.integrity import Snapshot, create_snapshot

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_TABLES = {
    "data_objects",
    "dataset_snapshots",
    "ingestion_runs",
    "lineage_edges",
    "snapshot_files",
}

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def _dsn() -> str:
    value = os.environ.get("PM_POSTGRES_DSN", "")
    if not value:
        pytest.skip("PM_POSTGRES_DSN is required for PostgreSQL integration tests.")
    parsed = urlsplit(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail("PostgreSQL integration tests require the disposable local port.")
    return value


def _database_dsn(dsn: str, database: str) -> str:
    parsed = urlsplit(dsn)
    return urlunsplit(parsed._replace(path=f"/{database}"))


def _compose_exec(*command: str, input_text: str | None = None) -> str:
    """Run one bounded command inside the disposable PostgreSQL service."""
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", *command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=120,
    ).stdout


@pytest.fixture(autouse=True)
def clean_operational_tables() -> Iterator[None]:
    """Reset only Phase 2 rows in the disposable local database."""
    dsn = _dsn()
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
    yield


def _snapshot(tmp_path: Path) -> Snapshot:
    return create_snapshot(
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw",
        code_revision="postgres-test",
    )


def test_migration_created_only_approved_private_objects() -> None:
    with psycopg.connect(_dsn()) as connection:
        major = connection.execute(
            "select current_setting('server_version_num')::integer"
        ).fetchone()
        assert major is not None
        assert 170000 <= major[0] < 180000
        tables = connection.execute(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'ops' and table_type = 'BASE TABLE'
            """
        ).fetchall()
        assert {row[0] for row in tables} == EXPECTED_TABLES
        managed_custom = connection.execute(
            """
            select n.nspname, c.relname
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname in ('auth', 'storage', 'realtime')
              and c.relkind in ('r', 'v', 'm', 'f')
            """
        ).fetchall()
        assert managed_custom == []


def test_runtime_role_is_no_login_no_bypassrls_and_narrowly_granted() -> None:
    with psycopg.connect(_dsn()) as connection:
        role = connection.execute(
            """
            select
                rolcanlogin,
                rolsuper,
                rolcreatedb,
                rolcreaterole,
                rolinherit,
                rolreplication,
                rolbypassrls
            from pg_roles
            where rolname = 'predictive_maintenance_runtime'
            """
        ).fetchone()
        assert role == (False, False, False, False, False, False, False)
        connection.execute("set local role predictive_maintenance_runtime")
        assert connection.execute(
            "select count(*) from ops.dataset_snapshots"
        ).fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("delete from ops.dataset_snapshots")


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_data_api_roles_cannot_access_ops(role: str) -> None:
    with psycopg.connect(_dsn()) as connection:
        connection.execute(f"set local role {role}")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("select * from ops.dataset_snapshots")


def test_rls_is_enabled_and_policies_target_only_runtime_role() -> None:
    with psycopg.connect(_dsn()) as connection:
        rls = connection.execute(
            """
            select c.relname, c.relrowsecurity
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'ops' and c.relkind = 'r'
            order by c.relname
            """
        ).fetchall()
        assert {row[0] for row in rls} == EXPECTED_TABLES
        assert all(row[1] is True for row in rls)
        granted_roles = connection.execute(
            """
            select distinct grantee
            from information_schema.role_table_grants
            where table_schema = 'ops'
            """
        ).fetchall()
        assert {row[0] for row in granted_roles} == {
            "postgres",
            "predictive_maintenance_runtime",
        }
        sequence_privileges = connection.execute(
            """
            select
                has_sequence_privilege(
                    'predictive_maintenance_runtime',
                    'ops.data_objects_object_id_seq',
                    'USAGE'
                ),
                has_sequence_privilege(
                    'predictive_maintenance_runtime',
                    'ops.data_objects_object_id_seq',
                    'SELECT'
                ),
                has_sequence_privilege(
                    'predictive_maintenance_runtime',
                    'ops.data_objects_object_id_seq',
                    'UPDATE'
                )
            """
        ).fetchone()
        assert sequence_privileges == (True, False, False)


def test_postgres_publication_is_idempotent_and_complete(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = PostgresMetadataRepository(_dsn())

    first = publish_snapshot(snapshot, "pm-raw", objects, metadata)
    second = publish_snapshot(snapshot, "pm-raw", objects, metadata)

    assert first.reused is False
    assert second.reused is True
    assert first.object_count == 5
    assert reconcile_snapshot(first.snapshot_id, objects, metadata).consistent
    with psycopg.connect(_dsn()) as connection:
        counts: dict[str, int] = {}
        for table in EXPECTED_TABLES:
            row = connection.execute(f"select count(*) from ops.{table}").fetchone()
            assert row is not None
            counts[table] = row[0]
    assert counts == {
        "data_objects": 5,
        "dataset_snapshots": 1,
        "ingestion_runs": 1,
        "lineage_edges": 4,
        "snapshot_files": 4,
    }
    with psycopg.connect(_dsn()) as connection:
        manifest_edges = connection.execute(
            """
            select count(*)
            from ops.lineage_edges edge
            join ops.dataset_snapshots snapshot
              on snapshot.manifest_object_id = edge.parent_object_id
            where edge.relationship_type = 'documented_by_manifest'
            """
        ).fetchone()
        assert manifest_edges == (4,)


def test_constraints_reject_bad_hash_and_self_lineage(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = PostgresMetadataRepository(_dsn())
    publish_snapshot(snapshot, "pm-raw", objects, metadata)

    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            )
            values (
                'pm-raw', 'invalid/hash', 'raw', 'bad', 1,
                'text/plain', 'verified', now()
            )
            """
        )
    with psycopg.connect(_dsn()) as connection:
        object_id = connection.execute(
            "select object_id from ops.data_objects limit 1"
        ).fetchone()
        assert object_id is not None
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                """
                insert into ops.lineage_edges (
                    parent_object_id, child_object_id, relationship_type
                )
                values (%s, %s, 'derived_from')
                """,
                (object_id[0], object_id[0]),
            )


@pytest.mark.parametrize(
    "object_key,zone,sha256,byte_size,state,verified_at",
    [
        ("constraint/probe", "invalid", "a" * 64, 1, "verified", datetime.now(UTC)),
        ("constraint/probe", "raw", "bad", 1, "verified", datetime.now(UTC)),
        ("constraint/probe", "raw", "a" * 64, -1, "verified", datetime.now(UTC)),
        ("constraint/probe", "raw", "a" * 64, 1, "pending", datetime.now(UTC)),
        (
            "constraint/probe",
            "raw",
            "a" * 64,
            1,
            "verified",
            datetime.now(UTC) + timedelta(minutes=10),
        ),
        ("/absolute", "raw", "a" * 64, 1, "verified", datetime.now(UTC)),
        ("trailing/", "raw", "a" * 64, 1, "verified", datetime.now(UTC)),
        ("windows\\path", "raw", "a" * 64, 1, "verified", datetime.now(UTC)),
    ],
)
def test_object_state_hash_size_and_timestamp_checks(
    object_key: str,
    zone: str,
    sha256: str,
    byte_size: int,
    state: str,
    verified_at: datetime,
) -> None:
    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            )
            values (
                'pm-raw', %s, %s, %s, %s,
                'text/plain', %s, %s
            )
            """,
            (object_key, zone, sha256, byte_size, state, verified_at),
        )


def test_foreign_unique_primary_and_run_timestamp_constraints(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = PostgresMetadataRepository(_dsn())
    publish_snapshot(snapshot, "pm-raw", objects, metadata)
    with psycopg.connect(_dsn()) as connection:
        object_row = connection.execute(
            """
            select
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            from ops.data_objects
            limit 1
            """
        ).fetchone()
        assert object_row is not None
    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.UniqueViolation),
    ):
        connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            object_row,
        )
    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.ForeignKeyViolation),
    ):
        connection.execute(
            """
            insert into ops.lineage_edges (
                parent_object_id, child_object_id, relationship_type
            )
            values (99999998, 99999999, 'derived_from')
            """
        )
    with psycopg.connect(_dsn()) as connection:
        edge = connection.execute(
            """
            select parent_object_id, child_object_id, relationship_type
            from ops.lineage_edges
            limit 1
            """
        ).fetchone()
        assert edge is not None
    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.UniqueViolation),
    ):
        connection.execute(
            """
            insert into ops.lineage_edges (
                parent_object_id, child_object_id, relationship_type
            )
            values (%s, %s, %s)
            """,
            edge,
        )
    with (
        psycopg.connect(_dsn()) as connection,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        connection.execute(
            """
            insert into ops.ingestion_runs (
                run_id, idempotency_key, state, started_at, finished_at
            )
            values (
                gen_random_uuid(), %s, 'available',
                now(), now() - interval '1 minute'
            )
            """,
            ("f" * 64,),
        )


def test_clean_reset_reapply_has_same_schema_fingerprint() -> None:
    dsn = _dsn()
    reset_database = "predictive_maintenance_reset"
    fingerprints: list[str] = []
    try:
        for _ in range(2):
            with psycopg.connect(dsn, autocommit=True) as connection:
                connection.execute(f"drop database if exists {reset_database}")
                connection.execute(f"create database {reset_database}")
            _compose_exec(
                "psql",
                "--username=postgres",
                "--set=ON_ERROR_STOP=1",
                "--dbname",
                reset_database,
                "--file",
                "/docker-entrypoint-initdb.d/010_phase_02_cloud_metadata.sql",
            )
            schema_dump = _compose_exec(
                "pg_dump",
                "--username=postgres",
                "--schema-only",
                "--schema=ops",
                "--no-owner",
                "--no-privileges",
                reset_database,
            )
            deterministic_lines = [
                line
                for line in schema_dump.splitlines()
                if not line.startswith(("\\restrict ", "\\unrestrict "))
            ]
            fingerprints.append("\n".join(deterministic_lines))
        assert fingerprints[0] == fingerprints[1]
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(f"drop database if exists {reset_database}")


def test_metadata_and_object_backup_restore_reconciles(
    tmp_path: Path,
) -> None:
    dsn = _dsn()
    snapshot = _snapshot(tmp_path)
    source_objects = FilesystemObjectRepository(tmp_path / "objects")
    metadata = PostgresMetadataRepository(dsn)
    result = publish_snapshot(snapshot, "pm-raw", source_objects, metadata)
    stored = metadata.get_snapshot(result.snapshot_id)
    assert stored is not None

    dump = _compose_exec(
        "pg_dump",
        "--username=postgres",
        "--data-only",
        "--schema=ops",
        "--no-owner",
        "--no-privileges",
        "predictive_maintenance",
    )
    restore_database = "predictive_maintenance_restore"
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(f"drop database if exists {restore_database}")
        connection.execute(f"create database {restore_database}")
    try:
        _compose_exec(
            "psql",
            "--username=postgres",
            "--set=ON_ERROR_STOP=1",
            "--dbname",
            restore_database,
            "--file",
            "/docker-entrypoint-initdb.d/010_phase_02_cloud_metadata.sql",
        )
        _compose_exec(
            "psql",
            "--username=postgres",
            "--set=ON_ERROR_STOP=1",
            "--dbname",
            restore_database,
            input_text=dump,
        )

        restored_root = tmp_path / "restored-objects"
        restored_objects = FilesystemObjectRepository(restored_root)
        for identity in stored.identities:
            payload = source_objects.read(
                identity.bucket_name,
                identity.object_key,
            )
            backup_file = tmp_path / f"{identity.sha256}.backup"
            backup_file.write_bytes(payload)
            restored_objects.put_verified(backup_file, identity)

        restored_metadata = PostgresMetadataRepository(
            _database_dsn(dsn, restore_database)
        )
        report = reconcile_snapshot(
            result.snapshot_id,
            restored_objects,
            restored_metadata,
        )
        assert report.consistent
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(
                """
                select pg_terminate_backend(pid)
                from pg_stat_activity
                where datname = %s and pid <> pg_backend_pid()
                """,
                (restore_database,),
            )
            connection.execute(f"drop database if exists {restore_database}")
