"""Smoke and parity checks against the loopback Compose inference service."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from predictive_maintenance.serving.predictor import ReleasePredictor

pytestmark = [pytest.mark.integration, pytest.mark.deployment]


def _release_dir() -> Path:
    value = os.environ.get("PM_CONTAINER_RELEASE_DIR", "")
    if not value:
        pytest.skip("PM_CONTAINER_RELEASE_DIR is required for container smoke tests.")
    return Path(value)


def test_container_is_ready_has_exact_contract_and_matches_direct_model() -> None:
    bundle = _release_dir()
    predictor = ReleasePredictor(bundle)
    fixture = json.loads((bundle / "verification-fixture.json").read_bytes())
    observations = fixture["observations"]
    expected = predictor.predict(observations)
    base = "http://127.0.0.1:18000"
    with httpx.Client(base_url=base, timeout=10) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["release_id"] == predictor.manifest.release_id
        assert client.get("/openapi.json").status_code == 200
        response = client.post("/v1/predict", json={"observations": observations})
        assert response.status_code == 200
        assert response.json()["predictions"] == expected
        invalid = client.post("/v1/predict", content=b"{}")
        assert invalid.status_code == 415
