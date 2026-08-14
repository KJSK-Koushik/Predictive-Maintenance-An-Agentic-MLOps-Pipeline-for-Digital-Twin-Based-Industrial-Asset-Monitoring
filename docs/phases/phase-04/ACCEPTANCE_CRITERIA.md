# Phase 4 Acceptance Criteria

## Authorization and scope

- [x] `START PHASE 4` is received before implementation begins.
- [x] The local MLflow topology, artifact path, evidence retention, reviewer,
  and no-paid-resource prerequisites are confirmed.
- [x] Work remains limited to baseline regression/classification, evaluation,
  MLflow tracking, tests, CI, security, and documentation.
- [x] No advanced tuning, registry promotion, serving, monitoring, retraining,
  agent, dashboard, cloud mutation, or deployment is introduced.

## Input and lineage gate

- [x] One explicit available `fd001-candidate-features-v1` snapshot is
  required; implicit latest selection is prohibited.
- [x] Snapshot state, parent lineage, file membership, size, SHA-256, schema,
  and feature/target key alignment are verified before training.
- [x] Unknown, inconsistent, missing, mismatched, or contract-invalid
  snapshots fail closed.
- [x] The modeling path does not read directly from mutable `Data/` files.
- [x] `engine_id`, `cycle`, `rul`, and `failure_risk_30` are absent from the
  model input matrix.
- [x] Model inputs are exactly the three settings and 21 sensors in declared
  order.
- [x] Uncapped RUL and inclusive 30-cycle failure risk retain their accepted
  semantics.

## Split and leakage controls

- [x] NASA training engines are divided once into seeded 80% training and 20%
  validation groups.
- [x] NASA test engines remain a separate final holdout.
- [x] Source partition plus engine ID prevents collision between overlapping
  NASA train/test engine numbers.
- [x] No composite `(source partition, engine ID)` group appears in more than
  one split and all expected rows occur exactly once; repeated numeric IDs
  across NASA train/test remain distinct groups.
- [x] One canonical, versioned split manifest is shared by both modeling tasks.
- [x] Repeated manifest creation produces the same bytes and SHA-256 identity.
- [x] Scaling and every fitted statistic use training engines only.
- [x] Tests prove that validation/test feature or target changes do not alter
  fitted preprocessing or model parameters.
- [x] Final test data does not influence features, configuration, class
  weights, thresholds, candidate choice, or validation gates.

## Baseline regression

- [x] A median `DummyRegressor` reference and one fixed scaled Ridge candidate
  are implemented.
- [x] The candidate predicts canonical uncapped RUL and applies only the
  documented non-negative output floor.
- [x] The primary validation metric is engine-balanced RMSE.
- [x] Engine-balanced and pooled MAE/RMSE, NASA score, lifecycle-band,
  residual, clipped-output, and final-cycle evidence is recorded.
- [x] The candidate validation engine-balanced RMSE is lower than the dummy
  reference before it is called eligible.
- [x] Predictions and metrics are finite and reproducible within declared
  tolerances.

## Baseline classification

- [x] A prior `DummyClassifier` reference and one fixed scaled class-balanced
  logistic candidate are implemented.
- [x] The candidate predicts probabilities for `failure_risk_30` and uses the
  fixed threshold `0.5`.
- [x] The primary validation metric is engine-balanced average precision.
- [x] Pooled average precision, ROC-AUC, Brier score, balanced accuracy,
  precision, recall, F1, confusion, calibration, and final-cycle evidence is
  recorded.
- [x] The candidate validation engine-balanced average precision is higher
  than the dummy reference before it is called eligible.
- [x] Probabilities stay in `[0, 1]`; predictions and metrics are finite and
  reproducible within declared tolerances.

## Evaluation and reproducibility

- [x] Fixed model and evaluation configurations are versioned and recorded
  before final test evaluation.
- [x] No test-driven retry, threshold optimization, feature choice, or
  hyperparameter change occurs.
- [x] Dataset IDs, split ID, code revision, dirty state, dependency versions,
  seed, features, targets, and protocol version are captured.
- [x] Repeated locked-environment runs reproduce split membership,
  predictions, eligibility outcomes, and metrics within declared tolerances.
- [x] Behavioral reproducibility is not overstated as byte-identical model
  serialization.
- [x] Actual FD001 results are reported as simulated research evidence, not
  field, production, real-time, digital-twin, or autonomous evidence.

## MLflow tracking

- [x] MLflow uses a loopback-only tracking server, local SQLite backend, and
  ignored local artifact root.
- [x] MLflow state does not share the operational PostgreSQL `ops` schema.
- [x] Explicit logging records run hierarchy, parameters, metrics, dataset
  metadata, snapshot/split IDs, reports, dependency evidence, signatures,
  input examples, and model artifacts.
- [x] Input examples are constructed schema-only values and do not copy a raw
  telemetry row.
- [x] Model artifacts use explicit `skops` serialization and trusted-type
  inspection.
- [x] A retrieved model passes signature validation and prediction parity.
- [x] A stopped-server copy/restore exercise retrieves the same run metadata
  and verified artifact from disposable restored state.
- [x] No registered-model version, alias, approval, promotion, or deployment
  record is created.
- [x] The server is not exposed beyond loopback and no remote/production
  availability or authentication claim is made.

## Security and generated artifacts

- [x] Pickle, joblib, and cloudpickle loading from untrusted sources is absent.
- [x] Model and report retrieval verifies run ownership and artifact
  provenance before loading.
- [x] Reports and MLflow metadata contain no credential, private endpoint,
  signed URL, raw absolute path, or unbounded telemetry/prediction dump.
- [x] Generated MLflow databases, models, plots, reports, and local evidence
  are ignored by Git.
- [x] Error and log output is bounded and sanitized.
- [x] Dependency and secret scans pass with no unresolved critical/high issue.

## Tests, engineering, and CI

- [x] Unit tests cover split, weighting, preprocessing, estimators,
  postprocessing, metrics, gates, manifests, and failures.
- [x] Integration tests cover verified feature loading, full synthetic
  training, MLflow server/log/retrieve/load, and restore behavior.
- [x] The ignored owner-provided FD001 feature snapshot passes the complete
  local baseline path.
- [x] Formatting, linting, strict typing, lock, Markdown, YAML, dependency,
  secret, existing migration, existing container, and security checks pass.
- [x] Product code maintains at least 90% branch-aware coverage.
- [x] Ordinary CI uses synthetic fixtures only and has no cloud, model
  promotion, or deployment credential.
- [x] CI performs no Supabase mutation, registration, promotion, or
  deployment.
- [x] The required GitHub Actions workflow passes on the completion commit.
- [x] Branch protection remains enforced.
- [x] No critical or high-severity issue remains unresolved.

## Documentation and completion

- [x] Master, roadmap, data-contract, security, test, manual-prerequisite, and
  Phase 4 documents match exercised behavior.
- [x] Phase 4 decisions are recorded in focused accepted ADRs.
- [x] `COMPLETION_REPORT.md` distinguishes unit, local integration, MLflow,
  actual dataset, Docker, CI, and unexercised cloud/registry evidence.
- [x] Metrics, commands, versions, run IDs, limitations, and deferred Phase 5
  work are recorded without secrets or private URLs.
- [x] `docs/PROJECT_STATUS.md` becomes `AWAITING_APPROVAL` only after every
  criterion passes.
- [x] The completion handoff asks for `APPROVE PHASE 4` and stops completely.

All acceptance criteria passed before the Phase 4 approval handoff.
