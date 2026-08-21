"""Read-only infrastructure adapters for direct local Phase 5 analysis."""

from __future__ import annotations

from predictive_maintenance.cloud.config import Phase2Settings
from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import (
    FilesystemObjectRepository,
)
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.modeling.loading import load_training_dataset
from predictive_maintenance.modeling.models import ModelingError, TrainingDataset
from predictive_maintenance.modeling.splitting import create_split_manifest


def load_phase5_input(feature_snapshot_id: str) -> tuple[TrainingDataset, str]:
    """Load one verified snapshot and its immutable Phase 4 split identity."""
    settings = Phase2Settings.from_env()
    if settings.app_env == "cloud":
        raise ModelingError(
            "config.phase5_local_only", "Phase 5 direct analysis is local-only."
        )
    if not settings.postgres_dsn.configured:
        raise ModelingError(
            "config.missing_postgres_dsn", "Set PM_POSTGRES_DSN for local Phase 5."
        )
    raw_metadata = PostgresMetadataRepository(settings.postgres_dsn.reveal())
    derived_metadata = PostgresDerivedMetadataRepository(settings.postgres_dsn.reveal())
    objects = FilesystemObjectRepository(settings.local_object_root)
    dataset = load_training_dataset(
        feature_snapshot_id, objects, raw_metadata, derived_metadata
    )
    return dataset, create_split_manifest(dataset).split_id
