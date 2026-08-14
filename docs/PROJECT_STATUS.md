# Project Status

## Current control state

| Field                     | Value                                    |
| ------------------------- | ---------------------------------------- |
| Current phase             | 4: Baseline model development            |
| Last completed phase      | 3: ETL and orchestration                 |
| State                     | PLANNED                                  |
| Phase 3 planned           | 2026-07-31 by explicit `PLAN PHASE 3`    |
| Phase 3 started           | 2026-08-08 by explicit `START PHASE 3`   |
| Phase 3 approved          | 2026-08-10 by explicit `APPROVE PHASE 3` |
| Phase 4 planned           | 2026-08-14 by explicit `PLAN PHASE 4`    |
| Next permitted transition | Explicit `START PHASE 4`                 |

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

| Evidence                  | Status                                                   |
| ------------------------- | -------------------------------------------------------- |
| Source-of-truth documents | Phase 3 completion and approval recorded                 |
| Accepted ADRs             | 20; Phase 3 decisions recorded                           |
| Phase 1 implementation    | Complete and owner-approved                              |
| Unit/contract tests       | Phase 1 evidence: passed locally, 46                     |
| Integration tests         | Phase 1 evidence: passed locally, 9                      |
| Actual FD001 test         | Phase 1 evidence: passed locally, 1                      |
| Phase 1 product coverage  | Phase 1 evidence: 92.63% branch-aware                    |
| Docker validation         | PostgreSQL 17 clean start/reset/recovery passed locally  |
| GitHub remote             | `origin/main` created at commit `6c968e0`                |
| Code ownership            | `@KJSK-Koushik` recorded in `.github/CODEOWNERS`         |
| Repository license        | Apache-2.0                                               |
| GitHub authentication     | Confirmed for `KJSK-Koushik`                             |
| GitHub Actions run        | Passed: run `30040721136`, job `Phase 0 quality`         |
| Branch protection         | Required CI, PR, conversations; destructive refs off     |
| Phase 1 GitHub Actions    | Passed: run `30153263553`, job `Phase 0 quality`         |
| Phase 2 local tests       | 125 passed; 2 hosted-cloud tests deliberately deselected |
| Product coverage          | Phase 2 CI-compatible evidence: 90.82% branch-aware      |
| Local quality checks      | Format, lint, typing, lock, YAML, audit passed           |
| Actual FD001 publication  | Local filesystem + PostgreSQL publication passed         |
| Backup/recovery           | `pg_dump`, restore, object restore, reconcile passed     |
| Phase 2 GitHub Actions    | Passed: run `30329857089`, job `Phase 0 quality`         |
| Phase 2 branch protection | Strict required CI/PR/review; destructive refs disabled  |
| Phase 2 cloud evidence    | Real Storage and project-scoped PostgreSQL checks passed |
| Supabase target           | Exact development/test project confirmed; Free plan      |
| Supabase advisors         | Security: none; Performance: five informational notices  |
| Critical/high issues      | None unresolved                                          |
| Phase 2 owner approval    | Received explicitly on 2026-07-30                        |
| Phase 3 implementation    | Complete and owner-approved                              |
| Phase 3 local ETL         | Deterministic direct run and actual FD001 run passed     |
| Phase 3 PostgreSQL        | 24 checks passed, including derived backup/recovery      |
| Phase 3 Airflow           | Build, health, retry, and two-date backfill passed       |
| Phase 3 product coverage  | 90.38% branch-aware                                      |
| Phase 3 hosted evidence   | Migration, Storage, SQL, lineage, and advisors passed    |
| Phase 3 GitHub Actions    | Passed: run `31327359011`, job `Phase 0 quality`         |
| Phase 3 owner approval    | Received explicitly on 2026-08-10                        |
| Phase 4 planning          | Complete; implementation and MLflow remain not started   |

## Repository observations

- A user-provided top-level `Data/` directory exists.
- Phase 1 inspected only the confirmed FD001 logical files and generated
  ignored local evidence.
- `Data/` is ignored so raw source material is not committed accidentally.
- FD002-FD004 and the supporting PDF were not parsed or ingested.
- The separate ML-Agent-Factory repository is outside project scope and has not
  been accessed.

## Phase 2 completed boundary

Phase 2 implementation is complete. The delivered scope is private Supabase
Storage zones, a private PostgreSQL `ops` schema, idempotent publication of the
accepted Phase 1 snapshot, metadata and lineage, local substitutes, and
separately recorded real-cloud verification.

The exact hosted development/test target was confirmed and the phase-scoped
cloud mutation was authorized. No paid resource was provisioned. Airflow,
transformations, models, serving, monitoring, agents, and the dashboard remain
outside the Phase 2 boundary.

The implementation includes a pinned PostgreSQL 17 container, one
CLI-generated forward migration, filesystem and Supabase Storage adapters,
direct PostgreSQL metadata access, idempotent publication, lineage,
reconciliation, and guarded hosted verification. The Python Storage adapter was
exercised against the approved hosted project. Hosted database checks used the
authenticated project-scoped Supabase tools because the workstation could not
reach PostgreSQL ports; this is not claimed as a hosted direct-adapter test.

## Phase 3 approved boundary

Phase 3 is limited to deterministic batch ETL, processed and candidate-feature
snapshots, targets, data-quality reports, derived lineage, and thin Airflow
orchestration. The plan uses one local Airflow runtime with `LocalExecutor` and
a separate metadata database. It adds no Celery, Redis, Kubernetes, streaming,
model training, MLflow, serving, monitoring, agent, dashboard, or deployment
component.

The implemented daily schedule and backfill operate on an explicit immutable FD001
snapshot. They demonstrate retry and idempotency; they do not create event time
or support a real-time claim. Local deterministic ETL, PostgreSQL, Airflow,
actual-dataset, retry, recovery, backfill, and coverage checks have passed.
The approved hosted migration, private Storage writes, project-scoped SQL,
lineage verification, conflict cleanup, and advisors have passed. The local
object contract gives a separate Airflow user read access while retaining
owner-only writes, and exact reuse requires no temporary write. The direct
hosted PostgreSQL adapter remains unexercised because the workstation cannot
resolve the database hostname; this limitation is reported separately. The
GitHub Actions run `31327359011` passed every required check and branch
protection remains enforced. The owner explicitly approved Phase 3 on
2026-08-10.

## Phase 4 planned boundary

Phase 4 is planned but not started. It is limited to one verified Phase 3
feature snapshot, a shared engine-disjoint train/validation/test manifest,
train-only preprocessing, fixed dummy/Ridge/logistic baselines, deterministic
aggregate evaluation, and local SQLite-backed MLflow tracking.

NASA training engines will supply one seeded 80/20 development split. The NASA
test partition remains the final holdout. The primary gates compare
engine-balanced validation RMSE and average precision against task-specific
dummy references. No absolute production claim or test-driven tuning is
permitted.

MLflow will remain loopback-only with ignored local metadata/artifacts. Phase 4
will not use Supabase as an MLflow backend, change a Supabase schema, register
or promote a model, add Airflow training, deploy a service, monitor, retrain,
add agents, or implement dashboard work. Implementation requires explicit
`START PHASE 4`.

## Phase history

| Phase | State       | Evidence                                    |
| ----- | ----------- | ------------------------------------------- |
| 0     | APPROVED    | `docs/phases/phase-00/COMPLETION_REPORT.md` |
| 1     | APPROVED    | `docs/phases/phase-01/COMPLETION_REPORT.md` |
| 2     | APPROVED    | `docs/phases/phase-02/COMPLETION_REPORT.md` |
| 3     | APPROVED    | `docs/phases/phase-03/COMPLETION_REPORT.md` |
| 4     | PLANNED     | `docs/phases/phase-04/PLAN.md`              |
| 5-10  | NOT_PLANNED | Await Phase 4 completion and approval       |
