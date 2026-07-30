"""Phase 2 identity and configuration contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from predictive_maintenance.cloud.config import (
    Phase2Settings,
    SecretValue,
)
from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    ObjectIdentity,
    raw_file_key,
    raw_manifest_key,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def test_raw_keys_are_deterministic_and_content_addressed() -> None:
    assert raw_file_key(SHA_A, SHA_B, "train_FD001.txt") == (
        f"fd001/{SHA_A}/{SHA_B}/train_FD001.txt"
    )
    assert raw_manifest_key(SHA_A) == f"fd001/{SHA_A}/manifest.json"


@pytest.mark.parametrize(
    "bucket,key,sha256,size",
    [
        ("UPPER", "valid/key", SHA_A, 1),
        ("pm-raw", "../escape", SHA_A, 1),
        ("pm-raw", "a//b", SHA_A, 1),
        ("pm-raw", "valid/key", "ABC", 1),
        ("pm-raw", "valid/key", SHA_A, -1),
    ],
)
def test_invalid_object_identity_is_rejected(
    bucket: str,
    key: str,
    sha256: str,
    size: int,
) -> None:
    with pytest.raises(CloudFoundationError):
        ObjectIdentity(bucket, key, "raw", sha256, size, "text/plain")


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/absolute",
        "trailing/",
        "windows\\path",
        "null\x00byte",
    ],
)
def test_unsafe_object_key_forms_are_rejected(key: str) -> None:
    with pytest.raises(CloudFoundationError, match=r"identity\.invalid_object_key"):
        ObjectIdentity("pm-raw", key, "raw", SHA_A, 1, "text/plain")


def test_invalid_content_type_and_logical_filename_are_rejected() -> None:
    with pytest.raises(CloudFoundationError, match=r"identity\.invalid_content_type"):
        ObjectIdentity("pm-raw", "valid/key", "raw", SHA_A, 1, "")
    with pytest.raises(
        CloudFoundationError, match=r"identity\.invalid_logical_filename"
    ):
        raw_file_key(SHA_A, SHA_B, "../train.txt")


def test_cloud_error_code_and_bounded_report_contract() -> None:
    with pytest.raises(ValueError, match="stable lowercase"):
        CloudFoundationError("INVALID", "message")
    error = CloudFoundationError("publication.failed", "x" * 1200)
    assert error.to_dict() == {
        "code": "publication.failed",
        "message": "x" * 1000,
    }


def test_secret_value_never_reveals_through_repr_or_str() -> None:
    secret = SecretValue("private-value")
    assert "private-value" not in repr(secret)
    assert "private-value" not in str(secret)
    assert secret.reveal() == "private-value"
    assert secret.configured is True
    assert SecretValue().configured is False


def test_settings_reject_same_raw_and_derived_bucket() -> None:
    with pytest.raises(CloudFoundationError, match=r"config\.duplicate_buckets"):
        Phase2Settings.from_env(
            {
                "APP_ENV": "local",
                "PM_RAW_BUCKET": "same-bucket",
                "PM_DERIVED_BUCKET": "same-bucket",
            }
        )


def test_local_settings_are_explicit_and_sanitized() -> None:
    settings = Phase2Settings.from_env(
        {
            "APP_ENV": "local",
            "PM_RAW_BUCKET": "pm-raw",
            "PM_DERIVED_BUCKET": "pm-derived",
            "PM_LOCAL_OBJECT_ROOT": "artifacts/test-store",
            "PM_POSTGRES_DSN": "postgresql://private",
        }
    )
    assert settings.local_object_root == Path("artifacts/test-store")
    assert settings.sanitized() == {
        "app_env": "local",
        "raw_bucket": "pm-raw",
        "derived_bucket": "pm-derived",
        "object_backend": "filesystem",
    }
    assert "postgresql://private" not in repr(settings)


def test_environment_is_not_inferred_from_cloud_credentials() -> None:
    with pytest.raises(
        CloudFoundationError,
        match=r"config\.invalid_environment",
    ):
        Phase2Settings.from_env(
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SECRET_KEY": "secret",
                "SUPABASE_DB_URL": "postgresql://private",
            }
        )


def test_cloud_settings_require_all_private_values() -> None:
    with pytest.raises(
        CloudFoundationError,
        match=r"config\.missing_cloud_value",
    ) as captured:
        Phase2Settings.from_env({"APP_ENV": "cloud"})
    assert "private-value" not in str(captured.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.supabase.co",
        "https://user:pass@example.supabase.co",
        "not-a-url",
    ],
)
def test_cloud_settings_reject_unsafe_url(url: str) -> None:
    with pytest.raises(
        CloudFoundationError,
        match=r"config\.invalid_supabase_url",
    ):
        Phase2Settings.from_env(
            {
                "APP_ENV": "cloud",
                "SUPABASE_URL": url,
                "SUPABASE_SECRET_KEY": "secret",
                "SUPABASE_DB_URL": "postgresql://private",
            }
        )
