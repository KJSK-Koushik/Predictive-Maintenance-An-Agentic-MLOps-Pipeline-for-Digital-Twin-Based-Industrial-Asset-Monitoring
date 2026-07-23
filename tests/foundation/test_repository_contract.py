"""Phase 0 repository and documentation contract tests."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    "README.md",
    "CONTRIBUTING.md",
    "LICENSE",
    ".env.example",
    ".gitignore",
    ".github/CODEOWNERS",
    "pyproject.toml",
    "docs/PROJECT_CHARTER.md",
    "docs/MASTER_ARCHITECTURE.md",
    "docs/ROADMAP.md",
    "docs/PROJECT_STATUS.md",
    "docs/MANUAL_PREREQUISITES.md",
    "docs/SECURITY_AND_SECRETS.md",
    "docs/TEST_STRATEGY.md",
    "docs/DATA_CONTRACT.md",
    "docs/adr/README.md",
    "docs/phases/phase-00/ARCHITECTURE.md",
    "docs/phases/phase-00/PLAN.md",
    "docs/phases/phase-00/ACCEPTANCE_CRITERIA.md",
    "docs/phases/phase-00/TEST_PLAN.md",
    "docs/phases/phase-00/COMPLETION_REPORT.md",
)

ADR_REQUIRED_HEADINGS = (
    "## Status",
    "## Date",
    "## Context",
    "## Decision",
    "## Consequences",
    "## Alternatives",
    "## Verification",
)

PERMITTED_PHASE_STATES = {
    "PLANNED",
    "IN_PROGRESS",
    "AWAITING_APPROVAL",
    "APPROVED",
    "BLOCKED",
}


@pytest.mark.foundation
def test_required_foundation_files_are_non_empty() -> None:
    missing = []
    empty = []
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif not path.read_text(encoding="utf-8").strip():
            empty.append(relative)

    assert not missing, f"Missing required files: {missing}"
    assert not empty, f"Empty required files: {empty}"


@pytest.mark.foundation
def test_phase_zero_is_the_single_active_phase() -> None:
    status = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    phase_match = re.search(r"\|\s*Current phase\s*\|\s*(\d+)\s*\|", status)
    state_match = re.search(r"\|\s*State\s*\|\s*([A-Z_]+)\s*\|", status)

    assert phase_match is not None, "Current phase is not declared"
    assert phase_match.group(1) == "0"
    assert state_match is not None, "Phase state is not declared"
    assert state_match.group(1) in PERMITTED_PHASE_STATES

    phase_directories = sorted((ROOT / "docs/phases").glob("phase-*"))
    assert [path.name for path in phase_directories] == ["phase-00"]


@pytest.mark.foundation
def test_adrs_are_sequential_and_complete() -> None:
    adrs = sorted((ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert adrs, "At least one ADR is required"

    identifiers = [int(path.name[:4]) for path in adrs]
    assert identifiers == list(range(1, len(adrs) + 1))

    for path in adrs:
        content = path.read_text(encoding="utf-8")
        missing = [
            heading for heading in ADR_REQUIRED_HEADINGS if heading not in content
        ]
        assert not missing, f"{path.name} is missing sections: {missing}"
        assert "\nAccepted\n" in content, f"{path.name} is not accepted"


@pytest.mark.foundation
def test_controlled_markdown_local_links_resolve() -> None:
    markdown_files = [ROOT / "README.md", ROOT / "CONTRIBUTING.md"]
    markdown_files.extend((ROOT / "docs").rglob("*.md"))
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    failures: list[str] = []

    for source in markdown_files:
        for target in pattern.findall(source.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean_target = target.split("#", maxsplit=1)[0]
            if not clean_target:
                continue
            resolved = (source.parent / clean_target).resolve()
            if not resolved.exists():
                failures.append(f"{source.relative_to(ROOT)} -> {target}")

    assert not failures, f"Broken local Markdown links: {failures}"


@pytest.mark.foundation
def test_local_dataset_is_ignored() -> None:
    ignore_file = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/Data/" in ignore_file
    assert "/data/" in ignore_file

    if (ROOT / ".git").exists() and (ROOT / "Data/train_FD001.txt").exists():
        result = subprocess.run(
            ["git", "check-ignore", "Data/train_FD001.txt"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


@pytest.mark.foundation
def test_no_later_phase_implementation_roots_exist() -> None:
    prohibited = ("src", "airflow", "supabase", "dashboard", "services", "models")
    present = [name for name in prohibited if (ROOT / name).exists()]
    assert not present, f"Later-phase implementation roots present: {present}"


@pytest.mark.foundation
def test_environment_example_has_no_secret_values() -> None:
    assignments: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        assert separator, f"Invalid environment example line: {line}"
        assignments[key] = value

    secret_keys = {
        "SUPABASE_SECRET_KEY",
        "SUPABASE_DB_URL",
        "SUPABASE_S3_ACCESS_KEY_ID",
        "SUPABASE_S3_SECRET_ACCESS_KEY",
        "LLM_API_KEY",
    }
    assert secret_keys <= assignments.keys()
    assert all(assignments[key] == "" for key in secret_keys)

    forbidden_fragments = ("eyJ", "postgresql://", "supabase.co", "sk-")
    combined = "\n".join(assignments.values())
    assert not any(fragment in combined for fragment in forbidden_fragments)


@pytest.mark.foundation
def test_no_external_repository_dependency_or_path() -> None:
    project_config = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "ml-agent-factory" not in project_config

    forbidden_paths = (
        "../ML-Agent-Factory",
        "..\\ML-Agent-Factory",
        "D:\\ML-Agent-Factory",
    )
    controlled_files = [ROOT / "pyproject.toml", ROOT / ".env.example"]
    controlled_files.extend((ROOT / ".github").rglob("*"))
    for path in controlled_files:
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert not any(value in content for value in forbidden_paths), path


@pytest.mark.foundation
def test_codeowners_records_owner_provided_identity() -> None:
    codeowners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    ownership_rules = [
        line.strip()
        for line in codeowners.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert ownership_rules == ["* @KJSK-Koushik"]


@pytest.mark.foundation
def test_apache_license_is_declared_consistently() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    project_config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert 'license = "Apache-2.0"' in project_config
    assert "Apache License 2.0" in readme


@pytest.mark.foundation
def test_charter_contains_claim_boundaries() -> None:
    charter = (ROOT / "docs/PROJECT_CHARTER.md").read_text(encoding="utf-8").lower()
    normalized = re.sub(r"\s+", " ", charter.replace("*", ""))
    required_terms = (
        "digital shadow",
        "cycle-level replay",
        "human-governed",
        "derived label",
        "monitor-triggered retraining evaluation",
    )
    missing = [term for term in required_terms if term not in normalized]
    assert not missing, f"Missing claim-boundary terms: {missing}"
