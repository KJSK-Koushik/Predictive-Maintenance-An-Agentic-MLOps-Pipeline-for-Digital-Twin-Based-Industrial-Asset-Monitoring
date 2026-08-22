"""Strict API, readiness, OpenAPI, and parity contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from phase6_support import SyntheticRelease

from predictive_maintenance.release.models import ReleaseError
from predictive_maintenance.serving.app import create_app
from predictive_maintenance.serving.config import ServingSettings
from predictive_maintenance.serving.predictor import ReleasePredictor

pytestmark = pytest.mark.api


def _client(release: SyntheticRelease) -> TestClient:
    return TestClient(
        create_app(ServingSettings(release.bundle, release.manifest.release_id))
    )


def test_health_release_prediction_and_openapi(
    synthetic_release: SyntheticRelease,
) -> None:
    with _client(synthetic_release) as client:
        assert client.get("/health/live").json() == {
            "status": "live",
            "release_id": None,
        }
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["release_id"] == synthetic_release.manifest.release_id
        release = client.get("/v1/release").json()
        assert release["predictive_uncertainty_status"] == "not_available"
        response = client.post(
            "/v1/predict", json={"observations": synthetic_release.observations}
        )
        assert response.status_code == 200
        item = response.json()["predictions"][0]
        assert item["rul_cycles"] == synthetic_release.expected_core[0]["rul_cycles"]
        assert (
            item["failure_risk_probability"]
            == synthetic_release.expected_core[0]["failure_risk_probability"]
        )
        assert item["release_id"] == synthetic_release.manifest.release_id
        assert item["risk_horizon_cycles"] == 30
        assert item["risk_threshold"] == 0.5
        assert item["predictive_uncertainty_status"] == "not_available"
        openapi = client.get("/openapi.json").json()
        assert set(openapi["paths"]) == {
            "/health/live",
            "/health/ready",
            "/v1/release",
            "/v1/predict",
        }
        assert openapi["info"]["version"] == "1.0.0"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"observations": []},
        {"observations": [{"engine_id": 1, "cycle": 1}]},
        {"observations": [{"engine_id": True, "cycle": 1}]},
        {"observations": [{"engine_id": 0, "cycle": 1}]},
        {"observations": [], "extra": 1},
    ],
)
def test_invalid_requests_are_stable(
    synthetic_release: SyntheticRelease, payload: object
) -> None:
    with _client(synthetic_release) as client:
        response = client.post("/v1/predict", json=payload)
        assert response.status_code == 422
        assert response.json() == {
            "error": {
                "code": "request.validation_failed",
                "message": "Request does not match fd001-inference-v1.",
            }
        }


def test_batch_limit_extra_feature_and_content_type(
    synthetic_release: SyntheticRelease,
) -> None:
    observation = synthetic_release.observations[0]
    with _client(synthetic_release) as client:
        assert (
            client.post(
                "/v1/predict", json={"observations": [observation] * 128}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/predict", json={"observations": [observation] * 129}
            ).status_code
            == 422
        )
        extra = {**observation, "rul": 12}
        assert (
            client.post("/v1/predict", json={"observations": [extra]}).status_code
            == 422
        )
        wrong_type = client.post(
            "/v1/predict", content=b"{}", headers={"content-type": "text/plain"}
        )
        assert wrong_type.status_code == 415


def test_corrupt_bundle_is_live_but_not_ready(
    synthetic_release: SyntheticRelease,
) -> None:
    (synthetic_release.bundle / "risk" / "model.skops").write_bytes(b"corrupt")
    with _client(synthetic_release) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert (
            client.post(
                "/v1/predict", json={"observations": synthetic_release.observations}
            ).status_code
            == 503
        )


def test_production_configuration_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match=r"serving\.production_disabled"):
        ServingSettings(tmp_path, "a" * 64, app_env="production")


def test_environment_configuration_and_missing_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PM_RELEASE_DIR", raising=False)
    monkeypatch.delenv("PM_RELEASE_ID", raising=False)
    with pytest.raises(ReleaseError, match=r"serving\.missing_release_dir"):
        ServingSettings.from_env()
    monkeypatch.setenv("PM_RELEASE_DIR", str(tmp_path))
    monkeypatch.setenv("PM_RELEASE_ID", "a" * 64)
    monkeypatch.setenv("APP_ENV", "staging")
    assert ServingSettings.from_env() == ServingSettings(tmp_path, "a" * 64)


def test_request_size_headers_and_unready_release_endpoint(
    synthetic_release: SyntheticRelease,
) -> None:
    (synthetic_release.bundle / "risk" / "model.skops").write_bytes(b"corrupt")
    with _client(synthetic_release) as client:
        invalid = client.post(
            "/v1/predict",
            content=b"{}",
            headers={"content-type": "application/json", "content-length": "bad"},
        )
        assert invalid.status_code == 400
        oversized = client.post(
            "/v1/predict",
            content=b"{}",
            headers={"content-type": "application/json", "content-length": "999999"},
        )
        assert oversized.status_code == 413
        assert client.get("/v1/release").status_code == 503


def test_predictor_rejects_empty_nonfinite_and_bad_model_outputs(
    synthetic_release: SyntheticRelease,
) -> None:
    predictor = ReleasePredictor(
        synthetic_release.bundle,
        expected_release_id=synthetic_release.manifest.release_id,
    )
    with pytest.raises(ReleaseError, match=r"serving\.invalid_features"):
        predictor._frame([])
    bad = dict(synthetic_release.observations[0])
    bad["sensor_1"] = float("inf")
    with pytest.raises(ReleaseError, match=r"serving\.invalid_features"):
        predictor._frame([bad])

    class _BadRegression:
        def predict(self, _: object) -> np.ndarray[Any, Any]:
            return np.array([float("nan")])

    predictor._regression = _BadRegression()
    with pytest.raises(ReleaseError, match=r"serving\.invalid_model_output"):
        predictor._predict_core(synthetic_release.observations)
