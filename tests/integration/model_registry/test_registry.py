"""Real database-backed local MLflow candidate and alias behavior."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, timedelta
from pathlib import Path
from typing import cast

import mlflow
import pytest
from mlflow.exceptions import MlflowException
from mlflow.models import Model
from mlflow.tracking import MlflowClient
from phase4_support import LocalMlflowServer
from phase6_support import SyntheticRelease, build_synthetic_release

from predictive_maintenance.modeling.models import FEATURE_COLUMNS, sha256_bytes
from predictive_maintenance.modeling.tracking import _signature
from predictive_maintenance.release.gates import build_candidate_manifest
from predictive_maintenance.release.models import ApprovalDecision, ReleaseError
from predictive_maintenance.release.registry import (
    register_candidate,
    reject_production_alias,
    restore_staging_aliases,
    set_staging_aliases,
)

pytestmark = [pytest.mark.integration, pytest.mark.mlflow, pytest.mark.registry]


def _source_run(
    server: LocalMlflowServer,
    release: SyntheticRelease,
    root: Path,
    task: str,
) -> str:
    reference = (
        release.manifest.regression
        if task == "regression"
        else release.manifest.classification
    )
    source = (
        release.bundle / "rul" / "model.skops"
        if task == "regression"
        else release.bundle / "risk" / "model.skops"
    )
    model_dir = root / task / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "model.skops").write_bytes(source.read_bytes())
    metadata = Model(signature=_signature())
    metadata.add_flavor("skops", data="model.skops", serialization_format="skops")
    metadata.save(model_dir / "MLmodel")
    mlflow.set_tracking_uri(server.uri)
    mlflow.set_experiment("phase6-registry-test")
    with mlflow.start_run(run_name=task) as run:
        mlflow.set_tags(
            {
                "phase": "5",
                "run_role": "model",
                "task": task,
                "feature_snapshot_id": release.manifest.feature_snapshot_id,
                "comparison_id": release.manifest.comparison_id,
                "selection_id": release.manifest.selection_id,
                "model_artifact_sha256": reference.artifact_sha256,
            }
        )
        mlflow.log_artifacts(str(model_dir), artifact_path="model")
        return cast(str, run.info.run_id)


def test_candidates_require_approval_before_staging_alias(
    tmp_path: Path,
    mlflow_server_factory: Callable[[Path], LocalMlflowServer],
) -> None:
    server = mlflow_server_factory(tmp_path / "mlflow")
    try:
        release = build_synthetic_release(tmp_path / "release")
        regression_run = _source_run(server, release, tmp_path / "source", "regression")
        classification_run = _source_run(
            server, release, tmp_path / "source", "classification"
        )
        regression = register_candidate(
            tracking_uri=server.uri,
            run_id=regression_run,
            task="regression",
            feature_snapshot_id=release.manifest.feature_snapshot_id,
            comparison_id=release.manifest.comparison_id,
            selection_id=release.manifest.selection_id,
            selected_family="histogram_gradient_boosting",
            selected_parameters=release.manifest.regression.selected_parameters,
        )
        classification = register_candidate(
            tracking_uri=server.uri,
            run_id=classification_run,
            task="classification",
            feature_snapshot_id=release.manifest.feature_snapshot_id,
            comparison_id=release.manifest.comparison_id,
            selection_id=release.manifest.selection_id,
            selected_family="class_balanced_logistic_regression",
            selected_parameters=release.manifest.classification.selected_parameters,
        )
        client = MlflowClient(tracking_uri=server.uri)
        with pytest.raises(MlflowException):
            client.get_model_version_by_alias(regression.registered_name, "staging")

        manifest = build_candidate_manifest(
            feature_snapshot_id=release.manifest.feature_snapshot_id,
            processed_snapshot_id=release.manifest.processed_snapshot_id,
            raw_snapshot_id=release.manifest.raw_snapshot_id,
            split_id=release.manifest.split_id,
            comparison_id=release.manifest.comparison_id,
            selection_id=release.manifest.selection_id,
            regression=regression,
            classification=classification,
            verification_fixture_sha256=release.manifest.verification_fixture_sha256,
            code_revision="phase6-registry-test",
            python_version="3.11",
            dependency_lock_sha256=sha256_bytes(b"test-lock"),
        )
        decided = release.approval.decided_at
        approval = ApprovalDecision(
            manifest.approval_request_id,
            manifest.release_id,
            "approved",
            "KJSK-Koushik",
            "Synthetic registry integration.",
            sha256_bytes(b"registry-approval"),
            decided,
            decided + timedelta(hours=1),
        )
        set_staging_aliases(
            manifest,
            approval,
            tracking_uri=server.uri,
            now=decided + timedelta(minutes=1),
        )
        assert (
            client.get_model_version_by_alias(
                regression.registered_name, "staging"
            ).version
            == regression.version
        )
        assert (
            client.get_model_version_by_alias(
                classification.registered_name, "staging"
            ).version
            == classification.version
        )
        restore_staging_aliases(
            regression.version,
            classification.version,
            tracking_uri=server.uri,
        )
        with pytest.raises(ReleaseError, match=r"registry\.production_disabled"):
            reject_production_alias("production")
        assert tuple(FEATURE_COLUMNS) == regression.feature_columns
        assert decided.tzinfo == UTC
    finally:
        server.stop()
