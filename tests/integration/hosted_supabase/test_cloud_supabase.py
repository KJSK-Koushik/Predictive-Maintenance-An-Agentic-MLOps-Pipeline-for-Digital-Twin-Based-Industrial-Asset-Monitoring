"""Real hosted Supabase verification, excluded from ordinary CI."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import psycopg
import pytest
from storage3.exceptions import StorageApiError

from predictive_maintenance.cloud.config import Phase2Settings
from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.models import CloudFoundationError, ObjectIdentity
from predictive_maintenance.cloud.object_store import SupabaseObjectRepository
from predictive_maintenance.cloud.publication import (
    build_publication,
    publish_snapshot,
    reconcile_snapshot,
)
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.pipeline import (
    materialize_pipeline,
    prepare_pipeline_artifacts,
)
from supabase import create_client

EXPECTED_SNAPSHOT_ID = (
    "17d1db8dd823266b58b9c8d5b6da8edace17220980b733188756cd6b630e453d"
)
APPROVAL_PHRASE = "I_CONFIRM_THIS_IS_THE_APPROVED_PHASE_2_TEST_PROJECT"
PHASE_3_APPROVAL_PHRASE = "I_CONFIRM_PHASE_3_DERIVED_WRITES_ARE_APPROVED"

pytestmark = [pytest.mark.integration, pytest.mark.cloud]


def _require_explicit_cloud_approval() -> Phase2Settings:
    if os.environ.get("PM_CLOUD_TEST_APPROVAL") != APPROVAL_PHRASE:
        pytest.skip("Explicit Phase 2 hosted Supabase approval is required.")
    settings = Phase2Settings.from_env()
    if settings.app_env != "cloud":
        pytest.fail("APP_ENV=cloud is required for hosted verification.")
    return settings


def _require_phase_3_cloud_approval() -> Phase2Settings:
    if os.environ.get("PM_PHASE_3_CLOUD_TEST_APPROVAL") != PHASE_3_APPROVAL_PHRASE:
        pytest.skip("Explicit Phase 3 hosted derived-write approval is required.")
    settings = Phase2Settings.from_env()
    if settings.app_env != "cloud":
        pytest.fail("APP_ENV=cloud is required for hosted verification.")
    return settings


def _list_all_keys(bucket: Any, prefix: str = "") -> tuple[str, ...]:
    keys: list[str] = []
    pending = [prefix]
    while pending:
        current = pending.pop()
        rows = bucket.list(
            current,
            {
                "limit": 1000,
                "offset": 0,
                "sortBy": {"column": "name", "order": "asc"},
            },
        )
        for row in rows:
            name = str(row["name"])
            child = f"{current}/{name}" if current else name
            if row.get("metadata") is None:
                pending.append(child)
            else:
                keys.append(child)
    return tuple(sorted(keys))


def test_approved_cloud_foundation_and_actual_fd001(tmp_path: Path) -> None:
    settings = _require_explicit_cloud_approval()
    source = Path("Data")
    if not all(
        (source / name).is_file()
        for name in (
            "train_FD001.txt",
            "test_FD001.txt",
            "RUL_FD001.txt",
            "readme.txt",
        )
    ):
        pytest.fail("Owner-provided FD001 files are required for cloud verification.")

    client = create_client(
        settings.supabase_url.reveal(),
        settings.supabase_secret_key.reveal(),
    )
    objects = SupabaseObjectRepository(client)
    metadata = PostgresMetadataRepository(settings.postgres_dsn.reveal())

    with psycopg.connect(settings.postgres_dsn.reveal()) as connection:
        migration_rows = connection.execute(
            """
            select version
            from supabase_migrations.schema_migrations
            order by version
            """
        ).fetchall()
        assert [str(row[0]) for row in migration_rows] == ["20260726144446"]
        existing_snapshots = connection.execute(
            "select snapshot_id from ops.dataset_snapshots"
        ).fetchall()
        assert {str(row[0]) for row in existing_snapshots} <= {EXPECTED_SNAPSHOT_ID}

    existing_buckets = {bucket.id: bucket for bucket in client.storage.list_buckets()}
    raw_existing = existing_buckets.get(settings.raw_bucket)
    if raw_existing is not None:
        assert raw_existing.public is False
        existing_raw_keys = _list_all_keys(client.storage.from_(settings.raw_bucket))
        assert all(
            key.startswith(f"fd001/{EXPECTED_SNAPSHOT_ID}/")
            for key in existing_raw_keys
        )
    derived_existing = existing_buckets.get(settings.derived_bucket)
    if derived_existing is not None:
        assert derived_existing.public is False
        assert _list_all_keys(client.storage.from_(settings.derived_bucket)) == ()

    objects.ensure_private_buckets(settings.raw_bucket, settings.derived_bucket)
    bucket_states = {
        bucket.id: bucket.public for bucket in client.storage.list_buckets()
    }
    assert bucket_states[settings.raw_bucket] is False
    assert bucket_states[settings.derived_bucket] is False

    ingestion = ingest_fd001(
        source,
        tmp_path / "raw",
        code_revision="phase-2-cloud-verification",
    )
    first = publish_snapshot(
        ingestion.snapshot,
        settings.raw_bucket,
        objects,
        metadata,
    )
    second = publish_snapshot(
        ingestion.snapshot,
        settings.raw_bucket,
        objects,
        metadata,
    )
    assert first.snapshot_id == EXPECTED_SNAPSHOT_ID
    assert first.state == "available"
    assert first.object_count == 5
    assert second.reused is True
    assert reconcile_snapshot(first.snapshot_id, objects, metadata).consistent

    stored = metadata.get_snapshot(first.snapshot_id)
    assert stored is not None
    target = stored.identities[1]
    conflict_source = tmp_path / "different.txt"
    conflict_source.write_bytes(b"different bytes")
    conflict = ObjectIdentity(
        bucket_name=target.bucket_name,
        object_key=target.object_key,
        zone="raw",
        sha256=hashlib.sha256(b"different bytes").hexdigest(),
        byte_size=len(b"different bytes"),
        content_type=target.content_type,
    )
    with pytest.raises(CloudFoundationError, match=r"object\.identity_conflict"):
        objects.put_verified(conflict_source, conflict)
    assert objects.read(target.bucket_name, target.object_key)


def test_approved_cloud_derived_integration_cleanup(tmp_path: Path) -> None:
    settings = _require_explicit_cloud_approval()
    client = create_client(
        settings.supabase_url.reveal(),
        settings.supabase_secret_key.reveal(),
    )
    objects = SupabaseObjectRepository(client)
    objects.ensure_private_buckets(settings.raw_bucket, settings.derived_bucket)
    payload = b"phase-2-cloud-integration"
    key = f"_integration/{hashlib.sha256(os.urandom(32)).hexdigest()}/probe.bin"
    source = tmp_path / "probe.bin"
    source.write_bytes(payload)
    identity = ObjectIdentity(
        bucket_name=settings.derived_bucket,
        object_key=key,
        zone="derived",
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        content_type="application/octet-stream",
    )
    try:
        assert objects.put_verified(source, identity).reused is False
        assert objects.read(settings.derived_bucket, key) == payload
        with pytest.raises(StorageApiError):
            client.storage.from_(settings.derived_bucket).upload(
                key,
                b"different",
                {"content-type": "application/octet-stream", "upsert": "false"},
            )
    finally:
        client.storage.from_(settings.derived_bucket).remove([key])
    assert key not in _list_all_keys(client.storage.from_(settings.derived_bucket))


def test_approved_phase_3_actual_derived_storage(tmp_path: Path) -> None:
    settings = _require_phase_3_cloud_approval()
    source = Path("Data")
    required = (
        "train_FD001.txt",
        "test_FD001.txt",
        "RUL_FD001.txt",
        "readme.txt",
    )
    if not all((source / filename).is_file() for filename in required):
        pytest.fail("Owner-provided FD001 files are required for cloud verification.")

    client = create_client(
        settings.supabase_url.reveal(),
        settings.supabase_secret_key.reveal(),
    )
    objects = SupabaseObjectRepository(client)
    objects.ensure_private_buckets(settings.raw_bucket, settings.derived_bucket)
    bucket_states = {
        bucket.id: bucket.public for bucket in client.storage.list_buckets()
    }
    assert bucket_states[settings.derived_bucket] is False

    ingestion = ingest_fd001(
        source,
        tmp_path / "raw",
        code_revision="phase-3-cloud-verification",
    )
    assert ingestion.snapshot.manifest.snapshot_id == EXPECTED_SNAPSHOT_ID
    raw_publication = build_publication(ingestion.snapshot, settings.raw_bucket)
    raw_files = {item.logical_filename: item.identity for item in raw_publication.files}
    materialized = materialize_pipeline(
        ingestion,
        code_revision="phase3-cloud-verification",
        workspace=tmp_path / "derived",
    )
    prepared = prepare_pipeline_artifacts(
        materialized,
        raw_files,
        settings.derived_bucket,
    )

    first_results = [
        objects.put_verified(item.path, item.identity)
        for artifact in prepared
        for item in artifact.objects
    ]
    second_results = [
        objects.put_verified(item.path, item.identity)
        for artifact in prepared
        for item in artifact.objects
    ]
    assert len(first_results) == 10
    assert all(result.reused for result in second_results)
    for artifact in prepared:
        for item in artifact.objects:
            payload = objects.read(
                item.identity.bucket_name,
                item.identity.object_key,
            )
            assert len(payload) == item.identity.byte_size
            assert hashlib.sha256(payload).hexdigest() == item.identity.sha256
