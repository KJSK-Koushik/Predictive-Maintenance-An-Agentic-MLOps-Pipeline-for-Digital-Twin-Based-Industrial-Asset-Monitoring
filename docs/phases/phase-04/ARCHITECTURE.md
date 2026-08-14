# Phase 4 Architecture

## Objective

Build reproducible, leakage-safe non-agentic baselines for FD001 remaining
useful life (RUL) regression and 30-cycle failure-risk classification. The
phase will consume only an approved Phase 3 candidate-feature snapshot, create
one versioned engine-level split, fit preprocessing on training engines only,
evaluate fixed scikit-learn baselines, and record the evidence in MLflow.

Phase 4 does not tune advanced models, create new learned features, register or
promote a model, serve predictions, schedule retraining, add agents, or claim
production readiness.

## Scope correction

C-MAPSS FD001 is simulated historical telemetry. A model trained on it is a
research baseline, not proof of field performance, a physical digital twin, or
autonomous maintenance. Failure risk remains the deterministic derived target
`failure_risk_30`; it is not an independently observed failure event.

The phase establishes an evaluation protocol and a reproducible reference
point. It does not search for the highest possible score. Hyperparameter
tuning, ensembles, neural networks, target capping, clustering, anomaly
detection, uncertainty methods, and explainability comparisons remain Phase 5.

## Component flow

```mermaid
flowchart LR
    FEATURES["Available Phase 3 feature snapshot"] --> LOAD["Verify and load"]
    LOAD --> SPLIT["Versioned engine-disjoint split"]
    SPLIT --> REG["RUL baseline pipeline"]
    SPLIT --> CLS["Risk baseline pipeline"]
    REG --> EVAL["Deterministic evaluation"]
    CLS --> EVAL
    EVAL --> MLFLOW["Local MLflow tracking"]
    EVAL --> REPORT["Aggregate evaluation report"]
    MLFLOW --> REVIEW["Human review only"]
```

MLflow records evidence. It does not approve, register, promote, or deploy a
model in this phase.

## Input gate

Phase 4 accepts only a feature snapshot that:

- has artifact kind `features` and specification
  `fd001-candidate-features-v1`;
- is in the `available` state in operational metadata;
- has a complete parent chain to the accepted FD001 raw and processed
  snapshots;
- passes object size and SHA-256 reconciliation;
- contains the four declared feature and target Parquet files;
- preserves exact key alignment between every feature and target row;
- contains only the declared 24 setting/sensor model inputs plus
  `engine_id`/`cycle` keys; and
- contains uncapped `rul` and inclusive `failure_risk_30` targets only in the
  target files.

The loader must not read directly from the mutable top-level `Data/` folder,
select an implicit latest snapshot, or accept an inconsistent snapshot.

## Model-input boundary

`engine_id` and `cycle` are identity and grouping keys. They are excluded from
the Phase 4 model matrix. The model matrix contains exactly:

- `setting_1` through `setting_3`; and
- `sensor_1` through `sensor_21`.

The target is either uncapped `rul` or `failure_risk_30`. Neither target may
appear in inputs, preprocessing, feature selection, sample grouping, or model
signatures.

No fitted value may be calculated before the engine split. The baseline
pipelines use `StandardScaler` followed by the estimator so scaling is learned
from training rows only. The data contract already rejects missing and
non-finite telemetry, so Phase 4 adds no silent imputation.

## Split protocol

The NASA source partitions have different roles:

- the source `train` partition supplies development engines;
- a single seeded `GroupShuffleSplit` divides those engines into 80% training
  and 20% validation groups; and
- the source `test` partition remains the final held-out evaluation set.

Rows from one engine can occur in only one development split. Source partition
is part of the identity because NASA train and test engine numbers overlap.
The final test partition is never used to fit scaling, coefficients, class
weights, thresholds, features, or configuration.

The canonical split manifest records:

- feature and parent snapshot IDs;
- split-contract version and random seed;
- source partition and ordered engine IDs for train, validation, and test;
- row and engine counts plus class prevalence for each split;
- exact feature and target names;
- scikit-learn and NumPy versions;
- a SHA-256 identity over canonical JSON; and
- zero-overlap and full-coverage assertions.

One manifest is shared by both tasks so regression and classification results
are comparable. Repeated creation from the same snapshot, version, and seed
must produce the same manifest bytes and ID.

## Baseline models

### RUL regression

- Reference: `DummyRegressor(strategy="median")`.
- Candidate: `StandardScaler` plus `Ridge` with one fixed, documented
  configuration.
- Target: canonical uncapped RUL.
- Output rule: apply a documented deterministic floor of zero to predictions
  for physical validity and report how many values were floored.

Primary validation metric is engine-balanced root mean squared error (RMSE),
where row weights give each engine equal total weight. Secondary evidence is
engine-balanced and pooled mean absolute error (MAE), pooled RMSE, the NASA
asymmetric score, residual summaries, lifecycle-band metrics, and final-cycle
test metrics.

### Failure-risk classification

- Reference: `DummyClassifier(strategy="prior")`.
- Candidate: `StandardScaler` plus class-balanced `LogisticRegression` with
  one fixed, documented configuration.
- Target: inclusive `failure_risk_30`.
- Decision threshold: fixed at `0.5`; threshold optimization is Phase 5 work.

Primary validation metric is engine-balanced average precision (PR-AUC).
Secondary evidence is pooled average precision, ROC-AUC, Brier score, balanced
accuracy, precision, recall, F1, confusion matrix, calibration summaries, and
final-cycle test metrics. Accuracy alone is not a sufficient gate because the
classes are imbalanced.

## Performance and holdout gate

The candidate configuration is fixed before test evaluation. To be called an
eligible Phase 4 baseline:

- all metrics and predictions must be finite and schema-valid;
- the RUL candidate must have lower validation engine-balanced RMSE than its
  median dummy reference; and
- the risk candidate must have higher validation engine-balanced average
  precision than its prior dummy reference.

The final test metrics are then reported without changing the model,
preprocessing, threshold, features, or gate. There is no post-test tuning. If a
candidate fails a gate, the run and failure evidence remain visible; it is not
renamed as an eligible model.

No absolute production threshold is invented from FD001. Phase 6 promotion
criteria require separate review after Phase 5 comparison evidence exists.

## Reproducibility contract

Each run binds:

- raw, processed, and feature snapshot IDs;
- split-manifest ID;
- task and fixed model-configuration version;
- code revision and dirty-worktree status;
- Python and locked dependency versions;
- random seed and deterministic execution settings;
- ordered feature list and target definition; and
- evaluation-protocol version.

Repeated runs in the same locked environment must reproduce split membership,
predictions, and metrics within declared numeric tolerances. Byte-identical
model files are not required because serialization metadata can vary. The
prediction digest and metric tolerance are the behavioral reproducibility
evidence.

## MLflow topology and ownership

Phase 4 uses the smallest database-backed topology permitted by ADR-0007:

- one MLflow tracking server bound to `127.0.0.1:5000`;
- a local SQLite backend under ignored `artifacts/mlflow/`;
- a local filesystem artifact root under the same ignored evidence tree; and
- explicit client logging rather than autologging.

SQLite is appropriate for this single-user local phase. The operational
PostgreSQL `ops` schema is not shared with MLflow. Supabase PostgreSQL and
Storage are not used as an MLflow backend or artifact store. A shared or remote
server requires a later decision covering authentication, TLS, backup,
availability, and network access.

The experiment contains one parent run for an evaluation execution and one
child run for each dummy/candidate task. Runs record parameters, metrics,
dataset metadata, source identities, the split manifest, aggregate evaluation
reports, dependency information, a model signature, a constructed schema-only
input example, and the trusted model artifact.

Phase 4 logs models but does not create registered-model versions, stages,
aliases, approvals, or deployment records. Those actions belong to Phase 6.

## Model-artifact security

The scikit-learn pipeline is logged explicitly using the `skops` serialization
format. Loading pickle, joblib, or cloudpickle artifacts from an untrusted
source is prohibited. Any model-load test must retrieve the exact run-owned
artifact, verify its provenance, inspect the trusted-type list, and use the
locked environment.

Reports contain aggregate metrics, plots, bounded examples, and hashes rather
than complete telemetry or per-row prediction dumps. Secrets, private service
URLs, absolute local paths, and credentials must not appear in MLflow params,
tags, reports, logs, or exceptions.

The loopback server has no production authentication or availability claim. It
must not bind to all interfaces. Generated databases, models, plots, and
artifacts remain ignored by Git.

## Implemented package boundaries

```text
src/predictive_maintenance/modeling/
  __init__.py
  models.py
  loading.py
  splitting.py
  baselines.py
  metrics.py
  tracking.py
  pipeline.py
  runtime.py
  cli.py

tests/modeling/
tests/integration/model_tracking/
```

Preprocessing stays directly inside scikit-learn pipelines, and evaluation is
kept in the small task pipeline and metrics modules. There is no
generic training framework, plugin system, registry service, or model-serving
package in Phase 4.

## Local and CI evidence

Local-real-data evidence trained and evaluated the ignored, approved actual
FD001 feature snapshot. CI uses a small committed synthetic feature
snapshot whose engine groups, labels, and signal are deliberately known.

MLflow integration tests start a temporary loopback server with a
temporary SQLite database and artifact root, exercise run/model logging and
retrieval, then clean only that temporary state. Ordinary CI has no Supabase
credentials and performs no cloud mutation, registration, promotion, or
deployment.

The full MLflow 3.15.1 metapackage is excluded because its
`cryptography<50` constraint conflicts with the security fix for
`PYSEC-2026-3552`. ADR-0023 records the audited lightweight-package and server
dependency topology that keeps `cryptography==50.0.0`.

## Explicit exclusions

- target capping, rolling features, PCA, feature selection, hyperparameter
  search, cross-validated tuning, ensembles, or deep learning;
- clustering, anomaly detection, explainability comparison, or formal
  uncertainty estimation;
- MLflow registered models, aliases, promotion decisions, or remote hosting;
- model serving, Docker inference images, staging, rollback, monitoring, or
  retraining triggers;
- Airflow-scheduled training;
- Supabase schema changes or model-artifact publication;
- agents, dashboard, Auth, Realtime, streaming, or real-time claims; and
- production, physical-engine, autonomous-maintenance, or safety claims.

## Planning references

- [scikit-learn GroupShuffleSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html)
- [scikit-learn data-leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html)
- [scikit-learn model evaluation](https://scikit-learn.org/stable/modules/model_evaluation.html)
- [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html)
- [MLflow self-hosting architecture](https://mlflow.org/docs/latest/self-hosting/architecture/overview/)
- [MLflow tracking server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)
- [MLflow backend stores](https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/)
- [MLflow model signatures](https://mlflow.org/docs/latest/ml/model/signatures/)
- [MLflow dataset tracking](https://mlflow.org/docs/latest/dataset/)
