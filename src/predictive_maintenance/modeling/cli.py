"""Sanitized direct CLI for the fixed Phase 4 baselines."""

from __future__ import annotations

import argparse
import json
import os
import sys

from predictive_maintenance.cloud.models import CloudFoundationError
from predictive_maintenance.etl.models import EtlError
from predictive_maintenance.modeling.models import ModelingError
from predictive_maintenance.modeling.runtime import run_from_environment
from predictive_maintenance.modeling.tracking import log_baseline_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train and track the fixed leakage-safe FD001 baselines."
    )
    parser.add_argument("--feature-snapshot-id", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"),
    )
    parser.add_argument("--dirty-worktree", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run baselines and print bounded run identifiers as JSON."""
    arguments = _parser().parse_args(argv)
    try:
        result = run_from_environment(arguments.feature_snapshot_id)
        tracked = log_baseline_result(
            result,
            tracking_uri=arguments.tracking_uri,
            code_revision=arguments.code_revision,
            dirty_worktree=arguments.dirty_worktree,
        )
    except (ModelingError, EtlError, CloudFoundationError) as error:
        code = getattr(error, "code", "modeling.failed")
        message = getattr(error, "message", "Baseline training failed.")
        print(
            json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr
        )
        return 2
    print(
        json.dumps(
            {
                "experiment_id": tracked.experiment_id,
                "parent_run_id": tracked.parent_run_id,
                "child_run_ids": tracked.child_run_ids,
                "feature_snapshot_id": result.split_manifest.feature_snapshot_id,
                "split_id": result.split_manifest.split_id,
                "eligible": {
                    "regression": result.evaluation("regression", "candidate").eligible,
                    "classification": result.evaluation(
                        "classification", "candidate"
                    ).eligible,
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
