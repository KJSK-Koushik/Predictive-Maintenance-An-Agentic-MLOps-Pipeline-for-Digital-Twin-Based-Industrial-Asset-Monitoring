"""Deterministic parser for C-MAPSS whitespace-delimited files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from predictive_maintenance.data.contract import TELEMETRY_COLUMNS, ContractError


def _token_rows(path: Path, width: int, logical_file: str) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        with path.open("r", encoding="ascii") as source:
            for line_number, line in enumerate(source, start=1):
                tokens = line.split()
                if len(tokens) != width:
                    raise ContractError(
                        "parser.wrong_column_count",
                        f"Expected {width} whitespace-delimited values; "
                        f"found {len(tokens)}.",
                        logical_file,
                        line_number,
                        {"expected": width, "observed": len(tokens)},
                    )
                rows.append(tokens)
    except UnicodeDecodeError as error:
        raise ContractError(
            "parser.non_ascii",
            "C-MAPSS text inputs must be ASCII.",
            logical_file,
        ) from error
    except OSError as error:
        raise ContractError(
            "source.file_unreadable",
            "Required source file could not be read.",
            logical_file,
        ) from error
    if not rows:
        raise ContractError(
            "parser.empty_file",
            "The required data file contains no rows.",
            logical_file,
        )
    return rows


def parse_telemetry(path: Path, logical_file: str | None = None) -> pd.DataFrame:
    """Parse one train/test file while preserving its original row order."""
    name = logical_file or path.name
    rows = _token_rows(path, len(TELEMETRY_COLUMNS), name)
    frame = pd.DataFrame(rows, columns=TELEMETRY_COLUMNS)
    for column in TELEMETRY_COLUMNS:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as error:
            raise ContractError(
                "parser.non_numeric",
                "Telemetry contains a non-numeric value.",
                name,
            ) from error
    for column in ("engine_id", "cycle"):
        values = frame[column]
        if values.notna().all() and (values % 1 == 0).all():
            frame[column] = values.astype("int64")
    for column in TELEMETRY_COLUMNS[2:]:
        frame[column] = frame[column].astype("float64")
    return frame


def parse_terminal_rul(path: Path, logical_file: str | None = None) -> pd.Series:
    """Parse the one-column test terminal-RUL vector."""
    name = logical_file or path.name
    rows = _token_rows(path, 1, name)
    try:
        values = pd.to_numeric(
            pd.Series([row[0] for row in rows], name="terminal_rul"),
            errors="raise",
        )
    except (TypeError, ValueError) as error:
        raise ContractError(
            "parser.non_numeric",
            "Terminal RUL contains a non-numeric value.",
            name,
        ) from error
    if values.notna().all() and (values % 1 == 0).all():
        return values.astype("int64")
    return values
