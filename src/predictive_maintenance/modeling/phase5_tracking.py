"""Explicit local MLflow evidence for the Phase 5 research comparison."""

from __future__ import annotations

import importlib.metadata
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import skops.io as sio  # type: ignore[import-untyped]
from mlflow.models import Model
from mlflow.tracking import MlflowClient

from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    ModelingError,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.modeling.phase5_models import (
    ANALYSIS_CONTRACT_VERSION,
    SEARCH_SPACE_VERSION,
    Phase5Result,
    Phase5TrackingResult,
)
from predictive_maintenance.modeling.tracking import (
    _flatten_metrics,
    _log_model_artifact,
    _trusted_types,
    mlflow,
)

EXPERIMENT_NAME = "fd001-phase-5-advanced-analysis"


def _write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def log_phase5_result(
    result: Phase5Result,
    *,
    tracking_uri: str,
    code_revision: str,
    dirty_worktree: bool,
) -> Phase5TrackingResult:
    """Log bounded development and benchmark evidence without registry actions."""
    if not tracking_uri.startswith("http://127.0.0.1:"):
        raise ModelingError(
            "tracking.non_loopback", "Phase 5 MLflow must use IPv4 loopback."
        )
    os.environ["MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT"] = "true"
    mlflow.set_tracking_uri(tracking_uri)
    experiment = mlflow.set_experiment(EXPERIMENT_NAME)
    development = result.development
    benchmark = result.benchmark
    common_tags = {
        "phase": "5",
        "run_role": "parent",
        "feature_snapshot_id": development.manifest.feature_snapshot_id,
        "comparison_id": development.manifest.comparison_id,
        "selection_id": development.selection.selection_id,
        "test_exposure_status": benchmark.test_exposure_status,
    }
    child_ids: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="phase5-mlflow-") as temporary:
        root = Path(temporary)
        development_report = root / "development_report.json"
        benchmark_report = root / "benchmark_report.json"
        _write(
            development_report,
            {
                "comparisons": [item.to_dict() for item in development.comparisons],
                "clustering": asdict(development.clustering),
                "novelty": asdict(development.novelty),
            },
        )
        _write(
            benchmark_report,
            {
                "selection_id": benchmark.selection_id,
                "test_exposure_status": benchmark.test_exposure_status,
                "evaluations": [asdict(item) for item in benchmark.evaluations],
            },
        )
        evidence_tags = {
            "development_evidence_sha256": sha256_bytes(
                development_report.read_bytes()
            ),
            "benchmark_evidence_sha256": sha256_bytes(benchmark_report.read_bytes()),
        }
        with mlflow.start_run(run_name="fd001-phase5-evaluation") as parent:
            mlflow.set_tags({**common_tags, **evidence_tags})
            mlflow.log_params(
                {
                    "search_space_version": SEARCH_SPACE_VERSION,
                    "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
                    "seed": development.manifest.seed,
                    "code_revision": code_revision,
                    "dirty_worktree": str(dirty_worktree).lower(),
                    "feature_count": len(FEATURE_COLUMNS),
                    "registry_action": "none",
                }
            )
            (root / "comparison_manifest.json").write_bytes(
                development.manifest.canonical_bytes()
            )
            (root / "selection_record.json").write_bytes(
                development.selection.canonical_bytes()
            )
            _write(
                root / "dependencies.json",
                {
                    name: importlib.metadata.version(name)
                    for name in ("mlflow-skinny", "numpy", "scikit-learn", "skops")
                },
            )
            mlflow.log_artifacts(str(root), artifact_path="evidence")
            for comparison in development.comparisons:
                task = comparison.task
                key = f"{task}_selected"
                benchmark_item = benchmark.evaluation(task)
                with mlflow.start_run(run_name=key, nested=True) as child:
                    mlflow.set_tags(
                        {
                            **common_tags,
                            **evidence_tags,
                            "run_role": "model",
                            "task": task,
                            "selected_model": comparison.preferred_model,
                        }
                    )
                    mlflow.log_params(
                        {
                            "search_space_version": SEARCH_SPACE_VERSION,
                            "selected_parameters": canonical_json_bytes(
                                comparison.final_parameters
                                if comparison.advanced_preferred
                                else {}
                            )
                            .decode("ascii")
                            .strip(),
                            "development_prediction_digest": (
                                comparison.advanced_prediction_digest
                                if comparison.advanced_preferred
                                else comparison.baseline_prediction_digest
                            ),
                            "benchmark_prediction_digest": (
                                benchmark_item.prediction_digest
                            ),
                            "threshold": "0.5" if task == "classification" else "none",
                        }
                    )
                    metrics: dict[str, float] = {}
                    _flatten_metrics(
                        "development.baseline", comparison.baseline_metrics, metrics
                    )
                    _flatten_metrics(
                        "development.advanced", comparison.advanced_metrics, metrics
                    )
                    _flatten_metrics("benchmark", benchmark_item.metrics, metrics)
                    metrics.update(
                        {
                            "comparison.improvement": (
                                comparison.interval.point_improvement
                            ),
                            "comparison.lower_95": comparison.interval.lower_95,
                            "comparison.upper_95": comparison.interval.upper_95,
                        }
                    )
                    mlflow.log_metrics(metrics)
                    digest = _log_model_artifact(
                        benchmark.models[key], root, f"phase5-{key}"
                    )
                    mlflow.set_tag("model_artifact_sha256", digest)
                    child_ids[key] = child.info.run_id
            return Phase5TrackingResult(
                experiment.experiment_id, parent.info.run_id, child_ids
            )


def load_verified_phase5_model(
    run_id: str,
    *,
    tracking_uri: str,
    feature_snapshot_id: str,
    comparison_id: str,
    selection_id: str,
    download_root: Path,
) -> Any:
    """Verify exact Phase 5 provenance, signature, digest, and trusted types."""
    if not tracking_uri.startswith("http://127.0.0.1:"):
        raise ModelingError(
            "tracking.non_loopback", "Phase 5 MLflow must use IPv4 loopback."
        )
    client = MlflowClient(tracking_uri=tracking_uri)
    run = client.get_run(run_id)
    expected_tags = {
        "phase": "5",
        "run_role": "model",
        "feature_snapshot_id": feature_snapshot_id,
        "comparison_id": comparison_id,
        "selection_id": selection_id,
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
    if tuple(item.name for item in inputs) != FEATURE_COLUMNS or any(
        str(item.type) != "DataType.double" for item in inputs
    ):
        raise ModelingError("model.signature_columns", "Stored signature is invalid.")
    return sio.load(model_path, trusted=_trusted_types(model_path))
