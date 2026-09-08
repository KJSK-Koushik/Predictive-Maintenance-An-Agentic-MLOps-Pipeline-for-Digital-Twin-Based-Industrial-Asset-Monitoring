"""Phase 7 Airflow monitoring-DAG structure and authority tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DAG_FILE = ROOT / "orchestration/airflow/dags/fd001_monitoring.py"

pytestmark = [pytest.mark.integration, pytest.mark.airflow]


def test_monitoring_dag_is_manual_thin_and_parse_safe() -> None:
    source = DAG_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {"validate_request", "monitor_window"} <= functions
    assert 'dag_id="fd001_monitoring_replay"' in source
    assert "schedule=None" in source
    assert "catchup=False" in source
    assert "max_active_runs=1" in source
    assert "run_monitoring_files" in source
    top_level_calls = [
        node.value.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    ]
    assert top_level_calls == ["fd001_monitoring_replay"]


def test_monitoring_dag_has_bounded_identity_only_xcom_and_no_authority() -> None:
    source = DAG_FILE.read_text(encoding="utf-8")
    assert '_RESULT_KEYS = {"report_id", "reused", "window_id"}' in source
    assert "_SHA256.fullmatch" in source
    assert "DataFrame" not in source
    assert "MLflowClient" not in source
    assert "set_registered_model_alias" not in source
    assert "deploy" not in source.lower()
    assert "rollback" not in source.lower()
    assert "train(" not in source
    assert "schedule=None" in source


def test_phase7_migration_and_monitoring_mount_are_in_compose() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "20260907042647_phase_07_monitoring.sql" in compose
    assert "./artifacts/monitoring:/opt/airflow/artifacts/monitoring" in compose
    requirements = (ROOT / "orchestration/airflow/requirements.txt").read_text(
        encoding="utf-8"
    )
    assert "scikit-learn==1.9.0" in requirements
