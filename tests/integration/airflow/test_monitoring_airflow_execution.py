"""Runtime parity and retry evidence for the thin Phase 7 monitoring DAG."""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

import pytest
from phase7_support import identity, prediction_frame, telemetry_frame

from predictive_maintenance.monitoring.models import MonitoringPolicy
from predictive_maintenance.monitoring.runtime import (
    build_reference_file,
    run_monitoring_files,
)

ROOT = Path(__file__).resolve().parents[3]
pytestmark = [pytest.mark.integration, pytest.mark.airflow]


def _airflow(*arguments: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", "compose", "exec", "-T", "airflow", "airflow", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        pytest.fail(
            "Phase 7 Airflow command failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def test_monitoring_dag_matches_direct_identity_and_reuses_after_retry() -> None:
    namespace = f"airflow-integration/{uuid.uuid4().hex}"
    host_root = ROOT / "artifacts/monitoring" / namespace
    container_root = Path("/opt/airflow/artifacts/monitoring") / namespace
    host_root.mkdir(parents=True)
    frame = telemetry_frame()
    predictions = prediction_frame(frame)
    feature_path = host_root / "features.parquet"
    current_path = host_root / "current-predictions.parquet"
    reference_predictions_path = host_root / "reference-predictions.parquet"
    frame.to_parquet(feature_path, index=False)
    predictions.to_parquet(current_path, index=False)
    predictions.to_parquet(reference_predictions_path, index=False)
    policy = MonitoringPolicy()
    reference_path = build_reference_file(
        feature_path,
        host_root / "references",
        release_id=identity("airflow-release"),
        feature_snapshot_id=identity("airflow-reference-feature"),
        policy=policy,
        code_revision="phase3-local",
        dependency_lock_sha256=identity("airflow-lock"),
    )
    direct, _, reused = run_monitoring_files(
        feature_path,
        current_path,
        reference_predictions_path,
        reference_path,
        host_root / "reports",
        policy=policy,
        raw_snapshot_id=identity("airflow-raw"),
        processed_snapshot_id=identity("airflow-processed"),
        feature_snapshot_id=identity("airflow-current-feature"),
        source_partition="synthetic",
        replay_sequence=1,
        code_revision="phase3-local",
        dependency_lock_sha256=identity("airflow-lock"),
    )
    assert not reused
    conf = {
        "features_path": str(container_root / "features.parquet"),
        "current_predictions_path": str(container_root / "current-predictions.parquet"),
        "reference_predictions_path": str(
            container_root / "reference-predictions.parquet"
        ),
        "reference_path": str(
            container_root / "references" / f"{direct.reference_id}.json"
        ),
        "output_dir": str(container_root / "reports"),
        "raw_snapshot_id": identity("airflow-raw"),
        "processed_snapshot_id": identity("airflow-processed"),
        "feature_snapshot_id": identity("airflow-current-feature"),
        "source_partition": "synthetic",
        "replay_sequence": 1,
        "dependency_lock_sha256": identity("airflow-lock"),
        "inject_retryable_failure": True,
    }
    _airflow(
        "dags",
        "test",
        "fd001_monitoring_replay",
        "2026-09-07T00:00:00+00:00",
        "--use-executor",
        "--conf",
        json.dumps(conf),
    )
    reports = sorted((host_root / "reports").glob("*.json"))
    assert reports == [host_root / "reports" / f"{direct.report_id}.json"]
    assert reports[0].read_bytes() == direct.canonical_bytes()
