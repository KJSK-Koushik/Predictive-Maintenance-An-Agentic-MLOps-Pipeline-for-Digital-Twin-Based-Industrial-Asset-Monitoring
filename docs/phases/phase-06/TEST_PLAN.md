# Phase 6 Test Plan

## Evidence classes

| Class                  | Environment                                          | What it can prove                                               |
| ---------------------- | ---------------------------------------------------- | --------------------------------------------------------------- |
| Unit/contract          | Python, memory, temporary paths                      | Release identities, gates, API schemas, state transitions       |
| Registry integration   | Real loopback MLflow with temporary SQLite/artifacts | Model version, tag, alias, retrieval, and denial behavior       |
| PostgreSQL integration | Disposable PostgreSQL 17                             | Approval/deployment constraints, grants, RLS, recovery          |
| API integration        | In-process and loopback FastAPI                      | Request, response, startup, readiness, and error contracts      |
| Container smoke        | Built Linux image and Docker Compose                 | Image startup, health, packaged-model parity, resource boundary |
| Actual dataset         | Ignored approved FD001 evidence                      | Real local research release behavior; not CI or field evidence  |
| Hosted Supabase        | Approved test project and private namespace          | Actual hosted migration, object publication, grants, lineage    |
| GitHub CI              | Clean credential-free runner                         | Synthetic build, quality, API, registry, and container gates    |
| Staging workflow       | Protected GitHub environment                         | Manual workflow and approval behavior when actually exercised   |

No evidence may be renamed as production, public-service, physical-engine,
real-time, predictive-interval, or safety evidence.

## Unit and contract tests

### Release identity and gate

- canonical manifest bytes and SHA-256 release identity;
- identity changes for model, source run, signature, selection, dependency,
  code, approval, or previous-release changes;
- exact Phase 5 selected-family and parameter verification;
- correct handling of the retained Phase 4 classifier;
- wrong feature/split/comparison/selection/run/model evidence rejection;
- missing, malformed, duplicated, stale, or tampered evidence rejection;
- artifact digest, signature, trusted-type, and prediction-parity checks;
- deterministic gate results and bounded stable failure codes; and
- proof that gate failure produces no approval, alias, package, or deployment.

### Registry behavior

- stable registered names for both tasks;
- candidate version creation from exact run-owned artifacts;
- complete task/provenance/version tags;
- idempotent exact registration and conflict rejection;
- no alias before human approval;
- staging alias set only for the exact approved versions;
- alias mismatch cannot change an immutable release or running service;
- rollback restores the recorded previous alias/version relationship; and
- production alias and deprecated stage operations remain absent.

### Approval and deployment events

- allowed states and transitions;
- exact release/actor/evidence references;
- immutable approval and rejection events;
- duplicate approval idempotency versus conflicting decision rejection;
- deployment start/success/failure and rollback event order;
- a deployment cannot claim success without passed smoke evidence; and
- sanitized bounded reason and error fields.

### FastAPI schemas

- exact field names, types, order-independent JSON parsing, and extra-field
  denial;
- positive integer engine/cycle values and finite feature values;
- batch boundaries at 0, 1, 128, and 129 observations;
- missing, `null`, string, Boolean, infinity, NaN, and oversized body cases;
- identity/target exclusion from the 24-column model matrix;
- non-negative RUL, bounded probability, horizon 30, and threshold 0.5;
- stable 2xx, 4xx, 422, and 503 response contracts;
- release/model provenance and unavailable predictive-uncertainty field;
- liveness independent of model state and readiness dependent on verified
  model state; and
- bounded structured logging with telemetry-value redaction.

## Integration tests

### Real local MLflow registry

A temporary loopback MLflow server with SQLite and proxied local artifacts
must:

1. log or load verified synthetic Phase 5 source runs;
1. register both task artifacts as candidate versions;
1. verify source run, tags, artifact path, signature, digest, and trusted types;
1. prove no alias exists before approval;
1. record an approved release and set only its staging aliases;
1. retrieve exact versions independently of aliases and check prediction
   parity;
1. mutate an alias and prove the immutable bundle/runtime does not change;
1. exercise rollback; and
1. stop, copy/restore SQLite plus artifacts, restart, and repeat retrieval.

This is real local registry evidence, not remote availability or authentication
evidence.

### PostgreSQL migration and recovery

- CLI-generated migration filename and history;
- clean apply and destructive-test reset/reapply;
- schema, columns, constraints, foreign keys, indexes, and timestamps;
- least grants, no-login/no-bypass runtime role, and RLS defense in depth;
- denial for `PUBLIC`, `anon`, and `authenticated`;
- concurrent/idempotent approval and deployment event behavior;
- backup with `pg_dump`, restore into a disposable database, and exact event
  verification; and
- reconciliation between release objects, registry references, and operational
  metadata.

### API and container

The synthetic release path must:

1. build a two-model release from deterministic fixtures;
1. start the API in-process and verify its OpenAPI document;
1. exercise valid single and maximum-size batch requests;
1. exercise every invalid-input and not-ready case;
1. build the digest-pinned inference image from the committed lock;
1. inspect user, command, health check, labels, layers, and secret absence;
1. start it through Compose on loopback;
1. compare container results with direct approved-model results;
1. corrupt a manifest/model and prove readiness and deployment fail;
1. deploy a second good synthetic release; and
1. roll back and verify the original result and release ID.

### Actual FD001 release

The separate owner-data run must:

1. reproduce or load the exact approved Phase 5 selection evidence;
1. create verified source runs and register the selected regression and
   classification models;
1. record deterministic gate evidence and the release approval request;
1. pause until the owner approves the exact release ID;
1. create the immutable approved bundle and local operational records;
1. build and start the actual release-specific container on loopback;
1. compare bounded direct and container predictions for exact parity;
1. record readiness, latency summaries, image size, startup time, and release
   identifiers;
1. exercise one controlled failed candidate and one explicit rollback; and
1. verify the restored release and measure recovery time.

The NASA test partition remains previously observed research evidence. This
run does not create a new performance estimate or permit retuning.

## Hosted Supabase verification

Only after the approved project and phase-scoped mutation are reconfirmed:

- apply exactly the reviewed Phase 6 migration;
- verify migration history, private schema placement, constraints, grants,
  RLS, and denial for client roles;
- publish only the approved content-addressed model release and generated
  integration objects to the private derived bucket;
- download and verify every object digest and size;
- test exact reuse, different-byte conflict, partial failure, retry, and
  reconciliation;
- keep metadata and object-byte backup procedures separate; and
- run Supabase Security and Performance Advisors.

If the workstation still cannot reach hosted PostgreSQL, project-scoped SQL
tool evidence and direct-adapter evidence remain separate. A skipped hosted
test is not a cloud pass.

## CI and CD checks

Pull-request CI adds:

- Phase 6 unit/contract tests;
- synthetic local MLflow registry integration;
- Phase 6 PostgreSQL migration tests;
- FastAPI OpenAPI and error-contract tests;
- inference image build and container smoke/parity tests;
- production-action denial and workflow contract checks;
- existing 90% branch-aware product coverage; and
- existing formatting, typing, YAML, lock, migration, dependency, secret, and
  earlier-phase regression gates.

The separate staging workflow:

- uses `workflow_dispatch`;
- references the protected `staging` environment;
- accepts only a SHA-256 release ID and an explicit non-production target;
- has bounded concurrency and least GitHub permissions;
- cannot use pull-request event secrets;
- validates the immutable release before rollout;
- records smoke/rollback evidence; and
- rejects a production target because none is configured.

The staging workflow cannot be reported as passed until it is actually present
on the default branch, manually dispatched, approved, and completed. Local
Docker staging and PR container smoke remain separate evidence classes.

## Planned command groups

Exact markers and commands may be refined during implementation, but the plan
adds `registry`, `api`, and `deployment` markers while retaining earlier gates:

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
uv run pytest -m "api and not dataset and not cloud"
docker compose build inference
docker compose up -d --wait inference
uv run pytest -m "deployment and not dataset and not cloud"
docker compose build airflow
docker compose up -d --wait airflow
uv run pytest -m "airflow and not dataset and not cloud"
uv run pytest -m "not dataset and not airflow and not cloud" --cov=src/predictive_maintenance --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
docker compose down --volumes
```

The actual FD001, hosted Supabase, and approved staging-release commands run
separately and are recorded with their exact environments.

## Exit criteria

All acceptance criteria pass; registry, release, approval, actual staging,
failure, rollback, recovery, API, container, security, and CI evidence is
recorded honestly; documentation matches behavior; and no critical/high issue
remains.
