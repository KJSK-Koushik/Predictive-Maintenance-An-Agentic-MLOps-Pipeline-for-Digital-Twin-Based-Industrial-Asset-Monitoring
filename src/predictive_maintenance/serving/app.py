"""FastAPI application exposing only the approved Phase 6 contract."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from predictive_maintenance.release.models import ReleaseError
from predictive_maintenance.serving.config import ServingSettings
from predictive_maintenance.serving.contracts import (
    ErrorResponse,
    HealthResponse,
    ModelProvenance,
    PredictionRequest,
    PredictionResponse,
    ReleaseResponse,
)
from predictive_maintenance.serving.predictor import ReleasePredictor

MAX_REQUEST_BYTES = 256 * 1024


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message[:500]}},
    )


def create_app(settings: ServingSettings | None = None) -> FastAPI:
    """Create an app whose liveness is independent from release readiness."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            active = ServingSettings.from_env() if settings is None else settings
            app.state.predictor = ReleasePredictor(
                active.release_dir, expected_release_id=active.release_id
            )
            app.state.readiness_error = None
        except ReleaseError as error:
            app.state.predictor = None
            app.state.readiness_error = error.code
        yield

    app = FastAPI(
        title="FD001 Predictive Maintenance Inference",
        version="1.0.0",
        openapi_version="3.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def enforce_request_boundary(request: Request, call_next: Any) -> Any:
        if request.method == "POST":
            content_type = request.headers.get("content-type", "").split(";", 1)[0]
            if content_type.lower() != "application/json":
                return _error(
                    415, "request.unsupported_media_type", "Use application/json."
                )
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_REQUEST_BYTES:
                        return _error(
                            413, "request.body_too_large", "Request body is too large."
                        )
                except ValueError:
                    return _error(
                        400,
                        "request.invalid_content_length",
                        "Content-Length is invalid.",
                    )
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time-Ms"] = (
            f"{(time.perf_counter() - started) * 1000:.3f}"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error(
            422,
            "request.validation_failed",
            "Request does not match fd001-inference-v1.",
        )

    @app.exception_handler(ReleaseError)
    async def release_error(_: Request, error: ReleaseError) -> JSONResponse:
        return _error(503, error.code, error.message)

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="live")

    @app.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def ready(request: Request) -> HealthResponse | JSONResponse:
        predictor = request.app.state.predictor
        if predictor is None:
            return _error(503, "service.not_ready", "Verified release is unavailable.")
        return HealthResponse(status="ready", release_id=predictor.manifest.release_id)

    @app.get(
        "/v1/release",
        response_model=ReleaseResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def release(request: Request) -> ReleaseResponse | JSONResponse:
        predictor = request.app.state.predictor
        if predictor is None:
            return _error(503, "service.not_ready", "Verified release is unavailable.")
        manifest = predictor.manifest
        return ReleaseResponse(
            release_id=manifest.release_id,
            release_contract_version=manifest.release_contract_version,
            feature_snapshot_id=manifest.feature_snapshot_id,
            selection_id=manifest.selection_id,
            regression_model=ModelProvenance(
                **predictor._provenance(manifest.regression)
            ),
            classification_model=ModelProvenance(
                **predictor._provenance(manifest.classification)
            ),
        )

    @app.post(
        "/v1/predict",
        response_model=PredictionResponse,
        responses={
            413: {"model": ErrorResponse},
            415: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def predict(
        payload: PredictionRequest, request: Request
    ) -> PredictionResponse | JSONResponse:
        predictor = request.app.state.predictor
        if predictor is None:
            return _error(503, "service.not_ready", "Verified release is unavailable.")
        observations = [item.model_dump() for item in payload.observations]
        return PredictionResponse(predictions=predictor.predict(observations))

    return app


app = create_app()
