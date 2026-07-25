"""Leakage-explicit RUL and horizon-risk label derivations."""

from __future__ import annotations

import pandas as pd

from predictive_maintenance.data.contract import PRIMARY_RISK_HORIZON, ContractError


def derive_train_rul(frame: pd.DataFrame) -> pd.DataFrame:
    """Add canonical uncapped run-to-failure RUL to training telemetry."""
    result = frame.copy()
    endpoint = result.groupby("engine_id", sort=False)["cycle"].transform("max")
    result["rul"] = (endpoint - result["cycle"]).astype("int64")
    if (result["rul"] < 0).any():
        raise ContractError(
            "label.train_rul_negative",
            "Derived training RUL cannot be negative.",
        )
    return result


def derive_test_rul(
    frame: pd.DataFrame, terminal_rul: pd.Series
) -> pd.DataFrame:
    """Add RUL using each test engine's observed endpoint and supplied RUL."""
    engine_ids = sorted(int(value) for value in frame["engine_id"].unique())
    if len(engine_ids) != len(terminal_rul):
        raise ContractError(
            "label.terminal_rul_count",
            "One terminal RUL value is required per test engine.",
        )
    terminal_by_engine = dict(
        zip(engine_ids, (int(value) for value in terminal_rul), strict=True)
    )
    result = frame.copy()
    observed_endpoint = result.groupby("engine_id", sort=False)["cycle"].transform(
        "max"
    )
    supplied_endpoint = result["engine_id"].map(terminal_by_engine)
    result["rul"] = (
        observed_endpoint + supplied_endpoint - result["cycle"]
    ).astype("int64")
    if (result["rul"] < 0).any():
        raise ContractError(
            "label.test_rul_negative",
            "Derived test RUL cannot be negative.",
        )
    return result


def add_failure_risk(
    frame: pd.DataFrame, horizon: int = PRIMARY_RISK_HORIZON
) -> pd.DataFrame:
    """Add the declared inclusive RUL-horizon classification label."""
    if horizon < 0:
        raise ContractError(
            "label.invalid_risk_horizon",
            "Failure-risk horizon must be non-negative.",
        )
    if "rul" not in frame:
        raise ContractError(
            "label.rul_missing",
            "RUL must be derived before failure risk.",
        )
    result = frame.copy()
    result[f"failure_risk_{horizon}"] = (result["rul"] <= horizon).astype("int8")
    return result
