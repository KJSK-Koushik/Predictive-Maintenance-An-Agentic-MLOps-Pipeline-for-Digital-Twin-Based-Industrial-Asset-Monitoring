"""Fail-closed inference runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from predictive_maintenance.release.models import ReleaseError, require_sha256


@dataclass(frozen=True, slots=True)
class ServingSettings:
    """Only immutable local release inputs; no cloud credentials are needed."""

    release_dir: Path
    release_id: str
    app_env: str = "staging"

    def __post_init__(self) -> None:
        if self.app_env.lower() == "production":
            raise ReleaseError(
                "serving.production_disabled", "No production target is configured."
            )
        require_sha256(self.release_id, "PM_RELEASE_ID")

    @classmethod
    def from_env(cls) -> ServingSettings:
        """Load a local staging configuration and reject production."""
        app_env = os.environ.get("APP_ENV", "staging").strip().lower()
        directory = os.environ.get("PM_RELEASE_DIR", "").strip()
        release_id = os.environ.get("PM_RELEASE_ID", "").strip()
        if not directory:
            raise ReleaseError(
                "serving.missing_release_dir", "PM_RELEASE_DIR is required."
            )
        return cls(Path(directory), release_id, app_env)
