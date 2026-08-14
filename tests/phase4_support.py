"""Shared deterministic Phase 4 test support."""

from __future__ import annotations

import hashlib
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import pytest
import requests

from predictive_maintenance.modeling.models import FEATURE_COLUMNS, TrainingDataset


@dataclass(slots=True)
class LocalMlflowServer:
    """Disposable real loopback tracking server used only by tests."""

    process: subprocess.Popen[bytes]
    log_stream: BinaryIO
    uri: str

    def stop(self) -> None:
        """Terminate the exact child process with a bounded fallback."""
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        self.log_stream.close()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _start_mlflow_server(root: Path) -> LocalMlflowServer:
    root.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    uri = f"http://127.0.0.1:{port}"
    database = root / "mlflow.db"
    artifacts = root / "artifacts"
    log_stream = (root / "server.log").open("wb")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mlflow",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
            "--backend-store-uri",
            f"sqlite:///{database.resolve().as_posix()}",
            "--artifacts-destination",
            artifacts.resolve().as_uri(),
            "--allowed-hosts",
            f"127.0.0.1:{port},localhost:{port}",
        ],
        stdout=log_stream,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_stream.flush()
            detail = (root / "server.log").read_text(errors="replace")[-2000:]
            log_stream.close()
            pytest.fail(f"MLflow server exited before readiness: {detail}")
        try:
            response = requests.get(f"{uri}/health", timeout=1)
            if response.status_code == 200:
                return LocalMlflowServer(process, log_stream, uri)
        except requests.RequestException:
            pass
        time.sleep(0.25)
    process.terminate()
    process.wait(timeout=20)
    log_stream.close()
    pytest.fail("MLflow server did not become ready within 90 seconds.")


@pytest.fixture
def mlflow_server_factory() -> Callable[[Path], LocalMlflowServer]:
    """Return the bounded real-server constructor."""
    return _start_mlflow_server


def _partition(engine_count: int, cycles: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows: list[dict[str, float | int]] = []
    target_rows: list[dict[str, int]] = []
    for engine_id in range(1, engine_count + 1):
        for cycle in range(1, cycles + 1):
            rul = cycles - cycle
            feature: dict[str, float | int] = {
                "engine_id": engine_id,
                "cycle": cycle,
            }
            for index, name in enumerate(FEATURE_COLUMNS):
                if name == "sensor_1":
                    value = float(rul)
                elif name == "sensor_2":
                    value = float(cycle)
                else:
                    value = float(index) + engine_id * 0.01 + cycle * 0.001
                feature[name] = value
            feature_rows.append(feature)
            target_rows.append(
                {
                    "engine_id": engine_id,
                    "cycle": cycle,
                    "rul": rul,
                    "failure_risk_30": int(rul <= 30),
                }
            )
    features = pd.DataFrame(feature_rows).astype(
        {
            "engine_id": "int64",
            "cycle": "int64",
            **dict.fromkeys(FEATURE_COLUMNS, "float64"),
        }
    )
    targets = pd.DataFrame(target_rows).astype(
        {
            "engine_id": "int64",
            "cycle": "int64",
            "rul": "int64",
            "failure_risk_30": "int8",
        }
    )
    return features, targets


@pytest.fixture
def synthetic_dataset() -> TrainingDataset:
    """Provide multiple engine trajectories with a simple known signal."""
    train_features, train_targets = _partition(10, 40)
    test_features, test_targets = _partition(4, 35)
    identities = [
        hashlib.sha256(name.encode()).hexdigest()
        for name in ("raw", "processed", "feature")
    ]
    return TrainingDataset(
        identities[0],
        identities[1],
        identities[2],
        train_features,
        train_targets,
        test_features,
        test_targets,
    )
