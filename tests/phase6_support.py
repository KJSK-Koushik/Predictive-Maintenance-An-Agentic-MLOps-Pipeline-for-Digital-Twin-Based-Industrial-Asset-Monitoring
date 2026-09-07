"""Deterministic synthetic release support shared by Phase 6 tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn import (  # type: ignore[import-untyped]
    ensemble,
    linear_model,
    pipeline,
    preprocessing,
)

from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.release.gates import build_candidate_manifest
from predictive_maintenance.release.models import (
    CLASSIFICATION_REGISTERED_NAME,
    REGRESSION_REGISTERED_NAME,
    ApprovalDecision,
    ModelReference,
    ReleaseManifest,
)
from predictive_maintenance.release.packaging import package_release
from predictive_maintenance.release.trust import dump_deterministic, trusted_types


@dataclass(frozen=True, slots=True)
class SyntheticRelease:
    """Paths and identities for one approved synthetic bundle."""

    bundle: Path
    manifest: ReleaseManifest
    approval: ApprovalDecision
    observations: list[dict[str, Any]]
    expected_core: list[dict[str, float | int]]


def _training_frame() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rows = 80
    values = np.arange(rows * len(FEATURE_COLUMNS), dtype="float64").reshape(
        rows, len(FEATURE_COLUMNS)
    )
    values = values / 1000.0
    frame = pd.DataFrame(values, columns=list(FEATURE_COLUMNS), dtype="float64")
    rul = np.linspace(79.0, 0.0, rows, dtype="float64")
    risk = (rul <= 30.0).astype("int64")
    return frame, rul, risk


def build_synthetic_release(root: Path) -> SyntheticRelease:
    """Train tiny deterministic models and create an approval-gated bundle."""
    frame, rul, risk = _training_frame()
    regression = ensemble.HistGradientBoostingRegressor(
        learning_rate=0.08, max_iter=30, max_leaf_nodes=7, random_state=42
    ).fit(frame, rul)
    classification = pipeline.make_pipeline(
        preprocessing.StandardScaler(),
        linear_model.LogisticRegression(
            class_weight="balanced", solver="liblinear", max_iter=1000, random_state=42
        ),
    ).fit(frame, risk)
    model_root = root / "source-models"
    model_root.mkdir(parents=True)
    regression_path = model_root / "regression.skops"
    classification_path = model_root / "classification.skops"
    dump_deterministic(regression, regression_path)
    dump_deterministic(classification, classification_path)

    observation: dict[str, Any] = {"engine_id": 7, "cycle": 11}
    observation.update({name: float(frame.iloc[20][name]) for name in FEATURE_COLUMNS})
    fixture_frame = pd.DataFrame(
        [{name: observation[name] for name in FEATURE_COLUMNS}],
        columns=list(FEATURE_COLUMNS),
        dtype="float64",
    )
    rul_value = max(float(regression.predict(fixture_frame)[0]), 0.0)
    probability = float(classification.predict_proba(fixture_frame)[0, 1])
    expected_core: list[dict[str, float | int]] = [
        {
            "rul_cycles": rul_value,
            "failure_risk_probability": probability,
            "failure_risk_label": int(probability >= 0.5),
        }
    ]
    fixture = canonical_json_bytes(
        {
            "contract_version": "fd001-startup-parity-v1",
            "observations": [observation],
            "expected": expected_core,
        }
    )
    regression_ref = ModelReference(
        task="regression",
        registered_name=REGRESSION_REGISTERED_NAME,
        version="1",
        source_run_id="synthetic-regression-run",
        artifact_sha256=sha256_bytes(regression_path.read_bytes()),
        selected_family="histogram_gradient_boosting",
        selected_parameters={
            "learning_rate": 0.08,
            "max_iter": 30,
            "max_leaf_nodes": 7,
        },
        trusted_types=trusted_types(regression_path),
    )
    classification_ref = ModelReference(
        task="classification",
        registered_name=CLASSIFICATION_REGISTERED_NAME,
        version="1",
        source_run_id="synthetic-classification-run",
        artifact_sha256=sha256_bytes(classification_path.read_bytes()),
        selected_family="class_balanced_logistic_regression",
        selected_parameters={
            "class_weight": "balanced",
            "solver": "liblinear",
            "max_iter": 1000,
        },
        trusted_types=trusted_types(classification_path),
    )
    identities = {
        name: sha256_bytes(name.encode("ascii"))
        for name in (
            "feature",
            "processed",
            "raw",
            "split",
            "comparison",
            "selection",
            "lock",
        )
    }
    manifest = build_candidate_manifest(
        feature_snapshot_id=identities["feature"],
        processed_snapshot_id=identities["processed"],
        raw_snapshot_id=identities["raw"],
        split_id=identities["split"],
        comparison_id=identities["comparison"],
        selection_id=identities["selection"],
        regression=regression_ref,
        classification=classification_ref,
        verification_fixture_sha256=sha256_bytes(fixture),
        code_revision="phase6-synthetic-test",
        python_version="3.11",
        dependency_lock_sha256=identities["lock"],
    )
    decided = datetime.now(UTC)
    approval = ApprovalDecision(
        approval_request_id=manifest.approval_request_id,
        release_id=manifest.release_id,
        decision="approved",
        actor="KJSK-Koushik",
        reason="Synthetic test release only.",
        evidence_sha256=sha256_bytes(b"synthetic-approval"),
        decided_at=decided,
        expires_at=decided + timedelta(days=1),
    )
    bundle = package_release(
        manifest,
        approval,
        regression_model=regression_path,
        classification_model=classification_path,
        verification_fixture=fixture,
        output_root=root / "releases",
        now=decided + timedelta(minutes=1),
    )
    return SyntheticRelease(bundle, manifest, approval, [observation], expected_core)
