"""Deterministic aggregate exploration for accepted FD001 telemetry."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from predictive_maintenance.data.contract import (
    SENSOR_COLUMNS,
    SENSITIVITY_RISK_HORIZONS,
)
from predictive_maintenance.data.labels import add_failure_risk


def _safe_float(value: float) -> float | None:
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _partition_profile(frame: pd.DataFrame) -> dict[str, Any]:
    cycle_lengths = frame.groupby("engine_id", sort=True)["cycle"].max()
    numeric = frame.select_dtypes(include="number")
    signals: dict[str, dict[str, float | int | None]] = {}
    for column in SENSOR_COLUMNS:
        series = frame[column]
        signals[column] = {
            "min": _safe_float(series.min()),
            "max": _safe_float(series.max()),
            "mean": _safe_float(series.mean()),
            "std": _safe_float(series.std()),
            "unique": int(series.nunique(dropna=False)),
        }
    return {
        "rows": int(len(frame)),
        "telemetry_columns": 26,
        "columns_with_derived_labels": int(len(frame.columns)),
        "engines": int(frame["engine_id"].nunique()),
        "cycle_length": {
            "min": int(cycle_lengths.min()),
            "max": int(cycle_lengths.max()),
            "mean": _safe_float(cycle_lengths.mean()),
            "median": _safe_float(cycle_lengths.median()),
        },
        "missing_values": int(frame.isna().sum().sum()),
        "duplicate_engine_cycles": int(
            frame.duplicated(["engine_id", "cycle"]).sum()
        ),
        "numeric_summary": {
            column: {
                "min": _safe_float(numeric[column].min()),
                "max": _safe_float(numeric[column].max()),
                "mean": _safe_float(numeric[column].mean()),
                "std": _safe_float(numeric[column].std()),
            }
            for column in numeric.columns
        },
        "sensor_summary": signals,
        "constant_sensors": [
            column for column in SENSOR_COLUMNS if frame[column].nunique() == 1
        ],
        "low_information_sensors": [
            column
            for column in SENSOR_COLUMNS
            if frame[column].nunique() <= 2 or float(frame[column].std()) <= 1e-8
        ],
    }


def build_exploration(
    train_with_rul: pd.DataFrame, test_with_rul: pd.DataFrame
) -> dict[str, Any]:
    """Build JSON-safe FD001-only descriptive evidence."""
    prevalence: dict[str, dict[str, float]] = {}
    for horizon in SENSITIVITY_RISK_HORIZONS:
        column = f"failure_risk_{horizon}"
        train_labeled = add_failure_risk(train_with_rul, horizon)
        test_labeled = add_failure_risk(test_with_rul, horizon)
        prevalence[str(horizon)] = {
            "train": float(train_labeled[column].mean()),
            "test": float(test_labeled[column].mean()),
        }
    return {
        "scope": (
            "FD001 simulated historical cycle telemetry; cycle is a sequence "
            "coordinate, not a wall-clock timestamp or live stream."
        ),
        "rul_definition": "Canonical uncapped RUL.",
        "risk_definition": "Inclusive label: failure_risk_H = 1 when RUL <= H.",
        "train": _partition_profile(train_with_rul),
        "test": _partition_profile(test_with_rul),
        "failure_risk_prevalence": prevalence,
    }
