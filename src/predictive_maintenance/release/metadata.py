"""Private PostgreSQL adapter for append-only release governance evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

import psycopg
from psycopg.types.json import Jsonb

from predictive_maintenance.release.models import (
    ApprovalDecision,
    ReleaseError,
    ReleaseManifest,
    sha256_bytes,
)

_RUNTIME_ROLE = "predictive_maintenance_runtime"


@dataclass(frozen=True, slots=True)
class DeploymentEvent:
    """One append-only staging deployment or rollback event."""

    release_id: str
    event_type: Literal[
        "deploy_started",
        "deploy_succeeded",
        "deploy_failed",
        "rollback_started",
        "rollback_succeeded",
        "rollback_failed",
    ]
    actor: str
    reason: str
    evidence_sha256: str
    occurred_at: datetime
    previous_release_id: str | None = None
    environment: str = "staging"


class PostgresReleaseRepository:
    """Record release governance through the existing restricted runtime role."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ReleaseError("metadata.missing_dsn", "A PostgreSQL DSN is required.")
        self._dsn = dsn

    def __repr__(self) -> str:
        return "PostgresReleaseRepository(dsn=***)"

    def _connect(self) -> psycopg.Connection[tuple[object, ...]]:
        try:
            return psycopg.connect(
                self._dsn,
                connect_timeout=10,
                application_name="predictive-maintenance-phase-6",
            )
        except psycopg.Error as error:
            raise ReleaseError(
                "metadata.connection_failed", "Release metadata connection failed."
            ) from error

    @staticmethod
    def _assume_role(connection: psycopg.Connection[tuple[object, ...]]) -> None:
        connection.execute(f"set local role {_RUNTIME_ROLE}")

    def record_candidate(self, manifest: ReleaseManifest) -> None:
        """Insert an immutable candidate or accept an exact existing row."""
        payload = manifest.to_dict()
        manifest_sha256 = sha256_bytes(manifest.canonical_bytes())
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                connection.execute(
                    """
                    insert into ops.model_releases (
                        release_id, approval_request_id,
                        release_contract_version, manifest_sha256, manifest_json,
                        feature_snapshot_id,
                        regression_registered_name, regression_model_version,
                        regression_source_run_id,
                        classification_registered_name,
                        classification_model_version,
                        classification_source_run_id, previous_release_id
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    on conflict (release_id) do nothing
                    """,
                    (
                        manifest.release_id,
                        manifest.approval_request_id,
                        manifest.release_contract_version,
                        manifest_sha256,
                        Jsonb(payload),
                        manifest.feature_snapshot_id,
                        manifest.regression.registered_name,
                        int(manifest.regression.version),
                        manifest.regression.source_run_id,
                        manifest.classification.registered_name,
                        int(manifest.classification.version),
                        manifest.classification.source_run_id,
                        manifest.previous_release_id,
                    ),
                )
                row = connection.execute(
                    """
                    select approval_request_id, manifest_sha256
                    from ops.model_releases where release_id = %s
                    """,
                    (manifest.release_id,),
                ).fetchone()
                if row != (manifest.approval_request_id, manifest_sha256):
                    raise ReleaseError(
                        "metadata.candidate_conflict",
                        "The release ID already has different candidate evidence.",
                    )
        except ReleaseError:
            raise
        except psycopg.Error as error:
            raise ReleaseError(
                "metadata.candidate_write_failed", "Candidate metadata write failed."
            ) from error

    def record_decision(self, decision: ApprovalDecision) -> None:
        """Insert one decision idempotently and reject conflicting decisions."""
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                connection.execute(
                    """
                    insert into ops.release_decisions (
                        approval_request_id, release_id, decision, actor, reason,
                        evidence_sha256, decided_at, expires_at
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (approval_request_id) do nothing
                    """,
                    (
                        decision.approval_request_id,
                        decision.release_id,
                        decision.decision,
                        decision.actor,
                        decision.reason,
                        decision.evidence_sha256,
                        decision.decided_at,
                        decision.expires_at,
                    ),
                )
                row = connection.execute(
                    """
                    select release_id, decision, actor, reason, evidence_sha256,
                           decided_at, expires_at
                    from ops.release_decisions where approval_request_id = %s
                    """,
                    (decision.approval_request_id,),
                ).fetchone()
                expected = (
                    decision.release_id,
                    decision.decision,
                    decision.actor,
                    decision.reason,
                    decision.evidence_sha256,
                    decision.decided_at,
                    decision.expires_at,
                )
                if row != expected:
                    raise ReleaseError(
                        "metadata.decision_conflict",
                        "The approval request already has a different decision.",
                    )
        except ReleaseError:
            raise
        except psycopg.Error as error:
            raise ReleaseError(
                "metadata.decision_write_failed", "Decision metadata write failed."
            ) from error

    def record_deployment_event(self, event: DeploymentEvent) -> int:
        """Append one staging event and return its database identity."""
        if event.environment != "staging":
            raise ReleaseError(
                "deployment.production_disabled", "Only staging is configured."
            )
        try:
            with self._connect() as connection:
                self._assume_role(connection)
                row = connection.execute(
                    """
                    insert into ops.deployment_events (
                        release_id, previous_release_id, environment, event_type,
                        actor, reason, evidence_sha256, occurred_at
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning deployment_event_id
                    """,
                    (
                        event.release_id,
                        event.previous_release_id,
                        event.environment,
                        event.event_type,
                        event.actor,
                        event.reason,
                        event.evidence_sha256,
                        event.occurred_at,
                    ),
                ).fetchone()
                if row is None:
                    raise ReleaseError(
                        "metadata.deployment_write_failed",
                        "Deployment event was not returned.",
                    )
                return cast(int, row[0])
        except ReleaseError:
            raise
        except psycopg.Error as error:
            raise ReleaseError(
                "metadata.deployment_write_failed", "Deployment event write failed."
            ) from error
