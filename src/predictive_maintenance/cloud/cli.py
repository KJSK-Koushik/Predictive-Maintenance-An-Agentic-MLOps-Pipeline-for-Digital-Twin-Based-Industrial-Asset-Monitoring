"""Sanitized Phase 2 publication command."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from predictive_maintenance.cloud.config import Phase2Settings
from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.models import CloudFoundationError
from predictive_maintenance.cloud.object_store import (
    FilesystemObjectRepository,
    ObjectRepository,
    SupabaseObjectRepository,
)
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.contract import ContractError
from predictive_maintenance.data.pipeline import ingest_fd001
from supabase import create_client


def _revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Publish an accepted FD001 raw snapshot and operational metadata.")
    )
    parser.add_argument("--source-dir", type=Path, default=Path("Data"))
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("artifacts/raw"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate FD001, publish it, and print only sanitized evidence."""
    arguments = _parser().parse_args(argv)
    try:
        settings = Phase2Settings.from_env()
        if not settings.postgres_dsn.configured:
            raise CloudFoundationError(
                "config.missing_postgres_dsn",
                "Set PM_POSTGRES_DSN locally or SUPABASE_DB_URL in cloud mode.",
            )
        ingestion = ingest_fd001(
            arguments.source_dir,
            arguments.raw_root,
            code_revision=_revision(),
        )
        metadata = PostgresMetadataRepository(
            settings.postgres_dsn.reveal(),
        )
        if settings.app_env == "cloud":
            client = create_client(
                settings.supabase_url.reveal(),
                settings.supabase_secret_key.reveal(),
            )
            supabase_objects = SupabaseObjectRepository(client)
            supabase_objects.ensure_private_buckets(
                settings.raw_bucket,
                settings.derived_bucket,
            )
            objects: ObjectRepository = supabase_objects
        else:
            objects = FilesystemObjectRepository(settings.local_object_root)
        result = publish_snapshot(
            ingestion.snapshot,
            settings.raw_bucket,
            objects,
            metadata,
        )
    except (CloudFoundationError, ContractError) as error:
        print(
            json.dumps(
                {"published": False, "error": error.to_dict()},
                indent=2,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "published": True,
                "snapshot_id": result.snapshot_id,
                "state": result.state,
                "object_count": result.object_count,
                "reused": result.reused,
                "configuration": settings.sanitized(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
