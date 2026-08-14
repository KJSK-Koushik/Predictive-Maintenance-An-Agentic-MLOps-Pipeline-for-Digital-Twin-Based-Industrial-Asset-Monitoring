"""Verified feature-snapshot loading tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from predictive_maintenance.cloud.models import StoredSnapshot
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import build_publication
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.models import StoredDerivedSnapshot
from predictive_maintenance.etl.publication import prepare_artifact
from predictive_maintenance.etl.serialization import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    materialize_features,
    materialize_processed,
)
from predictive_maintenance.modeling.loading import load_training_dataset
from predictive_maintenance.modeling.models import ModelingError

ROOT = Path(__file__).resolve().parents[2]


class RawMetadata:
    def __init__(self, snapshot: StoredSnapshot | None) -> None:
        self.snapshot = snapshot

    def get_snapshot(self, _snapshot_id: str) -> StoredSnapshot | None:
        return self.snapshot


class DerivedMetadata:
    def __init__(self, snapshots: tuple[StoredDerivedSnapshot, ...]) -> None:
        self.snapshots = {item.derived_snapshot_id: item for item in snapshots}

    def get_derived_snapshot(self, snapshot_id: str) -> StoredDerivedSnapshot | None:
        return self.snapshots.get(snapshot_id)


@dataclass(frozen=True, slots=True)
class PublishedInput:
    feature_id: str
    objects: FilesystemObjectRepository
    raw: Any
    derived: Any


def _stored(publication: Any) -> StoredDerivedSnapshot:
    return StoredDerivedSnapshot(
        publication.derived_snapshot_id,
        publication.source_snapshot_id,
        publication.parent_derived_snapshot_id,
        publication.artifact_kind,
        publication.contract_version,
        "available",
        publication.manifest.sha256,
        publication.identities,
    )


@pytest.fixture
def published_input(tmp_path: Path) -> PublishedInput:
    ingestion = ingest_fd001(
        ROOT / "tests/fixtures/cmapss/valid",
        tmp_path / "raw-snapshot",
        code_revision="phase4-loader-test",
    )
    raw_publication = build_publication(ingestion.snapshot, "pm-raw")
    processed = materialize_processed(
        ingestion.train,
        ingestion.test,
        source_snapshot_id=ingestion.snapshot.manifest.snapshot_id,
        code_revision="phase4-loader-test",
        output_dir=tmp_path / "processed",
    )
    raw_files = {item.logical_filename: item.identity for item in raw_publication.files}
    processed_prepared = prepare_artifact(
        processed,
        "pm-derived",
        parents_by_filename={
            "train.parquet": (raw_files["train_FD001.txt"],),
            "test.parquet": (
                raw_files["test_FD001.txt"],
                raw_files["RUL_FD001.txt"],
            ),
        },
        relationship_type="derived_from",
    )
    processed_files = {
        item.logical_filename: item.identity
        for item in processed_prepared.publication.files
    }
    feature = materialize_features(
        ingestion.train,
        ingestion.test,
        source_snapshot_id=ingestion.snapshot.manifest.snapshot_id,
        processed_snapshot_id=processed.snapshot_id,
        code_revision="phase4-loader-test",
        output_dir=tmp_path / "features",
    )
    feature_prepared = prepare_artifact(
        feature,
        "pm-derived",
        parents_by_filename={
            "train_features.parquet": (processed_files["train.parquet"],),
            "train_targets.parquet": (processed_files["train.parquet"],),
            "test_features.parquet": (processed_files["test.parquet"],),
            "test_targets.parquet": (processed_files["test.parquet"],),
        },
        relationship_type="derived_from",
    )
    objects = FilesystemObjectRepository(tmp_path / "objects")
    for item in raw_publication.files:
        objects.put_verified(
            ingestion.snapshot.path / item.logical_filename, item.identity
        )
    objects.put_verified(
        ingestion.snapshot.path / "manifest.json", raw_publication.manifest
    )
    for prepared in (*processed_prepared.objects, *feature_prepared.objects):
        objects.put_verified(prepared.path, prepared.identity)

    raw = StoredSnapshot(
        raw_publication.snapshot_id,
        "available",
        raw_publication.manifest.sha256,
        len(raw_publication.files),
        raw_publication.identities,
    )
    return PublishedInput(
        feature.snapshot_id,
        objects,
        RawMetadata(raw),
        DerivedMetadata(
            (
                _stored(processed_prepared.publication),
                _stored(feature_prepared.publication),
            )
        ),
    )


def test_loads_explicit_verified_feature_snapshot(
    published_input: PublishedInput,
) -> None:
    dataset = load_training_dataset(
        published_input.feature_id,
        published_input.objects,
        published_input.raw,
        published_input.derived,
    )
    assert dataset.feature_snapshot_id == published_input.feature_id
    assert tuple(dataset.train_features.columns) == FEATURE_COLUMNS
    assert tuple(dataset.train_targets.columns) == TARGET_COLUMNS
    assert len(dataset.train_features) == len(dataset.train_targets)
    assert dataset.train_targets["failure_risk_30"].equals(
        (dataset.train_targets["rul"] <= 30).astype("int8")
    )


def test_requires_explicit_snapshot_id(published_input: PublishedInput) -> None:
    with pytest.raises(ModelingError, match="required"):
        load_training_dataset(
            "",
            published_input.objects,
            published_input.raw,
            published_input.derived,
        )


def test_rejects_unknown_snapshot(published_input: PublishedInput) -> None:
    with pytest.raises(ModelingError, match="not found"):
        load_training_dataset(
            "f" * 64,
            published_input.objects,
            published_input.raw,
            published_input.derived,
        )


def test_rejects_inconsistent_feature_snapshot(published_input: PublishedInput) -> None:
    feature = published_input.derived.snapshots[published_input.feature_id]
    metadata: Any = DerivedMetadata((replace(feature, state="inconsistent"),))
    with pytest.raises(ModelingError, match="not available"):
        load_training_dataset(
            published_input.feature_id,
            published_input.objects,
            published_input.raw,
            metadata,
        )


def test_rejects_wrong_feature_contract(published_input: PublishedInput) -> None:
    feature = published_input.derived.snapshots[published_input.feature_id]
    metadata: Any = DerivedMetadata((replace(feature, contract_version="wrong"),))
    with pytest.raises(ModelingError, match="contract"):
        load_training_dataset(
            published_input.feature_id,
            published_input.objects,
            published_input.raw,
            metadata,
        )


def test_rejects_missing_parent_lineage(published_input: PublishedInput) -> None:
    feature = published_input.derived.snapshots[published_input.feature_id]
    metadata: Any = DerivedMetadata(
        (replace(feature, parent_derived_snapshot_id=None),)
    )
    with pytest.raises(ModelingError, match="lineage"):
        load_training_dataset(
            published_input.feature_id,
            published_input.objects,
            published_input.raw,
            metadata,
        )


def test_rejects_unavailable_raw_snapshot(published_input: PublishedInput) -> None:
    assert published_input.raw.snapshot is not None
    unavailable: Any = RawMetadata(
        replace(published_input.raw.snapshot, state="inconsistent")
    )
    with pytest.raises(ModelingError, match="Raw source"):
        load_training_dataset(
            published_input.feature_id,
            published_input.objects,
            unavailable,
            published_input.derived,
        )


def test_rejects_recorded_object_identity_mismatch(
    published_input: PublishedInput,
) -> None:
    feature = published_input.derived.snapshots[published_input.feature_id]
    bad_identity = replace(feature.identities[1], sha256="0" * 64)
    processed = published_input.derived.snapshots[feature.parent_derived_snapshot_id]
    metadata: Any = DerivedMetadata(
        (
            processed,
            replace(
                feature,
                identities=(
                    feature.identities[0],
                    bad_identity,
                    *feature.identities[2:],
                ),
            ),
        )
    )
    with pytest.raises(ModelingError, match="recorded size and SHA-256"):
        load_training_dataset(
            published_input.feature_id,
            published_input.objects,
            published_input.raw,
            metadata,
        )
