# Phase 3 Completion Report

## Status

**COMPLETE — AWAITING OWNER APPROVAL**

Implementation was authorized by `START PHASE 3` on 2026-08-08. This report is
the completion handoff after all local, hosted, and GitHub gates passed.

## Delivered scope

- deterministic `fd001-processed-v1` train/test Parquet artifacts;
- deterministic `fd001-candidate-features-v1` feature and separate target
  artifacts;
- canonical `fd001-data-quality-v1` aggregate JSON evidence;
- content-addressed manifests, object keys, put-if-absent publication, exact
  reuse, reconciliation, and derived lineage;
- one forward-only PostgreSQL 17 migration for derived snapshots, files, and
  transformation runs;
- a direct sanitized `run-fd001-etl` CLI;
- Airflow 3.3.0 on Python 3.11 with `LocalExecutor`, a dedicated metadata
  database/user, and loopback-only UI/API;
- one static-batch DAG with bounded retries, timeouts, controlled failure,
  backfill, and identifier-only XCom; and
- credential-free Phase 3 CI gates.

No model, MLflow integration, serving API, monitoring system, agent, dashboard,
streaming component, or deployment was added.

## Deterministic local evidence

The committed synthetic source produced these stable IDs with code revision
`phase3-local`:

| Artifact                       | Snapshot ID                                                        |
| ------------------------------ | ------------------------------------------------------------------ |
| Raw source                     | `a793898150be06e5079dc92a327ab3abe298ca5f3198c10aa9c0745f840b87e2` |
| Processed                      | `0bb163edf0afd6e85246a308734dcb8b55382e48ed6b0af6d291f4f5a19f1c8d` |
| Candidate features and targets | `6e89993c6accc32e21725398f3ca2241c23a745ab4ccbbc9d0568f6f73658968` |
| Quality report                 | `82915a01767250440f3695ed2852ffdd8a56ccfe3a5e53709e02f5bb561843dd` |

The direct run and Airflow run returned the same IDs. Repeated runs, one retry
after verified publication, and a two-date backfill left one transformation run
and one snapshot per artifact kind.

## Local test and quality evidence

Evidence recorded on 2026-08-08/09:

| Evidence                      | Result                                                                                               |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| Python and tooling            | Python 3.11.9; `uv` 0.11.8; Docker 29.1.3; Compose 2.40.3                                            |
| Unit and contract tests       | 134 passed                                                                                           |
| Local integration tests       | 9 passed                                                                                             |
| Deterministic ETL tests       | Passed, including success, reuse, tampering, partial publication, recovery, and fail-closed branches |
| PostgreSQL integration        | 24 passed                                                                                            |
| Actual owner FD001 direct ETL | 1 passed; 20,631 train rows and 13,096 test rows exercised                                           |
| Airflow image/runtime         | Build, health, Airflow 3.3.0, LocalExecutor, and zero import errors passed                           |
| Airflow execution             | 6 passed; normal run and controlled post-publication retry passed on attempt 2                       |
| Airflow backfill              | Two logical dates passed; one reused artifact set                                                    |
| XCom boundary                 | Maximum stored value 381 bytes; identifiers/status only                                              |
| Coverage-compatible suite     | 167 passed; 12 dataset/Airflow/cloud tests deselected                                                |
| Product coverage              | 90.38% branch-aware                                                                                  |
| Formatting, lint, typing      | Ruff and strict mypy passed for 58 source/test files                                                 |
| Dependency audit              | No known vulnerability after locking `cryptography` 50.0.0 and `h2` 4.4.1                            |
| YAML and Compose              | Passed                                                                                               |

The local PostgreSQL database is disposable `tmpfs`. Recreating the Compose
service removes that local database and Airflow history; it does not remove
hosted or durable object data.

## Static-batch claim boundary

FD001 is fixed simulated run-to-failure telemetry. The daily schedule and
backfill demonstrate orchestration, retry, and idempotency. Airflow logical
dates are not source event timestamps, and this evidence is not real-time,
streaming, fleet-scale, or autonomous operation.

## Hosted Supabase evidence

The owner approved the Phase 3 migration and private derived writes on
2026-08-09. The confirmed development/test project remained healthy on its Free
plan; no paid resource was created.

| Evidence                    | Result                                                                                   |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| Migration                   | `20260809165753_phase_03_derived_metadata` applied; repository history matches           |
| Storage adapter             | 1 hosted test passed in 38.13 seconds                                                    |
| Private derived objects     | 10 objects uploaded/downloaded and SHA-256 verified; exact rerun reused all 10           |
| Generated conflict cleanup  | 1 hosted test passed in 6.67 seconds; only its generated `_integration` key was removed  |
| Derived PostgreSQL metadata | 3 snapshots, 7 data/report files, 3 manifests, and 1 available run                       |
| Lineage                     | 24 total edges: 11 manifest, 7 derived-from, and 6 report edges                          |
| Reconciliation              | 0 invalid derived references                                                             |
| Access boundary             | RLS on; `anon`/`authenticated` denied; runtime grants present; no Airflow table in `ops` |
| Security Advisor            | 0 findings                                                                               |
| Performance Advisor         | 9 informational notices and 1 performance warning; no critical/high finding              |

The accepted actual-FD001 derived snapshot IDs are:

| Artifact                       | Snapshot ID                                                        |
| ------------------------------ | ------------------------------------------------------------------ |
| Processed                      | `30e22602ec9528c8d348bda68ef7c9294586a8d05f769daaba2c9e4a4147a7c2` |
| Candidate features and targets | `d16197d85f439083041364142be3e0d76647943fade35c55212b0a48dd49ec44` |
| Quality report                 | `d1dcd2d2506b02ae24fa5c88ee6506ca865f3da229e086c2ba051f132fd71a57` |

The Python Supabase Storage adapter was exercised end to end. The direct hosted
PostgreSQL adapter was retried but the workstation could not resolve the
database hostname. The metadata transaction and verification therefore used
the authenticated project-scoped SQL channel. These are separate evidence
paths and are not claimed as one hosted Python pipeline run.

## GitHub Actions evidence

Runs `31274882270`, `31325137898`, `31325822247`, and `31326394097` correctly
failed on cross-platform fixture line endings and two layers of fresh-runner
host/container filesystem permissions. The final diagnostic log proved that
atomic files inherited owner-only mode `600` from `mkstemp`, so the separate
Airflow user could not read the raw manifest. The adapter now gives completed
immutable local objects mode `644`, verifies existing objects before any
temporary write, and has regression tests for both contracts.

Run `31327359011`, job `Phase 0 quality`, passed on the completed
implementation commit `646984b` in 2 minutes 51 seconds. It included the
pinned Airflow image build, Linux LocalExecutor execution, controlled retry,
two-date backfill, coverage, formatting, linting, typing, migration/recovery,
dependency audit, and cleanup. The completion-state documentation commit is
also subject to the same required PR check.

`main` branch protection was queried after the passing run. It still requires
strict `Phase 0 quality`, a pull request, resolved conversations, and admin
enforcement; force pushes and branch deletion remain disabled.

## Known limitations and deferred work

- The first feature snapshot is a passthrough settings/sensors view; it does
  not claim predictive improvement.
- Fitted preprocessing, engine-disjoint splits, model training, MLflow, and
  performance gates remain Phase 4 work.
- Local Airflow standalone/LocalExecutor is development evidence, not a
  production orchestration deployment.
- The workstation's hosted PostgreSQL network limitation requires Storage and
  project-scoped SQL evidence to be reported separately unless connectivity
  changes.
- Application immutability is not compliance-grade WORM; privileged cloud
  administrators retain deletion/replacement authority.
- The Performance Advisor reports one multiple-permissive-policy warning and
  informational unused-index notices on this tiny research workload. There is
  no critical/high finding; policy consolidation and index usage should be
  reassessed using measured workload evidence rather than speculative changes.

## Current handoff

Phase 3 is `AWAITING_APPROVAL`. Stop completely and wait for the owner command:

`APPROVE PHASE 3`

Do not plan or implement Phase 4.
