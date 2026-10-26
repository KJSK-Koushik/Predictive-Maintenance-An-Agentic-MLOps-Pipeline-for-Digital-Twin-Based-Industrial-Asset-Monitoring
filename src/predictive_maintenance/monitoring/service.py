"""Bounded loopback inference probes for monitored replay windows."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import pandas as pd
from pydantic import ValidationError

from predictive_maintenance.monitoring.models import MonitoringError
from predictive_maintenance.release.models import FEATURE_COLUMNS
from predictive_maintenance.serving.contracts import (
    HealthResponse,
    PredictionResponse,
)

MAX_BATCH_ROWS = 128


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Aligned predictions plus bounded service evidence."""

    predictions: pd.DataFrame
    readiness: bool
    status_codes: tuple[int, ...]
    latencies_ms: tuple[float, ...]

    @property
    def service_evidence(self) -> dict[str, Any]:
        """Return input for the separated service-health signal."""
        return {
            "readiness": self.readiness,
            "status_codes": self.status_codes,
            "latencies_ms": self.latencies_ms,
        }


def _loopback_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise MonitoringError(
            "service.non_loopback_target",
            "Phase 7 probes require a plain HTTP loopback origin.",
        )
    return value.rstrip("/")


def _request_json(
    request: urllib.request.Request, *, timeout_seconds: float
) -> tuple[int, bytes, float]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read(1_000_001)
            status = response.status
    except urllib.error.HTTPError as error:
        payload = error.read(1_000_001)
        status = error.code
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise MonitoringError(
            "service.probe_unavailable", "Loopback inference probe was unavailable."
        ) from error
    latency = (time.perf_counter() - started) * 1000.0
    if len(payload) > 1_000_000:
        raise MonitoringError(
            "service.response_too_large", "Loopback response exceeded one megabyte."
        )
    return status, payload, latency


def probe_loopback_service(
    frame: pd.DataFrame,
    *,
    base_url: str,
    expected_release_id: str,
    timeout_seconds: float = 10.0,
) -> ProbeResult:
    """Probe readiness and predict in bounded batches against one exact release."""
    origin = _loopback_origin(base_url)
    status_codes: list[int] = []
    latencies: list[float] = []
    ready_request = urllib.request.Request(f"{origin}/health/ready", method="GET")
    status, payload, latency = _request_json(
        ready_request, timeout_seconds=timeout_seconds
    )
    status_codes.append(status)
    latencies.append(latency)
    readiness = False
    if status == 200:
        try:
            health = HealthResponse.model_validate_json(payload)
        except ValidationError as error:
            raise MonitoringError(
                "service.invalid_readiness", "Readiness response contract is invalid."
            ) from error
        readiness = (
            health.status == "ready" and health.release_id == expected_release_id
        )
    if not readiness:
        return ProbeResult(
            pd.DataFrame(
                columns=[
                    "engine_id",
                    "cycle",
                    "rul_cycles",
                    "failure_risk_probability",
                    "failure_risk_label",
                ]
            ),
            False,
            tuple(status_codes),
            tuple(latencies),
        )

    observations = frame.loc[:, ["engine_id", "cycle", *FEATURE_COLUMNS]].to_dict(
        orient="records"
    )
    predictions: list[dict[str, Any]] = []
    for start in range(0, len(observations), MAX_BATCH_ROWS):
        request_payload = json.dumps(
            {"observations": observations[start : start + MAX_BATCH_ROWS]},
            allow_nan=False,
            separators=(",", ":"),
        ).encode("ascii")
        request = urllib.request.Request(
            f"{origin}/v1/predict",
            data=request_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        status, payload, latency = _request_json(
            request, timeout_seconds=timeout_seconds
        )
        status_codes.append(status)
        latencies.append(latency)
        if status != 200:
            continue
        try:
            response = PredictionResponse.model_validate_json(payload)
        except ValidationError as error:
            raise MonitoringError(
                "service.invalid_prediction", "Prediction response contract is invalid."
            ) from error
        for item in response.predictions:
            if item.release_id != expected_release_id:
                raise MonitoringError(
                    "service.release_mismatch", "Prediction used a different release."
                )
            predictions.append(
                {
                    "engine_id": item.engine_id,
                    "cycle": item.cycle,
                    "rul_cycles": item.rul_cycles,
                    "failure_risk_probability": item.failure_risk_probability,
                    "failure_risk_label": item.failure_risk_label,
                }
            )
    prediction_frame = pd.DataFrame(
        predictions,
        columns=[
            "engine_id",
            "cycle",
            "rul_cycles",
            "failure_risk_probability",
            "failure_risk_label",
        ],
    )
    return ProbeResult(
        prediction_frame,
        readiness,
        tuple(status_codes),
        tuple(latencies),
    )
