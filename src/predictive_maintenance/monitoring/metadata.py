"""Private PostgreSQL adapter for Phase 7 monitoring governance."""

from __future__ import annotations

from datetime import datetime
from typing import cast

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import Jsonb

from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringReport,
    MonitoringWindow,
    ReferenceProfile,
)
from predictive_maintenance.monitoring.triggers import CandidateRequest, Investigation
from predictive_maintenance.retraining.evaluation import ChallengerEvaluation

_RUNTIME_ROLE = "predictive_maintenance_runtime"


class PostgresMonitoringRepository:
    """Write immutable monitoring records through the restricted runtime role."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise MonitoringError(
                "metadata.missing_dsn", "A PostgreSQL DSN is required."
            )
        self._dsn = dsn

    def __repr__(self) -> str:
        return "PostgresMonitoringRepository(dsn=***)"

    def _connect(self) -> Connection[DictRow]:
        try:
            return psycopg.connect(
                self._dsn,
                connect_timeout=10,
                application_name="predictive-maintenance-phase-7",
                row_factory=dict_row,
            )
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.connection_failed", "Monitoring metadata connection failed."
            ) from error

    @staticmethod
    def _assume_role(connection: Connection[DictRow]) -> None:
        connection.execute(f"set local role {_RUNTIME_ROLE}")

    @staticmethod
    def _object_id(
        connection: Connection[DictRow],
        identity: ObjectIdentity,
        verified_at: datetime,
    ) -> int:
        connection.execute(
            """
            insert into ops.data_objects (
                bucket_name, object_key, zone, sha256, byte_size,
                content_type, verification_state, verified_at
            ) values (%s, %s, %s, %s, %s, %s, 'verified', %s)
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
            from ops.data_objects where bucket_name = %s and object_key = %s
            """,
            (identity.bucket_name, identity.object_key),
        ).fetchone()
        if row is None or (
            row["zone"],
            row["sha256"],
            row["byte_size"],
            row["content_type"],
        ) != (
            identity.zone,
            identity.sha256,
            identity.byte_size,
            identity.content_type,
        ):
            raise MonitoringError(
                "metadata.object_conflict",
                "Report object metadata is missing or conflicts.",
            )
        return cast(int, row["object_id"])

    def record_reference(
        self,
        reference: ReferenceProfile,
        object_identity: ObjectIdentity,
        *,
        verified_at: datetime,
    ) -> None:
        """Insert or exactly reuse one reference and its verified object."""
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                object_id = self._object_id(connection, object_identity, verified_at)
                connection.execute(
                    """
                    insert into ops.monitoring_references (
                        reference_id, release_id, feature_snapshot_id, policy_id,
                        reference_contract_version, profile_sha256, profile_object_id,
                        row_count, engine_count, sampled_row_count
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (reference_id) do nothing
                    """,
                    (
                        reference.reference_id,
                        reference.release_id,
                        reference.feature_snapshot_id,
                        reference.policy_id,
                        reference.reference_contract_version,
                        object_identity.sha256,
                        object_id,
                        reference.row_count,
                        reference.engine_count,
                        reference.sampled_row_count,
                    ),
                )
                row = connection.execute(
                    """
                    select release_id, policy_id, profile_sha256, profile_object_id
                    from ops.monitoring_references where reference_id = %s
                    """,
                    (reference.reference_id,),
                ).fetchone()
                expected = (
                    reference.release_id,
                    reference.policy_id,
                    object_identity.sha256,
                    object_id,
                )
                if row is None or tuple(row.values()) != expected:
                    raise MonitoringError(
                        "metadata.reference_conflict",
                        "Reference identity already has different evidence.",
                    )
        except MonitoringError:
            raise
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.reference_write_failed", "Reference metadata write failed."
            ) from error

    def record_window(self, window: MonitoringWindow) -> None:
        """Insert or exactly reuse one immutable monitoring window."""
        values = (
            window.window_id,
            window.release_id,
            window.reference_id,
            window.policy_id,
            window.feature_snapshot_id,
            window.source_partition,
            window.membership_sha256,
            window.row_count,
            window.engine_count,
            window.replay_sequence,
            window.window_contract_version,
        )
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                connection.execute(
                    """
                    insert into ops.monitoring_windows (
                        window_id, release_id, reference_id, policy_id,
                        feature_snapshot_id, source_partition, membership_sha256,
                        row_count, engine_count, replay_sequence,
                        window_contract_version
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (window_id) do nothing
                    """,
                    values,
                )
                row = connection.execute(
                    """
                    select window_id, release_id, reference_id, policy_id,
                           feature_snapshot_id, source_partition, membership_sha256,
                           row_count, engine_count, replay_sequence,
                           window_contract_version
                    from ops.monitoring_windows where window_id = %s
                    """,
                    (window.window_id,),
                ).fetchone()
                if row is None or tuple(row.values()) != values:
                    raise MonitoringError(
                        "metadata.window_conflict",
                        "Window identity already has different evidence.",
                    )
        except MonitoringError:
            raise
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.window_write_failed", "Window metadata write failed."
            ) from error

    def record_report(
        self,
        report: MonitoringReport,
        object_identity: ObjectIdentity,
        *,
        verified_at: datetime,
    ) -> None:
        """Insert or exactly reuse one immutable report."""
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                object_id = self._object_id(connection, object_identity, verified_at)
                connection.execute(
                    """
                    insert into ops.monitoring_reports (
                        report_id, window_id, parent_report_id, label_snapshot_id,
                        report_contract_version, report_sha256, report_object_id,
                        data_quality_status, feature_shift_status,
                        prediction_shift_status, service_status, performance_status
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (report_id) do nothing
                    """,
                    (
                        report.report_id,
                        report.window.window_id,
                        report.parent_report_id,
                        report.label_snapshot_id,
                        report.report_contract_version,
                        object_identity.sha256,
                        object_id,
                        report.data_quality.status,
                        report.feature_shift.status,
                        report.prediction_shift.status,
                        report.service_health.status,
                        report.delayed_performance.status,
                    ),
                )
                row = connection.execute(
                    """
                    select window_id, report_sha256, report_object_id
                    from ops.monitoring_reports where report_id = %s
                    """,
                    (report.report_id,),
                ).fetchone()
                if row is None or tuple(row.values()) != (
                    report.window.window_id,
                    object_identity.sha256,
                    object_id,
                ):
                    raise MonitoringError(
                        "metadata.report_conflict",
                        "Report identity already has different evidence.",
                    )
        except MonitoringError:
            raise
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.report_write_failed", "Report metadata write failed."
            ) from error

    def record_investigation(self, investigation: Investigation) -> None:
        """Insert or exactly reuse one append-only investigation."""
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                connection.execute(
                    """
                    insert into ops.monitoring_alerts (
                        alert_id, report_id, category, reason_codes
                    ) values (%s, %s, %s, %s)
                    on conflict (alert_id) do nothing
                    """,
                    (
                        investigation.investigation_id,
                        investigation.report_id,
                        investigation.category,
                        Jsonb(investigation.reason_codes),
                    ),
                )
                row = connection.execute(
                    """
                    select report_id, category, reason_codes
                    from ops.monitoring_alerts where alert_id = %s
                    """,
                    (investigation.investigation_id,),
                ).fetchone()
                if row is None or tuple(row.values()) != (
                    investigation.report_id,
                    investigation.category,
                    list(investigation.reason_codes),
                ):
                    raise MonitoringError(
                        "metadata.alert_conflict",
                        "Investigation identity already has different evidence.",
                    )
        except MonitoringError:
            raise
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.alert_write_failed", "Investigation metadata write failed."
            ) from error

    def record_candidate_request(self, request: CandidateRequest) -> None:
        """Insert or exactly reuse an evaluation-only candidate request."""
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                connection.execute(
                    """
                    insert into ops.retraining_candidate_requests (
                        request_id, release_id, policy_id, requested_task,
                        data_cutoff_window_id, evidence_report_ids, reason,
                        authority, trigger_contract_version
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (request_id) do nothing
                    """,
                    (
                        request.request_id,
                        request.release_id,
                        request.policy_id,
                        request.requested_task,
                        request.data_cutoff_window_id,
                        Jsonb(request.evidence_report_ids),
                        request.reason,
                        request.authority,
                        request.trigger_contract_version,
                    ),
                )
                row = connection.execute(
                    """
                    select release_id, policy_id, requested_task,
                           data_cutoff_window_id, evidence_report_ids, reason,
                           authority, trigger_contract_version
                    from ops.retraining_candidate_requests where request_id = %s
                    """,
                    (request.request_id,),
                ).fetchone()
                if row is None or tuple(row.values()) != (
                    request.release_id,
                    request.policy_id,
                    request.requested_task,
                    request.data_cutoff_window_id,
                    list(request.evidence_report_ids),
                    request.reason,
                    request.authority,
                    request.trigger_contract_version,
                ):
                    raise MonitoringError(
                        "metadata.request_conflict",
                        "Candidate request identity already has different evidence.",
                    )
        except MonitoringError:
            raise
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.request_write_failed", "Candidate request write failed."
            ) from error

    def record_evaluation(
        self,
        evaluation: ChallengerEvaluation,
        object_identity: ObjectIdentity,
        *,
        verified_at: datetime,
    ) -> None:
        """Insert one immutable evaluation with explicit zero promotion authority."""
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                object_id = self._object_id(connection, object_identity, verified_at)
                connection.execute(
                    """
                    insert into ops.challenger_evaluations (
                        evaluation_id, request_id, champion_release_id,
                        challenger_artifact_sha256, outcome, checks_json,
                        evaluation_sha256, evaluation_object_id, source_partition,
                        promotion_authority, evaluation_contract_version
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (evaluation_id) do nothing
                    """,
                    (
                        evaluation.evaluation_id,
                        evaluation.request_id,
                        evaluation.champion_release_id,
                        evaluation.challenger_artifact_sha256,
                        evaluation.outcome,
                        Jsonb(evaluation.checks),
                        object_identity.sha256,
                        object_id,
                        evaluation.source_partition,
                        evaluation.promotion_authority,
                        evaluation.evaluation_contract_version,
                    ),
                )
                row = connection.execute(
                    """
                    select request_id, champion_release_id,
                           challenger_artifact_sha256, outcome, checks_json,
                           evaluation_sha256, evaluation_object_id,
                           source_partition, promotion_authority,
                           evaluation_contract_version
                    from ops.challenger_evaluations where evaluation_id = %s
                    """,
                    (evaluation.evaluation_id,),
                ).fetchone()
                if row is None or tuple(row.values()) != (
                    evaluation.request_id,
                    evaluation.champion_release_id,
                    evaluation.challenger_artifact_sha256,
                    evaluation.outcome,
                    evaluation.checks,
                    object_identity.sha256,
                    object_id,
                    evaluation.source_partition,
                    evaluation.promotion_authority,
                    evaluation.evaluation_contract_version,
                ):
                    raise MonitoringError(
                        "metadata.evaluation_conflict",
                        "Evaluation identity already has different evidence.",
                    )
        except MonitoringError:
            raise
        except psycopg.Error as error:
            raise MonitoringError(
                "metadata.evaluation_write_failed", "Evaluation metadata write failed."
            ) from error
