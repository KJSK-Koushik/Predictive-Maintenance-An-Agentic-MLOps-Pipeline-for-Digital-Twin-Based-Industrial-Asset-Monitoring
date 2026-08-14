"""Versioned contracts for Phase 4 training and evaluation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd

from predictive_maintenance.data.contract import SENSOR_COLUMNS, SETTING_COLUMNS

FEATURE_COLUMNS = SETTING_COLUMNS + SENSOR_COLUMNS
KEY_COLUMNS = ("engine_id", "cycle")
TARGET_COLUMNS = ("rul", "failure_risk_30")
SPLIT_CONTRACT_VERSION = "fd001-engine-split-v1"
MODEL_CONFIG_VERSION = "fd001-linear-baselines-v1"
EVALUATION_PROTOCOL_VERSION = "fd001-baseline-evaluation-v1"
RANDOM_SEED = 42
RISK_THRESHOLD = 0.5

Task = Literal["regression", "classification"]
Partition = Literal["train", "validation", "test"]
ModelName = Literal["dummy", "candidate"]

_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.]{2,99}$")


class ModelingError(Exception):
    """Stable, bounded modeling failure safe for reports and logs."""

    def __init__(self, code: str, message: str) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError(
                "Modeling error codes must be stable lowercase identifiers."
            )
        bounded = message[:1000]
        super().__init__(f"{code}: {bounded}")
        self.code = code
        self.message = bounded

    def to_dict(self) -> dict[str, str]:
        """Return a sanitized JSON representation."""
        return {"code": self.code, "message": self.message}


def canonical_json_bytes(value: object) -> bytes:
    """Encode one finite, canonical JSON representation."""
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise ModelingError(
            "serialization.invalid_json", "Modeling evidence must be finite JSON."
        ) from error
    return (text + "\n").encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class TrainingDataset:
    """Verified Phase 3 features and targets with immutable lineage."""

    raw_snapshot_id: str
    processed_snapshot_id: str
    feature_snapshot_id: str
    train_features: pd.DataFrame
    train_targets: pd.DataFrame
    test_features: pd.DataFrame
    test_targets: pd.DataFrame


@dataclass(frozen=True, slots=True)
class PartitionSummary:
    """Aggregate split evidence without row-level telemetry."""

    source_partition: str
    engine_ids: tuple[int, ...]
    row_count: int
    failure_risk_prevalence: float


@dataclass(frozen=True, slots=True)
class SplitManifest:
    """Canonical engine-disjoint split shared by both tasks."""

    feature_snapshot_id: str
    processed_snapshot_id: str
    raw_snapshot_id: str
    seed: int
    feature_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    numpy_version: str
    sklearn_version: str
    train: PartitionSummary
    validation: PartitionSummary
    test: PartitionSummary
    split_contract_version: str = SPLIT_CONTRACT_VERSION

    def identity_dict(self) -> dict[str, Any]:
        """Return exactly the fields that determine split identity."""
        return asdict(self)

    @property
    def split_id(self) -> str:
        """Hash the canonical manifest fields."""
        return sha256_bytes(canonical_json_bytes(self.identity_dict()))

    def to_dict(self) -> dict[str, Any]:
        """Return stored manifest fields including the derived identity."""
        return {"split_id": self.split_id, **self.identity_dict()}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored bytes."""
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class Evaluation:
    """One bounded aggregate model evaluation."""

    task: Task
    model_name: ModelName
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    validation_prediction_digest: str
    test_prediction_digest: str
    eligible: bool

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready aggregate evidence."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Complete four-model Phase 4 result with shared provenance."""

    split_manifest: SplitManifest
    evaluations: tuple[Evaluation, ...]
    models: dict[str, Any]

    def evaluation(self, task: Task, model_name: ModelName) -> Evaluation:
        """Return one exact evaluation or fail closed."""
        for item in self.evaluations:
            if item.task == task and item.model_name == model_name:
                return item
        raise ModelingError("evaluation.missing", "Expected evaluation is missing.")


@dataclass(frozen=True, slots=True)
class TrackingResult:
    """Run identifiers returned after explicit MLflow logging."""

    experiment_id: str
    parent_run_id: str
    child_run_ids: dict[str, str]
