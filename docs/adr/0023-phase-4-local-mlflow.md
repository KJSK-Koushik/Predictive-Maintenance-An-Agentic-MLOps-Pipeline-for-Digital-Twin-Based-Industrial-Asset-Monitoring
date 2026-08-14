# ADR 0023: Loopback SQLite MLflow and trusted skops artifacts

## Status

Accepted

## Date

2026-08-14

## Context

Phase 4 needs database-backed experiment evidence without a shared service,
registry, cloud mutation, or unsafe pickle loading. MLflow 3.15.1's full
metapackage requires `cryptography<50`, but version 49.0.0 is affected by
`PYSEC-2026-3552`; the fix is 50.0.0.

## Decision

Run one MLflow 3.15.1 tracking server bound to `127.0.0.1`, with a local SQLite
backend and local proxied artifact directory under ignored
`artifacts/mlflow/`. Keep it separate from operational PostgreSQL and Supabase.
Use explicit logging and one parent run plus four child model runs. Do not
create a registered-model version, alias, stage, promotion, or deployment.

Install the official `mlflow-skinny` and `mlflow-tracing` packages plus the
server runtime dependencies declared by MLflow's published package metadata.
Do not install the vulnerable full metapackage. Keep `cryptography==50.0.0` and
require `pip-audit` to pass. Suppress MLflow's optional Unicode run-link output
so the Windows CP1252 console cannot fail after run completion.

Serialize estimators only with `skops`. Each run-owned model includes an
MLflow signature, a constructed all-zero schema example, a SHA-256 tag, and a
custom `skops` flavor record. Retrieval verifies run provenance, artifact
digest, exact feature signature, and inspected trusted types before loading.

## Consequences

The topology is appropriate for one local researcher and has no remote
availability or authentication claim. The intentionally explicit dependency
list is longer than the full MLflow metapackage but avoids a known vulnerable
constraint. Dependency updates must recheck whether the metapackage conflict
still exists.

## Alternatives

- Full MLflow 3.15.1 with `cryptography` 49.0.0: rejected because the security
  audit reports `PYSEC-2026-3552`.
- File-only MLflow tracking: rejected because Phase 4 requires a real SQLite
  tracking server and restore evidence.
- Operational PostgreSQL or Supabase as MLflow storage: rejected to preserve
  ownership and avoid cloud mutation.
- Pickle, joblib, or cloudpickle loading: rejected for untrusted-code risk.

## Verification

A real loopback integration test starts the server, logs and queries five
runs, downloads and verifies `skops` artifacts, checks prediction parity,
proves the registry is empty, stops the server, copies SQLite and artifacts,
starts from the copy, and repeats retrieval. `pip-audit` and credential scans
remain required gates.
