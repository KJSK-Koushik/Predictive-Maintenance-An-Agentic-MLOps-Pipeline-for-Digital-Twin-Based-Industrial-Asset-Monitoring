"""Phase 2 command-line composition and redaction tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from predictive_maintenance.cloud import cli
from predictive_maintenance.cloud.config import Phase2Settings, SecretValue
from predictive_maintenance.cloud.models import (
    CloudFoundationError,
    PublicationResult,
)
from predictive_maintenance.data.contract import ContractError


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


def _configure_success(
    monkeypatch: pytest.MonkeyPatch,
    settings: Phase2Settings,
    captured: dict[str, Any],
) -> None:
    monkeypatch.setattr(
        Phase2Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(
        cli,
        "ingest_fd001",
        lambda source, raw, code_revision: SimpleNamespace(snapshot="accepted"),
    )
    monkeypatch.setattr(cli, "_revision", lambda: "abc123")

    def metadata_repository(dsn: str) -> object:
        captured["dsn"] = dsn
        return "metadata"

    monkeypatch.setattr(cli, "PostgresMetadataRepository", metadata_repository)

    def publish(
        snapshot: object,
        raw_bucket: str,
        objects: object,
        metadata: object,
    ) -> PublicationResult:
        captured.update(
            snapshot=snapshot,
            raw_bucket=raw_bucket,
            objects=objects,
            metadata=metadata,
        )
        return PublicationResult(
            snapshot_id="a" * 64,
            state="available",
            object_count=5,
            reused=False,
        )

    monkeypatch.setattr(cli, "publish_snapshot", publish)


def test_local_cli_composes_filesystem_and_prints_sanitized_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}
    settings = _settings()
    _configure_success(monkeypatch, settings, captured)
    local_repository = object()

    def filesystem_repository(root: Path) -> object:
        captured["local_root"] = root
        return local_repository

    monkeypatch.setattr(cli, "FilesystemObjectRepository", filesystem_repository)

    assert cli.main(["--source-dir", "Data", "--raw-root", "artifacts/raw"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload == {
        "published": True,
        "snapshot_id": "a" * 64,
        "state": "available",
        "object_count": 5,
        "reused": False,
        "configuration": {
            "app_env": "local",
            "raw_bucket": "pm-raw",
            "derived_bucket": "pm-derived",
            "object_backend": "filesystem",
        },
    }
    assert captured["dsn"] == "postgres://private"
    assert captured["local_root"] == Path("local-objects")
    assert captured["objects"] is local_repository
    assert "private" not in output


def test_cloud_cli_composes_supabase_and_private_buckets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}
    settings = _settings(app_env="cloud")
    _configure_success(monkeypatch, settings, captured)
    client = object()
    monkeypatch.setattr(
        cli,
        "create_client",
        lambda url, key: captured.update(url=url, key=key) or client,
    )

    class FakeSupabaseRepository:
        def __init__(self, supplied_client: object) -> None:
            captured["client"] = supplied_client

        def ensure_private_buckets(self, raw: str, derived: str) -> None:
            captured["buckets"] = (raw, derived)

    monkeypatch.setattr(cli, "SupabaseObjectRepository", FakeSupabaseRepository)

    assert cli.main([]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["configuration"]["object_backend"] == "supabase"
    assert captured["client"] is client
    assert captured["buckets"] == ("pm-raw", "pm-derived")
    assert "private-secret" not in output
    assert "example.supabase.co" not in output


def test_cli_reports_missing_postgres_without_running_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(dsn="")
    monkeypatch.setattr(
        Phase2Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(
        cli,
        "ingest_fd001",
        lambda *args, **kwargs: pytest.fail("ingestion must not run"),
    )

    assert cli.main([]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "config.missing_postgres_dsn"


@pytest.mark.parametrize(
    "error,expected_key,expected_value",
    [
        (
            CloudFoundationError("publication.failed", "Safe failure."),
            "code",
            "publication.failed",
        ),
        (
            ContractError("semantic.invalid", "Rejected telemetry."),
            "rule_id",
            "semantic.invalid",
        ),
    ],
)
def test_cli_reports_sanitized_domain_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    expected_key: str,
    expected_value: str,
) -> None:
    monkeypatch.setattr(
        Phase2Settings,
        "from_env",
        classmethod(lambda cls: _settings()),
    )

    def reject(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(cli, "ingest_fd001", reject)
    assert cli.main([]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["published"] is False
    assert payload["error"][expected_key] == expected_value


def test_revision_returns_git_value_or_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="0123456789ab\n"),
    )
    assert cli._revision() == "0123456789ab"

    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("git", 5)

    monkeypatch.setattr(subprocess, "run", fail)
    assert cli._revision() == "unknown"
