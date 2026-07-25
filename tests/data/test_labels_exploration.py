from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from predictive_maintenance.data.contract import ContractError
from predictive_maintenance.data.exploration import build_exploration
from predictive_maintenance.data.labels import (
    add_failure_risk,
    derive_test_rul,
    derive_train_rul,
)
from predictive_maintenance.data.parser import parse_telemetry, parse_terminal_rul


def test_train_rul_endpoint_and_off_by_one(valid_source: Path) -> None:
    frame = parse_telemetry(valid_source / "train_FD001.txt")

    result = derive_train_rul(frame)

    assert result.loc[result["engine_id"] == 1, "rul"].tolist() == [2, 1, 0]
    assert result.loc[result["engine_id"] == 2, "rul"].tolist() == [1, 0]
    assert int(result["rul"].min()) == 0


def test_test_rul_uses_observed_endpoint_and_supplied_value(
    valid_source: Path,
) -> None:
    frame = parse_telemetry(valid_source / "test_FD001.txt")
    terminal = parse_terminal_rul(valid_source / "RUL_FD001.txt")

    result = derive_test_rul(frame, terminal)

    assert result.loc[result["engine_id"] == 1, "rul"].tolist() == [3, 2]
    assert result.loc[result["engine_id"] == 2, "rul"].tolist() == [2, 1]


def test_test_rul_rejects_count_mismatch(valid_source: Path) -> None:
    frame = parse_telemetry(valid_source / "test_FD001.txt")

    with pytest.raises(ContractError, match="label.terminal_rul_count"):
        derive_test_rul(frame, pd.Series([1]))


def test_failure_risk_inclusive_boundary() -> None:
    frame = pd.DataFrame({"rul": [29, 30, 31]})

    result = add_failure_risk(frame, 30)

    assert result["failure_risk_30"].tolist() == [1, 1, 0]


def test_failure_risk_requires_valid_inputs() -> None:
    with pytest.raises(ContractError, match="label.invalid_risk_horizon"):
        add_failure_risk(pd.DataFrame({"rul": [1]}), -1)
    with pytest.raises(ContractError, match="label.rul_missing"):
        add_failure_risk(pd.DataFrame({"cycle": [1]}))


def test_exploration_is_scoped_and_reports_prevalence(
    valid_source: Path,
) -> None:
    train = derive_train_rul(parse_telemetry(valid_source / "train_FD001.txt"))
    test = derive_test_rul(
        parse_telemetry(valid_source / "test_FD001.txt"),
        parse_terminal_rul(valid_source / "RUL_FD001.txt"),
    )

    report = build_exploration(train, test)

    assert "simulated historical cycle telemetry" in report["scope"]
    assert "live stream" in report["scope"]
    assert set(report["failure_risk_prevalence"]) == {"15", "30", "45"}
    assert report["train"]["rows"] == 5
    assert report["train"]["missing_values"] == 0
    assert report["train"]["duplicate_engine_cycles"] == 0


def test_single_row_exploration_remains_strict_json(valid_source: Path) -> None:
    one_row = parse_telemetry(valid_source / "train_FD001.txt").iloc[:1].copy()
    labeled = derive_train_rul(one_row)

    report = build_exploration(labeled, labeled)

    assert report["train"]["sensor_summary"]["sensor_1"]["std"] is None
    json.dumps(report, allow_nan=False)
