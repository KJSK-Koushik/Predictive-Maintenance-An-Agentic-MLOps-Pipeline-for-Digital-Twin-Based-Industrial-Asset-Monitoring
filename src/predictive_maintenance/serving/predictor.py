"""Verified immutable release loader and prediction implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import skops.io as sio  # type: ignore[import-untyped]

from predictive_maintenance.release.models import (
    FEATURE_COLUMNS,
    ReleaseError,
    canonical_json_bytes,
)
from predictive_maintenance.release.packaging import (
    FIXTURE_FILENAME,
    verify_release_bundle,
)
from predictive_maintenance.release.trust import trusted_types


class ReleasePredictor:
    """Load both trusted artifacts once and remain bound to one release ID."""

    def __init__(self, bundle: Path, *, expected_release_id: str | None = None) -> None:
        self.manifest = verify_release_bundle(
            bundle, expected_release_id=expected_release_id
        )
        self._regression = self._load_model(
            bundle / "rul" / "model.skops", self.manifest.regression.trusted_types
        )
        self._classification = self._load_model(
            bundle / "risk" / "model.skops",
            self.manifest.classification.trusted_types,
        )
        self._verify_startup_fixture(bundle / FIXTURE_FILENAME)

    @staticmethod
    def _load_model(path: Path, expected_types: tuple[str, ...]) -> Any:
        actual_types = trusted_types(path)
        if actual_types != expected_types:
            raise ReleaseError(
                "serving.trusted_types_mismatch",
                "Serialized model trusted types differ from the manifest.",
            )
        try:
            return sio.load(path, trusted=list(actual_types))
        except Exception as error:
            raise ReleaseError(
                "serving.model_load_failed", "A verified model could not be loaded."
            ) from error

    @staticmethod
    def _frame(observations: list[dict[str, Any]]) -> pd.DataFrame:
        values = [
            {name: float(observation[name]) for name in FEATURE_COLUMNS}
            for observation in observations
        ]
        frame = pd.DataFrame(values, columns=list(FEATURE_COLUMNS), dtype="float64")
        if frame.empty or not bool(np.isfinite(frame.to_numpy()).all()):
            raise ReleaseError(
                "serving.invalid_features", "Model features must be finite."
            )
        return frame

    def predict(self, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return safe deterministic values with immutable provenance."""
        core = self._predict_core(observations)
        regression_provenance = self._provenance(self.manifest.regression)
        classification_provenance = self._provenance(self.manifest.classification)
        return [
            {
                "engine_id": int(observation["engine_id"]),
                "cycle": int(observation["cycle"]),
                **core[index],
                "risk_horizon_cycles": 30,
                "risk_threshold": 0.5,
                "release_id": self.manifest.release_id,
                "regression_model": regression_provenance,
                "classification_model": classification_provenance,
                "predictive_uncertainty_status": "not_available",
            }
            for index, observation in enumerate(observations)
        ]

    def _predict_core(
        self, observations: list[dict[str, Any]]
    ) -> list[dict[str, float | int]]:
        """Return only model outputs used by the non-circular parity fixture."""
        frame = self._frame(observations)
        regression = np.asarray(self._regression.predict(frame), dtype="float64")
        probabilities = np.asarray(
            self._classification.predict_proba(frame)[:, 1], dtype="float64"
        )
        if (
            regression.shape != (len(observations),)
            or probabilities.shape != (len(observations),)
            or not bool(np.isfinite(regression).all())
            or not bool(np.isfinite(probabilities).all())
        ):
            raise ReleaseError(
                "serving.invalid_model_output",
                "Model output shape or values are invalid.",
            )
        regression = np.maximum(regression, 0.0)
        probabilities = np.clip(probabilities, 0.0, 1.0)
        return [
            {
                "rul_cycles": float(regression[index]),
                "failure_risk_probability": float(probabilities[index]),
                "failure_risk_label": int(probabilities[index] >= 0.5),
            }
            for index in range(len(observations))
        ]

    @staticmethod
    def _provenance(reference: Any) -> dict[str, str]:
        return {
            "registered_name": str(reference.registered_name),
            "version": str(reference.version),
            "source_run_id": str(reference.source_run_id),
            "artifact_sha256": str(reference.artifact_sha256),
        }

    def _verify_startup_fixture(self, path: Path) -> None:
        try:
            fixture = json.loads(path.read_bytes())
            observations = fixture["observations"]
            expected = fixture["expected"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ReleaseError(
                "serving.invalid_fixture", "Startup parity fixture is invalid."
            ) from error
        actual = self._predict_core(observations)
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ReleaseError(
                "serving.parity_failed", "Startup prediction parity check failed."
            )
