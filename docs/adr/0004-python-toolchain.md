# ADR-0004: Python Toolchain and Dependency Locking

## Status

Accepted

## Date

2026-07-23

## Context

Reproducible experiments require consistent interpreters and dependencies.
Global developer tools cannot be assumed, and later libraries must remain
compatible with Airflow, MLflow, scikit-learn, and FastAPI.

## Decision

Python 3.11 is the initial supported runtime. Project and development
dependencies are declared in `pyproject.toml`, resolved with `uv`, and committed
in `uv.lock`. Ruff handles Python formatting and linting, mypy handles static
typing, and pytest handles tests. CI installs from the locked environment.

Dependency changes require a reviewed lockfile diff and security audit.

## Consequences

Contributors need `uv`, but do not need globally installed linters. Python
runtime upgrades are explicit architecture changes. Phase-specific dependencies
are added only in their owning phase.

## Alternatives

- Unpinned `requirements.txt`: rejected as insufficiently reproducible.
- Conda as the primary environment: rejected because it adds a second package
  resolution model without a current need.
- Support many Python minors initially: rejected because the CI matrix would
  add little research value.

## Verification

CI runs `uv lock --check` and synchronizes with `--locked`.
