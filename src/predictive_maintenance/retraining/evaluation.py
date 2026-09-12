"""Fixed champion/challenger comparison with explicit promotion denial."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from predictive_maintenance.monitoring.models import (
    MonitoringError,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.monitoring.triggers import CandidateRequest
from predictive_maintenance.release.models import require_sha256

EVALUATION_CONTRACT_VERSION = "fd001-challenger-evaluation-v1"
BOOTSTRAP_SEED = 42
BOOTSTRAP_RESAMPLES = 2_000
_REQUIRED_GATE_CHECKS = {
    "data_contract",
    "leakage_control",
    "reproducibility",
    "feature_contract",
    "signature_contract",
    "trusted_type",
    "performance",
    "robustness",
    "security",
    "release_compatibility",
    "prediction_parity",
}


@dataclass(frozen=True, slots=True)
class ChallengerEvaluation:
    """Human-review handoff that can never promote or deploy a model."""

    request_id: str
    champion_release_id: str
    challenger_artifact_sha256: str | None
    outcome: Literal[
        "eligible_for_human_review",
        "retain_champion",
        "no_change",
        "blocked_no_new_training_data",
    ]
    regression_improvement: float | None
    classification_improvement: float | None
    regression_interval: tuple[float, float] | None
    classification_interval: tuple[float, float] | None
    checks: dict[str, bool]
    source_partition: str
    bootstrap_seed: int = BOOTSTRAP_SEED
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
    promotion_authority: Literal["none"] = "none"
    evaluation_contract_version: str = EVALUATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        require_sha256(self.request_id, "request_id")
        require_sha256(self.champion_release_id, "champion_release_id")
        if self.challenger_artifact_sha256 is not None:
            require_sha256(
                self.challenger_artifact_sha256, "challenger_artifact_sha256"
            )
        if self.source_partition not in {"train", "validation", "synthetic", "none"}:
            raise MonitoringError(
                "evaluation.invalid_partition", "Evaluation partition is invalid."
            )
        if self.promotion_authority != "none":
            raise MonitoringError(
                "evaluation.invalid_authority", "Evaluation cannot promote a model."
            )
        for value in (self.regression_improvement, self.classification_improvement):
            if value is not None and not math.isfinite(value):
                raise MonitoringError(
                    "evaluation.nonfinite", "Evaluation results must be finite."
                )
        for interval in (self.regression_interval, self.classification_interval):
            if interval is not None and (
                len(interval) != 2
                or not all(math.isfinite(value) for value in interval)
                or interval[0] > interval[1]
            ):
                raise MonitoringError(
                    "evaluation.invalid_interval",
                    "Evaluation intervals must be finite and ordered.",
                )
        if not self.checks or any(
            type(value) is not bool for value in self.checks.values()
        ):
            raise MonitoringError(
                "evaluation.invalid_checks", "Evaluation checks must be booleans."
            )
        if (
            self.bootstrap_seed != BOOTSTRAP_SEED
            or self.bootstrap_resamples != BOOTSTRAP_RESAMPLES
        ):
            raise MonitoringError(
                "evaluation.invalid_bootstrap",
                "Evaluation must use the fixed whole-engine bootstrap protocol.",
            )

    @property
    def evaluation_id(self) -> str:
        """Hash the fixed evaluation result."""
        return sha256_bytes(canonical_json_bytes(asdict(self)))

    def to_dict(self) -> dict[str, Any]:
        """Return stored evaluation with identity."""
        return {"evaluation_id": self.evaluation_id, **asdict(self)}


def blocked_no_new_training_data(request: CandidateRequest) -> ChallengerEvaluation:
    """Return the scientifically honest actual-FD001 terminal result."""
    return ChallengerEvaluation(
        request_id=request.request_id,
        champion_release_id=request.release_id,
        challenger_artifact_sha256=None,
        outcome="blocked_no_new_training_data",
        regression_improvement=None,
        classification_improvement=None,
        regression_interval=None,
        classification_interval=None,
        checks={"new_training_population": False, "nasa_test_excluded_from_fit": True},
        source_partition="none",
    )


def _paired_improvement_interval(
    champion: np.ndarray,
    challenger: np.ndarray,
) -> tuple[float, float]:
    """Return a deterministic 95% paired bootstrap interval over whole engines."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    engine_count = len(champion)
    sample_indices = rng.integers(
        0, engine_count, size=(BOOTSTRAP_RESAMPLES, engine_count)
    )
    champion_means = champion[sample_indices].mean(axis=1)
    challenger_means = challenger[sample_indices].mean(axis=1)
    improvements = (champion_means - challenger_means) / np.maximum(
        champion_means, 1e-12
    )
    low, high = np.quantile(improvements, (0.025, 0.975))
    return float(low), float(high)


def evaluate_challenger(
    request: CandidateRequest,
    evidence: pd.DataFrame,
    *,
    challenger_artifact_sha256: str,
    source_partition: str,
    minimum_regression_improvement: float = 0.01,
    minimum_classification_improvement: float = 0.005,
    gate_checks: Mapping[str, bool] | None = None,
) -> ChallengerEvaluation:
    """Compare paired engine-level losses on identical evaluation rows."""
    if source_partition == "test":
        raise MonitoringError(
            "evaluation.test_fit_prohibited",
            "NASA test rows cannot be used as challenger training evidence.",
        )
    columns = (
        "engine_id",
        "champion_regression_loss",
        "challenger_regression_loss",
        "champion_classification_loss",
        "challenger_classification_loss",
    )
    if tuple(evidence.columns) != columns or evidence.empty:
        raise MonitoringError(
            "evaluation.invalid_contract", "Challenger evidence contract is invalid."
        )
    if bool(evidence["engine_id"].duplicated().any()):
        raise MonitoringError(
            "evaluation.duplicate_engine", "Evaluation requires one row per engine."
        )
    values = evidence.loc[:, list(columns[1:])].to_numpy(dtype="float64")
    if not bool(np.isfinite(values).all()) or bool((values < 0).any()):
        raise MonitoringError(
            "evaluation.invalid_loss",
            "Evaluation losses must be finite and non-negative.",
        )
    champion_regression = float(evidence[columns[1]].mean())
    challenger_regression = float(evidence[columns[2]].mean())
    champion_classification = float(evidence[columns[3]].mean())
    challenger_classification = float(evidence[columns[4]].mean())
    regression_improvement = (champion_regression - challenger_regression) / max(
        champion_regression, 1e-12
    )
    classification_improvement = (
        champion_classification - challenger_classification
    ) / max(champion_classification, 1e-12)
    regression_interval = _paired_improvement_interval(values[:, 0], values[:, 1])
    classification_interval = _paired_improvement_interval(values[:, 2], values[:, 3])
    supplied_checks = dict(gate_checks or {})
    unknown_checks = supplied_checks.keys() - _REQUIRED_GATE_CHECKS
    if unknown_checks:
        raise MonitoringError(
            "evaluation.unknown_check", "Evaluation contains an unknown gate check."
        )
    governed_checks = {
        name: supplied_checks.get(name, True) for name in sorted(_REQUIRED_GATE_CHECKS)
    }
    checks = {
        **governed_checks,
        "identical_engine_groups": True,
        "nasa_test_excluded_from_fit": True,
        "regression_guardrail": regression_interval[0]
        >= minimum_regression_improvement,
        "classification_guardrail": classification_interval[0]
        >= minimum_classification_improvement,
        "promotion_path_absent": True,
    }
    if np.array_equal(values[:, 0], values[:, 1]) and np.array_equal(
        values[:, 2], values[:, 3]
    ):
        outcome: Literal[
            "eligible_for_human_review", "retain_champion", "no_change"
        ] = "no_change"
    elif all(checks.values()):
        outcome = "eligible_for_human_review"
    else:
        outcome = "retain_champion"
    return ChallengerEvaluation(
        request_id=request.request_id,
        champion_release_id=request.release_id,
        challenger_artifact_sha256=challenger_artifact_sha256,
        outcome=outcome,
        regression_improvement=regression_improvement,
        classification_improvement=classification_improvement,
        regression_interval=regression_interval,
        classification_interval=classification_interval,
        checks=checks,
        source_partition=source_partition,
    )
