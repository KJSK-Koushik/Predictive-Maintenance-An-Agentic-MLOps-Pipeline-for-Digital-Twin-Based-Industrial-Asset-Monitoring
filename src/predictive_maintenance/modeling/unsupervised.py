"""Bounded exploratory telemetry-state clustering and novelty scoring."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans  # type: ignore[import-untyped]
from sklearn.decomposition import PCA  # type: ignore[import-untyped]
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    adjusted_rand_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from predictive_maintenance.modeling.advanced import DevelopmentInput, feature_matrix
from predictive_maintenance.modeling.metrics import prediction_digest
from predictive_maintenance.modeling.models import RANDOM_SEED, ModelingError
from predictive_maintenance.modeling.phase5_models import (
    CLUSTER_COUNTS,
    CLUSTER_SEEDS,
    ClusterAnalysis,
    NoveltyAnalysis,
)

MAXIMUM_ROWS_PER_ENGINE = 100
CLUSTER_STABILITY_THRESHOLD = 0.80
EARLY_LIFECYCLE_FRACTION = 0.20


def _balanced_positions(features: pd.DataFrame) -> np.ndarray:
    positions: list[int] = []
    for _, group in features.groupby("engine_id", sort=True):
        indexes = group.sort_values("cycle").index.to_numpy(dtype="int64")
        if len(indexes) > MAXIMUM_ROWS_PER_ENGINE:
            selected = np.linspace(
                0, len(indexes) - 1, MAXIMUM_ROWS_PER_ENGINE, dtype="int64"
            )
            indexes = indexes[selected]
        positions.extend(int(value) for value in indexes)
    return np.asarray(sorted(positions), dtype="int64")


def _mean_pairwise_stability(labels: list[np.ndarray]) -> float:
    scores = [
        float(adjusted_rand_score(left, right))
        for left, right in combinations(labels, 2)
    ]
    return float(np.mean(scores)) if scores else 1.0


def _canonical_labels(labels: np.ndarray, centers: np.ndarray) -> np.ndarray:
    order = np.argsort(centers[:, 0], kind="stable")
    mapping = {
        int(original): int(canonical) for canonical, original in enumerate(order)
    }
    return np.asarray([mapping[int(value)] for value in labels], dtype="int64")


def cluster_telemetry(data: DevelopmentInput) -> ClusterAnalysis:
    """Find stable training-only telemetry partitions without target selection."""
    positions = _balanced_positions(data.features)
    sampled_features = data.features.loc[positions].reset_index(drop=True)
    sampled_targets = data.targets.loc[positions].reset_index(drop=True)
    matrix = feature_matrix(sampled_features)
    scaled = StandardScaler().fit_transform(matrix)
    pca = PCA(n_components=0.95, svd_solver="full")
    projected = pca.fit_transform(scaled)
    candidates: list[dict[str, Any]] = []
    labels_by_count: dict[int, np.ndarray] = {}
    centers_by_count: dict[int, np.ndarray] = {}
    for count in CLUSTER_COUNTS:
        if count >= len(projected):
            continue
        label_runs: list[np.ndarray] = []
        silhouettes: list[float] = []
        for seed in CLUSTER_SEEDS:
            model = KMeans(n_clusters=count, n_init=10, random_state=seed)
            labels = np.asarray(model.fit_predict(projected), dtype="int64")
            label_runs.append(labels)
            silhouettes.append(
                float(
                    silhouette_score(
                        projected,
                        labels,
                        sample_size=min(2_000, len(projected)),
                        random_state=RANDOM_SEED,
                    )
                )
            )
            if seed == CLUSTER_SEEDS[0]:
                labels_by_count[count] = labels
                centers_by_count[count] = np.asarray(
                    model.cluster_centers_, dtype="float64"
                )
        candidates.append(
            {
                "cluster_count": count,
                "mean_silhouette": float(np.mean(silhouettes)),
                "mean_pairwise_adjusted_rand": _mean_pairwise_stability(label_runs),
            }
        )
    supported = [
        item
        for item in candidates
        if float(item["mean_pairwise_adjusted_rand"]) >= CLUSTER_STABILITY_THRESHOLD
    ]
    if not supported:
        return ClusterAnalysis(
            False,
            None,
            int(pca.n_components_),
            len(sampled_features),
            MAXIMUM_ROWS_PER_ENGINE,
            tuple(candidates),
            {},
        )
    winner = max(
        supported,
        key=lambda item: (float(item["mean_silhouette"]), -int(item["cluster_count"])),
    )
    selected = int(winner["cluster_count"])
    labels = _canonical_labels(labels_by_count[selected], centers_by_count[selected])
    rul = sampled_targets["rul"].to_numpy(dtype="float64")
    bands = {
        "near_0_30": rul <= 30,
        "middle_31_100": (rul >= 31) & (rul <= 100),
        "early_over_100": rul > 100,
    }
    association: dict[str, Any] = {}
    for name, mask in bands.items():
        if not bool(mask.any()):
            continue
        counts = np.bincount(labels[mask], minlength=selected)
        association[name] = {
            "row_count": int(mask.sum()),
            "cluster_fractions": [float(value / mask.sum()) for value in counts],
        }
    return ClusterAnalysis(
        True,
        selected,
        int(pca.n_components_),
        len(sampled_features),
        MAXIMUM_ROWS_PER_ENGINE,
        tuple(candidates),
        association,
    )


def _rank_correlation(left: np.ndarray, right: np.ndarray) -> float:
    left_rank = pd.Series(left).rank(method="average")
    right_rank = pd.Series(right).rank(method="average")
    value = left_rank.corr(right_rank, method="pearson")
    return 0.0 if pd.isna(value) else float(value)


def score_novelty(data: DevelopmentInput) -> NoveltyAnalysis:
    """Fit novelty models on first-20%-lifecycle reference telemetry only."""
    matrix = feature_matrix(data.features)
    maximum = data.features.groupby("engine_id")["cycle"].transform("max")
    fraction = data.features["cycle"].to_numpy(dtype="float64") / maximum.to_numpy(
        dtype="float64"
    )
    reference = fraction <= EARLY_LIFECYCLE_FRACTION
    if int(reference.sum()) < 2:
        raise ModelingError(
            "novelty.reference_rows", "Early-life novelty reference is too small."
        )
    scaler = StandardScaler().fit(matrix.loc[reference])
    scaled_reference = scaler.transform(matrix.loc[reference])
    scaled_all = scaler.transform(matrix)
    score_runs: list[np.ndarray] = []
    for seed in CLUSTER_SEEDS:
        detector = IsolationForest(
            n_estimators=100,
            contamination="auto",
            n_jobs=1,
            random_state=seed,
        )
        detector.fit(scaled_reference)
        score_runs.append(-np.asarray(detector.decision_function(scaled_all)))
    correlations = [
        _rank_correlation(left, right) for left, right in combinations(score_runs, 2)
    ]
    scores = score_runs[0]
    bands = {
        "early_0_20": fraction <= 0.20,
        "middle_20_80": (fraction > 0.20) & (fraction <= 0.80),
        "late_80_100": fraction > 0.80,
    }
    summaries = {
        name: {
            "row_count": int(mask.sum()),
            "mean": float(np.mean(scores[mask])),
            "median": float(np.median(scores[mask])),
            "p95": float(np.quantile(scores[mask], 0.95)),
        }
        for name, mask in bands.items()
        if bool(mask.any())
    }
    return NoveltyAnalysis(
        reference_rows=int(reference.sum()),
        early_lifecycle_fraction=EARLY_LIFECYCLE_FRACTION,
        seed_stability=float(np.mean(correlations)),
        lifecycle_scores=summaries,
        score_digest=prediction_digest(
            data.features.loc[:, ["engine_id", "cycle"]], scores
        ),
    )


def run_unsupervised_analysis(
    data: DevelopmentInput,
) -> tuple[ClusterAnalysis, NoveltyAnalysis]:
    """Run both bounded exploratory analyses on source-training rows."""
    return cluster_telemetry(data), score_novelty(data)
