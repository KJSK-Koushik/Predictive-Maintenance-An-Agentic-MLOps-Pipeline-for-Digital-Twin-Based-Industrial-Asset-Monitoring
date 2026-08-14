# Phase 4 Test Plan

## Evidence classes

| Class                | Environment                                        | What it can prove                                         |
| -------------------- | -------------------------------------------------- | --------------------------------------------------------- |
| Unit/contract        | Python, memory, temporary paths                    | Split, leakage, preprocessing, metrics, gates, identities |
| Modeling integration | Synthetic feature snapshot plus local repositories | Complete verified baseline workflow                       |
| MLflow integration   | Loopback server, temporary SQLite and artifacts    | Tracking, retrieval, signature, trusted model, restore    |
| Existing PostgreSQL  | Pinned local PostgreSQL 17                         | Read-only feature metadata and lineage retrieval          |
| Actual dataset       | Ignored approved FD001 feature snapshot            | Real local baseline behavior; not CI/cloud evidence       |
| GitHub CI            | Clean credential-free runner                       | Reproducible synthetic gates; not actual FD001 or cloud   |

No evidence class may be reported as another. Phase 4 has no hosted MLflow,
model registry, Supabase mutation, deployment, or production evidence.

## Unit and contract tests

### Training-input gate

- explicit available feature snapshot accepted;
- implicit latest, unknown, inconsistent, missing, or mismatched snapshot
  rejected;
- parent lineage and every declared object identity verified;
- feature/target keys and row counts must align exactly;
- reordered, duplicate, missing, or extra keys fail closed;
- only 24 ordered settings/sensors enter `X`;
- identity keys and both labels are prohibited from `X`; and
- non-finite values, invalid RUL, and non-binary risk fail before fitting.

### Split manifest

- exactly 80/20 unique development engines for the 100-engine actual
  contract, with fixture counts adjusted proportionally;
- source test engines are held out and source partition is part of identity;
- zero composite-group overlap and complete row coverage, while repeated
  numeric IDs across source train/test remain distinct;
- row-order changes do not change engine assignment;
- seed, contract, snapshot, or engine-set changes alter manifest identity;
- repeated creation produces byte-identical canonical JSON and SHA-256; and
- regression and classification receive the same split manifest.

### Leakage resistance

- scaler statistics equal statistics computed from training rows only;
- validation/test feature changes do not alter fitted scaler or estimator;
- validation/test target changes do not alter fitted scaler or estimator;
- test metrics cannot be passed into candidate creation or selection;
- target columns cannot enter feature selection through a reordered schema;
- classification class weights are derived only during training; and
- threshold remains exactly `0.5` regardless of validation/test outcomes.

### Regression behavior

- median dummy behavior on known inputs;
- fixed Ridge configuration and deterministic fit;
- negative raw predictions are floored to zero and counted;
- engine-balanced sample weights sum equally per engine;
- pooled and engine-balanced RMSE/MAE use known vectors;
- NASA asymmetric score covers early, late, zero, and overflow-safe cases;
- lifecycle bands have declared inclusive boundaries;
- final-cycle selection returns one row per engine; and
- lower-is-better eligibility accepts/rejects boundary cases correctly.

### Classification behavior

- prior dummy probability behavior;
- fixed class-balanced logistic configuration and deterministic fit;
- probabilities remain finite and within `[0, 1]`;
- fixed-threshold boundary covers values below, equal to, and above `0.5`;
- engine-balanced average precision uses correct row weights;
- pooled AP, ROC-AUC, Brier, balanced accuracy, precision, recall, F1, and
  confusion values match known vectors;
- undefined single-class metric cases produce an explicit unavailable status,
  not a fabricated zero; and
- higher-is-better eligibility accepts/rejects boundary cases correctly.

### Reproducibility and reports

- canonical run configuration and report ordering;
- stable prediction digest from ordered keys and predictions;
- same locked inputs reproduce predictions and metrics within declared
  tolerance;
- changed snapshot, split, feature order, model config, or code revision
  changes provenance identity;
- model-file byte hashes are not used as the behavioral determinism gate;
- reports are aggregate and bounded; and
- secrets, endpoints, absolute paths, and complete row dumps are rejected.

## Modeling integration tests

Using a committed synthetic Phase 3-style feature snapshot with multiple
engines and known signal:

1. publish or materialize verified feature and target objects in a temporary
   object repository;
1. expose an available snapshot and complete parent lineage through the local
   metadata substitute;
1. load and validate the snapshot by explicit ID;
1. create and persist the shared split manifest;
1. fit both dummy and fixed candidate pipelines;
1. evaluate validation before final test;
1. prove both synthetic candidates cross their declared dummy gates;
1. produce bounded aggregate reports and stable prediction digests;
1. rerun from a clean output tree and compare identities and behavior; and
1. inject one lineage/object/contract failure and prove no model run is
   reported as successful.

The synthetic fixture is designed for software verification, not as evidence
of FD001 predictive performance.

## MLflow integration tests

Start an MLflow server on an available loopback test port with a temporary
SQLite backend and temporary artifact root. Readiness uses a bounded health
poll, never a fixed sleep.

Tests must:

- create the Phase 4 experiment and parent/child run hierarchy;
- log fixed parameters, metrics, tags, dataset metadata, snapshot IDs, split
  manifest, aggregate reports, and dependency evidence;
- log each model with an explicit signature, constructed schema-only input
  example, and `skops` serialization;
- inspect untrusted types before loading the exact run-owned artifact;
- retrieve the model and prove prediction parity with the in-memory pipeline;
- query runs by dataset/split/task metadata;
- reject missing signatures, wrong feature order, and wrong dtypes;
- prove no registered model or alias was created;
- stop the server, copy the SQLite database and artifact tree to a disposable
  restore location, restart against the copy, and retrieve the same run/model;
- verify the restored artifact digest and prediction parity; and
- terminate the process and remove only the temporary test state.

A skipped or mocked server test cannot be reported as MLflow integration.

## Existing PostgreSQL/read-only integration

Against the pinned disposable PostgreSQL 17 service:

- retrieve an available Phase 3 feature snapshot and its ordered files;
- verify complete parent/object lineage through the existing `ops` tables;
- deny an inconsistent or unavailable snapshot;
- perform no INSERT, UPDATE, DELETE, migration, or MLflow table creation in
  `ops`; and
- retain all existing migration, grant, RLS, reconciliation, and recovery
  tests.

## Actual FD001 evidence

The `dataset`-marked run uses the ignored accepted Phase 3 actual-FD001 feature
snapshot. It must:

1. record the exact feature snapshot and split-manifest IDs;
1. verify expected train/test engine and row counts;
1. train and evaluate all four fixed runs without changing configuration;
1. prove both validation eligibility gates or report the phase as incomplete;
1. record aggregate validation and final-test metrics;
1. repeat the run and compare behavioral reproducibility;
1. retrieve both candidate models from local MLflow and verify predictions;
   and
1. record execution time and artifact sizes as observations, not service-level
   objectives.

The actual dataset is local research evidence. CI does not contain or download
NASA data.

## Security tests

- secret, token, connection-string, private-endpoint, and absolute-path scans;
- loopback-only MLflow binding and no all-interface default;
- generated MLflow databases and artifacts are ignored and untracked;
- no pickle, joblib, or cloudpickle load path for untrusted artifacts;
- exact run/artifact provenance and trusted-type inspection before model load;
- bounded params, tags, report examples, errors, and logs;
- no raw telemetry or complete per-row prediction artifact;
- no Supabase credential in CI and no cloud mutation;
- no registered-model, alias, promotion, deployment, or Airflow-training
  command; and
- dependency audit after the reviewed lockfile change.

## Planned local and CI command groups

Exact marker expressions and server helpers will be finalized after dependency
compatibility is verified following `START PHASE 4`. The planned gates are:

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
docker compose config --quiet
docker compose up -d --wait postgres
uv run pytest -m "not integration and not dataset and not postgres and not airflow and not mlflow and not cloud"
uv run pytest -m "integration and not dataset and not postgres and not airflow and not mlflow and not cloud"
uv run pytest -m "postgres and not dataset and not cloud"
uv run pytest -m "mlflow and not dataset and not cloud"
docker compose build airflow
docker compose up -d --wait airflow
uv run pytest -m "airflow and not dataset and not cloud"
uv run pytest -m "not dataset and not airflow and not cloud" --cov=src/predictive_maintenance --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
docker compose down --volumes
```

The actual FD001 command runs separately under the `dataset` marker. Cleanup
must run even when a check fails.

## Performance observations

Phase 4 sets no online latency, throughput, fleet-scale, or availability
objective. It records local fit/evaluation duration, peak or bounded memory
where practical, MLflow artifact sizes, and repeated-run behavior only as
engineering observations.

## Exit criteria

All acceptance criteria and local gates pass; both actual-FD001 relative dummy
gates pass; split, leakage, behavioral reproducibility, MLflow round-trip,
restore, existing container, actual dataset, and GitHub Actions evidence are
recorded; documentation matches behavior; and no critical/high issue remains.
