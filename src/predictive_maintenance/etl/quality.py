"""Bounded deterministic data-quality evidence for Phase 3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from predictive_maintenance.data.contract import IDENTIFIER_COLUMNS
from predictive_maintenance.etl.models import (
    PIPELINE_VERSION,
    QUALITY_CONTRACT_VERSION,
    SERIALIZER_VERSION,
    TRANSFORMATION_VERSION,
    ColumnContract,
    DerivedManifest,
    EtlError,
    ManifestFile,
    MaterializedArtifact,
    MaterializedFile,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.etl.serialization import PROCESSED_COLUMNS


@dataclass(frozen=True, slots=True)
class QualityRule:
    """One bounded project-owned quality result."""

    rule_id: str
    passed: bool
    count: int
    examples: tuple[dict[str, int], ...] = ()


def _examples(frame: pd.DataFrame, mask: pd.Series) -> tuple[dict[str, int], ...]:
    return tuple(
        {
            "engine_id": int(cast(Any, row.engine_id)),
            "cycle": int(cast(Any, row.cycle)),
        }
        for row in frame.loc[mask, list(IDENTIFIER_COLUMNS)]
        .head(5)
        .itertuples(index=False)
    )


def _partition_quality(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    exact_columns = tuple(frame.columns) == PROCESSED_COLUMNS
    null_count = int(frame.isna().sum().sum())
    duplicate = frame.duplicated(list(IDENTIFIER_COLUMNS), keep=False)
    same_engine = frame["engine_id"].eq(frame["engine_id"].shift())
    bad_cycle = (same_engine & frame["cycle"].ne(frame["cycle"].shift() + 1)) | (
        ~same_engine & frame["cycle"].ne(1)
    )
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    finite_count = int((~np.isfinite(numeric.to_numpy(dtype="float64"))).sum())
    negative_rul = frame["rul"] < 0
    incorrect_risk = frame["failure_risk_30"].ne((frame["rul"] <= 30).astype("int8"))
    rules = (
        QualityRule(
            f"quality.{name}.non_empty", bool(len(frame)), 0 if len(frame) else 1
        ),
        QualityRule(
            f"quality.{name}.columns", exact_columns, 0 if exact_columns else 1
        ),
        QualityRule(f"quality.{name}.nulls", null_count == 0, null_count),
        QualityRule(
            f"quality.{name}.duplicate_keys",
            not bool(duplicate.any()),
            int(duplicate.sum()),
            _examples(frame, duplicate),
        ),
        QualityRule(
            f"quality.{name}.cycle_order",
            not bool(bad_cycle.any()),
            int(bad_cycle.sum()),
            _examples(frame, bad_cycle),
        ),
        QualityRule(f"quality.{name}.finite", finite_count == 0, finite_count),
        QualityRule(
            f"quality.{name}.rul_non_negative",
            not bool(negative_rul.any()),
            int(negative_rul.sum()),
            _examples(frame, negative_rul),
        ),
        QualityRule(
            f"quality.{name}.risk_boundary",
            not bool(incorrect_risk.any()),
            int(incorrect_risk.sum()),
            _examples(frame, incorrect_risk),
        ),
    )
    return {
        "columns": len(frame.columns),
        "duplicate_engine_cycles": int(duplicate.sum()),
        "engines": int(frame["engine_id"].nunique()),
        "null_values": null_count,
        "rows": len(frame),
        "rules": [asdict(rule) for rule in rules],
    }


def materialize_quality_report(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    source_snapshot_id: str,
    processed_snapshot_id: str,
    feature_snapshot_id: str,
    code_revision: str,
    output_dir: Path,
) -> MaterializedArtifact:
    """Write aggregate quality results and fail closed when a rule fails."""
    partitions = {
        "test": _partition_quality("test", test),
        "train": _partition_quality("train", train),
    }
    rules = [rule for partition in partitions.values() for rule in partition["rules"]]
    passed = all(bool(rule["passed"]) for rule in rules)
    report = {
        "feature_snapshot_id": feature_snapshot_id,
        "pipeline_version": PIPELINE_VERSION,
        "processed_snapshot_id": processed_snapshot_id,
        "report_contract_version": QUALITY_CONTRACT_VERSION,
        "serializer_version": SERIALIZER_VERSION,
        "source_snapshot_id": source_snapshot_id,
        "status": "passed" if passed else "failed",
        "transformation_version": TRANSFORMATION_VERSION,
        "partitions": partitions,
    }
    payload = canonical_json_bytes(report)
    if len(payload) > 256 * 1024:
        raise EtlError(
            "quality.report_too_large",
            "The bounded data-quality report exceeded 256 KiB.",
        )
    path = output_dir / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    record = ManifestFile(
        logical_filename=path.name,
        file_position=1,
        byte_size=len(payload),
        sha256=sha256_bytes(payload),
        content_type="application/json",
        row_count=None,
        columns=(ColumnContract("aggregate_quality_evidence", "json", "feature"),),
    )
    manifest = DerivedManifest(
        artifact_kind="quality_report",
        source_snapshot_id=source_snapshot_id,
        parent_snapshot_id=processed_snapshot_id,
        contract_version=QUALITY_CONTRACT_VERSION,
        transformation_version=TRANSFORMATION_VERSION,
        serializer_version=SERIALIZER_VERSION,
        code_revision=code_revision,
        files=(record,),
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(manifest.canonical_bytes())
    if not passed:
        raise EtlError(
            "quality.gate_failed",
            "One or more deterministic data-quality rules failed.",
        )
    return MaterializedArtifact(
        manifest,
        manifest_path,
        (MaterializedFile(path, record),),
    )
