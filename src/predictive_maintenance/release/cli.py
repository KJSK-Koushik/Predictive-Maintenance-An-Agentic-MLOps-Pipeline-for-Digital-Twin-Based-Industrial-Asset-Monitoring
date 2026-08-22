"""Phase 6 candidate preparation CLI with a hard pre-approval stop."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

from predictive_maintenance.cloud.metadata import PostgresMetadataRepository
from predictive_maintenance.cloud.models import CloudFoundationError
from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.cloud.publication import publish_snapshot
from predictive_maintenance.data.pipeline import ingest_fd001
from predictive_maintenance.etl.metadata import PostgresDerivedMetadataRepository
from predictive_maintenance.etl.models import EtlError
from predictive_maintenance.etl.pipeline import run_pipeline
from predictive_maintenance.modeling.loading import load_training_dataset
from predictive_maintenance.modeling.models import ModelingError
from predictive_maintenance.modeling.phase5_pipeline import run_phase5
from predictive_maintenance.modeling.phase5_tracking import log_phase5_result
from predictive_maintenance.modeling.splitting import create_split_manifest
from predictive_maintenance.release.gates import build_candidate_manifest
from predictive_maintenance.release.metadata import PostgresReleaseRepository
from predictive_maintenance.release.models import (
    FEATURE_COLUMNS,
    ReleaseError,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.release.registry import register_candidate

APPROVED_ACTUAL_FEATURE_SNAPSHOT_ID = (
    "0fa9261023ce5ba902be85db4fd4539badf0260f1e560bd1a3e32a374b6ee8d9"
)
APPROVED_ACTUAL_SPLIT_ID = (
    "f03c3e85bf1be56cee842b06eeb2e637d920db8bf3af321a904de070cd6e3dac"
)
APPROVED_ACTUAL_COMPARISON_ID = (
    "762103b8364de5323d90084158159c987dd1659d3043806034e61493cbce07d8"
)
APPROVED_ACTUAL_SELECTION_ID = (
    "81e9d56fd843652cb29de06424298077abe318ceb3a309402bcd428c3863583e"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the exact FD001 candidate and stop before approval."
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--postgres-dsn", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--dependency-lock", type=Path, default=Path("uv.lock"))
    return parser


def _write_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(payload)
    except OSError as error:
        raise ReleaseError(
            "candidate.evidence_write_failed",
            "Candidate evidence could not be written.",
        ) from error
    if path.read_bytes() != payload:
        raise ReleaseError(
            "candidate.evidence_write_failed",
            "Candidate evidence verification failed.",
        )


def _fixture(result: Any, dataset: Any) -> bytes:
    row = dataset.test_features.iloc[0]
    observation: dict[str, int | float] = {
        "engine_id": int(row["engine_id"]),
        "cycle": int(row["cycle"]),
    }
    observation.update({name: float(row[name]) for name in FEATURE_COLUMNS})
    frame = dataset.test_features.loc[
        [dataset.test_features.index[0]], list(FEATURE_COLUMNS)
    ]
    frame = frame.astype("float64")
    regression = result.benchmark.models["regression_selected"]
    classification = result.benchmark.models["classification_selected"]
    rul = max(float(np.asarray(regression.predict(frame))[0]), 0.0)
    probability = float(np.asarray(classification.predict_proba(frame))[0, 1])
    return canonical_json_bytes(
        {
            "contract_version": "fd001-startup-parity-v1",
            "observations": [observation],
            "expected": [
                {
                    "rul_cycles": rul,
                    "failure_risk_probability": min(max(probability, 0.0), 1.0),
                    "failure_risk_label": int(probability >= 0.5),
                }
            ],
        }
    )


def _require_approved_phase5_result(result: Any) -> None:
    """Reject a rerun that differs from the owner-approved Phase 5 evidence."""
    if result.development.manifest.comparison_id != APPROVED_ACTUAL_COMPARISON_ID:
        raise ReleaseError(
            "candidate.comparison_mismatch",
            "Reproduced comparison differs from approved Phase 5 evidence.",
        )
    if result.development.selection.selection_id != APPROVED_ACTUAL_SELECTION_ID:
        raise ReleaseError(
            "candidate.selection_mismatch",
            "Reproduced selection differs from approved Phase 5 evidence.",
        )


def prepare(arguments: argparse.Namespace) -> dict[str, str]:
    """Prepare an actual candidate and perform no approval-gated operation."""
    workspace: Path = arguments.workspace
    ingestion = ingest_fd001(
        arguments.data_dir,
        workspace / "raw",
        code_revision="phase5-actual-dataset-test",
    )
    objects = FilesystemObjectRepository(workspace / "objects")
    raw_metadata = PostgresMetadataRepository(arguments.postgres_dsn)
    derived_metadata = PostgresDerivedMetadataRepository(arguments.postgres_dsn)
    raw = publish_snapshot(ingestion.snapshot, "pm-raw", objects, raw_metadata)
    etl = run_pipeline(
        raw.snapshot_id,
        "pm-derived",
        objects,
        raw_metadata,
        derived_metadata,
        code_revision="phase5-actual-dataset-test",
    )
    if etl.feature_snapshot_id != APPROVED_ACTUAL_FEATURE_SNAPSHOT_ID:
        raise ReleaseError(
            "candidate.feature_snapshot_mismatch",
            "Reproduced features differ from approved Phase 5 input.",
        )
    dataset = load_training_dataset(
        etl.feature_snapshot_id, objects, raw_metadata, derived_metadata
    )
    split_id = create_split_manifest(dataset).split_id
    if split_id != APPROVED_ACTUAL_SPLIT_ID:
        raise ReleaseError(
            "candidate.split_mismatch", "Reproduced split differs from Phase 5."
        )
    result = run_phase5(dataset, phase4_split_id=split_id)
    _require_approved_phase5_result(result)
    tracking = log_phase5_result(
        result,
        tracking_uri=arguments.tracking_uri,
        code_revision=arguments.code_revision,
        dirty_worktree=False,
    )
    selection = result.development.selection
    regression = register_candidate(
        tracking_uri=arguments.tracking_uri,
        run_id=tracking.child_run_ids["regression_selected"],
        task="regression",
        feature_snapshot_id=etl.feature_snapshot_id,
        comparison_id=result.development.manifest.comparison_id,
        selection_id=selection.selection_id,
        selected_family="histogram_gradient_boosting",
        selected_parameters=selection.regression_parameters,
    )
    classification = register_candidate(
        tracking_uri=arguments.tracking_uri,
        run_id=tracking.child_run_ids["classification_selected"],
        task="classification",
        feature_snapshot_id=etl.feature_snapshot_id,
        comparison_id=result.development.manifest.comparison_id,
        selection_id=selection.selection_id,
        selected_family="class_balanced_logistic_regression",
        selected_parameters=selection.classification_parameters,
    )
    fixture = _fixture(result, dataset)
    try:
        lock_digest = sha256_bytes(arguments.dependency_lock.read_bytes())
    except OSError as error:
        raise ReleaseError(
            "candidate.lock_unreadable", "Dependency lock could not be read."
        ) from error
    manifest = build_candidate_manifest(
        feature_snapshot_id=etl.feature_snapshot_id,
        processed_snapshot_id=etl.processed_snapshot_id,
        raw_snapshot_id=raw.snapshot_id,
        split_id=split_id,
        comparison_id=result.development.manifest.comparison_id,
        selection_id=selection.selection_id,
        regression=regression,
        classification=classification,
        verification_fixture_sha256=sha256_bytes(fixture),
        code_revision=arguments.code_revision,
        python_version=platform.python_version(),
        dependency_lock_sha256=lock_digest,
    )
    PostgresReleaseRepository(arguments.postgres_dsn).record_candidate(manifest)
    candidate = workspace / "candidates" / manifest.release_id
    _write_exact(candidate / "candidate-manifest.json", manifest.canonical_bytes())
    _write_exact(candidate / "verification-fixture.json", fixture)
    _write_exact(
        candidate / "candidate-evidence.json",
        canonical_json_bytes(
            {
                "release_id": manifest.release_id,
                "approval_request_id": manifest.approval_request_id,
                "parent_run_id": tracking.parent_run_id,
                "regression_run_id": regression.source_run_id,
                "classification_run_id": classification.source_run_id,
                "approval_status": "not_requested_from_owner_yet",
                "alias_status": "none",
                "package_status": "not_created",
                "publication_status": "not_published",
                "deployment_status": "not_deployed",
            }
        ),
    )
    return {
        "release_id": manifest.release_id,
        "approval_request_id": manifest.approval_request_id,
        "feature_snapshot_id": manifest.feature_snapshot_id,
        "comparison_id": manifest.comparison_id,
        "selection_id": manifest.selection_id,
        "regression_model_version": regression.version,
        "classification_model_version": classification.version,
        "state": "candidate_waiting_for_exact_owner_approval",
    }


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        output = prepare(arguments)
    except (ReleaseError, ModelingError, EtlError, CloudFoundationError) as error:
        code = getattr(error, "code", "candidate.failed")
        message = getattr(error, "message", "Candidate preparation failed.")
        print(
            json.dumps({"error": {"code": code, "message": message}}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
