# Project Status

## Current control state

| Field                     | Value                                        |
| ------------------------- | -------------------------------------------- |
| Current phase             | 2: Cloud data foundation                     |
| Last completed phase      | 1: Local dataset ingestion and data contract |
| State                     | IN_PROGRESS                                  |
| Planned                   | 2026-07-25 by explicit `PLAN PHASE 2`        |
| Started                   | 2026-07-26 by explicit `START PHASE 2`       |
| Next permitted transition | Complete Phase 2 acceptance and validation   |

## Bootstrap record

The repository did not contain source-of-truth documents when Phase 0 was
authorized. The owner's initial assignment and explicit start command are the
bootstrap authority for creating them. From this revision onward, this document
is authoritative for the active phase.

## Phase 0 objective

Establish scope, architecture, repository governance, technology decisions,
threat and secret controls, test strategy, CI quality gates, manual
prerequisites, and the Phase 0 evidence record without implementing a project
feature or initializing a cloud service.

## Current evidence

| Evidence                  | Status                                                  |
| ------------------------- | ------------------------------------------------------- |
| Source-of-truth documents | Phase 2 plan active; implementation started             |
| Accepted ADRs             | 17; Phase 2 decisions recorded                          |
| Phase 1 implementation    | Complete and owner-approved                             |
| Unit/contract tests       | Phase 1 evidence: passed locally, 46                    |
| Integration tests         | Phase 1 evidence: passed locally, 9                     |
| Actual FD001 test         | Phase 1 evidence: passed locally, 1                     |
| Phase 1 product coverage  | Phase 1 evidence: 92.63% branch-aware                   |
| Docker validation         | PostgreSQL 17 clean start/reset/recovery passed locally |
| GitHub remote             | `origin/main` created at commit `6c968e0`               |
| Code ownership            | `@KJSK-Koushik` recorded in `.github/CODEOWNERS`        |
| Repository license        | Apache-2.0                                              |
| GitHub authentication     | Confirmed for `KJSK-Koushik`                            |
| GitHub Actions run        | Passed: run `30040721136`, job `Phase 0 quality`        |
| Branch protection         | Required CI, PR, conversations; destructive refs off    |
| Phase 1 GitHub Actions    | Passed: run `30153263553`, job `Phase 0 quality`        |
| Phase 2 local tests       | 124 passed; 2 hosted-cloud tests deliberately skipped   |
| Product coverage          | Phase 2 local evidence: 90.50% branch-aware             |
| Local quality checks      | Format, lint, typing, lock, YAML, audit passed          |
| Actual FD001 publication  | Local filesystem + PostgreSQL publication passed        |
| Backup/recovery           | `pg_dump`, restore, object restore, reconcile passed    |
| Phase 2 cloud evidence    | Not run; local/mocked evidence is not cloud evidence    |
| Supabase target           | Blocked pending owner confirmation of project mismatch  |
| Critical/high issues      | None identified by current planning review              |

## Repository observations

- A user-provided top-level `Data/` directory exists.
- Phase 1 inspected only the confirmed FD001 logical files and generated
  ignored local evidence.
- `Data/` is ignored so raw source material is not committed accidentally.
- FD002-FD004 and the supporting PDF were not parsed or ingested.
- The separate ML-Agent-Factory repository is outside project scope and has not
  been accessed.

## Phase 2 active boundary

Phase 2 implementation is active. The approved scope is private Supabase
Storage zones, a private PostgreSQL `ops` schema, idempotent publication of the
accepted Phase 1 snapshot, metadata and lineage, local substitutes, and
separately recorded real-cloud verification.

Local implementation, migrations, dependencies, containers, and tests are
authorized. No hosted Supabase resource, schema, bucket, or cloud object may be
changed until the owner confirms the exact development/test target and approves
any activation or cost. Airflow, transformations, models, serving, monitoring,
agents, and the dashboard remain outside the Phase 2 boundary.

The local implementation now includes a pinned PostgreSQL 17 container, one
CLI-generated forward migration, filesystem and Supabase Storage adapters,
direct PostgreSQL metadata access, idempotent publication, lineage,
reconciliation, and a guarded hosted-test suite. Only the filesystem and local
PostgreSQL paths have been exercised against real infrastructure.

## Phase history

| Phase | State       | Evidence                                    |
| ----- | ----------- | ------------------------------------------- |
| 0     | APPROVED    | `docs/phases/phase-00/COMPLETION_REPORT.md` |
| 1     | APPROVED    | `docs/phases/phase-01/COMPLETION_REPORT.md` |
| 2     | IN_PROGRESS | `docs/phases/phase-02/PLAN.md`              |
| 3-10  | NOT_PLANNED | Outside the current authorization           |
