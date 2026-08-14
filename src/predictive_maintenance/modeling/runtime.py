"""Read-only infrastructure adapters for direct Phase 4 training."""

from __future__ import annotations

from predictive_maintenance.cloud.config import Phase2Settings
from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import (
    FilesystemObjectRepository,
    ObjectRepository,
    SupabaseObjectRepository,
)
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.modeling.loading import load_training_dataset
from predictive_maintenance.modeling.models import BaselineResult, ModelingError
from predictive_maintenance.modeling.pipeline import run_baselines
from supabase import create_client


def run_from_environment(feature_snapshot_id: str) -> BaselineResult:
    """Load an explicit verified snapshot and run fixed baselines read-only."""
    settings = Phase2Settings.from_env()
    if not settings.postgres_dsn.configured:
        raise ModelingError(
            "config.missing_postgres_dsn",
            "Set PM_POSTGRES_DSN locally or SUPABASE_DB_URL in cloud mode.",
        )
    raw_metadata = PostgresMetadataRepository(settings.postgres_dsn.reveal())
    derived_metadata = PostgresDerivedMetadataRepository(settings.postgres_dsn.reveal())
    if settings.app_env == "cloud":
        client = create_client(
            settings.supabase_url.reveal(), settings.supabase_secret_key.reveal()
        )
        objects: ObjectRepository = SupabaseObjectRepository(client)
    else:
        objects = FilesystemObjectRepository(settings.local_object_root)
    dataset = load_training_dataset(
        feature_snapshot_id, objects, raw_metadata, derived_metadata
    )
    return run_baselines(dataset)
