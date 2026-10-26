"""Deterministic monitoring support shared by Phase 7 tests."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from predictive_maintenance.release.models import FEATURE_COLUMNS


def identity(name: str) -> str:
    """Return a stable test SHA-256."""
    return hashlib.sha256(name.encode("ascii")).hexdigest()


def telemetry_frame(*, shift: float = 0.0) -> pd.DataFrame:
    """Return three ordered synthetic engine trajectories."""
    rows: list[dict[str, float | int]] = []
    for engine_id in range(1, 4):
        for cycle in range(1, 21):
            row: dict[str, float | int] = {
                "engine_id": engine_id,
                "cycle": cycle,
            }
            for index, name in enumerate(FEATURE_COLUMNS, start=1):
                row[name] = engine_id * 0.1 + cycle * 0.01 + index * 0.001 + shift
            rows.append(row)
    return pd.DataFrame(rows, columns=["engine_id", "cycle", *FEATURE_COLUMNS])


def prediction_frame(frame: pd.DataFrame, *, shift: float = 0.0) -> pd.DataFrame:
    """Return aligned deterministic two-task prediction evidence."""
    rul = np.maximum(80.0 - frame["cycle"].to_numpy(dtype="float64") + shift, 0.0)
    probability = np.clip((frame["cycle"].to_numpy() - 5.0 + shift) / 20.0, 0, 1)
    return pd.DataFrame(
        {
            "engine_id": frame["engine_id"].to_numpy(),
            "cycle": frame["cycle"].to_numpy(),
            "rul_cycles": rul,
            "failure_risk_probability": probability,
            "failure_risk_label": (probability >= 0.5).astype("int64"),
        }
    )
