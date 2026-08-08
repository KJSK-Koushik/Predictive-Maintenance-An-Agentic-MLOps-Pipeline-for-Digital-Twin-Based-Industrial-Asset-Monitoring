"""Deterministic Parquet and manifest materialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from predictive_maintenance.data.contract import (
    IDENTIFIER_COLUMNS,
    SENSOR_COLUMNS,
    SETTING_COLUMNS,
    TELEMETRY_COLUMNS,
)
from predictive_maintenance.etl.models import (
    FEATURE_SPEC_VERSION,
    PROCESSED_CONTRACT_VERSION,
    SERIALIZER_VERSION,
    TRANSFORMATION_VERSION,
    ArtifactKind,
    ColumnContract,
    ColumnRole,
    DerivedManifest,
    EtlError,
    ManifestFile,
    MaterializedArtifact,
    MaterializedFile,
    sha256_bytes,
)

LABEL_COLUMNS = ("rul", "failure_risk_30")
PROCESSED_COLUMNS = TELEMETRY_COLUMNS + LABEL_COLUMNS
FEATURE_COLUMNS = IDENTIFIER_COLUMNS + SETTING_COLUMNS + SENSOR_COLUMNS
TARGET_COLUMNS = IDENTIFIER_COLUMNS + LABEL_COLUMNS

_TYPE_BY_COLUMN: Mapping[str, pa.DataType] = {
    "engine_id": pa.int64(),
    "cycle": pa.int64(),
    **{column: pa.float64() for column in SETTING_COLUMNS + SENSOR_COLUMNS},
    "rul": pa.int64(),
    "failure_risk_30": pa.int8(),
}


def _role(column: str, *, target_file: bool = False) -> ColumnRole:
    if column in IDENTIFIER_COLUMNS:
        return "key"
    if column in LABEL_COLUMNS or target_file:
        return "target"
    return "feature"


def _validate_frame(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    if tuple(frame.columns) != tuple(columns):
        raise EtlError(
            "contract.column_order",
            "Derived columns do not match the declared ordered contract.",
        )
    if frame.empty:
        raise EtlError("contract.empty_frame", "Derived tables cannot be empty.")
    if bool(frame.isna().to_numpy().any()):
        raise EtlError("contract.null_value", "Derived tables cannot contain nulls.")
    if frame.duplicated(list(IDENTIFIER_COLUMNS)).any():
        raise EtlError(
            "contract.duplicate_key",
            "Derived (engine_id, cycle) keys must be unique.",
        )
    numeric = frame.loc[:, list(columns)].to_numpy(dtype="float64", copy=False)
    if not bool(np.isfinite(numeric).all()):
        raise EtlError(
            "contract.non_finite",
            "Derived tables cannot contain non-finite numeric values.",
        )
    for column in columns:
        expected = {
            "engine_id": "int64",
            "cycle": "int64",
            "rul": "int64",
            "failure_risk_30": "int8",
        }.get(column, "float64")
        if str(frame[column].dtype) != expected:
            raise EtlError(
                "contract.dtype",
                f"Derived column {column} must use dtype {expected}.",
            )


def _write_parquet(
    frame: pd.DataFrame,
    path: Path,
    columns: Sequence[str],
    *,
    file_position: int,
    target_file: bool = False,
) -> ManifestFile:
    _validate_frame(frame, columns)
    arrays = [
        pa.array(frame[column].to_numpy(copy=False), type=_TYPE_BY_COLUMN[column])
        for column in columns
    ]
    table = pa.Table.from_arrays(arrays, names=list(columns))
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        path,
        version="2.6",
        compression="zstd",
        compression_level=3,
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
        row_group_size=65_536,
        store_schema=True,
    )
    payload = path.read_bytes()
    return ManifestFile(
        logical_filename=path.name,
        file_position=file_position,
        byte_size=len(payload),
        sha256=sha256_bytes(payload),
        content_type="application/vnd.apache.parquet",
        row_count=len(frame),
        columns=tuple(
            ColumnContract(
                column, str(frame[column].dtype), _role(column, target_file=target_file)
            )
            for column in columns
        ),
    )


def _finalize_artifact(
    *,
    artifact_kind: ArtifactKind,
    source_snapshot_id: str,
    parent_snapshot_id: str,
    contract_version: str,
    code_revision: str,
    output_dir: Path,
    records: Sequence[tuple[Path, ManifestFile]],
) -> MaterializedArtifact:
    positioned = tuple(
        ManifestFile(
            logical_filename=record.logical_filename,
            file_position=position,
            byte_size=record.byte_size,
            sha256=record.sha256,
            content_type=record.content_type,
            row_count=record.row_count,
            columns=record.columns,
        )
        for position, (_, record) in enumerate(records, start=1)
    )
    manifest = DerivedManifest(
        artifact_kind=artifact_kind,
        source_snapshot_id=source_snapshot_id,
        parent_snapshot_id=parent_snapshot_id,
        contract_version=contract_version,
        transformation_version=TRANSFORMATION_VERSION,
        serializer_version=SERIALIZER_VERSION,
        code_revision=code_revision,
        files=positioned,
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(manifest.canonical_bytes())
    materialized = tuple(
        MaterializedFile(path, positioned[index])
        for index, (path, _) in enumerate(records)
    )
    return MaterializedArtifact(manifest, manifest_path, materialized)


def materialize_processed(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    source_snapshot_id: str,
    code_revision: str,
    output_dir: Path,
) -> MaterializedArtifact:
    """Write the exact Phase 1 labeled rows as deterministic processed Parquet."""
    train_output = train.loc[:, PROCESSED_COLUMNS].copy()
    test_output = test.loc[:, PROCESSED_COLUMNS].copy()
    records = []
    for position, (filename, frame) in enumerate(
        (
            ("train.parquet", train_output),
            ("test.parquet", test_output),
        ),
        start=1,
    ):
        path = output_dir / filename
        records.append(
            (
                path,
                _write_parquet(
                    frame,
                    path,
                    PROCESSED_COLUMNS,
                    file_position=position,
                ),
            )
        )
    return _finalize_artifact(
        artifact_kind="processed",
        source_snapshot_id=source_snapshot_id,
        parent_snapshot_id=source_snapshot_id,
        contract_version=PROCESSED_CONTRACT_VERSION,
        code_revision=code_revision,
        output_dir=output_dir,
        records=records,
    )


def materialize_features(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    source_snapshot_id: str,
    processed_snapshot_id: str,
    code_revision: str,
    output_dir: Path,
) -> MaterializedArtifact:
    """Separate candidate inputs from labels without fitted preprocessing."""
    frames = (
        (
            "train_features.parquet",
            train.loc[:, FEATURE_COLUMNS].copy(),
            FEATURE_COLUMNS,
            False,
        ),
        (
            "train_targets.parquet",
            train.loc[:, TARGET_COLUMNS].copy(),
            TARGET_COLUMNS,
            True,
        ),
        (
            "test_features.parquet",
            test.loc[:, FEATURE_COLUMNS].copy(),
            FEATURE_COLUMNS,
            False,
        ),
        (
            "test_targets.parquet",
            test.loc[:, TARGET_COLUMNS].copy(),
            TARGET_COLUMNS,
            True,
        ),
    )
    records = []
    for position, (filename, frame, columns, target_file) in enumerate(frames, start=1):
        path = output_dir / filename
        records.append(
            (
                path,
                _write_parquet(
                    frame,
                    path,
                    columns,
                    file_position=position,
                    target_file=target_file,
                ),
            )
        )
    return _finalize_artifact(
        artifact_kind="feature",
        source_snapshot_id=source_snapshot_id,
        parent_snapshot_id=processed_snapshot_id,
        contract_version=FEATURE_SPEC_VERSION,
        code_revision=code_revision,
        output_dir=output_dir,
        records=records,
    )
