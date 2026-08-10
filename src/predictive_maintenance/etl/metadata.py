"""Transactional PostgreSQL repository for Phase 3 derived metadata."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.etl.models import (
    DerivedBatchPublication,
    DerivedSnapshotPublication,
    EtlError,
    StoredDerivedSnapshot,
)

_RUNTIME_ROLE = "predictive_maintenance_runtime"


class DerivedMetadataRepository(Protocol):
    """Minimal derived metadata operations used by the Phase 3 pipeline."""

    def begin_transformation(self, publication: DerivedBatchPublication) -> None:
        """Open or safely restart one idempotent transformation run."""

    def get_derived_snapshot(self, snapshot_id: str) -> StoredDerivedSnapshot | None:
        """Return one authoritative derived snapshot and its objects."""

    def commit_derived_batch(self, publication: DerivedBatchPublication) -> bool:
        """Commit all artifact, lineage, and completed-run metadata atomically."""

    def record_transformation_failure(
        self,
        idempotency_key: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        """Record a bounded pre-availability failure."""

    def mark_derived_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        """Block a derived snapshot and its completed transformation run."""


class PostgresDerivedMetadataRepository:
    """Direct PostgreSQL adapter that immediately assumes the restricted role."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise EtlError(
                "config.missing_postgres_dsn",
                "A direct PostgreSQL DSN is required for derived metadata.",
            )
        self._dsn = dsn

    def __repr__(self) -> str:
        return "PostgresDerivedMetadataRepository(dsn=***)"

    def _connect(self) -> Connection[DictRow]:
        try:
            return psycopg.connect(
                self._dsn,
                row_factory=dict_row,
                connect_timeout=10,
                application_name="predictive-maintenance-phase-3",
            )
        except psycopg.Error as error:
            raise EtlError(
                "metadata.connection_failed",
                "The operational PostgreSQL connection failed.",
            ) from error

    @staticmethod
    def _assume_runtime_role(connection: Connection[DictRow]) -> None:
        connection.execute(f"set local role {_RUNTIME_ROLE}")

    @staticmethod
    def _identity(row: DictRow) -> ObjectIdentity:
        return ObjectIdentity(
            bucket_name=cast(str, row["bucket_name"]),
            object_key=cast(str, row["object_key"]),
            zone=cast(Any, row["zone"]),
            sha256=cast(str, row["sha256"]),
            byte_size=cast(int, row["byte_size"]),
            content_type=cast(str, row["content_type"]),
        )

    def begin_transformation(self, publication: DerivedBatchPublication) -> None:
        """Create one run or restart a failed/started attempt."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                connection.execute(
                    """
                    insert into ops.transformation_runs (
                        run_id,
                        idempotency_key,
                        source_snapshot_id,
                        pipeline_version,
                        code_revision,
                        state,
                        started_at
                    )
                    values (%s, %s, %s, %s, %s, 'started', %s)
                    on conflict (idempotency_key) do update
                    set state = 'started',
                        started_at = excluded.started_at,
                        finished_at = null,
                        error_code = null,
                        error_detail = null
                    where ops.transformation_runs.state <> 'available'
                    """,
                    (
                        uuid.uuid4(),
                        publication.idempotency_key,
                        publication.source_snapshot_id,
                        publication.pipeline_version,
                        publication.code_revision,
                        publication.verified_at,
                    ),
                )
        except psycopg.Error as error:
            raise EtlError(
                "metadata.begin_transformation_failed",
                "The transformation run could not be opened.",
            ) from error

    def _snapshot_objects(
        self,
        connection: Connection[DictRow],
        snapshot_id: str,
    ) -> tuple[ObjectIdentity, ...]:
        rows = connection.execute(
            """
            select bucket_name, object_key, zone, sha256, byte_size, content_type
            from (
                select o.*, 0 as sort_order
                from ops.derived_snapshots s
                join ops.data_objects o on o.object_id = s.manifest_object_id
                where s.derived_snapshot_id = %s
                union all
                select o.*, f.file_position as sort_order
                from ops.derived_snapshot_files f
                join ops.data_objects o on o.object_id = f.object_id
                where f.derived_snapshot_id = %s
            ) as derived_objects
            order by sort_order
            """,
            (snapshot_id, snapshot_id),
        ).fetchall()
        return tuple(self._identity(row) for row in rows)

    def _get_derived_snapshot(
        self,
        connection: Connection[DictRow],
        snapshot_id: str,
    ) -> StoredDerivedSnapshot | None:
        row = connection.execute(
            """
            select
                derived_snapshot_id,
                source_snapshot_id,
                parent_derived_snapshot_id,
                artifact_kind,
                contract_version,
                state,
                manifest_sha256
            from ops.derived_snapshots
            where derived_snapshot_id = %s
            """,
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredDerivedSnapshot(
            derived_snapshot_id=cast(str, row["derived_snapshot_id"]),
            source_snapshot_id=cast(str, row["source_snapshot_id"]),
            parent_derived_snapshot_id=cast(
                str | None, row["parent_derived_snapshot_id"]
            ),
            artifact_kind=cast(Any, row["artifact_kind"]),
            contract_version=cast(str, row["contract_version"]),
            state=cast(Any, row["state"]),
            manifest_sha256=cast(str, row["manifest_sha256"]),
            identities=self._snapshot_objects(connection, snapshot_id),
        )

    def get_derived_snapshot(self, snapshot_id: str) -> StoredDerivedSnapshot | None:
        """Read one derived snapshot under the runtime role."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                return self._get_derived_snapshot(connection, snapshot_id)
        except psycopg.Error as error:
            raise EtlError(
                "metadata.derived_read_failed",
                "Derived metadata could not be read.",
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
            raise EtlError(
                "metadata.object_missing_after_insert",
                "Derived object metadata was not visible after insertion.",
            )
        if (
            row["zone"] != identity.zone
            or row["sha256"] != identity.sha256
            or row["byte_size"] != identity.byte_size
            or row["content_type"] != identity.content_type
        ):
            raise EtlError(
                "metadata.object_conflict",
                "An existing object key has different metadata.",
            )
        return cast(int, row["object_id"])

    @staticmethod
    def _existing_object_id(
        connection: Connection[DictRow], identity: ObjectIdentity
    ) -> int:
        row = connection.execute(
            """
            select object_id, zone, sha256, byte_size, content_type
            from ops.data_objects
            where bucket_name = %s and object_key = %s
            """,
            (identity.bucket_name, identity.object_key),
        ).fetchone()
        if row is None or (
            row["zone"] != identity.zone
            or row["sha256"] != identity.sha256
            or row["byte_size"] != identity.byte_size
            or row["content_type"] != identity.content_type
        ):
            raise EtlError(
                "metadata.lineage_parent_invalid",
                "A declared lineage parent is absent or has conflicting metadata.",
            )
        return cast(int, row["object_id"])

    @staticmethod
    def _matches(
        current: StoredDerivedSnapshot,
        publication: DerivedSnapshotPublication,
    ) -> bool:
        return (
            current.state == "available"
            and current.source_snapshot_id == publication.source_snapshot_id
            and current.parent_derived_snapshot_id
            == publication.parent_derived_snapshot_id
            and current.artifact_kind == publication.artifact_kind
            and current.contract_version == publication.contract_version
            and current.manifest_sha256 == publication.manifest.sha256
            and current.identities == publication.identities
        )

    def _commit_artifact(
        self,
        connection: Connection[DictRow],
        publication: DerivedSnapshotPublication,
        verified_at: datetime,
    ) -> bool:
        current = self._get_derived_snapshot(
            connection, publication.derived_snapshot_id
        )
        if current is not None:
            if self._matches(current, publication):
                return True
            raise EtlError(
                "metadata.derived_snapshot_conflict",
                "The derived snapshot ID already has different metadata or state.",
            )
        object_ids = {
            identity: self._object_id(connection, identity, verified_at)
            for identity in publication.identities
        }
        manifest_id = object_ids[publication.manifest]
        connection.execute(
            """
            insert into ops.derived_snapshots (
                derived_snapshot_id,
                source_snapshot_id,
                parent_derived_snapshot_id,
                artifact_kind,
                contract_version,
                transformation_version,
                serializer_version,
                code_revision,
                manifest_sha256,
                manifest_object_id,
                required_file_count,
                state,
                created_at,
                updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'available', %s, %s)
            """,
            (
                publication.derived_snapshot_id,
                publication.source_snapshot_id,
                publication.parent_derived_snapshot_id,
                publication.artifact_kind,
                publication.contract_version,
                publication.transformation_version,
                publication.serializer_version,
                publication.code_revision,
                publication.manifest.sha256,
                manifest_id,
                len(publication.files),
                verified_at,
                verified_at,
            ),
        )
        for item in publication.files:
            child_id = object_ids[item.identity]
            connection.execute(
                """
                insert into ops.derived_snapshot_files (
                    derived_snapshot_id,
                    logical_filename,
                    file_position,
                    object_id,
                    schema_json,
                    column_roles
                )
                values (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    publication.derived_snapshot_id,
                    item.logical_filename,
                    item.file_position,
                    child_id,
                    json.dumps(item.schema, sort_keys=True),
                    json.dumps(item.column_roles, sort_keys=True),
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
                (manifest_id, child_id),
            )
            for parent in item.parents:
                parent_id = self._existing_object_id(connection, parent)
                connection.execute(
                    """
                    insert into ops.lineage_edges (
                        parent_object_id,
                        child_object_id,
                        relationship_type
                    )
                    values (%s, %s, %s)
                    on conflict do nothing
                    """,
                    (parent_id, child_id, item.relationship_type),
                )
        return False

    def commit_derived_batch(self, publication: DerivedBatchPublication) -> bool:
        """Commit all artifacts and complete the run in one transaction."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                connection.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (publication.idempotency_key,),
                )
                reused = [
                    self._commit_artifact(connection, artifact, publication.verified_at)
                    for artifact in publication.artifacts
                ]
                by_kind = {
                    item.artifact_kind: item.derived_snapshot_id
                    for item in publication.artifacts
                }
                connection.execute(
                    """
                    update ops.transformation_runs
                    set state = 'available',
                        processed_snapshot_id = %s,
                        feature_snapshot_id = %s,
                        quality_snapshot_id = %s,
                        finished_at = %s,
                        error_code = null,
                        error_detail = null
                    where idempotency_key = %s
                    """,
                    (
                        by_kind["processed"],
                        by_kind["feature"],
                        by_kind["quality_report"],
                        publication.verified_at,
                        publication.idempotency_key,
                    ),
                )
                return all(reused)
        except EtlError:
            raise
        except psycopg.Error as error:
            raise EtlError(
                "metadata.derived_commit_failed",
                "The verified derived metadata transaction failed.",
            ) from error

    def record_transformation_failure(
        self,
        idempotency_key: str,
        error_code: str,
        error_detail: str,
        finished_at: datetime,
    ) -> None:
        """Record a sanitized failure without changing an available run."""
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                connection.execute(
                    """
                    update ops.transformation_runs
                    set state = 'failed',
                        finished_at = %s,
                        error_code = %s,
                        error_detail = %s
                    where idempotency_key = %s and state <> 'available'
                    """,
                    (finished_at, error_code, error_detail[:1000], idempotency_key),
                )
        except psycopg.Error as error:
            raise EtlError(
                "metadata.transformation_failure_record_failed",
                "The sanitized transformation failure could not be recorded.",
            ) from error

    def mark_derived_inconsistent(
        self,
        snapshot_id: str,
        error_code: str,
        error_detail: str,
        detected_at: datetime,
    ) -> None:
        """Block one available derived snapshot and its completed run."""
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=UTC)
        try:
            with self._connect() as connection:
                self._assume_runtime_role(connection)
                row = connection.execute(
                    """
                    update ops.derived_snapshots
                    set state = 'inconsistent', updated_at = %s
                    where derived_snapshot_id = %s and state = 'available'
                    returning derived_snapshot_id
                    """,
                    (detected_at, snapshot_id),
                ).fetchone()
                if row is None:
                    raise EtlError(
                        "metadata.derived_not_available",
                        "The derived snapshot is unknown or already inconsistent.",
                    )
                connection.execute(
                    """
                    update ops.transformation_runs
                    set state = 'inconsistent',
                        finished_at = %s,
                        error_code = %s,
                        error_detail = %s
                    where state = 'available'
                      and %s in (
                          processed_snapshot_id,
                          feature_snapshot_id,
                          quality_snapshot_id
                      )
                    """,
                    (detected_at, error_code, error_detail[:1000], snapshot_id),
                )
        except EtlError:
            raise
        except psycopg.Error as error:
            raise EtlError(
                "metadata.derived_inconsistent_update_failed",
                "The derived snapshot could not be marked inconsistent.",
            ) from error
