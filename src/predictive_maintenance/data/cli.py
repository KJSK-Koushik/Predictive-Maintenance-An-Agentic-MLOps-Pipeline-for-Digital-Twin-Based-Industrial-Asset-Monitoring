"""Command line validation for the owner-provided local FD001 files."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Sequence

from predictive_maintenance.data.contract import ContractError
from predictive_maintenance.data.pipeline import ingest_fd001


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
        description="Validate and profile local NASA C-MAPSS FD001 telemetry."
    )
    parser.add_argument("--source-dir", type=Path, default=Path("Data"))
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("artifacts/raw"),
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("artifacts/reports/phase-01"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run local-real-data validation and write sanitized aggregate evidence."""
    arguments = _parser().parse_args(argv)
    try:
        result = ingest_fd001(
            arguments.source_dir,
            arguments.raw_root,
            code_revision=_revision(),
        )
    except ContractError as error:
        print(json.dumps({"accepted": False, "error": error.to_dict()}, indent=2))
        return 1

    arguments.report_dir.mkdir(parents=True, exist_ok=True)
    (arguments.report_dir / "manifest.json").write_text(
        result.snapshot.manifest.canonical_json() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (arguments.report_dir / "validation.json").write_text(
        result.validation.canonical_json() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (arguments.report_dir / "exploration.json").write_text(
        json.dumps(
            result.exploration,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "accepted": True,
                "snapshot_id": result.snapshot.manifest.snapshot_id,
                "snapshot_reused": result.snapshot.reused,
                "train_rows": len(result.train),
                "test_rows": len(result.test),
                "reports": [
                    "manifest.json",
                    "validation.json",
                    "exploration.json",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
