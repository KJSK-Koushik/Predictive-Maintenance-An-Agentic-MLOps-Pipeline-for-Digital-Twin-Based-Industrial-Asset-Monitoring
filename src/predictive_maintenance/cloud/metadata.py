"""Transactional PostgreSQL metadata repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    ObjectIdentity,
    SnapshotPublication,
    StoredSnapshot,
)

_RUNTIME_ROLE = "predictive_maintenance_runtime"


class MetadataRepository(Protocol):
    """Minimal metadata operations used by publication and reconciliation."""

    def begin_run(self, snapshot_id: str, started_at: datetime) -> None:
        """Create or restart one idempotent publication run."""

    def get_snapshot(self, snapshot_id: str) -> StoredSnapshot | None:
        """Return the authoritative snapshot and object identities."""

    def commit_publication(self, publication: SnapshotPublication) -> StoredSnapshot:
        """Atomically commit all verified object and lineage metadata."""

    def record_failure(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        """Record a sanitized failed publication attempt."""

    def mark_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        """Block downstream use after a referenced object inconsistency."""


class PostgresMetadataRepository:
    """Direct PostgreSQL adapter that immediately assumes a restricted role."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise CloudFoundationError(
                "config.missing_postgres_dsn",
                "A direct PostgreSQL DSN is required.",
            )
        self._dsn = dsn

    def __repr__(self) -> str:
        return "PostgresMetadataRepository(dsn=***)"

    def _connect(self) -> Connection[DictRow]:
        try:
            return psycopg.connect(
                self._dsn,
                row_factory=dict_row,
                connect_timeout=10,
                application_name="predictive-maintenance-phase-2",
            )
        except psycopg.Error as error:
            raise CloudFoundationError(
                "metadata.connection_failed",
                "The operational PostgreSQL connection failed.",
            ) from error

    @staticmethod
    def _assume_runtime_role(connection: Connection[DictRow]) -> None:
        connection.execute(f"set local role {_RUNTIME_ROLE}")

    def begin_run(self, snapshot_id: str, started_at: datetime) -> None:
        """Create one run or safely restart a non-available attempt."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                connection.execute(
                    """
                    insert into ops.ingestion_runs (
                        run_id,
                        idempotency_key,
                        state,
                        started_at
                    )
                    values (%s, %s, 'started', %s)
                    on conflict (idempotency_key) do update
                    set state = 'started',
                        started_at = excluded.started_at,
                        finished_at = null,
                        error_code = null,
                        error_detail = null
                    where ops.ingestion_runs.state <> 'available'
                    """,
                    (uuid.uuid4(), snapshot_id, started_at),
                )
        except psycopg.Error as error:
            raise CloudFoundationError(
                "metadata.begin_run_failed",
                "The publication run could not be opened.",
            ) from error

    @staticmethod
    def _identity_from_row(row: DictRow) -> ObjectIdentity:
        return ObjectIdentity(
            bucket_name=cast(str, row["bucket_name"]),
            object_key=cast(str, row["object_key"]),
            zone=cast(Any, row["zone"]),
            sha256=cast(str, row["sha256"]),
            byte_size=cast(int, row["byte_size"]),
            content_type=cast(str, row["content_type"]),
        )

    def _snapshot_objects(
        self,
        connection: Connection[DictRow],
        snapshot_id: str,
    ) -> tuple[ObjectIdentity, ...]:
        rows = connection.execute(
            """
            select
                object_id,
                bucket_name,
                object_key,
                zone,
                sha256,
                byte_size,
                content_type,
                sort_order
            from (
                select
                    o.object_id,
                    o.bucket_name,
                    o.object_key,
                    o.zone,
                    o.sha256,
                    o.byte_size,
                    o.content_type,
                    0 as sort_order
                from ops.dataset_snapshots s
                join ops.data_objects o
                    on o.object_id = s.manifest_object_id
                where s.snapshot_id = %s
                union all
                select
                    o.object_id,
                    o.bucket_name,
                    o.object_key,
                    o.zone,
                    o.sha256,
                    o.byte_size,
                    o.content_type,
                    f.file_position as sort_order
                from ops.snapshot_files f
                join ops.data_objects o on o.object_id = f.object_id
                where f.snapshot_id = %s
            ) as snapshot_objects
            order by sort_order
            """,
            (snapshot_id, snapshot_id),
        ).fetchall()
        return tuple(self._identity_from_row(row) for row in rows)

    def _get_snapshot(
        self,
        connection: Connection[DictRow],
        snapshot_id: str,
    ) -> StoredSnapshot | None:
        row = connection.execute(
            """
            select
                snapshot_id,
                state,
                manifest_sha256,
                required_file_count
            from ops.dataset_snapshots
            where snapshot_id = %s
            """,
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredSnapshot(
            snapshot_id=cast(str, row["snapshot_id"]),
            state=cast(Any, row["state"]),
            manifest_sha256=cast(str, row["manifest_sha256"]),
            required_file_count=cast(int, row["required_file_count"]),
            identities=self._snapshot_objects(connection, snapshot_id),
        )

    def get_snapshot(self, snapshot_id: str) -> StoredSnapshot | None:
        """Read one snapshot under the restricted runtime role."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                return self._get_snapshot(connection, snapshot_id)
        except psycopg.Error as error:
            raise CloudFoundationError(
                "metadata.read_failed",
                "Operational metadata could not be read.",
            ) from error

    @staticmethod
    def _object_id(
        connection: Connection[DictRow],
        identity: ObjectIdentity,
        verified_at: datetime,
    ) -> int:
        connection.execute(
            """
            insert into ops.data_objects (
                bucket_name,
                object_key,
                zone,
                sha256,
                byte_size,
                content_type,
                verification_state,
                verified_at
            )
            values (%s, %s, %s, %s, %s, %s, 'verified', %s)
            on conflict (bucket_name, object_key) do nothing
            """,
            (
                identity.bucket_name,
                identity.object_key,
                identity.zone,
                identity.sha256,
                identity.byte_size,
                identity.content_type,
                verified_at,
            ),
        )
        row = connection.execute(
            """
            select object_id, zone, sha256, byte_size, content_type
            from ops.data_objects
            where bucket_name = %s and object_key = %s
            """,
            (identity.bucket_name, identity.object_key),
        ).fetchone()
        if row is None:
            raise CloudFoundationError(
                "metadata.object_missing_after_insert",
                "Object metadata was not visible after insertion.",
            )
        if (
            row["zone"] != identity.zone
            or row["sha256"] != identity.sha256
            or row["byte_size"] != identity.byte_size
            or row["content_type"] != identity.content_type
        ):
            raise CloudFoundationError(
                "metadata.object_conflict",
                "An existing object key has different metadata.",
            )
        return cast(int, row["object_id"])

    @staticmethod
    def _matches(
        current: StoredSnapshot,
        publication: SnapshotPublication,
    ) -> bool:
        return (
            current.state == "available"
            and current.manifest_sha256 == publication.manifest.sha256
            and current.required_file_count == len(publication.files)
            and current.identities == publication.identities
        )

    def commit_publication(self, publication: SnapshotPublication) -> StoredSnapshot:
        """Commit verified object, snapshot, file, lineage, and run metadata."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                connection.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (publication.snapshot_id,),
                )
                current = self._get_snapshot(connection, publication.snapshot_id)
                if current is not None:
                    if self._matches(current, publication):
                        return current
                    raise CloudFoundationError(
                        "metadata.snapshot_conflict",
                        "The snapshot ID already has different metadata or state.",
                    )

                object_ids = {
                    identity: self._object_id(
                        connection,
                        identity,
                        publication.verified_at,
                    )
                    for identity in publication.identities
                }
                manifest_id = object_ids[publication.manifest]
                connection.execute(
                    """
                    insert into ops.dataset_snapshots (
                        snapshot_id,
                        dataset_family,
                        dataset_subset,
                        contract_version,
                        parser_version,
                        code_revision,
                        manifest_sha256,
                        manifest_object_id,
                        required_file_count,
                        state,
                        created_at,
                        updated_at
                    )
                    values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'available', %s, %s
                    )
                    """,
                    (
                        publication.snapshot_id,
                        publication.dataset_family,
                        publication.dataset_subset,
                        publication.contract_version,
                        publication.parser_version,
                        publication.code_revision,
                        publication.manifest.sha256,
                        manifest_id,
                        len(publication.files),
                        publication.verified_at,
                        publication.verified_at,
                    ),
                )
                for item in publication.files:
                    object_id = object_ids[item.identity]
                    connection.execute(
                        """
                        insert into ops.snapshot_files (
                            snapshot_id,
                            logical_filename,
                            file_position,
                            object_id
                        )
                        values (%s, %s, %s, %s)
                        """,
                        (
                            publication.snapshot_id,
                            item.logical_filename,
                            item.file_position,
                            object_id,
                        ),
                    )
                    connection.execute(
                        """
                        insert into ops.lineage_edges (
                            parent_object_id,
                            child_object_id,
                            relationship_type
                        )
                        values (%s, %s, 'documented_by_manifest')
                        """,
                        (manifest_id, object_id),
                    )
                connection.execute(
                    """
                    update ops.ingestion_runs
                    set state = 'available',
                        finished_at = %s,
                        error_code = null,
                        error_detail = null
                    where idempotency_key = %s
                    """,
                    (publication.verified_at, publication.snapshot_id),
                )
                stored = self._get_snapshot(connection, publication.snapshot_id)
                if stored is None:
                    raise CloudFoundationError(
                        "metadata.snapshot_missing_after_commit",
                        "Snapshot metadata was not visible before commit.",
                    )
                return stored
        except CloudFoundationError:
            raise
        except psycopg.Error as error:
            raise CloudFoundationError(
                "metadata.commit_failed",
                "The verified metadata transaction failed.",
            ) from error

    def record_failure(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        """Record a bounded error without leaking database details."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                connection.execute(
                    """
                    update ops.ingestion_runs
                    set state = 'failed',
                        finished_at = %s,
                        error_code = %s,
                        error_detail = %s
                    where idempotency_key = %s
                      and state <> 'available'
                    """,
                    (
                        finished_at,
                        error_code,
                        error_detail[:1000],
                        snapshot_id,
                    ),
                )
        except psycopg.Error as error:
            raise CloudFoundationError(
                "metadata.failure_record_failed",
                "The sanitized failure could not be recorded.",
            ) from error

    def mark_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        """Change an available snapshot to fail-closed inconsistent state."""
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=UTC)
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                snapshot = connection.execute(
                    """
                    update ops.dataset_snapshots
                    set state = 'inconsistent', updated_at = %s
                    where snapshot_id = %s
                    returning snapshot_id
                    """,
                    (detected_at, snapshot_id),
                ).fetchone()
                if snapshot is None:
                    raise CloudFoundationError(
                        "metadata.snapshot_not_found",
                        "Cannot mark an unknown snapshot inconsistent.",
                    )
                connection.execute(
                    """
                    update ops.ingestion_runs
                    set state = 'inconsistent',
                        finished_at = %s,
                        error_code = %s,
                        error_detail = %s
                    where idempotency_key = %s
                    """,
                    (
                        detected_at,
                        error_code,
                        error_detail[:1000],
                        snapshot_id,
                    ),
                )
        except CloudFoundationError:
            raise
        except psycopg.Error as error:
            raise CloudFoundationError(
                "metadata.inconsistent_update_failed",
                "The snapshot could not be marked inconsistent.",
            ) from error
