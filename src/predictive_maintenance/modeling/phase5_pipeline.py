"""Phase 5 development and separately gated benchmark orchestration."""

from __future__ import annotations

from predictive_maintenance.modeling.advanced import DevelopmentInput
from predictive_maintenance.modeling.comparison import (
    development_input_from_dataset,
    run_locked_benchmark,
    run_supervised_development,
)
from predictive_maintenance.modeling.models import TrainingDataset
from predictive_maintenance.modeling.phase5_models import (
    DevelopmentResult,
    Phase5Result,
)
from predictive_maintenance.modeling.unsupervised import run_unsupervised_analysis


def run_phase5_development(data: DevelopmentInput) -> DevelopmentResult:
    """Produce all development evidence without accepting benchmark rows."""
    supervised = run_supervised_development(data)
    clustering, novelty = run_unsupervised_analysis(data)
    return DevelopmentResult(
        supervised.manifest,
        supervised.comparisons,
        supervised.selection,
        clustering,
        novelty,
    )


def run_phase5(dataset: TrainingDataset, *, phase4_split_id: str) -> Phase5Result:
    """Lock development first, then execute the separate known benchmark step."""
    development_input = development_input_from_dataset(
        dataset, phase4_split_id=phase4_split_id
    )
    development = run_phase5_development(development_input)
    benchmark = run_locked_benchmark(
        dataset, development.selection, phase4_split_id=phase4_split_id
    )
    return Phase5Result(development, benchmark)
