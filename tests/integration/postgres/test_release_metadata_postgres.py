"""Phase 6 PostgreSQL release governance, RLS, and append-only tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest
from phase6_support import SyntheticRelease, build_synthetic_release

from predictive_maintenance.modeling.models import sha256_bytes
from predictive_maintenance.release.metadata import (
    DeploymentEvent,
    PostgresReleaseRepository,
)
from predictive_maintenance.release.models import ReleaseError

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def _required_scalar(row: tuple[object, ...] | None) -> object:
    assert row is not None
    return row[0]


def _dsn() -> str:
    value = os.environ.get("PM_POSTGRES_DSN", "")
    if not value:
        pytest.skip("PM_POSTGRES_DSN is required for PostgreSQL integration tests.")
    parsed = urlsplit(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail("PostgreSQL integration tests require the disposable local port.")
    return value


@pytest.fixture
def release(tmp_path: Path) -> Iterator[SyntheticRelease]:
    """Insert the minimum immutable data lineage needed by a model release."""
    value = build_synthetic_release(tmp_path)
    manifest = value.manifest
    with psycopg.connect(_dsn(), autocommit=True) as connection:
        connection.execute(
            """
            truncate table
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
        raw_object = _required_scalar(
            connection.execute(
                """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values ('pm-raw', 'phase6/raw.json', 'raw', %s, 1,
                      'application/json', 'verified', now())
            returning object_id
            """,
                ("1" * 64,),
            ).fetchone()
        )
        processed_object = _required_scalar(
            connection.execute(
                """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values ('pm-derived', 'phase6/processed.json', 'derived', %s, 1,
                      'application/json', 'verified', now())
            returning object_id
            """,
                ("2" * 64,),
            ).fetchone()
        )
        feature_object = _required_scalar(
            connection.execute(
                """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values ('pm-derived', 'phase6/feature.json', 'derived', %s, 1,
                      'application/json', 'verified', now())
            returning object_id
            """,
                ("3" * 64,),
            ).fetchone()
        )
        connection.execute(
            """
            insert into ops.dataset_snapshots (
                snapshot_id, dataset_family, dataset_subset, contract_version,
                parser_version, code_revision, manifest_sha256,
                manifest_object_id, required_file_count, state
            ) values (%s, 'NASA C-MAPSS', 'FD001', 'test', 'test', 'test',
                      %s, %s, 1, 'available')
            """,
            (manifest.raw_snapshot_id, "1" * 64, raw_object),
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
                manifest.processed_snapshot_id,
                manifest.raw_snapshot_id,
                "2" * 64,
                processed_object,
                manifest.feature_snapshot_id,
                manifest.raw_snapshot_id,
                manifest.processed_snapshot_id,
                "3" * 64,
                feature_object,
            ),
        )
    yield value


def test_candidate_decision_and_deployment_are_idempotent_or_append_only(
    release: SyntheticRelease,
) -> None:
    repository = PostgresReleaseRepository(_dsn())
    repository.record_candidate(release.manifest)
    repository.record_candidate(release.manifest)
    repository.record_decision(release.approval)
    repository.record_decision(release.approval)
    event = DeploymentEvent(
        release.manifest.release_id,
        "deploy_succeeded",
        "KJSK-Koushik",
        "Synthetic smoke passed.",
        sha256_bytes(b"smoke"),
        release.approval.decided_at + timedelta(minutes=2),
    )
    first_event_id = repository.record_deployment_event(event)
    second_event_id = repository.record_deployment_event(event)
    assert second_event_id > first_event_id
    with psycopg.connect(_dsn()) as connection:
        assert connection.execute(
            "select count(*) from ops.model_releases"
        ).fetchone() == (1,)
        assert connection.execute(
            "select count(*) from ops.release_decisions"
        ).fetchone() == (1,)
        assert connection.execute(
            "select count(*) from ops.deployment_events"
        ).fetchone() == (2,)


def test_runtime_and_client_role_permissions_are_fail_closed(
    release: SyntheticRelease,
) -> None:
    PostgresReleaseRepository(_dsn()).record_candidate(release.manifest)
    with psycopg.connect(_dsn()) as connection:
        connection.execute("set local role predictive_maintenance_runtime")
        assert connection.execute(
            "select count(*) from ops.model_releases"
        ).fetchone() == (1,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("delete from ops.model_releases")
    for role in ("anon", "authenticated"):
        with psycopg.connect(_dsn()) as connection:
            connection.execute(f"set local role {role}")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute("select * from ops.model_releases")


def test_production_deployment_event_is_rejected(release: SyntheticRelease) -> None:
    event = DeploymentEvent(
        release.manifest.release_id,
        "deploy_started",
        "KJSK-Koushik",
        "Must fail.",
        "a" * 64,
        release.approval.decided_at,
        environment="production",
    )
    with pytest.raises(ReleaseError, match=r"deployment\.production_disabled"):
        PostgresReleaseRepository(_dsn()).record_deployment_event(event)
