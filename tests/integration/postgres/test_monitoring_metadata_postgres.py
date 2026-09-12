"""Phase 7 PostgreSQL monitoring persistence, RLS, and authority tests."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from phase7_support import identity, prediction_frame, telemetry_frame

from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.monitoring.metadata import PostgresMonitoringRepository
from predictive_maintenance.monitoring.models import (
    MonitoringPolicy,
    MonitoringReport,
    MonitoringWindow,
    ReferenceProfile,
    canonical_json_bytes,
)
from predictive_maintenance.monitoring.pipeline import (
    build_monitoring_report,
    create_window,
)
from predictive_maintenance.monitoring.publication import monitoring_report_key
from predictive_maintenance.monitoring.reference import build_reference_profile
from predictive_maintenance.monitoring.triggers import (
    CandidateRequest,
    Investigation,
)
from predictive_maintenance.retraining.evaluation import blocked_no_new_training_data

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase/migrations/20260907042647_phase_07_monitoring.sql"
pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def _dsn() -> str:
    value = os.environ.get("PM_POSTGRES_DSN", "")
    parsed = urlsplit(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.skip("Phase 7 PostgreSQL tests require the disposable local port.")
    return value


def _object_identity(*, bucket: str, key: str, payload: bytes) -> ObjectIdentity:
    from predictive_maintenance.monitoring.models import sha256_bytes

    return ObjectIdentity(
        bucket_name=bucket,
        object_key=key,
        zone="derived",
        sha256=sha256_bytes(payload),
        byte_size=len(payload),
        content_type="application/json",
    )


def _database_dsn(database_name: str) -> str:
    parsed = urlsplit(_dsn())
    return urlunsplit(parsed._replace(path=f"/{database_name}"))


def _compose_exec(*arguments: str, input_text: str | None = None) -> str:
    completed = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", *arguments],
        cwd=ROOT,
        input=input_text,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        pytest.fail(
            "PostgreSQL utility command failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout


def _seed_release() -> None:
    """Insert the minimum valid Phase 2/3/6 lineage for monitoring."""
    with psycopg.connect(_dsn(), autocommit=True) as connection:
        connection.execute(
            """
            truncate table
                ops.challenger_evaluations,
                ops.retraining_candidate_requests,
                ops.monitoring_alerts,
                ops.monitoring_reports,
                ops.monitoring_windows,
                ops.monitoring_references,
                ops.deployment_events,
                ops.release_decisions,
                ops.model_releases,
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
        raw_object = connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values ('pm-raw', 'phase7/raw.json', 'raw', %s, 1,
                      'application/json', 'verified', now())
            returning object_id
            """,
            (identity("raw-object"),),
        ).fetchone()
        processed_object = connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values ('pm-derived', 'phase7/processed.json', 'derived', %s, 1,
                      'application/json', 'verified', now())
            returning object_id
            """,
            (identity("processed-object"),),
        ).fetchone()
        feature_object = connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values ('pm-derived', 'phase7/features.json', 'derived', %s, 1,
                      'application/json', 'verified', now())
            returning object_id
            """,
            (identity("feature-object"),),
        ).fetchone()
        assert raw_object and processed_object and feature_object
        connection.execute(
            """
            insert into ops.dataset_snapshots (
                snapshot_id, dataset_family, dataset_subset, contract_version,
                parser_version, code_revision, manifest_sha256,
                manifest_object_id, required_file_count, state
            ) values (%s, 'NASA C-MAPSS', 'FD001', 'test', 'test', 'test',
                      %s, %s, 1, 'available')
            """,
            (identity("raw"), identity("raw-object"), raw_object[0]),
        )
        connection.execute(
            """
            insert into ops.derived_snapshots (
                derived_snapshot_id, source_snapshot_id,
                parent_derived_snapshot_id, artifact_kind, contract_version,
                transformation_version, serializer_version, code_revision,
                manifest_sha256, manifest_object_id, required_file_count, state
            ) values
                (%s, %s, null, 'processed', 'test', 'test', 'test', 'test',
                 %s, %s, 1, 'available'),
                (%s, %s, %s, 'feature', 'test', 'test', 'test', 'test',
                 %s, %s, 1, 'available')
            """,
            (
                identity("processed"),
                identity("raw"),
                identity("processed-object"),
                processed_object[0],
                identity("feature"),
                identity("raw"),
                identity("processed"),
                identity("feature-object"),
                feature_object[0],
            ),
        )
        connection.execute(
            """
            insert into ops.model_releases (
                release_id, approval_request_id, release_contract_version,
                manifest_sha256, manifest_json, feature_snapshot_id,
                regression_registered_name, regression_model_version,
                regression_source_run_id, classification_registered_name,
                classification_model_version, classification_source_run_id
            ) values (
                %s, %s, 'fd001-two-model-release-v1', %s,
                jsonb_build_object(
                    'release_id', %s::text,
                    'approval_request_id', %s::text
                ),
                %s, 'fd001-rul-regression', 1, 'phase7-test-r',
                'fd001-failure-risk-classification', 1, 'phase7-test-c'
            )
            """,
            (
                identity("release"),
                identity("approval"),
                identity("manifest"),
                identity("release"),
                identity("approval"),
                identity("feature"),
            ),
        )


def _evidence() -> tuple[
    MonitoringPolicy, ReferenceProfile, MonitoringWindow, MonitoringReport
]:
    policy = MonitoringPolicy()
    frame = telemetry_frame()
    reference = build_reference_profile(
        frame,
        release_id=identity("release"),
        feature_snapshot_id=identity("feature"),
        policy=policy,
        code_revision="phase7-test",
        dependency_lock_sha256=identity("lock"),
    )
    window = create_window(
        frame,
        reference=reference,
        policy=policy,
        raw_snapshot_id=identity("raw"),
        processed_snapshot_id=identity("processed"),
        feature_snapshot_id=identity("feature"),
        source_partition="synthetic",
        replay_sequence=1,
        code_revision="phase7-test",
        dependency_lock_sha256=identity("lock"),
    )
    report = build_monitoring_report(
        frame,
        prediction_frame(frame),
        prediction_frame(frame),
        window=window,
        reference=reference,
        policy=policy,
        service_evidence={
            "readiness": True,
            "status_codes": [200],
            "latencies_ms": [1.0],
        },
    )
    return policy, reference, window, report


def test_migration_is_cli_named_private_and_contains_no_managed_schema_changes() -> (
    None
):
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert MIGRATION.name == "20260907042647_phase_07_monitoring.sql"
    for table in (
        "monitoring_references",
        "monitoring_windows",
        "monitoring_reports",
        "monitoring_alerts",
        "retraining_candidate_requests",
        "challenger_evaluations",
    ):
        assert f"create table ops.{table}" in source
        assert f"alter table ops.{table} enable row level security" in source
        assert f"revoke all on ops.{table} from public, anon, authenticated" in source
    assert "create table public." not in source
    assert "auth." not in source
    assert "storage." not in source


def _record_monitoring_evidence() -> None:
    _seed_release()
    policy, reference, window, report = _evidence()
    repository = PostgresMonitoringRepository(_dsn())
    now = datetime.now(UTC)
    reference_object = _object_identity(
        bucket="pm-derived",
        key=f"reports/monitoring/{reference.release_id}/references/{reference.reference_id}.json",
        payload=reference.canonical_bytes(),
    )
    report_object = _object_identity(
        bucket="pm-derived",
        key=monitoring_report_key(report),
        payload=report.canonical_bytes(),
    )
    repository.record_reference(reference, reference_object, verified_at=now)
    repository.record_reference(reference, reference_object, verified_at=now)
    repository.record_window(window)
    repository.record_window(window)
    repository.record_report(report, report_object, verified_at=now)
    repository.record_report(report, report_object, verified_at=now)
    investigation = Investigation(
        report.report_id, "distribution_shift", ("shift.investigation",)
    )
    repository.record_investigation(investigation)
    repository.record_investigation(investigation)
    request = CandidateRequest(
        release_id=identity("release"),
        policy_id=policy.policy_id,
        requested_task="both",
        data_cutoff_window_id=window.window_id,
        evidence_report_ids=(report.report_id,),
        reason="persistent_shift",
    )
    repository.record_candidate_request(request)
    repository.record_candidate_request(request)
    evaluation = blocked_no_new_training_data(request)
    evaluation_payload = canonical_json_bytes(evaluation.to_dict())
    evaluation_object = _object_identity(
        bucket="pm-derived",
        key=f"reports/retraining/{request.request_id}/{evaluation.evaluation_id}.json",
        payload=evaluation_payload,
    )
    repository.record_evaluation(evaluation, evaluation_object, verified_at=now)
    repository.record_evaluation(evaluation, evaluation_object, verified_at=now)


def test_metadata_writes_are_idempotent_and_append_only() -> None:
    _record_monitoring_evidence()
    with psycopg.connect(_dsn()) as connection:
        for table in (
            "monitoring_references",
            "monitoring_windows",
            "monitoring_reports",
            "monitoring_alerts",
            "retraining_candidate_requests",
            "challenger_evaluations",
        ):
            assert connection.execute(
                f"select count(*) from ops.{table}"
            ).fetchone() == (1,)


def test_phase7_schema_reapply_indexes_and_data_restore() -> None:
    _record_monitoring_evidence()
    dump = _compose_exec(
        "pg_dump",
        "--username=postgres",
        "--data-only",
        "--schema=ops",
        "--no-owner",
        "--no-privileges",
        "predictive_maintenance",
    )
    database_name = "predictive_maintenance_phase7_restore"
    with psycopg.connect(_dsn(), autocommit=True) as connection:
        connection.execute(f"drop database if exists {database_name}")
        connection.execute(f"create database {database_name}")
    try:
        for migration in (
            "010_phase_02_cloud_metadata.sql",
            "020_phase_03_derived_metadata.sql",
            "030_phase_06_model_releases.sql",
            "040_phase_07_monitoring.sql",
        ):
            _compose_exec(
                "psql",
                "--username=postgres",
                "--set=ON_ERROR_STOP=1",
                "--dbname",
                database_name,
                "--file",
                f"/docker-entrypoint-initdb.d/{migration}",
            )
        _compose_exec(
            "psql",
            "--username=postgres",
            "--set=ON_ERROR_STOP=1",
            "--dbname",
            database_name,
            input_text=dump,
        )
        with psycopg.connect(_database_dsn(database_name)) as connection:
            table_rows = connection.execute(
                """
                select relname, relrowsecurity
                from pg_class
                where relnamespace = 'ops'::regnamespace
                  and relname in (
                    'monitoring_references', 'monitoring_windows',
                    'monitoring_reports', 'monitoring_alerts',
                    'retraining_candidate_requests', 'challenger_evaluations'
                  )
                order by relname
                """
            ).fetchall()
            assert len(table_rows) == 6
            assert all(row[1] for row in table_rows)
            for table in (
                "monitoring_references",
                "monitoring_windows",
                "monitoring_reports",
                "monitoring_alerts",
                "retraining_candidate_requests",
                "challenger_evaluations",
            ):
                assert connection.execute(
                    f"select count(*) from ops.{table}"
                ).fetchone() == (1,)
            index_count = connection.execute(
                """
                select count(*) from pg_indexes
                where schemaname = 'ops'
                  and indexname in (
                    'monitoring_references_feature_snapshot_idx',
                    'monitoring_windows_reference_idx',
                    'monitoring_reports_parent_idx',
                    'retraining_candidate_cutoff_idx',
                    'challenger_evaluations_champion_idx'
                  )
                """
            ).fetchone()
            assert index_count == (5,)
    finally:
        with psycopg.connect(_dsn(), autocommit=True) as connection:
            connection.execute(f"drop database if exists {database_name}")


def test_runtime_and_client_roles_cannot_mutate_or_read_without_grant() -> None:
    _seed_release()
    _, reference, _, _ = _evidence()
    repository = PostgresMonitoringRepository(_dsn())
    reference_object = _object_identity(
        bucket="pm-derived",
        key=f"reports/monitoring/{reference.release_id}/references/{reference.reference_id}.json",
        payload=reference.canonical_bytes(),
    )
    repository.record_reference(
        reference, reference_object, verified_at=datetime.now(UTC)
    )
    with psycopg.connect(_dsn()) as connection:
        connection.execute("set local role predictive_maintenance_runtime")
        assert connection.execute(
            "select count(*) from ops.monitoring_references"
        ).fetchone() == (1,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("delete from ops.monitoring_references")
    for role in ("anon", "authenticated"):
        with psycopg.connect(_dsn()) as connection:
            connection.execute(f"set local role {role}")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute("select * from ops.monitoring_references")
