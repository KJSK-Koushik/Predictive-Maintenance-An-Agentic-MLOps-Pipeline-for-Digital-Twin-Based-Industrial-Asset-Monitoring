# Phase 3 Acceptance Criteria

## Authorization and scope

- [ ] `START PHASE 3` is received before implementation begins.
- [ ] Manual Airflow, Docker, cloud-target, migration, retention, and cost
  prerequisites are completed.
- [ ] Work remains limited to deterministic ETL, derived publication, data
  quality, Airflow orchestration, tests, CI, and documentation.
- [ ] No model, MLflow, serving, monitoring, agent, dashboard, streaming, or
  production deployment is introduced.

## Source gate and data contracts

- [ ] Only an explicit available and reconciled Phase 2 raw snapshot is
  accepted.
- [ ] Unknown, inconsistent, missing, mismatched, or invalid sources fail
  before derived availability.
- [ ] The executable Phase 1 schema, semantic, RUL, and failure-risk contracts
  are reused without silent change.
- [ ] `fd001-processed-v1` defines exact files, order, columns, dtypes, nulls,
  and row-count rules.
- [ ] Processed train/test outputs preserve source row order and keys.
- [ ] No row is silently sorted, dropped, imputed, capped, scaled, or assigned
  a synthetic event timestamp.
- [ ] Test RUL/risk are documented as evaluation targets, not inference inputs.

## Deterministic artifacts

- [ ] Parquet and JSON writer versions and options are pinned and documented.
- [ ] Canonical manifests contain parent, contract, serializer, schema, file,
  size, SHA-256, and column-role evidence.
- [ ] Two clean direct runs in the locked environment produce identical
  snapshot IDs and object hashes.
- [ ] Object keys are content-addressed and reject traversal.
- [ ] Uploads are put-if-absent and downloaded hashes are verified.
- [ ] Exact reruns reuse verified objects and metadata.
- [ ] Different bytes at an existing key fail closed.
- [ ] Generated artifacts, Airflow logs, databases, and credentials are not
  tracked by Git.

## Feature and target boundary

- [ ] `fd001-candidate-features-v1` is versioned and deterministic.
- [ ] Candidate features contain only declared settings and sensors with
  key-aligned engine/cycle identity.
- [ ] Targets are stored separately with uncapped RUL and inclusive
  `failure_risk_30`.
- [ ] RUL and failure-risk labels never appear as candidate-feature columns.
- [ ] No dataset-fitted scaler, imputer, selector, PCA, target cap, rolling
  statistic, or model-informed feature is introduced.
- [ ] Documentation reserves split-fitted preprocessing for Phase 4.

## Data-quality evidence

- [ ] A canonical bounded JSON report records row, engine, column, null,
  duplicate, cycle, finite-value, label, and hash checks.
- [ ] Quality rules have stable project-owned IDs.
- [ ] Failure examples are sanitized and limited to at most five per rule.
- [ ] Raw rows, secrets, private endpoints, absolute paths, and unbounded data
  are absent from reports and logs.
- [ ] Failed quality gates prevent processed and feature availability.

## PostgreSQL, lineage, and recovery

- [ ] One reviewed forward-only Phase 3 migration applies cleanly to
  PostgreSQL 17.
- [ ] Clean reset/reapply produces the same schema fingerprint.
- [ ] Derived snapshot, derived file, and transformation-run constraints are
  exercised.
- [ ] Existing data-object and lineage authorities are reused.
- [ ] Raw-to-processed, processed-to-feature, and artifact-to-report lineage is
  complete and queryable.
- [ ] `PUBLIC`, `anon`, and `authenticated` have no access to new `ops` objects.
- [ ] Runtime-role grants and RLS are tested independently.
- [ ] Airflow metadata uses a separate database/user and never enters `ops`.
- [ ] Storage-success/database-failure retry converges without duplicates.
- [ ] Missing, mismatched, and orphaned derived objects are reported without
  silent deletion or repair.
- [ ] A referenced inconsistency blocks downstream use.
- [ ] Metadata and object-byte backup/recovery evidence covers derived assets.

## Pure ETL and command-line path

- [ ] Core ETL stages are typed and runnable without Airflow.
- [ ] The direct CLI accepts an explicit source snapshot and prints only
  sanitized identifiers and outcomes.
- [ ] Unit and local integration tests cover success, invalid source, quality
  failure, partial publication, retry, exact reuse, and reconciliation.
- [ ] The ignored owner-provided FD001 snapshot passes the direct local path.

## Airflow orchestration

- [ ] A versioned official Airflow Python 3.11 image is pinned by digest.
- [ ] The local topology uses LocalExecutor with bounded resources and no
  Celery, Redis, Kubernetes, or Helm dependency.
- [ ] The DAG imports with zero errors and performs no I/O during parsing.
- [ ] DAG task IDs, dependencies, schedule, catchup, concurrency, retries, and
  timeouts match the approved architecture.
- [ ] XCom contains only bounded identifiers/statuses, never DataFrames,
  telemetry, temporary paths, or credentials.
- [ ] Tasks do not depend on another task's local filesystem.
- [ ] Direct and DAG-triggered runs produce identical derived identities.
- [ ] A controlled task failure and retry converges without duplicate objects
  or metadata.
- [ ] A bounded backfill over at least two logical dates completes with the
  declared reprocessing behavior and one artifact identity per source/version.
- [ ] Backfill evidence is described as static batch orchestration, not event
  time or real-time ingestion.
- [ ] Container startup, health, DAG test, and cleanup pass locally and in CI.

## Hosted Supabase evidence

- [ ] The exact development/test project and mutation scope are reconfirmed.
- [ ] The Phase 3 migration history matches the repository.
- [ ] Processed, feature, target, manifest, and report objects are private and
  verified in the derived bucket.
- [ ] Hosted metadata and lineage reference every accepted derived object.
- [ ] Exact rerun reuse and reconciliation pass.
- [ ] Cleanup is limited to generated integration prefixes; approved durable
  artifacts are not silently deleted.
- [ ] Storage, project-scoped SQL, and direct-adapter evidence are reported
  separately when network limits prevent one end-to-end path.
- [ ] Supabase Security and Performance Advisor evidence is recorded and every
  introduced critical/high finding is resolved.

## Engineering and CI evidence

- [ ] Formatting, linting, strict typing, lock, Markdown, YAML, dependency,
  secret, migration, container, and security checks pass.
- [ ] Product code maintains at least 90% branch-aware coverage.
- [ ] Ordinary CI uses only committed synthetic fixtures and contains no cloud
  or production credential.
- [ ] CI performs verification only and contains no deployment or cloud
  mutation.
- [ ] The required GitHub Actions workflow passes on the completion commit.
- [ ] Branch protection remains enforced.
- [ ] No critical or high-severity issue remains unresolved.

## Documentation and completion

- [ ] Master, data-contract, security, test, manual-prerequisite, and Phase 3
  documents match exercised behavior.
- [ ] Phase 3 decisions are recorded in focused ADRs.
- [ ] `COMPLETION_REPORT.md` distinguishes unit, local, Docker, Airflow, actual
  dataset, cloud, advisor, recovery, and GitHub evidence.
- [ ] Known limitations and deferred Phase 4 work are explicit.
- [ ] `docs/PROJECT_STATUS.md` is updated to `AWAITING_APPROVAL` only after all
  criteria pass.
- [ ] The completion handoff asks for `APPROVE PHASE 3` and stops.

Unchecked criteria prevent Phase 3 completion.
