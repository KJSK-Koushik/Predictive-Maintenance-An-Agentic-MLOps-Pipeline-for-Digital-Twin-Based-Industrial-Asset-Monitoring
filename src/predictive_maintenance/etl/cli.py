"""Sanitized direct command for the Phase 3 derived pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Sequence

from predictive_maintenance.cloud.models import CloudFoundationError
from predictive_maintenance.etl.models import EtlError
from predictive_maintenance.etl.runtime import run_from_environment


def _revision() -> str:
    configured = os.environ.get("PM_CODE_REVISION", "").strip()
    if configured:
        return configured
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
        description="Create deterministic FD001 processed and feature snapshots."
    )
    parser.add_argument("--source-snapshot-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one explicit source snapshot and print identifier-only evidence."""
    arguments = _parser().parse_args(argv)
    try:
        result = run_from_environment(
            arguments.source_snapshot_id,
            code_revision=_revision(),
        )
    except (CloudFoundationError, EtlError) as error:
        details = error.to_dict()
        print(json.dumps({"accepted": False, "error": details}, indent=2))
        return 1
    print(json.dumps({"accepted": True, **result.to_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
