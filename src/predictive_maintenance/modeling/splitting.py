"""Deterministic engine-level development split and final holdout."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import sklearn  # type: ignore[import-untyped]
from sklearn.model_selection import GroupShuffleSplit  # type: ignore[import-untyped]

from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    RANDOM_SEED,
    TARGET_COLUMNS,
    PartitionSummary,
    SplitManifest,
    TrainingDataset,
)


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    """Row frames selected by the one shared split manifest."""

    train_features: pd.DataFrame
    train_targets: pd.DataFrame
    validation_features: pd.DataFrame
    validation_targets: pd.DataFrame
    test_features: pd.DataFrame
    test_targets: pd.DataFrame


def _summary(
    source_partition: str,
    engine_ids: tuple[int, ...],
    features: pd.DataFrame,
    targets: pd.DataFrame,
) -> PartitionSummary:
    mask = features["engine_id"].isin(engine_ids)
    selected = targets.loc[mask, "failure_risk_30"]
    return PartitionSummary(
        source_partition=source_partition,
        engine_ids=engine_ids,
        row_count=int(mask.sum()),
        failure_risk_prevalence=float(selected.mean()),
    )


def create_split_manifest(
    dataset: TrainingDataset,
    *,
    seed: int = RANDOM_SEED,
) -> SplitManifest:
    """Split sorted source-training engines 80/20 with stable membership."""
    development_engines = np.array(
        sorted(dataset.train_features["engine_id"].unique()), dtype="int64"
    )
    if len(development_engines) < 5:
        raise ValueError("At least five development engines are required.")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_indexes, validation_indexes = next(
        splitter.split(development_engines, groups=development_engines)
    )
    train_engines = tuple(
        sorted(int(value) for value in development_engines[train_indexes])
    )
    validation_engines = tuple(
        sorted(int(value) for value in development_engines[validation_indexes])
    )
    test_engines = tuple(
        sorted(int(value) for value in dataset.test_features["engine_id"].unique())
    )
    if set(train_engines) & set(validation_engines):
        raise ValueError("Development engine groups overlap.")
    if set(train_engines) | set(validation_engines) != set(development_engines):
        raise ValueError("Development engine coverage is incomplete.")
    return SplitManifest(
        feature_snapshot_id=dataset.feature_snapshot_id,
        processed_snapshot_id=dataset.processed_snapshot_id,
        raw_snapshot_id=dataset.raw_snapshot_id,
        seed=seed,
        feature_columns=FEATURE_COLUMNS,
        target_columns=TARGET_COLUMNS,
        numpy_version=np.__version__,
        sklearn_version=sklearn.__version__,
        train=_summary(
            "train", train_engines, dataset.train_features, dataset.train_targets
        ),
        validation=_summary(
            "train",
            validation_engines,
            dataset.train_features,
            dataset.train_targets,
        ),
        test=_summary(
            "test", test_engines, dataset.test_features, dataset.test_targets
        ),
    )


def apply_split(dataset: TrainingDataset, manifest: SplitManifest) -> DatasetSplits:
    """Apply a manifest only to its exact snapshot lineage."""
    if (
        manifest.feature_snapshot_id != dataset.feature_snapshot_id
        or manifest.processed_snapshot_id != dataset.processed_snapshot_id
        or manifest.raw_snapshot_id != dataset.raw_snapshot_id
    ):
        raise ValueError("Split manifest does not belong to this dataset.")
    train_mask = dataset.train_features["engine_id"].isin(manifest.train.engine_ids)
    validation_mask = dataset.train_features["engine_id"].isin(
        manifest.validation.engine_ids
    )
    test_mask = dataset.test_features["engine_id"].isin(manifest.test.engine_ids)
    if bool((train_mask & validation_mask).any()):
        raise ValueError("Split rows overlap.")
    if int(train_mask.sum() + validation_mask.sum()) != len(dataset.train_features):
        raise ValueError("Development split does not cover every row exactly once.")
    if int(test_mask.sum()) != len(dataset.test_features):
        raise ValueError("Test split does not cover every row exactly once.")
    return DatasetSplits(
        dataset.train_features.loc[train_mask].reset_index(drop=True),
        dataset.train_targets.loc[train_mask].reset_index(drop=True),
        dataset.train_features.loc[validation_mask].reset_index(drop=True),
        dataset.train_targets.loc[validation_mask].reset_index(drop=True),
        dataset.test_features.loc[test_mask].reset_index(drop=True),
        dataset.test_targets.loc[test_mask].reset_index(drop=True),
    )
