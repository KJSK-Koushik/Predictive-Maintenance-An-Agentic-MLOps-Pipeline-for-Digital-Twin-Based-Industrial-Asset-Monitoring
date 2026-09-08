"""Engine-balanced reference-profile construction."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from predictive_maintenance.monitoring.models import (
    FeatureReference,
    MonitoringError,
    MonitoringPolicy,
    ReferenceProfile,
)
from predictive_maintenance.release.models import FEATURE_COLUMNS

KEY_COLUMNS = ("engine_id", "cycle")


def validate_feature_frame(frame: pd.DataFrame) -> None:
    """Validate ordered FD001 row keys and exact model-input columns."""
    expected = (*KEY_COLUMNS, *FEATURE_COLUMNS)
    if tuple(frame.columns) != expected:
        raise MonitoringError(
            "quality.schema_mismatch",
            "Telemetry must contain ordered engine, cycle, and 24 model inputs.",
        )
    if frame.empty:
        raise MonitoringError("quality.empty_window", "Telemetry window is empty.")
    if frame.loc[:, list(expected)].isna().any().any():
        raise MonitoringError(
            "quality.missing_value", "Telemetry contains missing values."
        )
    keys = frame.loc[:, list(KEY_COLUMNS)]
    if bool(keys.duplicated().any()):
        raise MonitoringError(
            "quality.duplicate_key", "Telemetry row keys are duplicated."
        )
    engine_values = keys["engine_id"].to_numpy()
    cycle_values = keys["cycle"].to_numpy()
    if not bool(
        np.equal(engine_values, np.floor(engine_values)).all()
        and np.equal(cycle_values, np.floor(cycle_values)).all()
        and (engine_values > 0).all()
        and (cycle_values > 0).all()
    ):
        raise MonitoringError(
            "quality.invalid_key", "Engine IDs and cycles must be positive integers."
        )
    values = frame.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype="float64")
    if not bool(np.isfinite(values).all()):
        raise MonitoringError(
            "quality.nonfinite", "Telemetry contains non-finite values."
        )
    ordered = frame.sort_values(list(KEY_COLUMNS), kind="stable").index
    if not ordered.equals(frame.index):
        raise MonitoringError(
            "quality.cycle_order", "Telemetry must be ordered by engine and cycle."
        )
    cycle_differences = frame.groupby("engine_id", sort=False)["cycle"].diff()
    if bool((cycle_differences.dropna() <= 0).any()):
        raise MonitoringError(
            "quality.cycle_order", "Cycles must increase within each engine."
        )


def engine_balanced_sample(frame: pd.DataFrame, maximum: int) -> pd.DataFrame:
    """Select at most the same number of ordered rows from every engine."""
    if maximum < 1:
        raise MonitoringError(
            "reference.invalid_sampling", "Per-engine sample limit must be positive."
        )
    positions: list[int] = []
    for _, group in frame.groupby("engine_id", sort=True):
        count = min(len(group), maximum)
        indexes = np.linspace(0, len(group) - 1, count, dtype="int64")
        positions.extend(group.iloc[indexes].index.tolist())
    return frame.loc[positions].sort_values(list(KEY_COLUMNS), kind="stable")


def lifecycle_mix(frame: pd.DataFrame) -> dict[str, float]:
    """Summarize lifecycle composition when an RUL column is available."""
    if "rul" not in frame:
        return {"status_unavailable": 1.0}
    rul = frame["rul"].to_numpy(dtype="float64")
    if not bool(np.isfinite(rul).all()):
        raise MonitoringError("quality.nonfinite_label", "RUL labels are non-finite.")
    return {
        "near_0_30": float(np.mean(rul <= 30.0)),
        "middle_31_100": float(np.mean((rul > 30.0) & (rul <= 100.0))),
        "early_over_100": float(np.mean(rul > 100.0)),
    }


def operating_setting_summary(frame: pd.DataFrame) -> dict[str, float]:
    """Return bounded aggregate operating-setting context."""
    result: dict[str, float] = {}
    for name in ("setting_1", "setting_2", "setting_3"):
        values = frame[name].to_numpy(dtype="float64")
        result[f"{name}_median"] = float(np.median(values))
        result[f"{name}_iqr"] = float(
            np.quantile(values, 0.75) - np.quantile(values, 0.25)
        )
    return result


def _feature_reference(name: str, values: np.ndarray) -> FeatureReference:
    quantiles = np.quantile(values, np.linspace(0.1, 0.9, 9))
    edges = tuple(float(item) for item in np.unique(quantiles))
    counts, _ = np.histogram(values, bins=(-np.inf, *edges, np.inf))
    probabilities = tuple(float(item / counts.sum()) for item in counts)
    return FeatureReference(
        name=name,
        quantile_edges=edges,
        bin_probabilities=probabilities,
        minimum=float(np.min(values)),
        maximum=float(np.max(values)),
        median=float(np.median(values)),
        iqr=float(np.quantile(values, 0.75) - np.quantile(values, 0.25)),
    )


def build_reference_profile(
    frame: pd.DataFrame,
    *,
    release_id: str,
    feature_snapshot_id: str,
    policy: MonitoringPolicy,
    code_revision: str,
    dependency_lock_sha256: str,
) -> ReferenceProfile:
    """Build one immutable profile from source-training telemetry only."""
    validate_feature_frame(frame.loc[:, [*KEY_COLUMNS, *FEATURE_COLUMNS]])
    sample = engine_balanced_sample(frame, policy.max_rows_per_engine)
    features = tuple(
        _feature_reference(name, sample[name].to_numpy(dtype="float64", copy=True))
        for name in FEATURE_COLUMNS
    )
    return ReferenceProfile(
        release_id=release_id,
        feature_snapshot_id=feature_snapshot_id,
        source_partition="train",
        policy_id=policy.policy_id,
        row_count=len(frame),
        engine_count=int(frame["engine_id"].nunique()),
        sampled_row_count=len(sample),
        features=features,
        lifecycle_mix=lifecycle_mix(frame),
        operating_setting_summary=operating_setting_summary(frame),
        code_revision=code_revision,
        dependency_lock_sha256=dependency_lock_sha256,
    )


def reference_from_dict(value: dict[str, Any]) -> ReferenceProfile:
    """Load a strict reference from decoded canonical JSON."""
    content = dict(value)
    stored_id = content.pop("reference_id", None)
    features = tuple(
        FeatureReference(
            **{
                **item,
                "quantile_edges": tuple(item["quantile_edges"]),
                "bin_probabilities": tuple(item["bin_probabilities"]),
            }
        )
        for item in content.pop("features")
    )
    reference = ReferenceProfile(features=features, **content)
    if stored_id != reference.reference_id:
        raise MonitoringError(
            "reference.identity_mismatch", "Stored reference identity is invalid."
        )
    return reference
