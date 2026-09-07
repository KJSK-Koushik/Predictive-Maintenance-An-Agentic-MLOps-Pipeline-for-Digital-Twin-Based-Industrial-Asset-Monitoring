# Phase 6 Acceptance Criteria

## Authorization and scope

- [x] `START PHASE 6` is received before implementation begins.
- [x] Local/ephemeral staging, no-production scope, human roles, recovery
  objective, local MLflow, and Supabase test-project prerequisites are
  reconfirmed.
- [x] The actual release is not promoted or deployed until the owner explicitly
  approves its exact release ID.
- [x] No monitoring, retraining, agent, working dashboard, public API,
  production, FD002-FD004, paid resource, or physical-control feature is
  introduced.
- [x] UI work is limited to technology-neutral screen design; no frontend
  dependency, browser bundle, dashboard service, or live backend connection is
  introduced.

## Registry and selected-model integrity

- [x] The release gate requires the exact approved Phase 5 feature, split,
  comparison, and selection identities.
- [x] The registered regression artifact is the selected histogram gradient
  boosting model and the registered classifier is the retained logistic model.
- [x] Each registered version binds its source run, task, feature order,
  artifact digest, signature, trusted types, code, dependencies, and selection
  identity.
- [x] Registration uses the database-backed local MLflow registry and creates
  candidate versions only.
- [x] Registered artifacts pass verified `skops` loading and prediction parity;
  unsafe or unknown serialized types fail closed.
- [x] Registration, tags, aliases, approval, packaging, and deployment are
  separate tested operations.
- [x] No `production` model alias, stage, or deployment is created.

## Approval and operational metadata

- [x] One CLI-generated forward-only migration adds private release, approval,
  deployment, and rollback evidence without modifying managed Supabase schemas.
- [x] Clean apply, reset/reapply, constraints, indexes, grants, RLS, migration
  history, backup, and restore pass on PostgreSQL 17.
- [x] `PUBLIC`, `anon`, and `authenticated` cannot access Phase 6 operational
  records; the runtime role has only required operations.
- [x] Approval/rejection and deployment/rollback events are append-only and bind
  actor, release ID, evidence IDs, timestamps, and bounded reasons.
- [x] A missing, rejected, stale, mismatched, or tampered approval prevents alias
  mutation, packaging, publication, and deployment.
- [x] The completion evidence includes the exact explicit human staging-release
  approval without placing a credential or private endpoint in Git.

## Release packaging and publication

- [x] One canonical release manifest binds both task versions and every required
  data, model, signature, dependency, approval, and previous-release identity.
- [x] The release ID is a SHA-256 of canonical manifest content and changes when
  any governed input changes.
- [x] Repeated clean packaging produces identical manifest and model bytes.
- [x] Local publication is put-if-absent, rehashes stored bytes, permits exact
  reuse, and rejects different-byte conflicts.
- [x] Hosted publication, if authorized, uses the private derived bucket under
  the approved model prefix and verifies downloaded SHA-256 values.
- [x] Partial object/database failure, retry, reconciliation, and separate
  metadata/object recovery are exercised.
- [x] Generated releases, model bytes, credentials, endpoints, and full
  telemetry/prediction data remain outside Git.

## FastAPI inference contract

- [x] The service exposes only the documented versioned prediction, release,
  liveness, and readiness endpoints.
- [x] Readiness fails until both artifacts, the manifest, signatures, trusted
  types, digests, and startup parity fixture are verified.
- [x] Prediction accepts 1-128 observations with positive identity fields and
  exactly the 24 ordered finite telemetry features.
- [x] Identity fields and targets never enter either model matrix.
- [x] Missing, extra, invalid, non-finite, oversized, and wrong-content-type
  requests return stable bounded errors without model execution.
- [x] RUL output is finite and non-negative; probability is finite and within
  `[0, 1]`; risk label uses horizon 30 and threshold 0.5.
- [x] Responses include immutable release/model provenance and explicitly state
  that per-prediction uncertainty is unavailable.
- [x] OpenAPI and response schemas are versioned and checked into contract
  tests.
- [x] Logs omit complete features, predictions, credentials, private endpoints,
  absolute paths, and stack traces.

## Container, staging, and rollback

- [x] The inference image uses a digest-pinned Python 3.11 base, locked runtime
  dependencies, a non-root user, exec-form startup, and a health check.
- [x] The image contains exactly one verified release and contains no secret.
- [x] The Compose staging service binds only to loopback and applies supported
  read-only filesystem, capability, resource, and restart controls.
- [x] Synthetic CI builds the image, starts it, checks readiness/OpenAPI/error
  contracts, and verifies prediction parity.
- [x] The owner-approved actual FD001 release is deployed to local staging and
  passes the same smoke/parity tests.
- [x] A corrupted, mismatched, or unhealthy candidate does not replace the
  previous staging release.
- [x] Explicit rollback restores the previous release, passes post-rollback
  parity, and records the event.
- [x] The measured rollback meets the five-minute local objective or the phase
  remains incomplete or records an owner-approved revised objective.

## CI/CD and security

- [x] Pull-request CI remains read-only, credential-free, and deployment-free.
- [x] API contract, container build/smoke, migration, registry, release, and
  rollback tests are required CI checks where they can use synthetic evidence.
- [x] A separate manual staging workflow uses `workflow_dispatch`, the protected
  `staging` environment, least permissions, bounded concurrency, and no
  production target.
- [x] The completion report distinguishes PR CI, local actual staging, hosted
  Supabase, protected-workflow, mocked, and unexercised evidence.
- [x] Dependency locking, audit, secret scanning, image inspection, and model
  artifact trust checks pass with no unresolved critical/high issue.
- [x] Production inputs fail closed because no production target is configured.

## Regression tests and documentation

- [x] `docs/UI_ARCHITECTURE.md` defines the screen hierarchy, low-fidelity
  layouts, shared states, backend owners, maturity gate, safety wording, and
  Phase 9 connection boundary.
- [x] Every screen remains explicitly `Design only`; mock examples are not
  reported as working UI or integration evidence.
- [x] All applicable Phase 0-5 regression tests continue to pass.
- [x] Product code maintains at least 90% branch-aware coverage.
- [x] Formatting, linting, strict typing, lock, Markdown, YAML, migration,
  Docker, and dependency/security checks pass locally.
- [x] The required GitHub Actions workflow passes on the completion commit.
- [x] Master, roadmap, data contract, security, test, manual-prerequisite, ADR,
  README, status, and Phase 6 documents match exercised behavior.
- [x] The completion report records exact commands, versions, results, URLs,
  limitations, skipped evidence, rollback timing, and severity findings.
- [x] `docs/PROJECT_STATUS.md` becomes `AWAITING_APPROVAL` only after every
  required criterion is satisfied.
- [x] The completion handoff asks for `APPROVE PHASE 6` and stops completely.
