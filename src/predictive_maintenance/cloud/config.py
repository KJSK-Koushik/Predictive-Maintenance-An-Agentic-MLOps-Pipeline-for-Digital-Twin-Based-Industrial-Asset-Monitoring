"""Validated Phase 2 configuration with redacted secrets."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    validate_bucket_name,
)


@dataclass(frozen=True, slots=True)
class SecretValue:
    """Secret text that never reveals its value through string representation."""

    _value: str = ""

    def __repr__(self) -> str:
        return "SecretValue(***)"

    def __str__(self) -> str:
        return "***"

    def reveal(self) -> str:
        """Return the secret only at the infrastructure call boundary."""
        return self._value

    @property
    def configured(self) -> bool:
        """Return whether a non-empty secret is present."""
        return bool(self._value)


@dataclass(frozen=True, slots=True)
class Phase2Settings:
    """Explicit local or cloud configuration."""

    app_env: str
    raw_bucket: str
    derived_bucket: str
    local_object_root: Path
    postgres_dsn: SecretValue
    supabase_url: SecretValue
    supabase_secret_key: SecretValue

    def __post_init__(self) -> None:
        if self.app_env not in {"local", "cloud"}:
            raise CloudFoundationError(
                "config.invalid_environment",
                "APP_ENV must be explicitly set to local or cloud.",
            )
        validate_bucket_name(self.raw_bucket)
        validate_bucket_name(self.derived_bucket)
        if self.raw_bucket == self.derived_bucket:
            raise CloudFoundationError(
                "config.duplicate_buckets",
                "Raw and derived bucket names must be different.",
            )
        if self.app_env == "cloud":
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_SECRET_KEY", self.supabase_secret_key),
                    ("SUPABASE_DB_URL", self.postgres_dsn),
                )
                if not value.configured
            ]
            if missing:
                raise CloudFoundationError(
                    "config.missing_cloud_value",
                    "Cloud configuration is incomplete: " + ", ".join(missing),
                )
            parsed = urlsplit(self.supabase_url.reveal())
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise CloudFoundationError(
                    "config.invalid_supabase_url",
                    "SUPABASE_URL must be an HTTPS origin without credentials.",
                )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Phase2Settings:
        """Load settings without inferring environment from credentials."""
        values = os.environ if environ is None else environ
        app_env = values.get("APP_ENV", "").strip()
        dsn_name = "SUPABASE_DB_URL" if app_env == "cloud" else "PM_POSTGRES_DSN"
        object_root = Path(
            values.get("PM_LOCAL_OBJECT_ROOT", "artifacts/cloud-objects")
        )
        return cls(
            app_env=app_env,
            raw_bucket=values.get("PM_RAW_BUCKET", "pm-raw").strip(),
            derived_bucket=values.get("PM_DERIVED_BUCKET", "pm-derived").strip(),
            local_object_root=object_root,
            postgres_dsn=SecretValue(values.get(dsn_name, "").strip()),
            supabase_url=SecretValue(values.get("SUPABASE_URL", "").strip()),
            supabase_secret_key=SecretValue(
                values.get("SUPABASE_SECRET_KEY", "").strip()
            ),
        )

    def sanitized(self) -> dict[str, str]:
        """Return configuration fields safe for logs and reports."""
        return {
            "app_env": self.app_env,
            "raw_bucket": self.raw_bucket,
            "derived_bucket": self.derived_bucket,
            "object_backend": "supabase" if self.app_env == "cloud" else "filesystem",
        }
