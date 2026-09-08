# Phase 7 Plan

## Authorization

Planning was authorized on 2026-08-22 by the explicit command
`PLAN PHASE 7`, after Phase 6 was owner-approved.

Implementation was authorized on 2026-09-07 by the explicit command
`START PHASE 7`. The recommended manual prerequisites were accepted without
changes. This authorization remains limited to the Phase 7 scope and does not
authorize model promotion, deployment, production access, public services, or
paid resources.

## Objective

Implement a deterministic batch monitoring workflow for the exact approved
Phase 6 staging release, persist private monitoring evidence, create governed
retraining-candidate requests, and compare synthetic challengers against the
champion without granting automatic promotion or deployment authority.

## Refined scope

Phase 7 will:

- create an immutable, engine-balanced monitoring reference profile;
- monitor explicit FD001 cycle-replay windows;
- report data quality, feature shift, prediction shift, sampled service
  behavior, and delayed-label performance separately;
- use versioned thresholds and explicit unavailable/insufficient states;
- write canonical reports to local content-addressed storage and, after
  authorization, the approved private Supabase derived bucket;
- add private operational PostgreSQL records for monitoring windows, reports,
  alerts, retraining requests, and challenger evaluations;
- implement deterministic trigger, deduplication, and fail-closed rules;
- attach delayed labels only after prediction evidence is fixed;
- exercise fixed champion/challenger evaluation with synthetic fixtures;
- produce an actual FD001 replay report without adding NASA test rows to
  training;
- add a thin Airflow wrapper only after the direct monitoring path is stable;
- stabilize monitoring and trigger contracts for the future Phase 9 UI; and
- preserve all Phase 6 approval, staging, and rollback controls.

Phase 7 will not build a working UI, add agents, expose a public service,
provision paid resources, or implement unattended retraining or promotion.

## Work breakdown after start authorization

1. Confirm Phase 6 PR 12 is merged to `main` and branch protection is still
   active before implementation starts.
1. Reconfirm the exact active Phase 6 release, feature snapshot, selected
   models, and loopback staging readiness.
1. Verify current NumPy, Pandas, scikit-learn, Airflow, MLflow, FastAPI, and
   Supabase behavior before changing dependencies or schemas.
1. Add typed monitoring-window, reference-profile, report, alert, trigger,
   delayed-label, and candidate-evaluation contracts.
1. Implement deterministic engine-balanced reference profiling and sample
   adequacy rules.
1. Implement data-quality, feature-shift, prediction-shift, service-probe, and
   delayed-performance metrics below infrastructure adapters.
1. Calibrate and version thresholds using reference evidence before reading
   each monitored window.
1. Implement explicit `pass`, `warning`, `alert`, `insufficient_data`,
   `unavailable`, and `invalid` states.
1. Implement canonical JSON reports, SHA-256 identities, bounded content, and
   local put-if-absent publication.
1. Generate one CLI-named forward-only Phase 7 migration and test it against
   disposable PostgreSQL 17.
1. Add least-privilege private metadata persistence, append-only alerts and
   evaluations, idempotent requests, lineage, reconciliation, and recovery.
1. Implement the deterministic trigger controller. Prove that quality and
   service failures open investigations rather than retraining requests.
1. Implement delayed-label attachment with exact key and lineage checks.
1. Implement fixed champion/challenger evaluation and explicit promotion
   denial. Reuse Phase 5 engine-level comparison rules instead of inventing a
   new performance protocol.
1. Add a thin parameterized Airflow monitoring DAG with no deployment or
   automatic retraining authority.
1. Extend credential-free CI with monitoring, migration, trigger,
   challenger-denial, and Airflow regression checks.
1. Run the synthetic no-shift, shifted, unavailable-label, invalid-quality,
   service-failure, duplicate-trigger, and challenger pass/fail scenarios.
1. Run the actual FD001 replay against the approved loopback release and
   report lifecycle-mix limitations explicitly.
1. After explicit cloud authorization, apply only the reviewed migration and
   publish only approved report objects to the existing development/test
   Supabase project.
1. Verify hosted privacy, grants, RLS, object hashes, reconciliation, migration
   history, and Supabase advisors separately from local evidence.
1. Update all source-of-truth documents and affected UI contract designs.
1. Push the implementation branch and inspect the exact GitHub Actions run
   before claiming completion.

## Expected new files

```text
src/predictive_maintenance/monitoring/
  __init__.py
  models.py
  reference.py
  metrics.py
  pipeline.py
  triggers.py
  metadata.py
  publication.py
  runtime.py
  cli.py

src/predictive_maintenance/retraining/
  __init__.py
  models.py
  evaluation.py
  controller.py
  cli.py

orchestration/airflow/dags/fd001_monitoring.py

tests/monitoring/
tests/retraining/
tests/integration/monitoring/

supabase/migrations/<cli-generated>_phase_07_monitoring.sql

docs/adr/0030-*.md
docs/adr/0031-*.md
docs/adr/0032-*.md
```

Files may be combined when a smaller design remains clear. No new service
fleet, message broker, metrics stack, frontend application, or production
target is planned.

## Existing files expected to change

```text
.env.example
.github/workflows/ci.yml
README.md
compose.yaml
pyproject.toml
uv.lock (only if a justified direct dependency changes)
src/predictive_maintenance/modeling/
src/predictive_maintenance/release/
src/predictive_maintenance/serving/ (only bounded monitoring hooks if needed)
src/predictive_maintenance/cloud/
orchestration/airflow/
supabase/config.toml
tests/foundation/test_repository_contract.py
tests/integration/airflow/
tests/integration/postgres/
tests/integration/hosted_supabase/
docs/DATA_CONTRACT.md
docs/MANUAL_PREREQUISITES.md
docs/MASTER_ARCHITECTURE.md
docs/PROJECT_STATUS.md
docs/ROADMAP.md
docs/SECURITY_AND_SECRETS.md
docs/TEST_STRATEGY.md
docs/UI_ARCHITECTURE.md
docs/adr/
docs/phases/phase-07/
```

The existing Phase 6 inference request and response contract should not change.
Any incompatible change requires a new API version and separate review.

## Architecture decisions to document

Implementation must create focused ADRs for:

1. immutable engine-balanced replay windows, reference profiles, effect-size
   monitoring, and explicit lifecycle-mix limitations;
1. private monitoring-report persistence, delayed-label attachment, lineage,
   and idempotent alert/request records; and
1. deterministic trigger semantics, fixed champion/challenger evaluation,
   promotion denial, and reuse of Phase 6 approval/rollback authority.

ADR-0011 remains binding. New ADRs refine its implementation and must not
rewrite its historical decision.

## Manual prerequisites before implementation

- Merge the owner-approved, passing Phase 6 PR 12 into `main` and confirm the
  protected check passes on the merged revision.
- Confirm the active loopback Phase 6 release may be used for bounded Phase 7
  replay probes.
- Accept that actual FD001 monitoring uses already observed, simulated NASA
  test trajectories and is not live or production evidence.
- Confirm NASA test rows remain prohibited from candidate training.
- Accept that without a new approved labeled dataset, the actual retraining
  path may correctly end as no-change or `blocked_no_new_training_data`.
- Approve local ignored monitoring evidence under `artifacts/monitoring/`.
- Approve a reviewed Phase 7 migration in the existing development/test
  Supabase project after local tests pass.
- Approve private derived-bucket writes only under content-addressed
  `reports/monitoring/`, `reports/retraining/`, and generated integration
  prefixes.
- Confirm no Supabase Auth, Realtime, Cron, public API, paid add-on, managed
  monitoring service, or external paging service will be provisioned.
- Keep Supabase, PostgreSQL, MLflow, GitHub, and staging values in ignored local
  configuration or approved secret stores.
- Confirm the project owner remains the human reviewer for any challenger
  eligibility result.

Sending `START PHASE 7` will accept these recommended prerequisites unless the
owner changes an item first. It will not approve a new model release, alias
change, staging deployment, production action, cloud spend, or public service.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. Completion also requires:

- deterministic synthetic monitoring and trigger evidence;
- actual FD001 replay evidence against the exact approved loopback release;
- explicit missing/delayed-label behavior;
- champion/challenger pass, fail, duplicate, and promotion-denial evidence;
- local PostgreSQL, Storage, Airflow, API, recovery, security, and coverage
  gates;
- separately classified hosted Supabase evidence;
- the required GitHub Actions pass on the completion commit;
- updated monitoring/UI contract documentation; and
- no unresolved critical or high-severity issue.

The phase does not require inventing an eligible actual challenger when the
approved data cannot support one. A scientifically honest no-change result is
valid if the complete trigger and evaluation mechanics are exercised.

## Planning risks

| Risk                                                        | Planned treatment                                                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Expected lifecycle degradation is called drift              | Report lifecycle mix and call signals distribution shift, not physical degradation                |
| Large row counts create tiny but meaningless differences    | Use engine balancing, adequacy rules, calibrated reference thresholds, and practical effect sizes |
| Missing labels are treated as good performance              | Use explicit `unavailable` state and prohibit performance triggers                                |
| Data-quality failure causes retraining                      | Route quality failures to investigation only                                                      |
| NASA test leaks into training                               | Enforce source-partition denial in candidate-data contracts                                       |
| Static FD001 is described as continuous monitoring          | Use explicit immutable replay windows and no live-time claim                                      |
| A drift alert changes the serving model                     | Give trigger code no registry/deployment credential and test alias immutability                   |
| Challenger evaluation silently changes the Phase 5 protocol | Reuse fixed engine-level metrics and guardrails with immutable evidence                           |
| Reports leak telemetry or credentials                       | Store bounded aggregates, redact errors, scan controlled files, and keep objects private          |
| Monitoring adds an unnecessary platform stack               | Start with project-owned batch metrics and existing Airflow/PostgreSQL/Storage adapters           |
| UI connects before contracts are approved                   | Keep every screen `Design only`; Phase 9 owns connection                                          |
| Phase 6 unmerged history causes a stacked implementation    | Require Phase 6 merge and merged CI before `START PHASE 7` work                                   |

## Stop condition

Planning stops after these documents are validated. No Phase 7 feature,
migration, report object, Airflow DAG, monitoring run, or challenger evaluation
may be created before:

`START PHASE 7`
