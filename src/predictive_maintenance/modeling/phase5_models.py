"""Versioned contracts for the bounded Phase 5 research comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from predictive_maintenance.modeling.models import canonical_json_bytes, sha256_bytes

COMPARISON_CONTRACT_VERSION = "fd001-nested-engine-comparison-v1"
SEARCH_SPACE_VERSION = "fd001-hist-gradient-boosting-search-v1"
SELECTION_CONTRACT_VERSION = "fd001-locked-selection-v1"
ANALYSIS_CONTRACT_VERSION = "fd001-exploratory-analysis-v1"
OUTER_FOLDS = 5
INNER_FOLDS = 4
BOOTSTRAP_SAMPLES = 2_000
CLUSTER_SEEDS = (42, 43, 44)
CLUSTER_COUNTS = (2, 3, 4, 5, 6)

PreferredModel = Literal["baseline", "advanced"]


@dataclass(frozen=True, slots=True)
class InnerFold:
    """One engine-disjoint inner tuning fold."""

    train_engine_ids: tuple[int, ...]
    validation_engine_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class OuterFold:
    """One outer evaluation fold and its inner tuning folds."""

    index: int
    train_engine_ids: tuple[int, ...]
    validation_engine_ids: tuple[int, ...]
    inner_folds: tuple[InnerFold, ...]


@dataclass(frozen=True, slots=True)
class ComparisonManifest:
    """Canonical nested engine-fold evidence for Phase 5."""

    feature_snapshot_id: str
    processed_snapshot_id: str
    raw_snapshot_id: str
    phase4_split_id: str
    seed: int
    feature_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    engine_ids: tuple[int, ...]
    row_count: int
    numpy_version: str
    sklearn_version: str
    search_space_version: str
    outer_folds: tuple[OuterFold, ...]
    final_inner_folds: tuple[InnerFold, ...]
    comparison_contract_version: str = COMPARISON_CONTRACT_VERSION

    def identity_dict(self) -> dict[str, Any]:
        """Return the exact fields bound by this manifest."""
        return asdict(self)

    @property
    def comparison_id(self) -> str:
        """Return the SHA-256 identity of canonical manifest fields."""
        return sha256_bytes(canonical_json_bytes(self.identity_dict()))

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready manifest evidence including its identity."""
        return {"comparison_id": self.comparison_id, **self.identity_dict()}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored bytes."""
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """Paired whole-engine model-difference uncertainty."""

    point_improvement: float
    lower_95: float
    upper_95: float
    samples: int = BOOTSTRAP_SAMPLES
    uncertainty_kind: str = "paired_whole_engine_evaluation_uncertainty"


@dataclass(frozen=True, slots=True)
class TaskComparison:
    """Development-only baseline versus advanced evidence for one task."""

    task: Literal["regression", "classification"]
    baseline_metrics: dict[str, Any]
    advanced_metrics: dict[str, Any]
    baseline_prediction_digest: str
    advanced_prediction_digest: str
    outer_selected_parameters: tuple[dict[str, Any], ...]
    final_parameters: dict[str, Any]
    interval: BootstrapInterval
    guardrails: dict[str, bool]
    advanced_preferred: bool
    preferred_model: PreferredModel
    baseline_coefficients: dict[str, float]
    advanced_permutation_importance: dict[str, float]
    feature_rank_stability: float
    error_analysis: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return bounded JSON-ready comparison evidence."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SelectionRecord:
    """Immutable development decision required before benchmark access."""

    feature_snapshot_id: str
    processed_snapshot_id: str
    raw_snapshot_id: str
    phase4_split_id: str
    comparison_id: str
    search_space_version: str
    regression_model: PreferredModel
    regression_parameters: dict[str, Any]
    classification_model: PreferredModel
    classification_parameters: dict[str, Any]
    regression_prediction_digest: str
    classification_prediction_digest: str
    test_exposure_status: str = "previously_observed_in_phase_4"
    locked: bool = True
    selection_contract_version: str = SELECTION_CONTRACT_VERSION

    def identity_dict(self) -> dict[str, Any]:
        """Return exact immutable decision fields."""
        return asdict(self)

    @property
    def selection_id(self) -> str:
        """Return the SHA-256 identity of the locked decision."""
        return sha256_bytes(canonical_json_bytes(self.identity_dict()))

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready selection evidence including identity."""
        return {"selection_id": self.selection_id, **self.identity_dict()}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored bytes."""
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class ClusterAnalysis:
    """Bounded label-free exploratory telemetry-state evidence."""

    supported: bool
    selected_cluster_count: int | None
    pca_components: int
    sampled_rows: int
    maximum_rows_per_engine: int
    candidates: tuple[dict[str, Any], ...]
    lifecycle_association: dict[str, Any]
    claim: str = "exploratory_telemetry_states_not_ground_truth_health_states"


@dataclass(frozen=True, slots=True)
class NoveltyAnalysis:
    """Bounded label-independent novelty-score evidence."""

    reference_rows: int
    early_lifecycle_fraction: float
    seed_stability: float
    lifecycle_scores: dict[str, Any]
    score_digest: str
    claim: str = "novelty_score_without_ground_truth_anomaly_labels"


@dataclass(frozen=True, slots=True)
class DevelopmentResult:
    """Complete Phase 5 evidence produced without benchmark inputs."""

    manifest: ComparisonManifest
    comparisons: tuple[TaskComparison, ...]
    selection: SelectionRecord
    clustering: ClusterAnalysis
    novelty: NoveltyAnalysis

    def comparison(
        self, task: Literal["regression", "classification"]
    ) -> TaskComparison:
        """Return one exact task comparison."""
        for item in self.comparisons:
            if item.task == task:
                return item
        raise ValueError(f"Missing Phase 5 comparison for {task}.")


@dataclass(frozen=True, slots=True)
class BenchmarkTaskResult:
    """One locked selected model evaluated on the known NASA benchmark."""

    task: Literal["regression", "classification"]
    selected_model: PreferredModel
    metrics: dict[str, Any]
    prediction_digest: str


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Separate locked benchmark result and fitted selected models."""

    selection_id: str
    feature_snapshot_id: str
    evaluations: tuple[BenchmarkTaskResult, ...]
    models: dict[str, Any]
    test_exposure_status: str = "previously_observed_in_phase_4"

    def evaluation(
        self, task: Literal["regression", "classification"]
    ) -> BenchmarkTaskResult:
        """Return one exact benchmark task result."""
        for item in self.evaluations:
            if item.task == task:
                return item
        raise ValueError(f"Missing benchmark evaluation for {task}.")


@dataclass(frozen=True, slots=True)
class Phase5Result:
    """Development and separately executed locked benchmark evidence."""

    development: DevelopmentResult
    benchmark: BenchmarkResult


@dataclass(frozen=True, slots=True)
class Phase5TrackingResult:
    """MLflow identifiers for explicit Phase 5 evidence logging."""

    experiment_id: str
    parent_run_id: str
    child_run_ids: dict[str, str]
