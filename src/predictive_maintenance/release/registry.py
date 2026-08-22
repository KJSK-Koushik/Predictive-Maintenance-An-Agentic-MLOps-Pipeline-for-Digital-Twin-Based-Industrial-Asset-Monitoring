"""Local MLflow registry operations kept separate from human approval."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Literal

from mlflow.entities.model_registry import ModelVersion
from mlflow.exceptions import MlflowException
from mlflow.models import Model
from mlflow.tracking import MlflowClient

from predictive_maintenance.release.gates import require_current_approval
from predictive_maintenance.release.models import (
    CLASSIFICATION_REGISTERED_NAME,
    FEATURE_COLUMNS,
    REGRESSION_REGISTERED_NAME,
    STAGING_ALIAS,
    ApprovalDecision,
    ModelReference,
    ReleaseError,
    ReleaseManifest,
    sha256_bytes,
)
from predictive_maintenance.release.trust import trusted_types


def _client(tracking_uri: str) -> MlflowClient:
    if not tracking_uri.startswith("http://127.0.0.1:"):
        raise ReleaseError(
            "registry.non_loopback", "The Phase 6 MLflow registry must use loopback."
        )
    return MlflowClient(tracking_uri=tracking_uri)


def _ensure_registered_model(client: MlflowClient, name: str) -> None:
    try:
        client.create_registered_model(
            name,
            tags={"phase": "6", "production_authorized": "false"},
            description="FD001 research staging model; not production-authorized.",
        )
    except MlflowException as error:
        if "already exists" not in str(error).lower():
            raise ReleaseError(
                "registry.create_failed", "Registered model creation failed."
            ) from error


def _matching_candidate(
    client: MlflowClient,
    name: str,
    run_id: str,
    selection_id: str,
) -> ModelVersion | None:
    matches = [
        item
        for item in client.search_model_versions(f"name = '{name}'")
        if item.run_id == run_id and item.tags.get("selection_id") == selection_id
    ]
    if len(matches) > 1:
        raise ReleaseError(
            "registry.duplicate_candidate", "Multiple matching candidates exist."
        )
    return matches[0] if matches else None


def register_candidate(
    *,
    tracking_uri: str,
    run_id: str,
    task: Literal["regression", "classification"],
    feature_snapshot_id: str,
    comparison_id: str,
    selection_id: str,
    selected_family: str,
    selected_parameters: dict[str, Any],
) -> ModelReference:
    """Register one exact run artifact as a candidate, without setting aliases."""
    client = _client(tracking_uri)
    run = client.get_run(run_id)
    expected_tags = {
        "phase": "5",
        "run_role": "model",
        "task": task,
        "feature_snapshot_id": feature_snapshot_id,
        "comparison_id": comparison_id,
        "selection_id": selection_id,
    }
    if any(run.data.tags.get(key) != value for key, value in expected_tags.items()):
        raise ReleaseError(
            "registry.source_provenance_mismatch",
            "The source run does not match the approved Phase 5 evidence.",
        )
    expected_digest = run.data.tags.get("model_artifact_sha256", "")
    name = (
        REGRESSION_REGISTERED_NAME
        if task == "regression"
        else CLASSIFICATION_REGISTERED_NAME
    )
    with tempfile.TemporaryDirectory(prefix="phase6-registry-") as temporary:
        local = Path(client.download_artifacts(run_id, "model", dst_path=temporary))
        model_path = local / "model.skops"
        metadata = Model.load(local / "MLmodel")
        if sha256_bytes(model_path.read_bytes()) != expected_digest:
            raise ReleaseError(
                "registry.artifact_digest_mismatch", "Source artifact digest differs."
            )
        if metadata.signature is None or metadata.signature.inputs is None:
            raise ReleaseError(
                "registry.signature_missing", "Source model signature is missing."
            )
        inputs = metadata.signature.inputs.inputs
        if tuple(item.name for item in inputs) != FEATURE_COLUMNS or any(
            str(item.type) != "DataType.double" for item in inputs
        ):
            raise ReleaseError(
                "registry.signature_mismatch", "Source model signature differs."
            )
        inspected_types = trusted_types(model_path)

    _ensure_registered_model(client, name)
    existing = _matching_candidate(client, name, run_id, selection_id)
    tags = {
        **expected_tags,
        "candidate": "true",
        "artifact_sha256": expected_digest,
        "feature_columns": ",".join(FEATURE_COLUMNS),
        "selected_family": selected_family,
        "production_authorized": "false",
    }
    if existing is None:
        version = client.create_model_version(
            name=name,
            source=f"runs:/{run_id}/model",
            run_id=run_id,
            tags=tags,
            description="Phase 6 candidate; human staging approval is separate.",
        )
    else:
        version = existing
        if any(version.tags.get(key) != value for key, value in tags.items()):
            raise ReleaseError(
                "registry.candidate_conflict", "Existing candidate tags differ."
            )
    return ModelReference(
        task=task,
        registered_name=name,
        version=str(version.version),
        source_run_id=run_id,
        artifact_sha256=expected_digest,
        selected_family=selected_family,
        selected_parameters=selected_parameters,
        trusted_types=inspected_types,
    )


def set_staging_aliases(
    manifest: ReleaseManifest,
    approval: ApprovalDecision,
    *,
    tracking_uri: str,
    now: Any,
) -> None:
    """Set only staging aliases for the exact approved atomic release."""
    require_current_approval(manifest, approval, now=now)
    client = _client(tracking_uri)
    for reference in (manifest.regression, manifest.classification):
        version = client.get_model_version(reference.registered_name, reference.version)
        if version.run_id != reference.source_run_id:
            raise ReleaseError(
                "registry.version_mismatch", "Registered version source run differs."
            )
    for reference in (manifest.regression, manifest.classification):
        client.set_registered_model_alias(
            reference.registered_name, STAGING_ALIAS, reference.version
        )


def restore_staging_aliases(
    regression_version: str,
    classification_version: str,
    *,
    tracking_uri: str,
) -> None:
    """Restore the recorded previous staging versions; production is unavailable."""
    client = _client(tracking_uri)
    client.set_registered_model_alias(
        REGRESSION_REGISTERED_NAME, STAGING_ALIAS, regression_version
    )
    client.set_registered_model_alias(
        CLASSIFICATION_REGISTERED_NAME, STAGING_ALIAS, classification_version
    )


def reject_production_alias(alias: str) -> None:
    """Make the missing production target an explicit fail-closed contract."""
    if alias.lower() == "production":
        raise ReleaseError(
            "registry.production_disabled", "No production target is configured."
        )
