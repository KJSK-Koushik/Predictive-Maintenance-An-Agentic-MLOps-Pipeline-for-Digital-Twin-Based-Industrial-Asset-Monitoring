# Phase 6 Acceptance Criteria

## Authorization and scope

- [ ] `START PHASE 6` is received before implementation begins.
- [ ] Local/ephemeral staging, no-production scope, human roles, recovery
  objective, local MLflow, and Supabase test-project prerequisites are
  reconfirmed.
- [ ] The actual release is not promoted or deployed until the owner explicitly
  approves its exact release ID.
- [ ] No monitoring, retraining, agent, dashboard, public API, production,
  FD002-FD004, paid resource, or physical-control feature is introduced.

## Registry and selected-model integrity

- [ ] The release gate requires the exact approved Phase 5 feature, split,
  comparison, and selection identities.
- [ ] The registered regression artifact is the selected histogram gradient
  boosting model and the registered classifier is the retained logistic model.
- [ ] Each registered version binds its source run, task, feature order,
  artifact digest, signature, trusted types, code, dependencies, and selection
  identity.
- [ ] Registration uses the database-backed local MLflow registry and creates
  candidate versions only.
- [ ] Registered artifacts pass verified `skops` loading and prediction parity;
  unsafe or unknown serialized types fail closed.
- [ ] Registration, tags, aliases, approval, packaging, and deployment are
  separate tested operations.
- [ ] No `production` model alias, stage, or deployment is created.

## Approval and operational metadata

- [ ] One CLI-generated forward-only migration adds private release, approval,
  deployment, and rollback evidence without modifying managed Supabase schemas.
- [ ] Clean apply, reset/reapply, constraints, indexes, grants, RLS, migration
  history, backup, and restore pass on PostgreSQL 17.
- [ ] `PUBLIC`, `anon`, and `authenticated` cannot access Phase 6 operational
  records; the runtime role has only required operations.
- [ ] Approval/rejection and deployment/rollback events are append-only and bind
  actor, release ID, evidence IDs, timestamps, and bounded reasons.
- [ ] A missing, rejected, stale, mismatched, or tampered approval prevents alias
  mutation, packaging, publication, and deployment.
- [ ] The completion evidence includes the exact explicit human staging-release
  approval without placing a credential or private endpoint in Git.

## Release packaging and publication

- [ ] One canonical release manifest binds both task versions and every required
  data, model, signature, dependency, approval, and previous-release identity.
- [ ] The release ID is a SHA-256 of canonical manifest content and changes when
  any governed input changes.
- [ ] Repeated clean packaging produces identical manifest and model bytes.
- [ ] Local publication is put-if-absent, rehashes stored bytes, permits exact
  reuse, and rejects different-byte conflicts.
- [ ] Hosted publication, if authorized, uses the private derived bucket under
  the approved model prefix and verifies downloaded SHA-256 values.
- [ ] Partial object/database failure, retry, reconciliation, and separate
  metadata/object recovery are exercised.
- [ ] Generated releases, model bytes, credentials, endpoints, and full
  telemetry/prediction data remain outside Git.

## FastAPI inference contract

- [ ] The service exposes only the documented versioned prediction, release,
  liveness, and readiness endpoints.
- [ ] Readiness fails until both artifacts, the manifest, signatures, trusted
  types, digests, and startup parity fixture are verified.
- [ ] Prediction accepts 1-128 observations with positive identity fields and
  exactly the 24 ordered finite telemetry features.
- [ ] Identity fields and targets never enter either model matrix.
- [ ] Missing, extra, invalid, non-finite, oversized, and wrong-content-type
  requests return stable bounded errors without model execution.
- [ ] RUL output is finite and non-negative; probability is finite and within
  `[0, 1]`; risk label uses horizon 30 and threshold 0.5.
- [ ] Responses include immutable release/model provenance and explicitly state
  that per-prediction uncertainty is unavailable.
- [ ] OpenAPI and response schemas are versioned and checked into contract
  tests.
- [ ] Logs omit complete features, predictions, credentials, private endpoints,
  absolute paths, and stack traces.

## Container, staging, and rollback

- [ ] The inference image uses a digest-pinned Python 3.11 base, locked runtime
  dependencies, a non-root user, exec-form startup, and a health check.
- [ ] The image contains exactly one verified release and contains no secret.
- [ ] The Compose staging service binds only to loopback and applies supported
  read-only filesystem, capability, resource, and restart controls.
- [ ] Synthetic CI builds the image, starts it, checks readiness/OpenAPI/error
  contracts, and verifies prediction parity.
- [ ] The owner-approved actual FD001 release is deployed to local staging and
  passes the same smoke/parity tests.
- [ ] A corrupted, mismatched, or unhealthy candidate does not replace the
  previous staging release.
- [ ] Explicit rollback restores the previous release, passes post-rollback
  parity, and records the event.
- [ ] The measured rollback meets the five-minute local objective or the phase
  remains incomplete or records an owner-approved revised objective.

## CI/CD and security

- [ ] Pull-request CI remains read-only, credential-free, and deployment-free.
- [ ] API contract, container build/smoke, migration, registry, release, and
  rollback tests are required CI checks where they can use synthetic evidence.
- [ ] A separate manual staging workflow uses `workflow_dispatch`, the protected
  `staging` environment, least permissions, bounded concurrency, and no
  production target.
- [ ] The completion report distinguishes PR CI, local actual staging, hosted
  Supabase, protected-workflow, mocked, and unexercised evidence.
- [ ] Dependency locking, audit, secret scanning, image inspection, and model
  artifact trust checks pass with no unresolved critical/high issue.
- [ ] Production inputs fail closed because no production target is configured.

## Regression tests and documentation

- [ ] All applicable Phase 0-5 regression tests continue to pass.
- [ ] Product code maintains at least 90% branch-aware coverage.
- [ ] Formatting, linting, strict typing, lock, Markdown, YAML, migration,
  Docker, and dependency/security checks pass locally.
- [ ] The required GitHub Actions workflow passes on the completion commit.
- [ ] Master, roadmap, data contract, security, test, manual-prerequisite, ADR,
  README, status, and Phase 6 documents match exercised behavior.
- [ ] The completion report records exact commands, versions, results, URLs,
  limitations, skipped evidence, rollback timing, and severity findings.
- [ ] `docs/PROJECT_STATUS.md` becomes `AWAITING_APPROVAL` only after every
  required criterion is satisfied.
- [ ] The completion handoff asks for `APPROVE PHASE 6` and stops completely.
