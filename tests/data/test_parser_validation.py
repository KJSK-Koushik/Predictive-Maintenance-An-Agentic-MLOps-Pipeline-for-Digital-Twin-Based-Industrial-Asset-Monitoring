from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from predictive_maintenance.data.contract import (
    RUL_FILENAME,
    TELEMETRY_COLUMNS,
    TEST_FILENAME,
    TRAIN_FILENAME,
    ContractError,
)
from predictive_maintenance.data.parser import parse_telemetry, parse_terminal_rul
from predictive_maintenance.data.validation import validate_fd001, validate_telemetry


def _valid_frames(source: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    return (
        parse_telemetry(source / TRAIN_FILENAME),
        parse_telemetry(source / TEST_FILENAME),
        parse_terminal_rul(source / RUL_FILENAME),
    )


def test_parser_names_exact_columns_and_preserves_order(valid_source: Path) -> None:
    frame = parse_telemetry(valid_source / TRAIN_FILENAME)

    assert tuple(frame.columns) == TELEMETRY_COLUMNS
    assert frame[["engine_id", "cycle"]].values.tolist() == [
        [1, 1],
        [1, 2],
        [1, 3],
        [2, 1],
        [2, 2],
    ]
    assert str(frame["engine_id"].dtype) == "int64"
    assert str(frame["sensor_1"].dtype) == "float64"


def test_parser_accepts_variable_and_trailing_whitespace(tmp_path: Path) -> None:
    values = ["1", "1", "0", "0", "100", *map(str, range(1, 22))]
    path = tmp_path / TRAIN_FILENAME
    path.write_text("  \t".join(values) + "   \n", encoding="ascii")

    frame = parse_telemetry(path)

    assert len(frame) == 1
    assert frame.loc[0, "sensor_21"] == 21


@pytest.mark.parametrize(
    ("content", "rule_id"),
    [
        ("1 1 2\n", "parser.wrong_column_count"),
        ("", "parser.empty_file"),
        (
            "1 1 0 0 100 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 x\n",
            "parser.non_numeric",
        ),
    ],
)
def test_parser_rejects_malformed_rows(
    tmp_path: Path, content: str, rule_id: str
) -> None:
    path = tmp_path / TRAIN_FILENAME
    path.write_text(content, encoding="ascii")

    with pytest.raises(ContractError, match=rule_id):
        parse_telemetry(path)


def test_terminal_rul_requires_one_value_per_row(tmp_path: Path) -> None:
    path = tmp_path / RUL_FILENAME
    path.write_text("1 2\n", encoding="ascii")

    with pytest.raises(ContractError, match="parser.wrong_column_count"):
        parse_terminal_rul(path)


def test_valid_fixture_passes_full_contract(valid_source: Path) -> None:
    report = validate_fd001(*_valid_frames(valid_source))

    assert report.accepted is True
    assert report.issues == ()
    assert report.canonical_json() == '{"accepted":true,"issues":[]}'


@pytest.mark.parametrize(
    ("mutation", "expected_rule"),
    [
        ("duplicate", "semantic.duplicate_engine_cycle"),
        ("reordered", "semantic.cycle_order"),
        ("missing_cycle", "semantic.cycle_contiguous"),
        ("non_positive_id", "semantic.engine_id_positive_integer"),
        ("positive_infinity", "schema.finite"),
        ("negative_infinity", "schema.finite"),
        ("nan", "schema.finite"),
        ("non_integral_cycle", "semantic.cycle_positive_integer"),
    ],
)
def test_semantic_failures_have_stable_rules(
    valid_source: Path, mutation: str, expected_rule: str
) -> None:
    train, _, _ = _valid_frames(valid_source)
    if mutation == "duplicate":
        train.loc[1, "cycle"] = 1
    elif mutation == "reordered":
        train.loc[1, "cycle"] = 0
    elif mutation == "missing_cycle":
        train.loc[1, "cycle"] = 3
    elif mutation == "non_positive_id":
        train.loc[0, "engine_id"] = 0
    elif mutation == "positive_infinity":
        train.loc[0, "sensor_1"] = np.inf
    elif mutation == "negative_infinity":
        train.loc[0, "sensor_1"] = -np.inf
    elif mutation == "nan":
        train.loc[0, "sensor_1"] = np.nan
    else:
        train["cycle"] = train["cycle"].astype("float64")
        train.loc[0, "cycle"] = 1.5

    issues = validate_telemetry(train, TRAIN_FILENAME)

    assert expected_rule in {issue.rule_id for issue in issues}
    assert all(len(issue.examples) <= 5 for issue in issues)
    assert all(issue.severity == "error" for issue in issues)


def test_column_order_is_strict(valid_source: Path) -> None:
    train, _, _ = _valid_frames(valid_source)
    reordered = train.loc[:, list(reversed(train.columns))]

    issues = validate_telemetry(reordered, TRAIN_FILENAME)

    assert [issue.rule_id for issue in issues] == ["schema.column_order"]


def test_cross_file_rul_count_is_enforced(valid_source: Path) -> None:
    train, test, terminal_rul = _valid_frames(valid_source)

    report = validate_fd001(train, test, terminal_rul.iloc[:1])

    assert report.accepted is False
    assert "cross_file.terminal_rul_count" in {
        issue.rule_id for issue in report.issues
    }


def test_terminal_rul_domain_is_enforced(valid_source: Path) -> None:
    train, test, terminal_rul = _valid_frames(valid_source)
    terminal_rul.iloc[0] = -1

    report = validate_fd001(train, test, terminal_rul)

    assert "cross_file.terminal_rul_non_negative_integer" in {
        issue.rule_id for issue in report.issues
    }


def test_test_engine_ids_must_be_contiguous(valid_source: Path) -> None:
    train, test, terminal_rul = _valid_frames(valid_source)
    test.loc[test["engine_id"] == 2, "engine_id"] = 3

    report = validate_fd001(train, test, terminal_rul)

    assert "cross_file.test_engine_ids_contiguous" in {
        issue.rule_id for issue in report.issues
    }
