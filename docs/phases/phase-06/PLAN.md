# Phase 6 Plan

## Authorization

Planning was authorized on 2026-08-21 by the explicit command
`PLAN PHASE 6`, after Phase 5 was owner-approved and merged.

Implementation is not authorized. This plan permits documentation and
governance changes only. Registry mutation, model approval, release packaging,
Supabase mutation, API implementation, image building, and deployment must wait
for `START PHASE 6` and any narrower approval described below.

## Objective

Create a deterministic, human-approved route from the exact Phase 5 selected
models to an immutable two-model release, local MLflow registry records, a
strict FastAPI service, a hardened container, and an exercised loopback staging
deployment with rollback.

## Refined scope

Phase 6 will:

- register exactly the Phase 5 selected RUL and failure-risk artifacts in the
  existing database-backed local MLflow registry;
- keep MLflow registration separate from operational approval;
- add immutable release, approval, deployment, and rollback evidence to the
  private operational PostgreSQL schema;
- build one content-addressed release containing both task models;
- optionally publish the verified release bytes to the approved private
  Supabase derived bucket after phase-scoped cloud authorization;
- implement a bounded versioned FastAPI prediction contract over the exact 24
  model inputs;
- state explicitly that per-prediction uncertainty is unavailable;
- build a non-root, release-specific container and expose it only on loopback;
- run API contract, model-parity, container smoke, staging failure, and rollback
  tests;
- extend pull-request CI with container and API gates without deployment
  credentials;
- add a separate manual protected-environment staging workflow; and
- establish technology-neutral UI screen designs, states, safety wording, and
  backend dependency gates without adding frontend code; and
- preserve a hard denial for production deployment.

Phase 6 will not select a different model, tune on NASA test, implement
monitoring or a working dashboard, or claim production readiness.

## Work breakdown after start authorization

1. Reconfirm the exact approved Phase 5 selection and generate fresh verified
   local MLflow source runs if the ignored local evidence is unavailable.
1. Verify current locked MLflow, FastAPI, Pydantic, Uvicorn, Docker, GitHub
   Actions, and Supabase APIs before dependency or configuration changes.
1. Review the early screen architecture against the final Phase 6 API fields,
   errors, provenance, freshness, and safety wording; keep every screen in
   `DESIGN ONLY` state.
1. Add canonical release, approval, registry, deployment, and rollback domain
   contracts below infrastructure adapters.
1. Generate one forward-only Phase 6 migration with the Supabase CLI and test
   constraints, grants, RLS, append-only behavior, reset, and recovery locally.
1. Implement local MLflow registration for the two selected trusted artifacts,
   with stable registered names, version tags, exact provenance, and no
   production alias.
1. Implement the deterministic release gate and prove every failure leaves the
   candidate undeployed.
1. Open an immutable staging-approval request and pause before any real Phase 5
   model alias or staging mutation.
1. Ask the owner for an explicit command in this form:
   `APPROVE PHASE 6 STAGING RELEASE <release-id>`.
1. After that exact approval, record the approval event, package the two models,
   and set only the `staging` aliases bound in the approved release.
1. Publish the content-addressed release locally and, if authorized, to the
   approved private Supabase test project with downloaded hash verification.
1. Implement the FastAPI lifespan loader, strict schemas, readiness checks,
   release endpoint, bounded batch prediction, and sanitized errors.
1. Build the pinned non-root inference image and add the loopback-only Compose
   staging service.
1. Exercise a successful actual-FD001 staging deployment, a rejected bad
   candidate, and an explicit rollback to the previous valid release.
1. Add a credential-free synthetic CI release for API, image, and smoke tests.
1. Add a manual GitHub `workflow_dispatch` staging workflow protected by the
   `staging` environment and keep it separate from CI.
1. Run local unit, contract, integration, PostgreSQL, MLflow, API, Docker,
   actual-data, security, and recovery gates.
1. Verify any approved hosted Supabase migration, private object publication,
   permissions, reconciliation, and advisors separately from local evidence.
1. Push the implementation branch and inspect the real required GitHub Actions
   run before claiming completion.
1. Update all source-of-truth documents and record limitations and evidence.

## Expected new files

```text
src/predictive_maintenance/release/
  __init__.py
  models.py
  gates.py
  registry.py
  metadata.py
  packaging.py
  publication.py
  runtime.py
  cli.py

src/predictive_maintenance/serving/
  __init__.py
  contracts.py
  predictor.py
  app.py
  config.py

deployment/inference/
  Dockerfile
  runtime-requirements.txt

tests/release/
tests/serving/
tests/integration/model_registry/
tests/integration/inference_api/
tests/integration/deployment/

supabase/migrations/<cli-generated>_phase_06_model_releases.sql
.github/workflows/staging.yml

docs/adr/0027-*.md
docs/adr/0028-*.md
docs/adr/0029-*.md
docs/UI_ARCHITECTURE.md
```

Files may be combined when that makes the design smaller and clearer. Phase 6
will not create a microservice fleet, Kubernetes manifests, a public gateway,
frontend application, or a production deployment target.

## Existing files expected to change

```text
.dockerignore
.env.example
.github/workflows/ci.yml
.gitignore
README.md
compose.yaml
pyproject.toml
uv.lock
src/predictive_maintenance/modeling/
src/predictive_maintenance/cloud/
src/predictive_maintenance/etl/
supabase/config.toml
tests/fixtures/
tests/foundation/test_repository_contract.py
tests/integration/test_ci_contract.py
tests/integration/postgres/
tests/integration/hosted_supabase/
docs/DATA_CONTRACT.md
docs/MANUAL_PREREQUISITES.md
docs/MASTER_ARCHITECTURE.md
docs/PROJECT_STATUS.md
docs/ROADMAP.md
docs/SECURITY_AND_SECRETS.md
docs/TEST_STRATEGY.md
docs/adr/
docs/phases/phase-06/
```

Existing ETL and Airflow business logic is not expected to change. Small shared
artifact or metadata adapters may be generalized only when Phase 6 requires the
same verified put-if-absent or PostgreSQL behavior.

## Architecture decisions to document

Implementation must create focused ADRs for:

1. two separately registered task models combined into one immutable release,
   with operational PostgreSQL as the approval/deployment authority;
1. strict FastAPI input/output, startup verification, unavailable predictive
   uncertainty, and immutable release loading; and
1. loopback/ephemeral staging, CI/CD separation, human approval, failure-safe
   rollout, rollback, and explicit absence of a production target.

The implementation must also update ADR-0007 and ADR-0009 through references,
not rewrite their historical decisions.

## Manual prerequisites before implementation

- Accept the recommended staging target: loopback-only Docker Compose on the
  owner workstation plus an ephemeral GitHub protected-environment validation.
- Explicitly limit Phase 6 to staging; no production target or public endpoint
  exists.
- Confirm `KJSK-Koushik` as model-promotion, staging-deployment, and rollback
  approver/owner.
- Create or approve creation of a GitHub environment named `staging`, with a
  required owner review. Do not enable “prevent self-review” while one person
  holds all human roles.
- Accept the planned five-minute local staging recovery-time objective as a
  test target, not a current guarantee.
- Keep MLflow loopback-only with SQLite/local artifacts; no remote unauthenticated
  tracking server is authorized.
- Approve a new local migration and, after review, its application to the same
  development/test Supabase project used in Phases 2-3.
- Approve private derived-bucket writes only under the content-addressed
  `models/releases/<release-id>/` prefix and generated integration prefixes.
- Keep Supabase, PostgreSQL, and GitHub credentials outside images, Git, logs,
  MLflow tags, and release manifests.
- Accept that the actual staging release requires the later explicit command
  `APPROVE PHASE 6 STAGING RELEASE <release-id>`.

Sending `START PHASE 6` accepts the recommended local/ephemeral staging scope,
the named human roles, the local migration, and the development/test Supabase
verification unless the owner changes an item first. It does not approve an
actual model release, public hosting, production deployment, or paid resource.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. Completion also requires a
real actual-FD001 staging release approved by its exact release ID, successful
rollback evidence, local MLflow registry evidence, all local gates, the required
GitHub Actions CI pass, updated documentation, and no unresolved critical/high
issue.

A protected staging workflow that cannot yet run because it is not on the
default branch must be reported as unexercised; a PR smoke test cannot be
renamed as that workflow. The phase can be approved only with the evidence
classification accepted in the completion report.

## Planning risks

| Risk                                                   | Planned treatment                                                                                            |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Registration is mistaken for approval                  | Keep candidate registration, operational approval, aliasing, and deployment as separate events               |
| A mutable alias changes serving silently               | Bake an immutable release ID into the image; never resolve aliases per request                               |
| Phase 5 model files are unavailable                    | Reproduce the approved run from immutable inputs before registration and compare all identities              |
| Packaging changes predictions                          | Verify signatures, trusted types, digests, and prediction parity before and inside the container             |
| Two task versions become inconsistent                  | Bind both versions in one canonical release manifest and deploy them atomically                              |
| Evaluation intervals are shown as predictive intervals | Return an explicit `not_available` uncertainty status                                                        |
| API accepts malformed or abusive input                 | Strict schema, finite values, extra-field rejection, batch and body limits, bounded errors                   |
| Model loading enables code execution                   | Continue inspected `skops` loading; reject pickle, joblib, cloudpickle, and unknown types                    |
| Failed rollout causes an outage                        | Test in a candidate slot and keep the previous immutable release available                                   |
| Local staging is overstated as production              | Use loopback/ephemeral terminology and publish no SLA, HA, TLS, or field claim                               |
| CI silently deploys                                    | Keep CI credential-free; use a separate manual protected-environment workflow                                |
| Supabase artifacts or records become public            | Private bucket, private `ops` schema, denied client roles, hash verification, advisors                       |
| Phase 6 grows into monitoring/dashboard work           | Defer service monitoring, digital-shadow state, retraining, agents, and dashboard to their owning phases     |
| UI connects to a draft or mocked backend               | Track contract maturity per screen and permit real connection only in Phase 9 after owner-approved contracts |

## Stop condition

Planning changes only architecture, governance, tests for those governance
records, and Phase 6 plan documents. Stop after planning checks and GitHub CI
are verified. Do not register, package, approve, serve, build, migrate, publish,
or deploy until the owner sends:

`START PHASE 6`
