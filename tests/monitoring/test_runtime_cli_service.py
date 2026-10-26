"""Direct runtime, CLI, and bounded loopback-probe tests."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, cast

import pytest
from phase7_support import identity, prediction_frame, telemetry_frame

from predictive_maintenance.monitoring.cli import main
from predictive_maintenance.monitoring.models import MonitoringError, MonitoringPolicy
from predictive_maintenance.monitoring.runtime import (
    build_reference_file,
    load_policy,
    run_monitoring_files,
)
from predictive_maintenance.monitoring.service import probe_loopback_service


def test_runtime_builds_and_reuses_exact_files(tmp_path: Path) -> None:
    frame = telemetry_frame()
    feature_path = tmp_path / "features.parquet"
    current_path = tmp_path / "current.parquet"
    reference_predictions_path = tmp_path / "reference-predictions.parquet"
    frame.to_parquet(feature_path, index=False)
    prediction_frame(frame).to_parquet(current_path, index=False)
    prediction_frame(frame).to_parquet(reference_predictions_path, index=False)
    policy = MonitoringPolicy()
    reference_path = build_reference_file(
        feature_path,
        tmp_path / "references",
        release_id=identity("release"),
        feature_snapshot_id=identity("reference-feature"),
        policy=policy,
        code_revision="phase7-test",
        dependency_lock_sha256=identity("lock"),
    )
    kwargs: dict[str, Any] = {
        "policy": policy,
        "raw_snapshot_id": identity("raw"),
        "processed_snapshot_id": identity("processed"),
        "feature_snapshot_id": identity("current-feature"),
        "source_partition": "synthetic",
        "replay_sequence": 1,
        "code_revision": "phase7-test",
        "dependency_lock_sha256": identity("lock"),
    }
    first, path, reused = run_monitoring_files(
        feature_path,
        current_path,
        reference_predictions_path,
        reference_path,
        tmp_path / "reports",
        **kwargs,
    )
    second, repeated_path, repeated = run_monitoring_files(
        feature_path,
        current_path,
        reference_predictions_path,
        reference_path,
        tmp_path / "reports",
        **kwargs,
    )
    assert not reused
    assert repeated
    assert first.report_id == second.report_id
    assert path == repeated_path
    assert path.read_bytes() == first.canonical_bytes()
    path.write_bytes(b"conflict")
    with pytest.raises(MonitoringError, match=r"runtime\.report_conflict"):
        run_monitoring_files(
            feature_path,
            current_path,
            reference_predictions_path,
            reference_path,
            tmp_path / "reports",
            **kwargs,
        )


def test_policy_loading_is_strict(tmp_path: Path) -> None:
    assert load_policy(None) == MonitoringPolicy()
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"minimum_rows": 10}), encoding="utf-8")
    assert load_policy(path).minimum_rows == 10
    path.write_text(json.dumps({"unknown": True}), encoding="utf-8")
    with pytest.raises(MonitoringError, match=r"runtime\.invalid_policy"):
        load_policy(path)


def test_cli_reports_bounded_success_and_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frame = telemetry_frame()
    features = tmp_path / "features.parquet"
    frame.to_parquet(features, index=False)
    result = main(
        [
            "build-reference",
            "--features",
            str(features),
            "--output-dir",
            str(tmp_path / "reference"),
            "--release-id",
            identity("release"),
            "--feature-snapshot-id",
            identity("feature"),
            "--code-revision",
            "phase7-test",
            "--dependency-lock-sha256",
            identity("lock"),
        ]
    )
    assert result == 0
    assert json.loads(capsys.readouterr().out)["status"] == "created_or_reused"
    missing = main(
        [
            "build-reference",
            "--features",
            str(tmp_path / "missing.parquet"),
            "--output-dir",
            str(tmp_path / "reference"),
            "--release-id",
            identity("release"),
            "--feature-snapshot-id",
            identity("feature"),
            "--code-revision",
            "phase7-test",
            "--dependency-lock-sha256",
            identity("lock"),
        ]
    )
    assert missing == 2
    assert (
        json.loads(capsys.readouterr().out)["error"]["code"]
        == "runtime.invalid_parquet"
    )


def test_loopback_probe_validates_release_and_prediction_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = telemetry_frame().iloc[:2]
    predictions = prediction_frame(frame)
    prediction_records = cast(
        list[dict[str, Any]], predictions.to_dict(orient="records")
    )
    release_id = identity("release")
    responses = iter(
        [
            (
                200,
                json.dumps({"status": "ready", "release_id": release_id}).encode(),
                1.0,
            ),
            (
                200,
                json.dumps(
                    {
                        "contract_version": "fd001-inference-v1",
                        "predictions": [
                            {
                                "engine_id": int(row["engine_id"]),
                                "cycle": int(row["cycle"]),
                                "rul_cycles": float(row["rul_cycles"]),
                                "failure_risk_probability": float(
                                    row["failure_risk_probability"]
                                ),
                                "failure_risk_label": int(row["failure_risk_label"]),
                                "risk_horizon_cycles": 30,
                                "risk_threshold": 0.5,
                                "release_id": release_id,
                                "regression_model": {
                                    "registered_name": "fd001-rul-regression",
                                    "version": "1",
                                    "source_run_id": "run-r",
                                    "artifact_sha256": identity("r"),
                                },
                                "classification_model": {
                                    "registered_name": (
                                        "fd001-failure-risk-classification"
                                    ),
                                    "version": "1",
                                    "source_run_id": "run-c",
                                    "artifact_sha256": identity("c"),
                                },
                                "predictive_uncertainty_status": "not_available",
                            }
                            for row in prediction_records
                        ],
                    }
                ).encode(),
                2.0,
            ),
        ]
    )

    def fake_request(
        _: urllib.request.Request, *, timeout_seconds: float
    ) -> tuple[int, bytes, float]:
        assert timeout_seconds == 10.0
        return next(responses)

    monkeypatch.setattr(
        "predictive_maintenance.monitoring.service._request_json", fake_request
    )
    result = probe_loopback_service(
        frame, base_url="http://127.0.0.1:18000", expected_release_id=release_id
    )
    assert result.readiness
    assert result.status_codes == (200, 200)
    assert result.predictions.equals(predictions)


def test_probe_rejects_non_loopback_and_wrong_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(MonitoringError, match=r"service\.non_loopback_target"):
        probe_loopback_service(
            telemetry_frame().iloc[:1],
            base_url="https://example.com",
            expected_release_id=identity("release"),
        )
    monkeypatch.setattr(
        "predictive_maintenance.monitoring.service._request_json",
        lambda request, timeout_seconds: (
            200,
            json.dumps(
                {"status": "ready", "release_id": identity("different")}
            ).encode(),
            1.0,
        ),
    )
    result = probe_loopback_service(
        telemetry_frame().iloc[:1],
        base_url="http://localhost:18000",
        expected_release_id=identity("release"),
    )
    assert not result.readiness
    assert result.predictions.empty


def test_probe_rejects_invalid_readiness_and_prediction_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            (200, b"{}", 1.0),
        ]
    )
    monkeypatch.setattr(
        "predictive_maintenance.monitoring.service._request_json",
        lambda request, timeout_seconds: next(responses),
    )
    with pytest.raises(MonitoringError, match=r"service\.invalid_readiness"):
        probe_loopback_service(
            telemetry_frame().iloc[:1],
            base_url="http://127.0.0.1:18000",
            expected_release_id=identity("release"),
        )

    release_id = identity("release")
    responses = iter(
        [
            (
                200,
                json.dumps({"status": "ready", "release_id": release_id}).encode(),
                1.0,
            ),
            (200, b"{}", 2.0),
        ]
    )
    with pytest.raises(MonitoringError, match=r"service\.invalid_prediction"):
        probe_loopback_service(
            telemetry_frame().iloc[:1],
            base_url="http://127.0.0.1:18000",
            expected_release_id=release_id,
        )
