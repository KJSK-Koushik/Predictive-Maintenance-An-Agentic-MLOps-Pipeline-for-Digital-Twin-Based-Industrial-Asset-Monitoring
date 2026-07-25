"""Integration tests spanning the current workflow and governance artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github/workflows/ci.yml"


def _load_workflow() -> dict[str, Any]:
    loaded = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.integration
def test_workflow_is_least_privilege_and_has_expected_triggers() -> None:
    workflow = _load_workflow()
    permissions = workflow.get("permissions")
    assert permissions == {"contents": "read"}

    triggers = workflow.get("on")
    assert isinstance(triggers, dict)
    assert {"pull_request", "push", "workflow_dispatch"} <= triggers.keys()


@pytest.mark.integration
def test_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]
    uses_values: list[str] = []

    for job in jobs.values():
        for step in job.get("steps", []):
            if "uses" in step:
                uses_values.append(step["uses"])

    assert uses_values
    sha_pattern = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
    invalid = [value for value in uses_values if not sha_pattern.fullmatch(value)]
    assert not invalid, f"Actions are not immutable: {invalid}"


@pytest.mark.integration
def test_workflow_runs_all_phase_one_quality_gates() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    required_commands = (
        "uv sync --locked --dev",
        "uv lock --check",
        "ruff format --check",
        "ruff check",
        "mypy src tests",
        'pytest -m "not integration and not dataset"',
        'pytest -m "integration and not dataset"',
        "--cov=src/predictive_maintenance",
        "--cov-fail-under=90",
        "mdformat --check",
        "yamllint",
        "pip-audit",
    )
    missing = [command for command in required_commands if command not in workflow_text]
    assert not missing, f"CI is missing quality gates: {missing}"


@pytest.mark.integration
def test_pull_request_ci_contains_no_release_or_cloud_mutation() -> None:
    workflow = _load_workflow()
    prohibited = (
        "deploy",
        "release",
        "promote",
        "supabase db",
        "supabase storage",
        "docker push",
        "mlflow register",
    )
    commands_and_names: list[str] = []

    for job in workflow["jobs"].values():
        commands_and_names.append(job.get("name", ""))
        for step in job.get("steps", []):
            commands_and_names.extend((step.get("name", ""), step.get("run", "")))

    combined = "\n".join(commands_and_names).lower()
    found = [term for term in prohibited if term in combined]
    assert not found, f"CI contains mutation/release terms: {found}"
    assert "secrets." not in WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.mark.integration
def test_approved_phase_zero_records_remote_ci_evidence() -> None:
    criteria = (ROOT / "docs/phases/phase-00/ACCEPTANCE_CRITERIA.md").read_text(
        encoding="utf-8"
    )
    status = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")

    assert "- [x] GitHub Actions required workflow passes on GitHub." in criteria
    assert "GitHub Actions run" in status
    assert "Passed: run `30040721136`" in status
    assert "Branch protection" in status
    assert "destructive refs off" in status
