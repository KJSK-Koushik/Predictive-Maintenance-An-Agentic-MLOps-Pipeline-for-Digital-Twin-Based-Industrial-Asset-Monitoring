"""Phase 1 local FD001 ingestion workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from predictive_maintenance.data.contract import (
    RUL_FILENAME,
    TEST_FILENAME,
    TRAIN_FILENAME,
    ContractError,
)
from predictive_maintenance.data.exploration import build_exploration
from predictive_maintenance.data.integrity import Snapshot, create_snapshot
from predictive_maintenance.data.labels import (
    add_failure_risk,
    derive_test_rul,
    derive_train_rul,
)
from predictive_maintenance.data.parser import parse_telemetry, parse_terminal_rul
from predictive_maintenance.data.validation import ValidationReport, validate_fd001


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Accepted in-memory Phase 1 outputs and their raw identity."""

    snapshot: Snapshot
    validation: ValidationReport
    train: pd.DataFrame
    test: pd.DataFrame
    exploration: dict[str, Any]


def ingest_fd001(
    source_dir: Path,
    raw_root: Path,
    *,
    code_revision: str = "unknown",
) -> IngestionResult:
    """Verify, parse, validate, label, and profile the local FD001 source set."""
    snapshot = create_snapshot(
        source_dir,
        raw_root,
        code_revision=code_revision,
    )
    train = parse_telemetry(snapshot.path / TRAIN_FILENAME, TRAIN_FILENAME)
    test = parse_telemetry(snapshot.path / TEST_FILENAME, TEST_FILENAME)
    terminal_rul = parse_terminal_rul(snapshot.path / RUL_FILENAME, RUL_FILENAME)
    validation = validate_fd001(train, test, terminal_rul)
    if not validation.accepted:
        raise ContractError(
            "validation.snapshot_rejected",
            "FD001 failed its executable data contract.",
            details={"issues": [issue.rule_id for issue in validation.issues]},
        )
    train_labeled = add_failure_risk(derive_train_rul(train))
    test_labeled = add_failure_risk(derive_test_rul(test, terminal_rul))
    exploration = build_exploration(train_labeled, test_labeled)
    return IngestionResult(
        snapshot,
        validation,
        train_labeled,
        test_labeled,
        exploration,
    )
