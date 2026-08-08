"""Thin orchestration for the deterministic FD001 derived pipeline."""

from __future__ import annotations

import os
import re
from datetime import timedelta
from typing import Any

import pendulum
from airflow.exceptions import AirflowException
from airflow.sdk import dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RESULT_KEYS = {
    "feature_snapshot_id",
    "processed_snapshot_id",
    "quality_snapshot_id",
    "reused",
    "source_snapshot_id",
}


def _revision() -> str:
    return os.environ.get("PM_CODE_REVISION", "phase3-local").strip()


def _validated_result(value: dict[str, Any]) -> dict[str, str | bool]:
    if set(value) != _RESULT_KEYS:
        raise ValueError("The pipeline returned an unexpected XCom contract.")
    for key in _RESULT_KEYS - {"reused"}:
        if not isinstance(value[key], str) or not _SHA256.fullmatch(value[key]):
            raise ValueError("The pipeline returned an invalid snapshot identifier.")
    if not isinstance(value["reused"], bool):
        raise ValueError("The pipeline returned an invalid reuse status.")
    return value


@dag(
    dag_id="fd001_derived_pipeline",
    description="Static FD001 batch ETL; not real-time ingestion.",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(seconds=10),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=2),
    },
    params={
        "source_snapshot_id": os.environ.get("PM_SOURCE_SNAPSHOT_ID", "").strip(),
        "inject_retryable_failure": False,
    },
    tags=["fd001", "batch", "phase-3"],
)
def fd001_derived_pipeline() -> None:
    """Schedule tested application code while exchanging identifiers only."""

    @task(execution_timeout=timedelta(minutes=5))
    def validate_source() -> str:
        context = get_current_context()
        source_id = str(context["params"]["source_snapshot_id"])
        if not _SHA256.fullmatch(source_id):
            raise AirflowFailException(
                "source_snapshot_id must be a lowercase SHA-256 digest."
            )
        return source_id

    @task(execution_timeout=timedelta(minutes=20))
    def publish_processed(source_snapshot_id: str) -> dict[str, str | bool]:
        from predictive_maintenance.etl.runtime import run_from_environment

        context = get_current_context()
        result = run_from_environment(
            source_snapshot_id,
            code_revision=_revision(),
        )
        validated = _validated_result(result.to_dict())
        if (
            bool(context["params"]["inject_retryable_failure"])
            and context["ti"].try_number == 1
        ):
            raise AirflowException(
                "Controlled retryable Phase 3 failure after verified publication."
            )
        return validated

    @task(execution_timeout=timedelta(minutes=5))
    def publish_candidate_features(
        result: dict[str, Any],
    ) -> dict[str, str | bool]:
        return _validated_result(result)

    @task(execution_timeout=timedelta(minutes=5))
    def verify_quality_and_lineage(
        result: dict[str, Any],
    ) -> dict[str, str | bool]:
        return _validated_result(result)

    source_id = validate_source()
    processed = publish_processed(source_id)
    features = publish_candidate_features(processed)
    verify_quality_and_lineage(features)


fd001_derived_pipeline()
