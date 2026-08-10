"""Airflow image, Compose, DAG structure, and parse-safety contracts."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "orchestration/airflow/Dockerfile"
DAG_FILE = ROOT / "orchestration/airflow/dags/fd001_etl.py"
COMPOSE_FILE = ROOT / "compose.yaml"

pytestmark = [pytest.mark.integration, pytest.mark.airflow]


def _compose() -> dict[str, Any]:
    value = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_official_airflow_image_and_dependencies_are_pinned() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    requirements = (ROOT / "orchestration/airflow/requirements.txt").read_text(
        encoding="utf-8"
    )
    assert (
        "apache/airflow:3.3.0-python3.11@sha256:"
        "7c7eda27057370576b845ced1269ec539e50588fb43ad0d3d9d20eff5f629fb6"
    ) in dockerfile
    assert '"apache-airflow==${AIRFLOW_VERSION}"' in dockerfile
    package_lines = [
        line for line in requirements.splitlines() if line and not line.startswith("#")
    ]
    assert package_lines
    assert all("==" in line for line in package_lines)
    assert "SECRET" not in dockerfile.upper()
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert dockerignore.startswith("#")
    assert "*\n" in dockerignore
    assert "!src/**" in dockerignore


def test_compose_uses_small_loopback_localexecutor_topology() -> None:
    compose = _compose()
    services = compose["services"]
    assert set(services) == {"airflow", "postgres"}
    airflow = services["airflow"]
    assert airflow["environment"]["AIRFLOW__CORE__EXECUTOR"] == "LocalExecutor"
    assert airflow["ports"] == ["127.0.0.1:18080:8080"]
    assert airflow["mem_limit"] == "2g"
    assert airflow["cpus"] == 2.0
    combined = COMPOSE_FILE.read_text(encoding="utf-8").lower()
    assert "celery" not in combined
    assert "redis" not in combined
    assert "kubernetes" not in combined


def test_dag_declares_approved_graph_and_no_parse_time_adapter_call() -> None:
    source = DAG_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {
        "validate_source",
        "publish_processed",
        "publish_candidate_features",
        "verify_quality_and_lineage",
    } <= functions
    assert 'dag_id="fd001_derived_pipeline"' in source
    assert 'schedule="@daily"' in source
    assert "catchup=False" in source
    assert "max_active_runs=1" in source
    assert 'os.environ.get("PM_SOURCE_SNAPSHOT_ID", "").strip()' in source
    assert '"inject_retryable_failure": False' in source
    assert "run_from_environment" in source
    top_level_calls = [
        node.value.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    ]
    assert top_level_calls == ["fd001_derived_pipeline"]


def test_xcom_contract_is_identifier_only_and_bounded() -> None:
    source = DAG_FILE.read_text(encoding="utf-8")
    assert "DataFrame" not in source
    assert "temporary" not in source.lower()
    assert "SUPABASE_SECRET_KEY" not in source
    assert "_RESULT_KEYS" in source
    assert "_SHA256.fullmatch" in source


def test_running_container_imports_dag_without_errors() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "airflow",
            "airflow",
            "dags",
            "list-import-errors",
            "--output",
            "json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout.strip()
    if output:
        parsed = json.loads(output.splitlines()[-1])
        assert parsed == []
    executor = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "airflow",
            "airflow",
            "config",
            "get-value",
            "core",
            "executor",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout.strip()
    assert executor == "LocalExecutor"
