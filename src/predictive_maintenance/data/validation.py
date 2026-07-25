"""Pandera-backed schema and deterministic FD001 semantic validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
import pandera.pandas as pa

from predictive_maintenance.data.contract import (
    IDENTIFIER_COLUMNS,
    SENSOR_COLUMNS,
    SETTING_COLUMNS,
    TELEMETRY_COLUMNS,
)

TELEMETRY_SCHEMA = pa.DataFrameSchema(
    {
        "engine_id": pa.Column(pa.Int64, nullable=False),
        "cycle": pa.Column(pa.Int64, nullable=False),
        **{
            column: pa.Column(pa.Float64, nullable=False)
            for column in SETTING_COLUMNS + SENSOR_COLUMNS
        },
    },
    strict=True,
    ordered=True,
    coerce=False,
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One stable validation finding with bounded, sanitized examples."""

    rule_id: str
    message: str
    logical_file: str
    count: int
    examples: tuple[dict[str, Any], ...] = ()
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Machine-readable result for the complete FD001 source set."""

    accepted: bool
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def _row_examples(
    frame: pd.DataFrame, mask: pd.Series, columns: tuple[str, ...]
) -> tuple[dict[str, Any], ...]:
    examples: list[dict[str, Any]] = []
    for _, row in frame.loc[mask, list(columns)].head(5).iterrows():
        example: dict[str, Any] = {}
        for column in columns:
            value = row[column]
            example[column] = value.item() if hasattr(value, "item") else value
        examples.append(example)
    return tuple(examples)


def _issue(
    issues: list[ValidationIssue],
    rule_id: str,
    message: str,
    logical_file: str,
    mask: pd.Series,
    frame: pd.DataFrame,
    columns: tuple[str, ...] = IDENTIFIER_COLUMNS,
) -> None:
    count = int(mask.sum())
    if count:
        issues.append(
            ValidationIssue(
                rule_id,
                message,
                logical_file,
                count,
                _row_examples(frame, mask, columns),
            )
        )


def validate_telemetry(
    frame: pd.DataFrame, logical_file: str
) -> tuple[ValidationIssue, ...]:
    """Validate exact schema plus FD001 cycle semantics."""
    issues: list[ValidationIssue] = []
    if tuple(frame.columns) != TELEMETRY_COLUMNS:
        issues.append(
            ValidationIssue(
                "schema.column_order",
                "Telemetry columns do not match the ordered 26-column contract.",
                logical_file,
                1,
            )
        )
        return tuple(issues)

    for column in IDENTIFIER_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        invalid = numeric.isna() | ~np.isfinite(numeric) | (numeric % 1 != 0)
        _issue(
            issues,
            f"semantic.{column}_positive_integer",
            f"{column} must contain positive integers.",
            logical_file,
            invalid | (numeric <= 0),
            frame,
            (column,),
        )

    numeric_frame = frame.loc[:, TELEMETRY_COLUMNS].apply(
        pd.to_numeric, errors="coerce"
    )
    non_finite = ~np.isfinite(numeric_frame)
    if bool(non_finite.to_numpy().any()):
        locations = np.argwhere(non_finite.to_numpy())
        examples = tuple(
            {
                "row": int(row),
                "column": TELEMETRY_COLUMNS[int(column)],
            }
            for row, column in locations[:5]
        )
        issues.append(
            ValidationIssue(
                "schema.finite",
                "All telemetry values must be present and finite.",
                logical_file,
                int(non_finite.to_numpy().sum()),
                examples,
            )
        )

    try:
        TELEMETRY_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as error:
        issues.append(
            ValidationIssue(
                "schema.pandera",
                "Pandera rejected one or more telemetry schema checks.",
                logical_file,
                len(error.failure_cases),
            )
        )

    duplicate = frame.duplicated(["engine_id", "cycle"], keep=False)
    _issue(
        issues,
        "semantic.duplicate_engine_cycle",
        "(engine_id, cycle) keys must be unique.",
        logical_file,
        duplicate,
        frame,
    )

    prior_engine = frame["engine_id"].shift()
    prior_cycle = frame["cycle"].shift()
    same_engine = frame["engine_id"].eq(prior_engine)
    non_increasing = same_engine & frame["cycle"].le(prior_cycle)
    _issue(
        issues,
        "semantic.cycle_order",
        "Cycles must be strictly increasing in source row order per engine.",
        logical_file,
        non_increasing,
        frame,
    )

    cycle_gap = same_engine & frame["cycle"].ne(prior_cycle + 1)
    first_for_engine = ~same_engine
    bad_start = first_for_engine & frame["cycle"].ne(1)
    _issue(
        issues,
        "semantic.cycle_contiguous",
        "Each engine must start at cycle 1 and advance by one cycle.",
        logical_file,
        cycle_gap | bad_start,
        frame,
    )
    return tuple(issues)


def validate_fd001(
    train: pd.DataFrame,
    test: pd.DataFrame,
    terminal_rul: pd.Series,
) -> ValidationReport:
    """Validate both telemetry partitions and their cross-file relationship."""
    issues = [
        *validate_telemetry(train, "train_FD001.txt"),
        *validate_telemetry(test, "test_FD001.txt"),
    ]

    rul_numeric = pd.to_numeric(terminal_rul, errors="coerce")
    invalid_rul = (
        rul_numeric.isna()
        | ~np.isfinite(rul_numeric)
        | (rul_numeric % 1 != 0)
        | (rul_numeric < 0)
    )
    if int(invalid_rul.sum()):
        issues.append(
            ValidationIssue(
                "cross_file.terminal_rul_non_negative_integer",
                "Terminal RUL values must be finite non-negative integers.",
                "RUL_FD001.txt",
                int(invalid_rul.sum()),
            )
        )

    engine_values = pd.to_numeric(test["engine_id"], errors="coerce")
    valid_engine_values = engine_values[
        engine_values.notna() & np.isfinite(engine_values)
    ]
    engine_ids = sorted({int(value) for value in valid_engine_values})
    expected_engine_ids = list(range(1, len(engine_ids) + 1))
    if engine_ids != expected_engine_ids:
        issues.append(
            ValidationIssue(
                "cross_file.test_engine_ids_contiguous",
                "Test engine IDs must be the ordered contiguous range 1..N.",
                "test_FD001.txt",
                1,
            )
        )
    if len(terminal_rul) != len(engine_ids):
        issues.append(
            ValidationIssue(
                "cross_file.terminal_rul_count",
                "Exactly one terminal RUL value is required per test engine.",
                "RUL_FD001.txt",
                abs(len(terminal_rul) - len(engine_ids)),
                (
                    {
                        "test_engine_count": len(engine_ids),
                        "terminal_rul_count": len(terminal_rul),
                    },
                ),
            )
        )
    return ValidationReport(not issues, tuple(issues))
