"""Explicit local MLflow logging with trusted skops model artifacts."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import skops.io as sio  # type: ignore[import-untyped]
from mlflow.models import Model, ModelSignature
from mlflow.tracking import MlflowClient
from mlflow.types.schema import ColSpec, Schema

from predictive_maintenance.modeling.models import (
    EVALUATION_PROTOCOL_VERSION,
    FEATURE_COLUMNS,
    MODEL_CONFIG_VERSION,
    BaselineResult,
    ModelingError,
    TrackingResult,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.release.trust import dump_deterministic

EXPERIMENT_NAME = "fd001-phase-4-baselines"
_TRUSTED_TYPE_PREFIXES = ("builtins.", "numpy.", "sklearn.")
mlflow: Any = importlib.import_module("mlflow")


def schema_only_input_example() -> pd.DataFrame:
    """Return constructed zero values that describe schema, not telemetry."""
    return pd.DataFrame(
        np.zeros((1, len(FEATURE_COLUMNS)), dtype="float64"),
        columns=list(FEATURE_COLUMNS),
    )


def validate_model_input(frame: pd.DataFrame) -> None:
    """Require the exact ordered signature before loaded-model prediction."""
    if tuple(frame.columns) != FEATURE_COLUMNS:
        raise ModelingError(
            "model.signature_columns", "Model input columns or order are invalid."
        )
    if any(str(frame[column].dtype) != "float64" for column in FEATURE_COLUMNS):
        raise ModelingError("model.signature_dtype", "Model inputs must be float64.")
    if frame.empty or not bool(np.isfinite(frame.to_numpy()).all()):
        raise ModelingError("model.signature_values", "Model inputs must be finite.")


def _signature() -> ModelSignature:
    return ModelSignature(
        inputs=Schema([ColSpec("double", name) for name in FEATURE_COLUMNS]),
        outputs=Schema([ColSpec("double")]),
    )


def _flatten_metrics(
    prefix: str, value: Mapping[str, Any], output: dict[str, float]
) -> None:
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, bool):
            continue
        if isinstance(item, int | float) and np.isfinite(float(item)):
            output[name] = float(item)
        elif isinstance(item, dict):
            _flatten_metrics(name, item, output)


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _log_model_artifact(model: Any, directory: Path, artifact_key: str) -> str:
    model_directory = directory / f"model-{artifact_key}"
    model_directory.mkdir()
    model_path = model_directory / "model.skops"
    dump_deterministic(model, model_path)
    digest = sha256_bytes(model_path.read_bytes())
    metadata = Model(signature=_signature())
    metadata.add_flavor(
        "skops",
        data="model.skops",
        serialization_format="skops",
        skops_version=importlib.metadata.version("skops"),
    )
    metadata.save(model_directory / "MLmodel")
    schema_only_input_example().to_json(
        model_directory / "input_example.json", orient="split", index=False
    )
    mlflow.log_artifacts(str(model_directory), artifact_path="model")
    return digest


def log_baseline_result(
    result: BaselineResult,
    *,
    tracking_uri: str,
    code_revision: str,
    dirty_worktree: bool,
) -> TrackingResult:
    """Log one parent and four child runs without registry side effects."""
    if not tracking_uri.startswith("http://127.0.0.1:"):
        raise ModelingError(
            "tracking.non_loopback", "Phase 4 MLflow must use IPv4 loopback."
        )
    os.environ["MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT"] = "true"
    mlflow.set_tracking_uri(tracking_uri)
    experiment = mlflow.set_experiment(EXPERIMENT_NAME)
    child_run_ids: dict[str, str] = {}
    common_tags = {
        "phase": "4",
        "feature_snapshot_id": result.split_manifest.feature_snapshot_id,
        "split_id": result.split_manifest.split_id,
        "evaluation_protocol": EVALUATION_PROTOCOL_VERSION,
    }
    with tempfile.TemporaryDirectory(prefix="phase4-mlflow-") as temporary:
        root = Path(temporary)
        with mlflow.start_run(run_name="fd001-baseline-evaluation") as parent:
            mlflow.set_tags({**common_tags, "run_role": "parent"})
            mlflow.log_params(
                {
                    "model_config_version": MODEL_CONFIG_VERSION,
                    "seed": result.split_manifest.seed,
                    "code_revision": code_revision,
                    "dirty_worktree": str(dirty_worktree).lower(),
                    "feature_count": len(FEATURE_COLUMNS),
                }
            )
            split_path = root / "split_manifest.json"
            split_path.write_bytes(result.split_manifest.canonical_bytes())
            report_path = root / "evaluation_report.json"
            _write_json(report_path, [item.to_dict() for item in result.evaluations])
            dependency_path = root / "dependencies.json"
            _write_json(
                dependency_path,
                {
                    name: importlib.metadata.version(name)
                    for name in ("mlflow-skinny", "numpy", "scikit-learn", "skops")
                },
            )
            mlflow.log_artifacts(str(root), artifact_path="evidence")
            for evaluation in result.evaluations:
                key = f"{evaluation.task}_{evaluation.model_name}"
                with mlflow.start_run(run_name=key, nested=True) as child:
                    mlflow.set_tags(
                        {
                            **common_tags,
                            "run_role": "model",
                            "task": evaluation.task,
                            "model_name": evaluation.model_name,
                            "eligible": str(evaluation.eligible).lower(),
                        }
                    )
                    mlflow.log_params(
                        {
                            "model_config_version": MODEL_CONFIG_VERSION,
                            "seed": result.split_manifest.seed,
                            "feature_columns": ",".join(FEATURE_COLUMNS),
                            "target": (
                                "rul"
                                if evaluation.task == "regression"
                                else "failure_risk_30"
                            ),
                            "threshold": (
                                "none" if evaluation.task == "regression" else "0.5"
                            ),
                            "estimator": (
                                "DummyRegressor(strategy=median)"
                                if key == "regression_dummy"
                                else "StandardScaler+Ridge(alpha=1.0)"
                                if key == "regression_candidate"
                                else "DummyClassifier(strategy=prior)"
                                if key == "classification_dummy"
                                else (
                                    "StandardScaler+LogisticRegression("
                                    "class_weight=balanced,solver=liblinear,"
                                    "max_iter=1000)"
                                )
                            ),
                            "validation_prediction_digest": (
                                evaluation.validation_prediction_digest
                            ),
                            "test_prediction_digest": evaluation.test_prediction_digest,
                        }
                    )
                    metrics: dict[str, float] = {}
                    _flatten_metrics(
                        "validation", evaluation.validation_metrics, metrics
                    )
                    _flatten_metrics("test", evaluation.test_metrics, metrics)
                    mlflow.log_metrics(metrics)
                    child_report = root / f"{key}.json"
                    _write_json(child_report, evaluation.to_dict())
                    mlflow.log_artifact(str(child_report), artifact_path="evidence")
                    digest = _log_model_artifact(result.models[key], root, key)
                    mlflow.set_tag("model_artifact_sha256", digest)
                    child_run_ids[key] = child.info.run_id
            return TrackingResult(
                experiment.experiment_id, parent.info.run_id, child_run_ids
            )


def _trusted_types(model_path: Path) -> list[str]:
    unknown = sorted(sio.get_untrusted_types(file=model_path))
    prohibited = [
        item for item in unknown if not item.startswith(_TRUSTED_TYPE_PREFIXES)
    ]
    if prohibited:
        raise ModelingError(
            "model.untrusted_type", "Model artifact contains a prohibited type."
        )
    return unknown


def load_verified_model(
    run_id: str,
    *,
    tracking_uri: str,
    feature_snapshot_id: str,
    split_id: str,
    download_root: Path,
) -> Any:
    """Verify run ownership, digest, signature, and types before skops loading."""
    if not tracking_uri.startswith("http://127.0.0.1:"):
        raise ModelingError(
            "tracking.non_loopback", "Phase 4 MLflow must use IPv4 loopback."
        )
    client = MlflowClient(tracking_uri=tracking_uri)
    run = client.get_run(run_id)
    expected_tags = {
        "phase": "4",
        "run_role": "model",
        "feature_snapshot_id": feature_snapshot_id,
        "split_id": split_id,
    }
    if any(run.data.tags.get(key) != value for key, value in expected_tags.items()):
        raise ModelingError("model.provenance", "MLflow run provenance does not match.")
    local = Path(
        client.download_artifacts(run_id, "model", dst_path=str(download_root))
    )
    model_path = local / "model.skops"
    metadata_path = local / "MLmodel"
    expected_digest = run.data.tags.get("model_artifact_sha256", "")
    if not expected_digest or sha256_bytes(model_path.read_bytes()) != expected_digest:
        raise ModelingError("model.artifact_identity", "Model digest does not match.")
    metadata = Model.load(metadata_path)
    if metadata.signature is None or metadata.signature.inputs is None:
        raise ModelingError("model.signature_missing", "Model signature is missing.")
    inputs = metadata.signature.inputs.inputs
    names = tuple(item.name for item in inputs)
    if names != FEATURE_COLUMNS or any(
        str(item.type) != "DataType.double" for item in inputs
    ):
        raise ModelingError("model.signature_columns", "Stored signature is invalid.")
    return sio.load(model_path, trusted=_trusted_types(model_path))
