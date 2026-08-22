# Phase 7 Acceptance Criteria

## Authorization and scope

- [ ] `START PHASE 7` is received before implementation begins.
- [ ] The approved Phase 6 work is merged to `main` and its required GitHub
  check passes on the merged revision.
- [ ] The exact Phase 6 release, feature snapshot, and loopback staging target
  are reconfirmed before monitoring evidence is generated.
- [ ] No working UI, agent, public service, production target, automatic
  retraining, automatic promotion, FD002-FD004, or paid resource is introduced.
- [ ] NASA test rows remain unavailable to candidate fitting and configuration
  selection.

## Monitoring contracts and identity

- [ ] Reference-profile, monitoring-window, policy, report, delayed-label,
  alert, request, and evaluation schemas are versioned and strictly validated.
- [ ] Every identity binds the exact data, release, policy, code, dependency,
  and parent evidence required by its contract.
- [ ] Canonical JSON and SHA-256 identities are deterministic across clean
  repeated runs.
- [ ] The same exact window and policy reuses the same report; different
  governed inputs create a different identity or a conflict.
- [ ] Source partition plus engine ID and cycle remain the row identity.
- [ ] Replay sequence and processing time remain separate from telemetry cycle;
  no synthetic event-time or real-time claim is created.

## Reference and data quality

- [ ] The reference profile uses only the approved source-training input and
  exact active release.
- [ ] Sampling and aggregate metrics are engine-balanced and bounded.
- [ ] Reference bins, adequacy rules, thresholds, and policy identity are fixed
  before the monitored window is evaluated.
- [ ] Schema, required features, finite values, keys, duplicate rows, cycle
  order, lineage, release, and object integrity are checked before drift.
- [ ] Invalid quality blocks feature drift, prediction drift, performance, and
  retraining-request creation.
- [ ] Lifecycle-band and operating-setting composition are recorded so expected
  lifecycle change is not silently described as model degradation.

## Monitoring signals

- [ ] Data quality, feature shift, prediction shift, service health, and
  delayed-label performance remain separate report sections and statuses.
- [ ] Feature shift covers all 24 ordered model inputs using deterministic
  fixed-reference metrics and practical effect-size thresholds.
- [ ] Prediction shift covers RUL, risk probability, and risk-label prevalence
  without calling shift a performance failure.
- [ ] Service monitoring records bounded readiness, status, request count, and
  p50/p95/max latency from actual loopback probes.
- [ ] Service evidence is not described as production availability or an SLA.
- [ ] Every signal uses only `pass`, `warning`, `alert`,
  `insufficient_data`, `unavailable`, or `invalid`.
- [ ] Reports are bounded and omit complete telemetry, complete prediction
  dumps, secrets, private endpoints, absolute paths, and unrestricted errors.

## Delayed-label performance

- [ ] Predictions and their report identity are fixed before labels may be
  attached.
- [ ] A report without labels explicitly states that performance is
  unavailable.
- [ ] Label attachment requires exact snapshot, partition, key, row-count, and
  lineage alignment.
- [ ] Missing, duplicate, stale, mismatched, or leaked labels fail closed.
- [ ] Available performance uses the approved engine-balanced RUL and risk
  metrics with bounded aggregate output.
- [ ] Label attachment creates new immutable evidence and cannot overwrite the
  original prediction report.

## Trigger and retraining-candidate governance

- [ ] Data-quality and service failures open investigations and cannot create
  retraining candidates.
- [ ] One drift alert opens an investigation; candidate creation requires the
  policy's persistence and adequacy rules.
- [ ] Confirmed adequate delayed-performance degradation may create a candidate
  request under the exact versioned policy.
- [ ] Unavailable or insufficient evidence cannot create an eligible request.
- [ ] Candidate requests are content-addressed, deduplicated, attributable, and
  conflict-safe.
- [ ] A request contains an immutable data cutoff and never implies approval,
  training success, registration, or deployment.
- [ ] The trigger controller has no code path or credential for MLflow alias
  mutation, deployment, rollback, or production action.

## Champion/challenger evaluation

- [ ] Synthetic passing and failing challengers are compared with the champion
  on identical engine-group evaluation rows.
- [ ] Paired whole-engine evidence and the approved Phase 5 practical
  guardrails determine eligibility.
- [ ] Data, leakage, reproducibility, feature, signature, trusted-type,
  performance, robustness, security, and release-compatibility checks pass
  before eligibility.
- [ ] A failed challenger remains contained and leaves the active release and
  MLflow staging aliases unchanged.
- [ ] An eligible challenger produces only a human-review handoff and still
  cannot change an alias or deployment.
- [ ] Actual FD001 evaluation honestly records no-change or
  `blocked_no_new_training_data` when no new approved training data exists.
- [ ] Existing Phase 6 staging smoke and rollback regression tests continue to
  pass.
- [ ] No production alias, target, approval, or deployment is created.

## Persistence, PostgreSQL, and Storage

- [ ] One CLI-generated forward-only migration adds only Phase 7 private `ops`
  objects and does not modify managed Supabase schemas.
- [ ] PostgreSQL 17 clean apply, reset/reapply, migration history, constraints,
  indexes, grants, RLS, append-only behavior, backup, and restore pass.
- [ ] `PUBLIC`, `anon`, and `authenticated` cannot access monitoring or
  retraining records; the runtime role has only required operations.
- [ ] Monitoring and retraining report publication is put-if-absent, verifies
  stored bytes, supports exact reuse, and rejects different-byte conflicts.
- [ ] Partial object/database failure, retry, reconciliation, orphan reporting,
  and separate metadata/object recovery are exercised.
- [ ] Hosted evidence, if authorized, uses only the approved private project,
  bucket prefixes, migration, and generated integration namespace.
- [ ] Supabase Security and Performance Advisors are checked and no critical or
  high-severity issue remains unresolved.

## Airflow, CI, security, and regression

- [ ] Core monitoring, metrics, trigger, and evaluation logic runs without
  Airflow or cloud services.
- [ ] The Airflow DAG is thin, parameterized by immutable identifiers,
  parse-safe, bounded, idempotent, and has no deployment or automatic-training
  authority.
- [ ] Direct and Airflow execution produce the same report and request
  identities for the same inputs.
- [ ] Pull-request CI remains read-only, credential-free, and deployment-free.
- [ ] Synthetic monitoring, migration, trigger, challenger-denial, container,
  Airflow, and prior-phase regression tests are required CI checks.
- [ ] Product code maintains at least 90% branch-aware coverage.
- [ ] Formatting, linting, strict typing, dependency lock, Markdown, YAML,
  Docker, migration, secret, and dependency-security checks pass locally.
- [ ] Required GitHub Actions passes on the completion commit.

## Actual evidence, UI contracts, and documentation

- [ ] An actual FD001 cycle-replay window is monitored against the exact
  approved loopback release and reported separately from synthetic tests.
- [ ] The actual report records lifecycle-mix and already-observed-benchmark
  limitations and makes no live, field, or production claim.
- [ ] Monitoring and trigger field meanings, freshness, nullability, partial,
  stale, unavailable, and error states are documented for the future UI.
- [ ] Every UI screen remains `Design only`; no browser-facing read API or live
  connection is created.
- [ ] Master, roadmap, data, security, test, manual-prerequisite, UI, ADR,
  README, status, and Phase 7 documents match exercised behavior.
- [ ] The completion report records exact commands, versions, results, URLs,
  evidence classes, limitations, skipped checks, and severity findings.
- [ ] `docs/PROJECT_STATUS.md` becomes `AWAITING_APPROVAL` only after every
  required criterion is satisfied.
- [ ] The completion handoff asks for `APPROVE PHASE 7` and stops completely.
