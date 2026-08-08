"""Pure processed, feature, target, identity, and quality contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from predictive_maintenance.data.contract import (
    IDENTIFIER_COLUMNS,
    SENSOR_COLUMNS,
    SETTING_COLUMNS,
)
from predictive_maintenance.data.pipeline import IngestionResult
from predictive_maintenance.etl.models import EtlError, canonical_json_bytes
from predictive_maintenance.etl.pipeline import materialize_pipeline
from predictive_maintenance.etl.quality import materialize_quality_report
from predictive_maintenance.etl.serialization import (
    LABEL_COLUMNS,
    PROCESSED_COLUMNS,
)


def _all_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_two_clean_materializations_are_byte_identical(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = materialize_pipeline(
        ingestion,
        code_revision="abc123",
        workspace=first_root,
    )
    second = materialize_pipeline(
        ingestion,
        code_revision="abc123",
        workspace=second_root,
    )

    assert first.processed.snapshot_id == second.processed.snapshot_id
    assert first.feature.snapshot_id == second.feature.snapshot_id
    assert first.quality.snapshot_id == second.quality.snapshot_id
    assert _all_bytes(first_root) == _all_bytes(second_root)


def test_processed_parquet_preserves_rows_columns_and_dtypes(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    artifacts = materialize_pipeline(
        ingestion,
        code_revision="abc123",
        workspace=tmp_path / "artifacts",
    )
    for filename, expected in (
        ("train.parquet", ingestion.train),
        ("test.parquet", ingestion.test),
    ):
        table = pq.read_table(artifacts.processed.manifest_path.parent / filename)
        actual = table.to_pandas()
        assert tuple(actual.columns) == PROCESSED_COLUMNS
        pd.testing.assert_frame_equal(actual, expected.loc[:, PROCESSED_COLUMNS])
        assert "timestamp" not in actual.columns


def test_candidate_features_exclude_targets_and_targets_remain_key_aligned(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    artifacts = materialize_pipeline(
        ingestion,
        code_revision="abc123",
        workspace=tmp_path / "artifacts",
    )
    root = artifacts.feature.manifest_path.parent
    expected_features = IDENTIFIER_COLUMNS + SETTING_COLUMNS + SENSOR_COLUMNS
    expected_targets = IDENTIFIER_COLUMNS + LABEL_COLUMNS
    for partition in ("train", "test"):
        features = pq.read_table(root / f"{partition}_features.parquet").to_pandas()
        targets = pq.read_table(root / f"{partition}_targets.parquet").to_pandas()
        assert tuple(features.columns) == expected_features
        assert tuple(targets.columns) == expected_targets
        assert not set(LABEL_COLUMNS).intersection(features.columns)
        pd.testing.assert_frame_equal(
            features.loc[:, list(IDENTIFIER_COLUMNS)],
            targets.loc[:, list(IDENTIFIER_COLUMNS)],
        )
        assert set(targets["failure_risk_30"].unique()) <= {0, 1}


def test_manifest_records_ordered_schema_roles_and_no_execution_time(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    artifacts = materialize_pipeline(
        ingestion,
        code_revision="abc123",
        workspace=tmp_path / "artifacts",
    )
    manifest = json.loads(artifacts.feature.manifest_path.read_text(encoding="ascii"))
    assert manifest["derived_snapshot_id"] == artifacts.feature.snapshot_id
    assert [item["file_position"] for item in manifest["files"]] == [1, 2, 3, 4]
    assert manifest["files"][0]["columns"][0] == {
        "dtype": "int64",
        "name": "engine_id",
        "role": "key",
    }
    combined = artifacts.feature.manifest_path.read_text(encoding="ascii").lower()
    assert "logical_date" not in combined
    assert "run_id" not in combined
    assert "created_at" not in combined


def test_code_revision_is_provenance_and_changes_identity(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    first = materialize_pipeline(
        ingestion,
        code_revision="revision-a",
        workspace=tmp_path / "a",
    )
    second = materialize_pipeline(
        ingestion,
        code_revision="revision-b",
        workspace=tmp_path / "b",
    )
    assert first.processed.snapshot_id != second.processed.snapshot_id
    assert first.feature.snapshot_id != second.feature.snapshot_id


def test_invalid_revision_and_non_finite_json_fail_closed(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    with pytest.raises(EtlError, match=r"identity\.invalid_code_revision"):
        materialize_pipeline(
            ingestion,
            code_revision="../unsafe",
            workspace=tmp_path / "unsafe",
        )
    with pytest.raises(EtlError, match=r"serialization\.invalid_json"):
        canonical_json_bytes({"value": float("nan")})


def test_quality_report_is_bounded_aggregate_evidence(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    artifacts = materialize_pipeline(
        ingestion,
        code_revision="abc123",
        workspace=tmp_path / "artifacts",
    )
    payload = artifacts.quality.files[0].path.read_bytes()
    report = json.loads(payload)
    assert len(payload) < 256 * 1024
    assert report["status"] == "passed"
    assert report["partitions"]["train"]["rows"] == len(ingestion.train)
    assert all(
        len(rule["examples"]) <= 5
        for partition in report["partitions"].values()
        for rule in partition["rules"]
    )
    combined = payload.decode("ascii").lower()
    assert "supabase.co" not in combined
    assert str(tmp_path).lower() not in combined


def test_failed_quality_gate_does_not_return_an_artifact(
    tmp_path: Path, ingestion: IngestionResult
) -> None:
    changed = ingestion.train.copy()
    current = int(cast(Any, changed.loc[0, "failure_risk_30"]))
    changed.loc[0, "failure_risk_30"] = 1 - current
    with pytest.raises(EtlError, match=r"quality\.gate_failed"):
        materialize_quality_report(
            changed,
            ingestion.test,
            source_snapshot_id=ingestion.snapshot.manifest.snapshot_id,
            processed_snapshot_id="a" * 64,
            feature_snapshot_id="b" * 64,
            code_revision="abc123",
            output_dir=tmp_path / "quality",
        )
