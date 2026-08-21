"""Sanitized two-step CLI for Phase 5 development and locked benchmarking."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from predictive_maintenance.cloud.models import CloudFoundationError
from predictive_maintenance.etl.models import EtlError
from predictive_maintenance.modeling.comparison import (
    development_input_from_dataset,
    run_locked_benchmark,
    selection_from_bytes,
)
from predictive_maintenance.modeling.models import ModelingError
from predictive_maintenance.modeling.phase5_pipeline import run_phase5_development
from predictive_maintenance.modeling.phase5_runtime import load_phase5_input


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bounded FD001 Phase 5 development or locked benchmark."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    develop = subcommands.add_parser(
        "develop", help="Tune and lock using source-training engines only."
    )
    develop.add_argument("--feature-snapshot-id", required=True)
    develop.add_argument("--selection-path", type=Path, required=True)
    benchmark = subcommands.add_parser(
        "benchmark", help="Evaluate an existing locked selection on NASA test."
    )
    benchmark.add_argument("--feature-snapshot-id", required=True)
    benchmark.add_argument("--selection-path", type=Path, required=True)
    return parser


def _write_selection(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as error:
        if path.read_bytes() != payload:
            raise ModelingError(
                "selection.conflict", "Selection path already contains other bytes."
            ) from error


def main(argv: list[str] | None = None) -> int:
    """Execute exactly one Phase 5 step and print bounded aggregate JSON."""
    arguments = _parser().parse_args(argv)
    try:
        dataset, phase4_split_id = load_phase5_input(arguments.feature_snapshot_id)
        if arguments.command == "develop":
            development_input = development_input_from_dataset(
                dataset, phase4_split_id=phase4_split_id
            )
            result = run_phase5_development(development_input)
            _write_selection(
                arguments.selection_path, result.selection.canonical_bytes()
            )
            output = {
                "step": "development_locked",
                "feature_snapshot_id": result.manifest.feature_snapshot_id,
                "comparison_id": result.manifest.comparison_id,
                "selection_id": result.selection.selection_id,
                "preferred_models": {
                    item.task: item.preferred_model for item in result.comparisons
                },
            }
        else:
            selection = selection_from_bytes(arguments.selection_path.read_bytes())
            benchmark = run_locked_benchmark(
                dataset, selection, phase4_split_id=phase4_split_id
            )
            output = {
                "step": "known_benchmark_complete",
                "feature_snapshot_id": benchmark.feature_snapshot_id,
                "selection_id": benchmark.selection_id,
                "test_exposure_status": benchmark.test_exposure_status,
                "prediction_digests": {
                    item.task: item.prediction_digest for item in benchmark.evaluations
                },
            }
    except (OSError, ModelingError, EtlError, CloudFoundationError) as error:
        code = getattr(error, "code", "phase5.failed")
        message = getattr(error, "message", "Phase 5 analysis failed.")
        print(
            json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr
        )
        return 2
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
