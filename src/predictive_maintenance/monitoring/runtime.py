"""Filesystem runtime for direct Phase 7 monitoring commands."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pandas as pd

from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    MonitoringReport,
)
from predictive_maintenance.monitoring.pipeline import (
    build_monitoring_report,
    create_window,
)
from predictive_maintenance.monitoring.reference import (
    build_reference_profile,
    reference_from_dict,
)


def load_policy(path: Path | None) -> MonitoringPolicy:
    """Load a strict policy or use documented version-one defaults."""
    if path is None:
        return MonitoringPolicy()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError
        allowed = {item.name for item in fields(MonitoringPolicy)}
        if set(value) - allowed:
            raise TypeError
        return MonitoringPolicy(**value)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise MonitoringError(
            "runtime.invalid_policy", "Monitoring policy file is invalid."
        ) from error


def _read_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except (OSError, ValueError) as error:
        raise MonitoringError(
            "runtime.invalid_parquet", "Monitoring input could not be read."
        ) from error


def _put_if_absent(destination: Path, payload: bytes, conflict_code: str) -> bool:
    """Create local evidence exclusively or verify the exact existing bytes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as stream:
            stream.write(payload)
        return False
    except FileExistsError:
        try:
            existing = destination.read_bytes()
        except OSError as error:
            raise MonitoringError(
                "runtime.output_unreadable", "Existing monitoring output is unreadable."
            ) from error
        if existing != payload:
            raise MonitoringError(
                conflict_code, "Content-addressed output has different bytes."
            ) from None
        return True
    except OSError as error:
        raise MonitoringError(
            "runtime.output_write_failed", "Monitoring output could not be written."
        ) from error


def build_reference_file(
    feature_path: Path,
    output_dir: Path,
    *,
    release_id: str,
    feature_snapshot_id: str,
    policy: MonitoringPolicy,
    code_revision: str,
    dependency_lock_sha256: str,
) -> Path:
    """Build and atomically write one local content-addressed reference."""
    reference = build_reference_profile(
        _read_parquet(feature_path),
        release_id=release_id,
        feature_snapshot_id=feature_snapshot_id,
        policy=policy,
        code_revision=code_revision,
        dependency_lock_sha256=dependency_lock_sha256,
    )
    destination = output_dir / f"{reference.reference_id}.json"
    payload = reference.canonical_bytes()
    _put_if_absent(destination, payload, "runtime.reference_conflict")
    return destination


def run_monitoring_files(
    feature_path: Path,
    current_predictions_path: Path,
    reference_predictions_path: Path,
    reference_path: Path,
    output_dir: Path,
    *,
    policy: MonitoringPolicy,
    raw_snapshot_id: str,
    processed_snapshot_id: str,
    feature_snapshot_id: str,
    source_partition: str,
    replay_sequence: int,
    code_revision: str,
    dependency_lock_sha256: str,
    service_evidence: dict[str, Any] | None = None,
) -> tuple[MonitoringReport, Path, bool]:
    """Run direct monitoring and put canonical report bytes if absent."""
    try:
        reference_value = json.loads(reference_path.read_text(encoding="ascii"))
        if not isinstance(reference_value, dict):
            raise TypeError
        reference = reference_from_dict(reference_value)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise MonitoringError(
            "runtime.invalid_reference", "Reference profile file is invalid."
        ) from error
    frame = _read_parquet(feature_path)
    window = create_window(
        frame,
        reference=reference,
        policy=policy,
        raw_snapshot_id=raw_snapshot_id,
        processed_snapshot_id=processed_snapshot_id,
        feature_snapshot_id=feature_snapshot_id,
        source_partition=source_partition,
        replay_sequence=replay_sequence,
        code_revision=code_revision,
        dependency_lock_sha256=dependency_lock_sha256,
    )
    report = build_monitoring_report(
        frame,
        _read_parquet(current_predictions_path),
        _read_parquet(reference_predictions_path),
        window=window,
        reference=reference,
        policy=policy,
        service_evidence=service_evidence,
    )
    destination = output_dir / f"{report.report_id}.json"
    payload = report.canonical_bytes()
    reused = _put_if_absent(destination, payload, "runtime.report_conflict")
    return report, destination, reused
