"""Runtime adapter construction shared by the direct CLI and Airflow tasks."""

from __future__ import annotations

from predictive_maintenance.cloud.config import Phase2Settings
from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.object_store import (
    FilesystemObjectRepository,
    ObjectRepository,
    SupabaseObjectRepository,
)
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.models import EtlError, PipelineResult
from predictive_maintenance.etl.pipeline import run_pipeline
from supabase import create_client


def run_from_environment(
    source_snapshot_id: str,
    *,
    code_revision: str,
) -> PipelineResult:
    """Construct approved adapters at task execution time and run the pipeline."""
    settings = Phase2Settings.from_env()
    if not settings.postgres_dsn.configured:
        raise EtlError(
            "config.missing_postgres_dsn",
            "Set PM_POSTGRES_DSN locally or SUPABASE_DB_URL in cloud mode.",
        )
    raw_metadata = PostgresMetadataRepository(settings.postgres_dsn.reveal())
    derived_metadata = PostgresDerivedMetadataRepository(settings.postgres_dsn.reveal())
    if settings.app_env == "cloud":
        client = create_client(
            settings.supabase_url.reveal(),
            settings.supabase_secret_key.reveal(),
        )
        cloud_objects = SupabaseObjectRepository(client)
        cloud_objects.ensure_private_buckets(
            settings.raw_bucket,
            settings.derived_bucket,
        )
        objects: ObjectRepository = cloud_objects
    else:
        objects = FilesystemObjectRepository(settings.local_object_root)
    return run_pipeline(
        source_snapshot_id,
        settings.derived_bucket,
        objects,
        raw_metadata,
        derived_metadata,
        code_revision=code_revision,
    )
