"""Airflow-independent composition of the complete Phase 3 pipeline."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from predictive_maintenance.cloud.metadata import MetadataRepository
from predictive_maintenance.cloud.models import ObjectIdentity
from predictive_maintenance.cloud.object_store import ObjectRepository
from predictive_maintenance.data.contract import (
    RUL_FILENAME,
    TEST_FILENAME,
    TRAIN_FILENAME,
)
from predictive_maintenance.data.pipeline import IngestionResult
from predictive_maintenance.etl.extraction import extract_validated_source
from predictive_maintenance.etl.metadata import DerivedMetadataRepository
from predictive_maintenance.etl.models import (
    EtlError,
    MaterializedArtifact,
    PipelineResult,
)
from predictive_maintenance.etl.publication import (
    PreparedArtifact,
    build_batch_publication,
    prepare_artifact,
    publish_batch,
)
from predictive_maintenance.etl.quality import materialize_quality_report
from predictive_maintenance.etl.serialization import (
    materialize_features,
    materialize_processed,
)

_REVISION = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


@dataclass(frozen=True, slots=True)
class MaterializedPipeline:
    """All deterministic local artifacts before external publication."""

    processed: MaterializedArtifact
    feature: MaterializedArtifact
    quality: MaterializedArtifact


def materialize_pipeline(
    ingestion: IngestionResult,
    *,
    code_revision: str,
    workspace: Path,
) -> MaterializedPipeline:
    """Build processed, feature, target, manifest, and quality files."""
    if not _REVISION.fullmatch(code_revision):
        raise EtlError(
            "identity.invalid_code_revision",
            "Code revision must be a bounded identifier without path characters.",
        )
    source_id = ingestion.snapshot.manifest.snapshot_id
    processed = materialize_processed(
        ingestion.train,
        ingestion.test,
        source_snapshot_id=source_id,
        code_revision=code_revision,
        output_dir=workspace / "processed",
    )
    feature = materialize_features(
        ingestion.train,
        ingestion.test,
        source_snapshot_id=source_id,
        processed_snapshot_id=processed.snapshot_id,
        code_revision=code_revision,
        output_dir=workspace / "features",
    )
    quality = materialize_quality_report(
        ingestion.train,
        ingestion.test,
        source_snapshot_id=source_id,
        processed_snapshot_id=processed.snapshot_id,
        feature_snapshot_id=feature.snapshot_id,
        code_revision=code_revision,
        output_dir=workspace / "quality",
    )
    return MaterializedPipeline(processed, feature, quality)


def _prepared_artifacts(
    materialized: MaterializedPipeline,
    raw_files: dict[str, ObjectIdentity],
    derived_bucket: str,
) -> tuple[PreparedArtifact, ...]:
    processed = prepare_artifact(
        materialized.processed,
        derived_bucket,
        parents_by_filename={
            "train.parquet": (raw_files[TRAIN_FILENAME],),
            "test.parquet": (
                raw_files[TEST_FILENAME],
                raw_files[RUL_FILENAME],
            ),
        },
        relationship_type="derived_from",
    )
    processed_by_name = {
        item.logical_filename: item.identity for item in processed.publication.files
    }
    feature = prepare_artifact(
        materialized.feature,
        derived_bucket,
        parents_by_filename={
            "train_features.parquet": (processed_by_name["train.parquet"],),
            "train_targets.parquet": (processed_by_name["train.parquet"],),
            "test_features.parquet": (processed_by_name["test.parquet"],),
            "test_targets.parquet": (processed_by_name["test.parquet"],),
        },
        relationship_type="derived_from",
    )
    report_parents = tuple(
        [item.identity for item in processed.publication.files]
        + [item.identity for item in feature.publication.files]
    )
    quality = prepare_artifact(
        materialized.quality,
        derived_bucket,
        parents_by_filename={"report.json": report_parents},
        relationship_type="reported_by",
    )
    return processed, feature, quality


def run_pipeline(
    source_snapshot_id: str,
    derived_bucket: str,
    objects: ObjectRepository,
    raw_metadata: MetadataRepository,
    derived_metadata: DerivedMetadataRepository,
    *,
    code_revision: str,
) -> PipelineResult:
    """Run the complete idempotent ETL using only durable identities externally."""
    with tempfile.TemporaryDirectory(prefix="pm-phase3-") as temporary:
        workspace = Path(temporary)
        source = extract_validated_source(
            source_snapshot_id,
            objects,
            raw_metadata,
            workspace / "extraction",
            code_revision=code_revision,
        )
        artifacts = materialize_pipeline(
            source.ingestion,
            code_revision=code_revision,
            workspace=workspace / "artifacts",
        )
        prepared = _prepared_artifacts(artifacts, source.raw_files, derived_bucket)
        batch = build_batch_publication(
            source_snapshot_id,
            code_revision,
            prepared,
        )
        return publish_batch(
            source_snapshot_id,
            prepared,
            batch,
            objects,
            derived_metadata,
        )
