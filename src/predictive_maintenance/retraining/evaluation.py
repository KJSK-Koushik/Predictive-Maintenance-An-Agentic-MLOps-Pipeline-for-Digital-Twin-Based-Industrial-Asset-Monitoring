"""Fixed champion/challenger comparison with explicit promotion denial."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from predictive_maintenance.modeling.comparison import _whole_engine_bootstrap
from predictive_maintenance.modeling.metrics import (
    classification_metrics,
    regression_metrics,
)
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


def evaluate_challenger(
    request: CandidateRequest,
    evidence: pd.DataFrame,
    *,
    challenger_artifact_sha256: str,
    source_partition: str,
    gate_checks: Mapping[str, bool] | None = None,
) -> ChallengerEvaluation:
    """Apply the fixed Phase 5 metrics and guards to aligned row predictions."""
    if source_partition == "test":
        raise MonitoringError(
            "evaluation.test_fit_prohibited",
            "NASA test rows cannot be used as challenger training evidence.",
        )
    columns = (
        "engine_id",
        "cycle",
        "rul",
        "failure_risk_30",
        "champion_rul_cycles",
        "challenger_rul_cycles",
        "champion_failure_risk_probability",
        "challenger_failure_risk_probability",
    )
    if tuple(evidence.columns) != columns or evidence.empty:
        raise MonitoringError(
            "evaluation.invalid_contract", "Challenger evidence contract is invalid."
        )
    keys = evidence.loc[:, ["engine_id", "cycle"]]
    if bool(keys.duplicated().any()):
        raise MonitoringError(
            "evaluation.duplicate_key", "Evaluation requires unique engine/cycle keys."
        )
    values = evidence.to_numpy(dtype="float64")
    if not bool(np.isfinite(values).all()) or bool((values < 0).any()):
        raise MonitoringError(
            "evaluation.invalid_loss",
            "Evaluation losses must be finite and non-negative.",
        )
    if (
        not bool(np.equal(values[:, :2], np.floor(values[:, :2])).all())
        or bool((values[:, :2] <= 0).any())
        or keys["engine_id"].nunique() < 3
        or not bool(np.isin(values[:, 3], [0, 1]).all())
        or len(np.unique(values[:, 3])) != 2
        or not bool((values[:, 6:] <= 1).all())
    ):
        raise MonitoringError(
            "evaluation.invalid_contract",
            "Evaluation keys, labels, or probabilities are invalid.",
        )
    champion_regression = regression_metrics(
        keys, values[:, 2], values[:, 4], clipped_count=0
    )
    challenger_regression = regression_metrics(
        keys, values[:, 2], values[:, 5], clipped_count=0
    )
    champion_classification = classification_metrics(keys, values[:, 3], values[:, 6])
    challenger_classification = classification_metrics(keys, values[:, 3], values[:, 7])
    regression_bootstrap = _whole_engine_bootstrap(
        "regression", keys, values[:, 2], values[:, 4], values[:, 5]
    )
    classification_bootstrap = _whole_engine_bootstrap(
        "classification", keys, values[:, 3], values[:, 6], values[:, 7]
    )
    regression_improvement = regression_bootstrap.point_improvement
    classification_improvement = classification_bootstrap.point_improvement
    regression_interval = (regression_bootstrap.lower_95, regression_bootstrap.upper_95)
    classification_interval = (
        classification_bootstrap.lower_95,
        classification_bootstrap.upper_95,
    )
    supplied_checks = dict(gate_checks or {})
    unknown_checks = supplied_checks.keys() - _REQUIRED_GATE_CHECKS
    if unknown_checks:
        raise MonitoringError(
            "evaluation.unknown_check", "Evaluation contains an unknown gate check."
        )
    governed_checks = {
        name: supplied_checks.get(name, False) for name in sorted(_REQUIRED_GATE_CHECKS)
    }
    checks = {
        **governed_checks,
        "identical_engine_groups": True,
        "nasa_test_excluded_from_fit": True,
        "regression_guardrail": (
            regression_improvement >= 0.03 * champion_regression["engine_balanced_rmse"]
            and regression_interval[0] > 0
            and challenger_regression["engine_balanced_mae"]
            <= 1.05 * champion_regression["engine_balanced_mae"]
            and challenger_regression["engine_balanced_nasa_score"]
            <= 1.05 * champion_regression["engine_balanced_nasa_score"]
        ),
        "classification_guardrail": (
            classification_improvement >= 0.005
            and classification_interval[0] > 0
            and challenger_classification["engine_balanced_brier_score"]
            <= champion_classification["engine_balanced_brier_score"] + 0.01
        ),
        "promotion_path_absent": True,
    }
    if np.array_equal(values[:, 4], values[:, 5]) and np.array_equal(
        values[:, 6], values[:, 7]
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
