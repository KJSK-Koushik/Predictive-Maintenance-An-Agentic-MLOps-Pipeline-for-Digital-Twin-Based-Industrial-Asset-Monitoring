# Phase 7 Test Plan

## Evidence classes

| Class                  | Environment                                    | What it can prove                                                       |
| ---------------------- | ---------------------------------------------- | ----------------------------------------------------------------------- |
| Unit/contract          | Python, memory, temporary paths                | deterministic metrics, schemas, identities, and trigger rules           |
| Local integration      | filesystem substitute and synthetic release    | publication, reconciliation, API probes, and failure behavior           |
| PostgreSQL integration | disposable PostgreSQL 17                       | constraints, grants, RLS, idempotency, append-only events, and recovery |
| Airflow integration    | pinned local Airflow container                 | thin orchestration, retry, idempotency, and direct/DAG parity           |
| Actual FD001 replay    | ignored owner data and active loopback release | actual simulated replay behavior, not live or field monitoring          |
| Hosted Supabase        | approved development/test project              | real private migration, report objects, permissions, and advisors       |
| GitHub CI              | clean credential-free runner                   | synthetic gates and regression checks, not cloud or deployment          |

No evidence class may be renamed as production monitoring, continuous
retraining, field performance, public availability, or autonomous promotion.

## Unit and contract tests

### Window, reference, and report identity

- canonical reference, window, policy, prediction, label-attachment, report,
  alert, request, and evaluation bytes;
- identity changes for any governed release, data, membership, policy, code,
  dependency, metric, threshold, or parent change;
- stable exact reuse and different-content conflict rejection;
- source partition, engine, cycle, row-count, ordering, and lineage checks;
- replay sequence versus processing-time separation; and
- bounded JSON with finite values and no private paths or endpoints.

### Data quality and adequacy

- exact 24-feature order and dtype rules;
- empty, too-small, missing, extra, duplicate, non-finite, and unordered rows;
- engine-balanced sampling and maximum-per-engine bounds;
- lifecycle-band and operating-setting composition;
- corrupt parent object, wrong release, and stale reference rejection; and
- proof that invalid quality prevents later metric and trigger execution.

### Feature and prediction shift

- known identical distributions produce no shift;
- controlled location, range, and bin-frequency changes produce expected
  metrics and policy states;
- constant and near-constant reference columns remain finite and deterministic;
- reference quantile bins are fixed before the current window is evaluated;
- PSI and robust location metrics match hand-calculated vectors;
- all 24 input features are reported in canonical order;
- RUL, risk probability, and risk prevalence are evaluated separately;
- insufficient samples return `insufficient_data`; and
- a distribution signal is never labelled performance degradation.

### Service evidence

- ready and not-ready probes;
- 2xx, 4xx, and 5xx status summaries;
- deterministic p50, p95, maximum, and request-count calculations;
- timeouts and connection errors become bounded unavailable/alert evidence;
- complete payloads and responses are absent from reports and logs; and
- no production availability or SLA field exists.

### Delayed labels and performance

- predictions are fixed before label access;
- missing labels produce `unavailable` performance;
- exact key-aligned attachment succeeds and creates a new evidence identity;
- missing, duplicate, wrong-partition, wrong-snapshot, stale, and future-leak
  cases fail closed;
- engine-balanced RMSE, MAE, NASA score, average precision, Brier score, and
  calibration summaries match known vectors; and
- small or single-class windows return an honest unavailable/insufficient
  result rather than a fabricated metric.

### Trigger controller

- data-quality alert creates investigation only;
- service alert creates investigation only;
- one drift alert does not create a candidate;
- persistent adequate drift can create exactly one candidate request;
- delayed-performance degradation can create exactly one candidate request;
- unavailable and insufficient evidence cannot trigger;
- exact duplicates reuse an ID and conflicting evidence fails closed;
- trigger results are deterministic and reasons are bounded; and
- no registry, alias, deployment, rollback, or production operation is
  reachable from the controller.

### Champion/challenger

- identical champion and challenger produce a no-change result;
- synthetic improvement passes the existing practical gates;
- regression, classification, robustness, calibration, and interval failures
  correctly retain the champion;
- paired bootstrap resamples whole engines and is reproducible;
- leakage, source-partition, feature, signature, digest, trusted-type, and
  prediction-parity failures reject the challenger;
- eligible means human-reviewable, not promoted; and
- MLflow staging aliases and active release identity remain unchanged after
  both passing and failing evaluations.

## Integration tests

### Local object publication

1. build a deterministic reference and monitoring report;
1. publish with put-if-absent;
1. read and rehash every stored object;
1. repeat and prove exact reuse;
1. attempt a different-byte conflict and fail closed;
1. inject object success followed by metadata failure;
1. retry and converge without deleting verified objects; and
1. report missing, mismatched, and orphan objects without silent repair.

### PostgreSQL migration and recovery

- CLI-generated migration filename and forward history;
- clean apply and destructive-test reset/reapply;
- tables, constraints, foreign keys, checks, indexes, timestamps, and bounded
  text/JSON fields;
- no access for `PUBLIC`, `anon`, and `authenticated`;
- no-login/no-bypass runtime role with narrow grants and RLS policies;
- immutable report and alert/evaluation behavior;
- idempotent monitoring window and candidate request behavior under
  concurrency;
- database failure and retry behavior;
- `pg_dump` and restore into a disposable database; and
- reconciliation with restored object bytes and existing Phase 6 release
  references.

### Inference and monitoring pipeline

The synthetic path will:

1. build and start the existing deterministic synthetic inference release;
1. create a reference profile from synthetic source-training engines;
1. run a no-shift replay window and verify pass states;
1. run controlled feature, prediction, quality, service, and performance
   failures separately;
1. prove predictions are committed before delayed labels are attached;
1. publish the report and metadata;
1. create, duplicate, and reject candidate requests; and
1. prove the active release and aliases never change.

### Airflow

- image and dependency pinning regression;
- no import errors and no network/database/Storage work during parse;
- explicit release, reference, window, and policy identifiers;
- bounded retries, timeout, XCom, and failure evidence;
- no automatic retraining, alias, deployment, or production operation;
- same direct and DAG report/request identities; and
- exact rerun reuse for one immutable window.

### Actual FD001 replay

The separate owner-data run will:

1. verify the active Phase 6 release and every parent identity;
1. create the reference profile only from source-training inputs;
1. select an explicit engine-balanced NASA test replay window;
1. call the actual loopback inference API and record bounded service evidence;
1. create a report with performance unavailable;
1. attach the exact test target snapshot separately and calculate performance;
1. interpret distribution signals alongside lifecycle mix;
1. evaluate trigger rules without adding test rows to training;
1. record a valid no-change or no-new-training-data outcome; and
1. repeat to prove deterministic identities and publication reuse.

The NASA test partition is already observed benchmark evidence. This run does
not create a new blind estimate, live source, field result, or continuous
retraining claim.

## Hosted Supabase verification

Only after the exact development/test project and phase-scoped mutation are
reconfirmed:

- apply exactly the reviewed Phase 7 migration;
- verify migration history, private `ops` placement, constraints, grants, RLS,
  and client-role denial;
- publish approved report bytes only under content-addressed monitoring and
  retraining prefixes;
- download and verify every object size and SHA-256;
- test exact reuse, different-byte conflict, partial failure, retry, and
  reconciliation in generated namespaces;
- verify Phase 6 release records remain unchanged;
- keep PostgreSQL and object-byte backup evidence separate; and
- run Supabase Security and Performance Advisors.

The workstation's hosted direct-PostgreSQL limitation remains separate from
project-scoped SQL evidence. A skipped cloud test is not a hosted pass.

## CI changes

Pull-request CI will add:

- monitoring and retraining unit/contract tests;
- synthetic inference-to-monitor integration;
- Phase 7 PostgreSQL migration and recovery tests;
- trigger deduplication and promotion-denial tests;
- Airflow monitoring DAG regression;
- existing inference container and Phase 0-6 regression suites;
- at least 90% branch-aware product coverage; and
- existing formatting, linting, typing, lock, Markdown, YAML, dependency,
  secret, Docker, and migration checks.

CI remains credential-free, performs no hosted Supabase mutation, and deploys
no release.

## Planned command groups

Exact markers may be refined during implementation:

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
docker compose config --quiet
docker compose up -d --wait postgres
uv run pytest -m "not integration and not dataset and not postgres and not airflow and not mlflow and not cloud and not deployment"
uv run pytest -m "integration and not dataset and not postgres and not airflow and not mlflow and not cloud and not deployment"
uv run pytest -m "postgres and not dataset and not cloud"
uv run pytest -m "mlflow and not dataset and not cloud"
docker compose build inference
docker compose up -d --wait inference
uv run pytest -m "deployment and not dataset and not cloud"
docker compose build airflow
docker compose up -d --wait airflow
uv run pytest -m "airflow and not dataset and not cloud"
uv run pytest -m "not dataset and not airflow and not cloud and not deployment" --cov=src/predictive_maintenance --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
docker compose down --volumes
```

Actual FD001 and hosted Supabase commands run separately with ignored local
configuration and are recorded by evidence class.

## Exit criteria

All acceptance criteria pass; monitoring, delayed-label, trigger,
champion/challenger, persistence, failure, recovery, Airflow, actual replay,
security, and CI evidence is recorded honestly; documentation matches
behavior; and no critical/high issue remains.
