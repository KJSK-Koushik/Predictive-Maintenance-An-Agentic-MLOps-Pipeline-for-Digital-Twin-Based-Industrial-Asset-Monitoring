"""Phase 3 CLI redaction and runtime adapter composition tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from predictive_maintenance.cloud.config import Phase2Settings, SecretValue
from predictive_maintenance.cloud.models import CloudFoundationError
from predictive_maintenance.etl import cli, runtime
from predictive_maintenance.etl.models import EtlError, PipelineResult


def _settings(
    *, app_env: str = "local", dsn: str = "postgres://private"
) -> Phase2Settings:
    return Phase2Settings(
        app_env=app_env,
        raw_bucket="pm-raw",
        derived_bucket="pm-derived",
        local_object_root=Path("local-objects"),
        postgres_dsn=SecretValue(dsn),
        supabase_url=SecretValue("https://example.supabase.co"),
        supabase_secret_key=SecretValue("private-secret"),
    )


def _result() -> PipelineResult:
    return PipelineResult("a" * 64, "b" * 64, "c" * 64, "d" * 64, False)


def test_cli_prints_identifier_only_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setenv("PM_CODE_REVISION", "phase3-test")

    def run(source_snapshot_id: str, *, code_revision: str) -> PipelineResult:
        captured.update(source=source_snapshot_id, revision=code_revision)
        return _result()

    monkeypatch.setattr(cli, "run_from_environment", run)
    assert cli.main(["--source-snapshot-id", "a" * 64]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"accepted": True, **_result().to_dict()}
    assert captured == {"source": "a" * 64, "revision": "phase3-test"}


@pytest.mark.parametrize(
    "error",
    [
        EtlError("source.not_found", "Unknown source."),
        CloudFoundationError("metadata.connection_failed", "Safe failure."),
    ],
)
def test_cli_prints_sanitized_domain_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    def reject(*args: object, **kwargs: object) -> PipelineResult:
        raise error

    monkeypatch.setattr(cli, "run_from_environment", reject)
    assert cli.main(["--source-snapshot-id", "a" * 64]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is False
    assert "private" not in json.dumps(payload)


def test_cli_revision_uses_git_or_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PM_CODE_REVISION", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="0123456789ab\n"),
    )
    assert cli._revision() == "0123456789ab"

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("git unavailable")

    monkeypatch.setattr(subprocess, "run", fail)
    assert cli._revision() == "unknown"


def _patch_runtime_settings(
    monkeypatch: pytest.MonkeyPatch, settings: Phase2Settings
) -> None:
    monkeypatch.setattr(
        Phase2Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )


def test_runtime_rejects_missing_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime_settings(monkeypatch, _settings(dsn=""))
    with pytest.raises(EtlError, match=r"config\.missing_postgres_dsn"):
        runtime.run_from_environment("a" * 64, code_revision="phase3-test")


def test_runtime_composes_local_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    _patch_runtime_settings(monkeypatch, _settings())
    monkeypatch.setattr(
        runtime,
        "PostgresMetadataRepository",
        lambda dsn: captured.update(raw_dsn=dsn) or "raw-metadata",
    )
    monkeypatch.setattr(
        runtime,
        "PostgresDerivedMetadataRepository",
        lambda dsn: captured.update(derived_dsn=dsn) or "derived-metadata",
    )
    monkeypatch.setattr(
        runtime,
        "FilesystemObjectRepository",
        lambda root: captured.update(root=root) or "filesystem-objects",
    )

    def run_pipeline(*args: object, **kwargs: object) -> PipelineResult:
        captured.update(args=args, kwargs=kwargs)
        return _result()

    monkeypatch.setattr(runtime, "run_pipeline", run_pipeline)
    assert runtime.run_from_environment("a" * 64, code_revision="phase3-test") == (
        _result()
    )
    assert captured["raw_dsn"] == "postgres://private"
    assert captured["derived_dsn"] == "postgres://private"
    assert captured["root"] == Path("local-objects")
    assert captured["args"][:3] == ("a" * 64, "pm-derived", "filesystem-objects")
    assert captured["kwargs"] == {"code_revision": "phase3-test"}


def test_runtime_composes_cloud_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    _patch_runtime_settings(monkeypatch, _settings(app_env="cloud"))
    monkeypatch.setattr(runtime, "PostgresMetadataRepository", lambda dsn: "raw")
    monkeypatch.setattr(
        runtime, "PostgresDerivedMetadataRepository", lambda dsn: "derived"
    )
    client = object()
    monkeypatch.setattr(
        runtime,
        "create_client",
        lambda url, key: captured.update(url=url, key=key) or client,
    )

    class FakeCloudObjects:
        def __init__(self, supplied_client: object) -> None:
            captured["client"] = supplied_client

        def ensure_private_buckets(self, raw: str, derived: str) -> None:
            captured["buckets"] = (raw, derived)

    monkeypatch.setattr(runtime, "SupabaseObjectRepository", FakeCloudObjects)
    monkeypatch.setattr(runtime, "run_pipeline", lambda *args, **kwargs: _result())
    assert runtime.run_from_environment("a" * 64, code_revision="phase3-test") == (
        _result()
    )
    assert captured == {
        "url": "https://example.supabase.co",
        "key": "private-secret",
        "client": client,
        "buckets": ("pm-raw", "pm-derived"),
    }
