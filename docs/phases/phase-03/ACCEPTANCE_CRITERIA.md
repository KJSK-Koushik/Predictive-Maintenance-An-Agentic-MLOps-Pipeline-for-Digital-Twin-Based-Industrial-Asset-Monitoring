# Phase 3 Acceptance Criteria

## Authorization and scope

- [x] `START PHASE 3` is received before implementation begins.
- [x] Manual Airflow, Docker, cloud-target, migration, retention, and cost
  prerequisites are completed.
- [x] Work remains limited to deterministic ETL, derived publication, data
  quality, Airflow orchestration, tests, CI, and documentation.
- [x] No model, MLflow, serving, monitoring, agent, dashboard, streaming, or
  production deployment is introduced.

## Source gate and data contracts

- [x] Only an explicit available and reconciled Phase 2 raw snapshot is
  accepted.
- [x] Unknown, inconsistent, missing, mismatched, or invalid sources fail
  before derived availability.
- [x] The executable Phase 1 schema, semantic, RUL, and failure-risk contracts
  are reused without silent change.
- [x] `fd001-processed-v1` defines exact files, order, columns, dtypes, nulls,
  and row-count rules.
- [x] Processed train/test outputs preserve source row order and keys.
- [x] No row is silently sorted, dropped, imputed, capped, scaled, or assigned
  a synthetic event timestamp.
- [x] Test RUL/risk are documented as evaluation targets, not inference inputs.

## Deterministic artifacts

- [x] Parquet and JSON writer versions and options are pinned and documented.
- [x] Canonical manifests contain parent, contract, serializer, schema, file,
  size, SHA-256, and column-role evidence.
- [x] Two clean direct runs in the locked environment produce identical
  snapshot IDs and object hashes.
- [x] Object keys are content-addressed and reject traversal.
- [x] Uploads are put-if-absent and downloaded hashes are verified.
- [x] Exact reruns reuse verified objects and metadata.
- [x] Different bytes at an existing key fail closed.
- [x] Generated artifacts, Airflow logs, databases, and credentials are not
  tracked by Git.

## Feature and target boundary

- [x] `fd001-candidate-features-v1` is versioned and deterministic.
- [x] Candidate features contain only declared settings and sensors with
  key-aligned engine/cycle identity.
- [x] Targets are stored separately with uncapped RUL and inclusive
  `failure_risk_30`.
- [x] RUL and failure-risk labels never appear as candidate-feature columns.
- [x] No dataset-fitted scaler, imputer, selector, PCA, target cap, rolling
  statistic, or model-informed feature is introduced.
- [x] Documentation reserves split-fitted preprocessing for Phase 4.

## Data-quality evidence

- [x] A canonical bounded JSON report records row, engine, column, null,
  duplicate, cycle, finite-value, label, and hash checks.
- [x] Quality rules have stable project-owned IDs.
- [x] Failure examples are sanitized and limited to at most five per rule.
- [x] Raw rows, secrets, private endpoints, absolute paths, and unbounded data
  are absent from reports and logs.
- [x] Failed quality gates prevent processed and feature availability.

## PostgreSQL, lineage, and recovery

- [x] One reviewed forward-only Phase 3 migration applies cleanly to
  PostgreSQL 17.
- [x] Clean reset/reapply produces the same schema fingerprint.
- [x] Derived snapshot, derived file, and transformation-run constraints are
  exercised.
- [x] Existing data-object and lineage authorities are reused.
- [x] Raw-to-processed, processed-to-feature, and artifact-to-report lineage is
  complete and queryable.
- [x] `PUBLIC`, `anon`, and `authenticated` have no access to new `ops` objects.
- [x] Runtime-role grants and RLS are tested independently.
- [x] Airflow metadata uses a separate database/user and never enters `ops`.
- [x] Storage-success/database-failure retry converges without duplicates.
- [x] Missing, mismatched, and orphaned derived objects are reported without
  silent deletion or repair.
- [x] A referenced inconsistency blocks downstream use.
- [x] Metadata and object-byte backup/recovery evidence covers derived assets.

## Pure ETL and command-line path

- [x] Core ETL stages are typed and runnable without Airflow.
- [x] The direct CLI accepts an explicit source snapshot and prints only
  sanitized identifiers and outcomes.
- [x] Unit and local integration tests cover success, invalid source, quality
  failure, partial publication, retry, exact reuse, and reconciliation.
- [x] The ignored owner-provided FD001 snapshot passes the direct local path.

## Airflow orchestration

- [x] A versioned official Airflow Python 3.11 image is pinned by digest.
- [x] The local topology uses LocalExecutor with bounded resources and no
  Celery, Redis, Kubernetes, or Helm dependency.
- [x] The DAG imports with zero errors and performs no I/O during parsing.
- [x] DAG task IDs, dependencies, schedule, catchup, concurrency, retries, and
  timeouts match the approved architecture.
- [x] XCom contains only bounded identifiers/statuses, never DataFrames,
  telemetry, temporary paths, or credentials.
- [x] Tasks do not depend on another task's local filesystem.
- [x] Direct and DAG-triggered runs produce identical derived identities.
- [x] A controlled task failure and retry converges without duplicate objects
  or metadata.
- [x] A bounded backfill over at least two logical dates completes with the
  declared reprocessing behavior and one artifact identity per source/version.
- [x] Backfill evidence is described as static batch orchestration, not event
  time or real-time ingestion.
- [x] Container startup, health, DAG test, and cleanup pass locally and in CI.

## Hosted Supabase evidence

- [x] The exact development/test project and mutation scope are reconfirmed.
- [x] The Phase 3 migration history matches the repository.
- [x] Processed, feature, target, manifest, and report objects are private and
  verified in the derived bucket.
- [x] Hosted metadata and lineage reference every accepted derived object.
- [x] Exact rerun reuse and reconciliation pass.
- [x] Cleanup is limited to generated integration prefixes; approved durable
  artifacts are not silently deleted.
- [x] Storage, project-scoped SQL, and direct-adapter evidence are reported
  separately when network limits prevent one end-to-end path.
- [x] Supabase Security and Performance Advisor evidence is recorded and every
  introduced critical/high finding is resolved.

## Engineering and CI evidence

- [x] Formatting, linting, strict typing, lock, Markdown, YAML, dependency,
  secret, migration, container, and security checks pass.
- [x] Product code maintains at least 90% branch-aware coverage.
- [x] Ordinary CI uses only committed synthetic fixtures and contains no cloud
  or production credential.
- [x] CI performs verification only and contains no deployment or cloud
  mutation.
- [x] The required GitHub Actions workflow passes on the completion commit.
- [x] Branch protection remains enforced.
- [x] No critical or high-severity issue remains unresolved.

## Documentation and completion

- [x] Master, data-contract, security, test, manual-prerequisite, and Phase 3
  documents match exercised behavior.
- [x] Phase 3 decisions are recorded in focused ADRs.
- [x] `COMPLETION_REPORT.md` distinguishes unit, local, Docker, Airflow, actual
  dataset, cloud, advisor, recovery, and GitHub evidence.
- [x] Known limitations and deferred Phase 4 work are explicit.
- [x] `docs/PROJECT_STATUS.md` is updated to `AWAITING_APPROVAL` only after all
  criteria pass.
- [x] The completion handoff asks for `APPROVE PHASE 3` and stops.

All Phase 3 acceptance criteria pass. Phase 4 remains outside authorization.
