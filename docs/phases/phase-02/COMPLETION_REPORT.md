# Phase 2 Completion Report

## Status

**IN PROGRESS — hosted Supabase and GitHub CI evidence remain blocked.**

## Authorization

`PLAN PHASE 2` was received on 2026-07-25. `START PHASE 2` was received on
2026-07-26. Local implementation, dependencies, migrations, containers, and
tests are authorized. Hosted Supabase mutation is not authorized until the
exact development/test target and any activation cost are approved.

## Implemented local foundation

- Supabase CLI configuration and one CLI-generated forward migration;
- PostgreSQL 17 with five private `ops` tables, constraints, grants, RLS, and a
  no-login runtime role;
- configurable raw and derived bucket roles;
- filesystem and Supabase Storage put-if-absent adapters;
- snapshot publication using the Phase 1 snapshot ID;
- atomic metadata, object/file links, lineage, and ingestion-run records;
- missing, mismatched, and orphan reconciliation;
- a sanitized local/cloud publication CLI;
- a guarded hosted Supabase test suite excluded from normal CI; and
- PostgreSQL plus object-byte backup/restore reconciliation.

No transformation, processed dataset, feature snapshot, Airflow component,
model, service, monitoring job, agent, or dashboard was added.

## Local evidence recorded on 2026-07-26

| Evidence               | Result                                                        |
| ---------------------- | ------------------------------------------------------------- |
| Runtime                | Python 3.11.9; `uv` 0.11.8                                    |
| Migration tooling      | Supabase CLI 2.109.1                                          |
| Container tooling      | Docker 29.1.3; Compose 2.40.3                                 |
| Database               | PostgreSQL 17.10, loopback-only disposable container          |
| Clean Compose start    | Passed with health wait                                       |
| Full non-cloud suite   | 124 passed; 2 hosted tests skipped                            |
| Actual FD001           | Local publication and exact rerun reuse passed                |
| PostgreSQL integration | 18 passed                                                     |
| Clean reset/reapply    | Equivalent schema fingerprints passed                         |
| Recovery               | `pg_dump`, restore database, object restore, reconcile passed |
| Coverage               | 90.82% branch-aware using the CI-compatible selector          |
| Formatting/lint/typing | Ruff and strict mypy passed                                   |
| Lock/YAML              | `uv lock --check` and yamllint passed                         |
| Dependency audit       | No known vulnerabilities; local project itself skipped        |
| Secret/target scan     | Repository contract test passed                               |

The Supabase adapter tests use an in-memory SDK boundary. They prove adapter
logic, not hosted Supabase behavior. The filesystem substitute and local
PostgreSQL are also reported only as local evidence.

## Evidence not yet available

- exact approved hosted Supabase target preflight;
- real private bucket, upload, download, conflict, database, lineage,
  idempotency, reconciliation, and cleanup results;
- hosted migration-history comparison;
- Supabase Security and Performance Advisor results;
- owner-approved hosted database and object backup method;
- GitHub Actions pass for the Phase 2 commit; and
- branch-protection verification for that commit.

## Current blockers

1. The exact Supabase development/test target must be confirmed because the
   connected project does not match the private URL supplied earlier.
1. Activation/cost and cloud mutation must be explicitly approved.
1. Safe target contents, region, bucket names, Data API posture, migration
   authority, and hosted backup method must be confirmed.
1. The implementation must be pushed before GitHub Actions and current branch
   protection can be verified.

## Severity and limitations

No critical or high-severity issue was found in the completed local checks.
Phase 2 cannot be completed while the hosted and GitHub evidence above is
missing. Raw overwrite denial is application-enforced and is not WORM. The
local PostgreSQL and filesystem substitutes are not treated as proof of hosted
Supabase behavior.
