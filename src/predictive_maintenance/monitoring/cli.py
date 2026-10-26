"""Command-line entry point for deterministic Phase 7 monitoring."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from predictive_maintenance.monitoring.models import MonitoringError
from predictive_maintenance.monitoring.runtime import (
    build_reference_file,
    load_policy,
    run_monitoring_files,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monitor-fd001",
        description="Deterministic FD001 batch replay monitoring; not real-time.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    reference = subcommands.add_parser("build-reference")
    reference.add_argument("--features", type=Path, required=True)
    reference.add_argument("--output-dir", type=Path, required=True)
    reference.add_argument("--release-id", required=True)
    reference.add_argument("--feature-snapshot-id", required=True)
    reference.add_argument("--code-revision", required=True)
    reference.add_argument("--dependency-lock-sha256", required=True)
    reference.add_argument("--policy", type=Path)

    monitor = subcommands.add_parser("run")
    monitor.add_argument("--features", type=Path, required=True)
    monitor.add_argument("--current-predictions", type=Path, required=True)
    monitor.add_argument("--reference-predictions", type=Path, required=True)
    monitor.add_argument("--reference", type=Path, required=True)
    monitor.add_argument("--output-dir", type=Path, required=True)
    monitor.add_argument("--raw-snapshot-id", required=True)
    monitor.add_argument("--processed-snapshot-id", required=True)
    monitor.add_argument("--feature-snapshot-id", required=True)
    monitor.add_argument(
        "--source-partition",
        choices=("train", "validation", "test", "synthetic"),
        required=True,
    )
    monitor.add_argument("--replay-sequence", type=int, required=True)
    monitor.add_argument("--code-revision", required=True)
    monitor.add_argument("--dependency-lock-sha256", required=True)
    monitor.add_argument("--policy", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one explicit command and print only bounded JSON evidence."""
    arguments = _parser().parse_args(argv)
    try:
        policy = load_policy(arguments.policy)
        result: dict[str, object]
        if arguments.command == "build-reference":
            path = build_reference_file(
                arguments.features,
                arguments.output_dir,
                release_id=arguments.release_id,
                feature_snapshot_id=arguments.feature_snapshot_id,
                policy=policy,
                code_revision=arguments.code_revision,
                dependency_lock_sha256=arguments.dependency_lock_sha256,
            )
            result = {"status": "created_or_reused", "filename": path.name}
        else:
            report, path, reused = run_monitoring_files(
                arguments.features,
                arguments.current_predictions,
                arguments.reference_predictions,
                arguments.reference,
                arguments.output_dir,
                policy=policy,
                raw_snapshot_id=arguments.raw_snapshot_id,
                processed_snapshot_id=arguments.processed_snapshot_id,
                feature_snapshot_id=arguments.feature_snapshot_id,
                source_partition=arguments.source_partition,
                replay_sequence=arguments.replay_sequence,
                code_revision=arguments.code_revision,
                dependency_lock_sha256=arguments.dependency_lock_sha256,
            )
            result = {
                "report_id": report.report_id,
                "filename": path.name,
                "reused": reused,
            }
    except MonitoringError as error:
        print(json.dumps({"error": error.to_dict()}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
