# Phase 3 Plan

## Authorization

Planning was authorized on 2026-07-31 by explicit `PLAN PHASE 3` after Phase 2
was owner-approved and merged. Implementation is not authorized until the owner
sends `START PHASE 3`.

This planning command authorizes documentation and governance changes only. It
does not authorize dependency installation, an Airflow runtime, a database
migration, derived artifact publication, or cloud mutation.

## Objective

Implement a reproducible FD001 batch ETL pipeline with immutable processed,
candidate-feature, target, and quality-report artifacts. Expose the same tested
pipeline through a direct CLI and a thin Airflow DAG, then prove retry, failure,
backfill, idempotency, lineage, and local-versus-cloud behavior.

## Refined scope

Phase 3 will:

- consume only an explicit available Phase 2 raw snapshot;
- reuse the Phase 1 executable contract and label semantics;
- write typed Parquet and canonical JSON artifacts;
- create a simple candidate-feature snapshot without fitted preprocessing;
- extend private operational metadata for derived snapshots and
  transformation runs;
- run core ETL independently of Airflow;
- add one scheduled Airflow DAG using `LocalExecutor` locally;
- exercise retry, failure, rerun, and backfill behavior;
- publish to the approved Supabase development/test project only after a
  separate cloud-mutation confirmation; and
- expand CI with container, DAG, migration, ETL, recovery, and coverage gates.

Phase 3 will not train a model or use feature performance to select inputs.

## Work breakdown after start authorization

1. Reconfirm the exact local and hosted targets and complete the Phase 3 manual
   prerequisites.
1. Check the current supported Airflow, PyArrow, PostgreSQL, Python, and provider
   compatibility using official sources.
1. Pin the official Airflow Python 3.11 image by version and digest and pin all
   added Python dependencies in reviewed lock/requirements files.
1. Define processed, feature, target, quality-report, and manifest contracts.
1. Add deterministic Parquet and canonical JSON serialization.
1. Add extraction that accepts only a reconciled available raw snapshot.
1. Add pure transformation and candidate-feature functions with no fitted
   preprocessing.
1. Add derived object keys, identities, manifests, and put-if-absent
   publication.
1. Generate and review one forward-only Phase 3 metadata migration.
1. Extend the PostgreSQL repository for derived snapshots, lineage, run states,
   sanitized failures, and inconsistency blocking.
1. Add the direct Phase 3 CLI and prove exact rerun reuse.
1. Build the minimal local Airflow image and isolated metadata database.
1. Add the thin scheduled DAG with explicit parameters, bounded retries,
   timeouts, and identifier-only XCom.
1. Add unit, contract, integration, migration, security, failure, recovery, DAG,
   and backfill tests alongside implementation.
1. Exercise the actual owner-provided FD001 snapshot locally.
1. After separate approval, exercise derived artifacts and metadata in the
   approved Supabase development/test project.
1. Run Supabase Security and Performance Advisors and resolve introduced
   critical/high findings.
1. Expand GitHub Actions without credentials, deployment, or cloud mutation.
1. Update all affected source-of-truth documents, ADRs, and the completion
   evidence.

## Expected new files

```text
src/predictive_maintenance/etl/
  __init__.py
  models.py
  extraction.py
  transformation.py
  features.py
  quality.py
  publication.py
  pipeline.py
  cli.py

orchestration/airflow/
  Dockerfile
  requirements.txt
  dags/fd001_etl.py

supabase/migrations/<timestamp>_phase_03_derived_metadata.sql

tests/etl/
tests/integration/airflow/
tests/integration/postgres/
tests/integration/hosted_supabase/
```

Names may be combined when that produces a simpler boundary. Phase 3 will not
create a generic transformation framework, feature-store product, worker fleet,
or new deployable application service.

## Existing files expected to change

```text
.env.example
.github/workflows/ci.yml
.gitignore
README.md
compose.yaml
pyproject.toml
uv.lock
src/predictive_maintenance/cloud/
src/predictive_maintenance/data/
supabase/config.toml
tests/foundation/test_repository_contract.py
tests/integration/test_ci_contract.py
docs/DATA_CONTRACT.md
docs/MASTER_ARCHITECTURE.md
docs/MANUAL_PREREQUISITES.md
docs/PROJECT_STATUS.md
docs/SECURITY_AND_SECRETS.md
docs/TEST_STRATEGY.md
docs/adr/
docs/phases/phase-03/
```

Any file outside this list requires a Phase 3 justification. Model, MLflow,
serving, monitoring, agent, or dashboard files are prohibited.

## Architecture decisions to document

Implementation must add focused ADRs for:

1. deterministic Parquet and canonical JSON derived contracts;
1. derived snapshot and transformation-run identity;
1. minimal candidate-feature view and fitted-preprocessing deferral;
1. staged derived object/PostgreSQL publication and reconciliation;
1. thin Airflow DAGs with pure Python business logic;
1. Airflow `LocalExecutor` and isolated metadata database for local evidence;
1. scheduled/static-snapshot and backfill semantics; and
1. identifier-only XCom and secret/logging boundaries.

Related decisions should be combined into a small number of ADRs. Existing
accepted ADRs are not rewritten to hide a changed decision.

## Planned CI growth

Phase 3 CI will retain every Phase 2 gate and add:

- deterministic ETL and output-contract tests;
- derived migration clean-apply and reset/reapply tests;
- derived publication, lineage, retry, failure, and recovery integration tests;
- Airflow image build and configuration validation;
- DAG import-error and stable-structure checks;
- direct-function versus DAG-run identity comparison;
- backfill and retry smoke tests on committed synthetic fixtures;
- Parquet safety and target-separation checks; and
- an unchanged minimum 90% branch-aware product coverage gate.

Ordinary CI excludes the owner dataset and hosted cloud markers. It contains no
Supabase or production credentials and performs no deployment.

## Manual prerequisites before implementation/cloud exercise

- confirm Docker Compose is at least the Airflow-supported minimum and Docker
  has at least 4 GB available memory;
- approve the local-only Airflow UI port and development credentials policy;
- confirm the same Supabase project remains development/test-only;
- explicitly approve the Phase 3 migration and derived-object writes;
- approve the processed, feature, target, report, and manifest retention rule;
- confirm no paid Airflow or cloud service will be provisioned; and
- provide an IPv6-capable or otherwise reachable PostgreSQL path only if a full
  hosted Python database-adapter run is required.

Credentials remain in ignored local configuration or approved secret stores.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. This includes pure ETL,
deterministic artifact hashes, local PostgreSQL and object integration, actual
FD001 evidence, Airflow DAG/runtime/backfill evidence, approved hosted evidence,
local quality gates, GitHub Actions, documentation, and severity review.

## Planning risks

| Risk                                          | Planned treatment                                                          |
| --------------------------------------------- | -------------------------------------------------------------------------- |
| Airflow overwhelms a small project            | One local runtime and LocalExecutor; no Celery, Redis, Kubernetes, or Helm |
| DAG files absorb business logic               | DAG calls tested application functions and owns orchestration only         |
| Daily schedule is mistaken for live telemetry | Document static batch semantics; logical date is not source event time     |
| Backfill creates duplicate artifacts          | Artifact identity excludes logical date; exact reruns reuse snapshots      |
| Parquet output changes across environments    | Pin writer version/options and test repeatable hashes                      |
| Feature generation causes leakage             | Candidate passthrough view only; no fitted statistics or labels in inputs  |
| Large data moves through XCom                 | Pass only snapshot IDs and bounded statuses                                |
| Task-local files break retries                | Tasks exchange durable object identities, not temporary paths              |
| Storage succeeds before metadata              | Staged publication, verified reuse, transaction, and reconciliation        |
| Airflow metadata mixes with application state | Separate Airflow database/user; no Airflow table in `ops`                  |
| Cloud ports remain unreachable                | Record split evidence honestly; do not claim hosted direct-adapter success |
| CI becomes slow or flaky                      | Separate fast pure tests from bounded container smoke/backfill tests       |
| Phase 4 model work leaks into Phase 3         | No training, split fitting, model metrics, MLflow, or feature tuning       |

## Stop condition

After this plan is reviewed and CI passes, stop completely. Do not add a
dependency, initialize Airflow, create a migration, or implement ETL until the
owner sends:

`START PHASE 3`
