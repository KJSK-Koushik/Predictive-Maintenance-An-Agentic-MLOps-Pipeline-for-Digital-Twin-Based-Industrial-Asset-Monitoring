"""Versioned FastAPI request and response contracts."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveIdentity = Annotated[StrictInt, Field(gt=0)]


class Observation(BaseModel):
    """One cycle-level FD001 identity plus exact ordered model features."""

    model_config = ConfigDict(extra="forbid")

    engine_id: PositiveIdentity
    cycle: PositiveIdentity
    setting_1: FiniteFloat
    setting_2: FiniteFloat
    setting_3: FiniteFloat
    sensor_1: FiniteFloat
    sensor_2: FiniteFloat
    sensor_3: FiniteFloat
    sensor_4: FiniteFloat
    sensor_5: FiniteFloat
    sensor_6: FiniteFloat
    sensor_7: FiniteFloat
    sensor_8: FiniteFloat
    sensor_9: FiniteFloat
    sensor_10: FiniteFloat
    sensor_11: FiniteFloat
    sensor_12: FiniteFloat
    sensor_13: FiniteFloat
    sensor_14: FiniteFloat
    sensor_15: FiniteFloat
    sensor_16: FiniteFloat
    sensor_17: FiniteFloat
    sensor_18: FiniteFloat
    sensor_19: FiniteFloat
    sensor_20: FiniteFloat
    sensor_21: FiniteFloat

    @field_validator("*")
    @classmethod
    def reject_boolean_and_nonfinite(cls, value: object) -> object:
        """Reject Boolean-as-number coercion and every non-finite float."""
        if isinstance(value, bool):
            raise ValueError("Boolean values are not valid telemetry.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Telemetry must be finite.")
        return value


class PredictionRequest(BaseModel):
    """Bounded inference batch."""

    model_config = ConfigDict(extra="forbid")
    observations: Annotated[list[Observation], Field(min_length=1, max_length=128)]


class ModelProvenance(BaseModel):
    """Immutable registry identity included in each response."""

    registered_name: str
    version: str
    source_run_id: str
    artifact_sha256: str


class PredictionItem(BaseModel):
    """One bounded prediction with explicit claim limitations."""

    engine_id: int
    cycle: int
    rul_cycles: float
    failure_risk_probability: float
    failure_risk_label: int
    risk_horizon_cycles: Literal[30] = 30
    risk_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    release_id: str
    regression_model: ModelProvenance
    classification_model: ModelProvenance
    predictive_uncertainty_status: Literal["not_available"] = "not_available"


class PredictionResponse(BaseModel):
    """Versioned response envelope."""

    contract_version: Literal["fd001-inference-v1"] = "fd001-inference-v1"
    predictions: list[PredictionItem]


class ReleaseResponse(BaseModel):
    """Safe release metadata without paths, credentials, or endpoints."""

    release_id: str
    release_contract_version: str
    feature_snapshot_id: str
    selection_id: str
    regression_model: ModelProvenance
    classification_model: ModelProvenance
    predictive_uncertainty_status: Literal["not_available"] = "not_available"


class HealthResponse(BaseModel):
    """Liveness or readiness response."""

    status: Literal["live", "ready"]
    release_id: str | None = None


class ErrorDetail(BaseModel):
    """Stable bounded service error."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Error response envelope."""

    error: ErrorDetail
