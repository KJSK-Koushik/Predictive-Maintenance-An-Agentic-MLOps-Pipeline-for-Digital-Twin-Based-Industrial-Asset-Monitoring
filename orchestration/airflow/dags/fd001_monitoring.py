"""Thin manual orchestration for one immutable FD001 replay window."""

from __future__ import annotations

import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import pendulum
from airflow.exceptions import AirflowException
from airflow.sdk import dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ROOT = Path("/opt/airflow/artifacts/monitoring").resolve()
_RESULT_KEYS = {"report_id", "reused", "window_id"}


def _safe_path(value: object) -> Path:
    path = Path(str(value)).resolve()
    if path != _SAFE_ROOT and _SAFE_ROOT not in path.parents:
        raise AirflowFailException("Monitoring paths must remain in the shared root.")
    return path


def _sha256_param(value: object, name: str) -> str:
    text = str(value)
    if not _SHA256.fullmatch(text):
        raise AirflowFailException(f"{name} must be a lowercase SHA-256 digest.")
    return text


def _validated_result(value: dict[str, Any]) -> dict[str, str | bool]:
    if set(value) != _RESULT_KEYS:
        raise ValueError("Monitoring returned an unexpected XCom contract.")
    for key in ("report_id", "window_id"):
        if not isinstance(value[key], str) or not _SHA256.fullmatch(value[key]):
            raise ValueError("Monitoring returned an invalid identifier.")
    if not isinstance(value["reused"], bool):
        raise ValueError("Monitoring returned an invalid reuse state.")
    return value


@dag(
    dag_id="fd001_monitoring_replay",
    description="Manual static FD001 cycle replay; not live or real-time monitoring.",
    schedule=None,
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
        "features_path": "",
        "current_predictions_path": "",
        "reference_predictions_path": "",
        "reference_path": "",
        "output_dir": "/opt/airflow/artifacts/monitoring/reports",
        "raw_snapshot_id": "",
        "processed_snapshot_id": "",
        "feature_snapshot_id": "",
        "source_partition": "synthetic",
        "replay_sequence": 1,
        "dependency_lock_sha256": "",
        "inject_retryable_failure": False,
    },
    tags=["fd001", "batch-replay", "phase-7", "manual"],
)
def fd001_monitoring_replay() -> None:
    """Execute application logic while exchanging only bounded identifiers."""

    @task(execution_timeout=timedelta(minutes=5))
    def validate_request() -> dict[str, Any]:
        context = get_current_context()
        params = dict(context["params"])
        for name in (
            "features_path",
            "current_predictions_path",
            "reference_predictions_path",
            "reference_path",
            "output_dir",
        ):
            params[name] = str(_safe_path(params[name]))
        for name in (
            "raw_snapshot_id",
            "processed_snapshot_id",
            "feature_snapshot_id",
            "dependency_lock_sha256",
        ):
            params[name] = _sha256_param(params[name], name)
        if params["source_partition"] not in {
            "train",
            "validation",
            "test",
            "synthetic",
        }:
            raise AirflowFailException("source_partition is invalid.")
        if (
            not isinstance(params["replay_sequence"], int)
            or params["replay_sequence"] < 1
        ):
            raise AirflowFailException("replay_sequence must be a positive integer.")
        return params

    @task(execution_timeout=timedelta(minutes=20))
    def monitor_window(request: dict[str, Any]) -> dict[str, str | bool]:
        from predictive_maintenance.monitoring.runtime import (
            load_policy,
            run_monitoring_files,
        )

        report, _, reused = run_monitoring_files(
            Path(request["features_path"]),
            Path(request["current_predictions_path"]),
            Path(request["reference_predictions_path"]),
            Path(request["reference_path"]),
            Path(request["output_dir"]),
            policy=load_policy(None),
            raw_snapshot_id=request["raw_snapshot_id"],
            processed_snapshot_id=request["processed_snapshot_id"],
            feature_snapshot_id=request["feature_snapshot_id"],
            source_partition=request["source_partition"],
            replay_sequence=request["replay_sequence"],
            code_revision=os.environ.get("PM_CODE_REVISION", "phase7-local"),
            dependency_lock_sha256=request["dependency_lock_sha256"],
        )
        result = _validated_result(
            {
                "report_id": report.report_id,
                "reused": reused,
                "window_id": report.window.window_id,
            }
        )
        context = get_current_context()
        if bool(request["inject_retryable_failure"]) and context["ti"].try_number == 1:
            raise AirflowException(
                "Controlled retryable failure after exact report publication."
            )
        return result

    monitor_window(validate_request())


fd001_monitoring_replay()
