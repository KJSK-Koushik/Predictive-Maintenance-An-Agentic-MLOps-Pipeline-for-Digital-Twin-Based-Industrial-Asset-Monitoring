"""MLflow boundary unit tests."""

from __future__ import annotations

import pandas as pd
import pytest

from predictive_maintenance.modeling.models import (
    FEATURE_COLUMNS,
    ModelingError,
    TrainingDataset,
)
from predictive_maintenance.modeling.tracking import (
    log_baseline_result,
    schema_only_input_example,
    validate_model_input,
)


def test_schema_only_example_is_zero_float64() -> None:
    example = schema_only_input_example()
    assert tuple(example.columns) == FEATURE_COLUMNS
    assert not example.to_numpy().any()
    validate_model_input(example)


@pytest.mark.parametrize(
    "frame, message",
    [
        (schema_only_input_example().iloc[:, ::-1], "columns"),
        (schema_only_input_example().astype("float32"), "float64"),
        (pd.DataFrame(columns=list(FEATURE_COLUMNS), dtype="float64"), "finite"),
    ],
)
def test_model_input_validation_fails_closed(frame: pd.DataFrame, message: str) -> None:
    with pytest.raises(ModelingError, match=message):
        validate_model_input(frame)


def test_tracking_rejects_non_loopback_before_network(
    synthetic_dataset: TrainingDataset,
) -> None:
    from predictive_maintenance.modeling.pipeline import run_baselines

    with pytest.raises(ModelingError, match="loopback"):
        log_baseline_result(
            run_baselines(synthetic_dataset),
            tracking_uri="http://0.0.0.0:5000",
            code_revision="test",
            dirty_worktree=False,
        )
