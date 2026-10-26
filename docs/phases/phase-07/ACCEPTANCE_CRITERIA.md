# Phase 7 Acceptance Criteria

Verification is recorded by evidence class in `COMPLETION_REPORT.md`.
Challenger pass/fail checks use synthetic fixtures and cannot be read as a
claim that a new actual model was verified or promoted. Hosted scoped SQL is
separate from the locally tested restricted-role PostgreSQL adapter. All
screens remain disconnected designs until the owning contracts are approved.

## Authorization and scope

- [x] `START PHASE 7` is received before implementation begins.
- [x] The approved Phase 6 work is merged to `main` and its required GitHub
  check passes on the merged revision.
- [x] The exact Phase 6 release, feature snapshot, and loopback staging target
  are reconfirmed before monitoring evidence is generated.
- [x] No working UI, agent, public service, production target, automatic
  retraining, automatic promotion, FD002-FD004, or paid resource is introduced.
- [x] NASA test rows remain unavailable to candidate fitting and configuration
  selection.

## Monitoring contracts and identity

- [x] Reference-profile, monitoring-window, policy, report, delayed-label,
  alert, request, and evaluation schemas are versioned and strictly validated.
- [x] Every identity binds the exact data, release, policy, code, dependency,
  and parent evidence required by its contract.
- [x] Canonical JSON and SHA-256 identities are deterministic across clean
  repeated runs.
- [x] The same exact window and policy reuses the same report; different
  governed inputs create a different identity or a conflict.
- [x] Source partition plus engine ID and cycle remain the row identity.
- [x] Replay sequence and processing time remain separate from telemetry cycle;
  no synthetic event-time or real-time claim is created.

## Reference and data quality

- [x] The reference profile uses only the approved source-training input and
  exact active release.
- [x] Sampling and aggregate metrics are engine-balanced and bounded.
- [x] Reference bins, adequacy rules, thresholds, and policy identity are fixed
  before the monitored window is evaluated.
- [x] Schema, required features, finite values, keys, duplicate rows, cycle
  order, lineage, release, and object integrity are checked before drift.
- [x] Invalid quality blocks feature drift, prediction drift, performance, and
  retraining-request creation.
- [x] Lifecycle-band and operating-setting composition are recorded so expected
  lifecycle change is not silently described as model degradation.

## Monitoring signals

- [x] Data quality, feature shift, prediction shift, service health, and
  delayed-label performance remain separate report sections and statuses.
- [x] Feature shift covers all 24 ordered model inputs using deterministic
  fixed-reference metrics and practical effect-size thresholds.
- [x] Prediction shift covers RUL, risk probability, and risk-label prevalence
  without calling shift a performance failure.
- [x] Service monitoring records bounded readiness, status, request count, and
  p50/p95/max latency from actual loopback probes.
- [x] Service evidence is not described as production availability or an SLA.
- [x] Every signal uses only `pass`, `warning`, `alert`,
  `insufficient_data`, `unavailable`, or `invalid`.
- [x] Reports are bounded and omit complete telemetry, complete prediction
  dumps, secrets, private endpoints, absolute paths, and unrestricted errors.

## Delayed-label performance

- [x] Predictions and their report identity are fixed before labels may be
  attached.
- [x] A report without labels explicitly states that performance is
  unavailable.
- [x] Label attachment requires exact snapshot, partition, key, row-count, and
  lineage alignment.
- [x] Missing, duplicate, stale, mismatched, or leaked labels fail closed.
- [x] Available performance uses the approved engine-balanced RUL and risk
  metrics with bounded aggregate output.
- [x] Label attachment creates new immutable evidence and cannot overwrite the
  original prediction report.

## Trigger and retraining-candidate governance

- [x] Data-quality and service failures open investigations and cannot create
  retraining candidates.
- [x] One drift alert opens an investigation; candidate creation requires the
  policy's persistence and adequacy rules.
- [x] Confirmed adequate delayed-performance degradation may create a candidate
  request under the exact versioned policy.
- [x] Unavailable or insufficient evidence cannot create an eligible request.
- [x] Candidate requests are content-addressed, deduplicated, attributable, and
  conflict-safe.
- [x] A request contains an immutable data cutoff and never implies approval,
  training success, registration, or deployment.
- [x] The trigger controller has no code path or credential for MLflow alias
  mutation, deployment, rollback, or production action.

## Champion/challenger evaluation

- [x] Synthetic passing and failing challengers are compared with the champion
  on identical engine-group evaluation rows.
- [x] Paired whole-engine evidence and the approved Phase 5 practical
  guardrails determine eligibility.
- [x] Data, leakage, reproducibility, feature, signature, trusted-type,
  performance, robustness, security, and release-compatibility checks pass
  before eligibility.
- [x] A failed challenger remains contained and leaves the active release and
  MLflow staging aliases unchanged.
- [x] An eligible challenger produces only a human-review handoff and still
  cannot change an alias or deployment.
- [x] Actual FD001 evaluation honestly records no-change or
  `blocked_no_new_training_data` when no new approved training data exists.
- [x] Existing Phase 6 staging smoke and rollback regression tests continue to
  pass.
- [x] No production alias, target, approval, or deployment is created.

## Persistence, PostgreSQL, and Storage

- [x] One CLI-generated forward-only migration adds only Phase 7 private `ops`
  objects and does not modify managed Supabase schemas.
- [x] PostgreSQL 17 clean apply, reset/reapply, migration history, constraints,
  indexes, grants, RLS, append-only behavior, backup, and restore pass.
- [x] `PUBLIC`, `anon`, and `authenticated` cannot access monitoring or
  retraining records; the runtime role has only required operations.
- [x] Monitoring and retraining report publication is put-if-absent, verifies
  stored bytes, supports exact reuse, and rejects different-byte conflicts.
- [x] Partial object/database failure, retry, reconciliation, orphan reporting,
  and separate metadata/object recovery are exercised.
- [x] Hosted evidence, if authorized, uses only the approved private project,
  bucket prefixes, migration, and generated integration namespace.
- [x] Supabase Security and Performance Advisors are checked and no critical or
  high-severity issue remains unresolved.

## Airflow, CI, security, and regression

- [x] Core monitoring, metrics, trigger, and evaluation logic runs without
  Airflow or cloud services.
- [x] The Airflow DAG is thin, parameterized by immutable identifiers,
  parse-safe, bounded, idempotent, and has no deployment or automatic-training
  authority.
- [x] Direct and Airflow execution produce the same report and request
  identities for the same inputs.
- [x] Pull-request CI remains read-only, credential-free, and deployment-free.
- [x] Synthetic monitoring, migration, trigger, challenger-denial, container,
  Airflow, and prior-phase regression tests are required CI checks.
- [x] Product code maintains at least 90% branch-aware coverage.
- [x] Formatting, linting, strict typing, dependency lock, Markdown, YAML,
  Docker, migration, secret, and dependency-security checks pass locally.
- [x] Required GitHub Actions passes on the completion commit.

## Actual evidence, UI contracts, and documentation

- [x] An actual FD001 cycle-replay window is monitored against the exact
  approved loopback release and reported separately from synthetic tests.
- [x] The actual report records lifecycle-mix and already-observed-benchmark
  limitations and makes no live, field, or production claim.
- [x] Monitoring and trigger field meanings, freshness, nullability, partial,
  stale, unavailable, and error states are documented for the future UI.
- [x] Every UI screen remains `Design only`; no browser-facing read API or live
  connection is created.
- [x] Master, roadmap, data, security, test, manual-prerequisite, UI, ADR,
  README, status, and Phase 7 documents match exercised behavior.
- [x] The completion report records exact commands, versions, results, URLs,
  evidence classes, limitations, skipped checks, and severity findings.
- [x] `docs/PROJECT_STATUS.md` becomes `AWAITING_APPROVAL` only after every
  required criterion is satisfied.
- [x] The completion handoff asks for `APPROVE PHASE 7` and stops completely.
