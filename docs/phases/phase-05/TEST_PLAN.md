# Phase 5 Test Plan

## Evidence classes

| Class                | Environment                                      | What it can prove                                              |
| -------------------- | ------------------------------------------------ | -------------------------------------------------------------- |
| Unit/contract        | Python, memory, temporary paths                  | Fold, search, metric, bootstrap, gate, and analysis logic      |
| Modeling integration | Synthetic verified feature snapshot              | Complete advanced comparison and locked benchmark flow         |
| MLflow integration   | Real loopback server, temporary SQLite/artifacts | Tracking, retrieval, trusted models, provenance                |
| Actual dataset       | Ignored approved FD001 feature snapshot          | Local research behavior; not CI or field evidence              |
| Existing containers  | PostgreSQL 17 and Airflow regression services    | Earlier integration remains healthy; not Phase 5 orchestration |
| GitHub CI            | Clean credential-free runner                     | Synthetic reproducibility and quality gates                    |

No test may be reported as cloud, production, anomaly-ground-truth, blind-test,
deployment, or physical-engine evidence.

## Unit and contract tests

### Fold and search protocol

- canonical five-outer/four-inner fold identity and byte stability;
- source partition plus engine identity, zero overlap, and full coverage;
- every engine appears in exactly one outer validation fold;
- inner folds remain inside each outer training set;
- row-order changes do not change fold membership;
- seed, snapshot, search-space, engine set, or version changes identity;
- all fitted transforms receive training rows only;
- a finite search rejects unknown parameters and more than 12 configurations;
- deterministic tie-breaking chooses the same configuration; and
- tuning APIs reject NASA test partitions and test-derived metrics.

### Model comparison

- Phase 4 Ridge/logistic configurations remain exact;
- histogram-gradient-boosting search settings and seeds are versioned;
- engine-balanced outer out-of-fold metrics match known vectors;
- one out-of-fold prediction exists for each source-training row;
- whole-engine bootstrap is paired, deterministic, and uses 2,000 replicates;
- regression and classification point/interval/guardrail boundary cases;
- failure of a complexity gate selects the baseline;
- optional ensemble weights use development predictions only; and
- probabilities remain finite and in `[0, 1]`, while RUL output remains
  non-negative under the documented rule.

### Selection and benchmark isolation

- canonical locked-selection record includes all required identities;
- missing, tampered, mismatched, unlocked, or stale records fail closed;
- benchmark code cannot call tuning or change a model configuration;
- repeated benchmark execution reuses the same selection identity; and
- changed NASA test metrics cannot change the selection decision.

### Clustering and novelty

- sampling capped at 100 cycles per engine prevents long trajectories
  dominating;
- scaler/PCA/KMeans fit only source-training features;
- cluster search is limited to two through six with fixed seeds;
- 95%-variance PCA, silhouette, 0.80 adjusted-Rand stability, and rejection
  rules match known data;
- label changes do not alter fitted clusters or selected cluster count;
- cluster labels are canonicalized for stable reporting;
- Isolation Forest with automatic contamination sees only rows in the first
  20% of each declared source-training lifecycle;
- RUL/risk changes do not alter detector state;
- score direction, bounds, seed reproducibility, and lifecycle summaries; and
- reports omit unsupported anomaly precision/recall fields.

### Explainability and reports

- permutation importance uses held-out outer-fold rows;
- feature order and fold-ranking stability are deterministic;
- coefficients and importance values bind to the correct feature names;
- lifecycle bands and engine error summaries match known vectors;
- output examples and worst-engine lists are bounded; and
- reports reject secrets, endpoints, absolute paths, full telemetry, and full
  prediction dumps.

## Synthetic integration path

The committed synthetic fixture must contain enough engines, class balance,
nonlinear signal, and lifecycle progression to exercise reduced fold counts in
CI while preserving the same contracts.

The integration test will:

1. publish a verified temporary Phase 3-style feature snapshot;
1. load it by explicit ID and validate lineage;
1. create nested engine folds;
1. compare both Phase 4 references with bounded advanced searches;
1. create paired bootstrap evidence and apply both decision gates;
1. lock the selection record;
1. prove tuning cannot see the synthetic benchmark partition;
1. evaluate the locked benchmark in a separate call;
1. run clustering, novelty, explanations, and bounded reports;
1. log and retrieve the evidence through a real temporary MLflow server;
1. rerun from clean state and compare identities/behavior; and
1. inject a fold, artifact, or selection-record failure and prove no successful
   benchmark result is recorded.

Synthetic model performance proves software behavior only.

## Actual FD001 evidence

The separate `dataset`-marked run must:

1. verify the approved raw/processed/feature and Phase 4 split identities;
1. create and record the Phase 5 nested fold-manifest ID;
1. run the bounded source-training comparison without NASA test access;
1. record outer out-of-fold metrics, confidence intervals, gates, and the
   locked selection record;
1. run exactly one separate NASA benchmark evaluation for the locked winner;
1. record the known-test-exposure limitation;
1. run and record cluster stability and novelty score summaries without
   ground-truth claims;
1. record explainability/error evidence, runtime, peak or bounded memory where
   practical, and artifact sizes;
1. repeat the deterministic development path and compare behavior; and
1. retrieve the selected trusted model from local MLflow and verify prediction
   parity.

CI does not contain or download NASA data.

## MLflow and security tests

- real loopback server with temporary SQLite and proxied local artifacts;
- Phase 5 parent/child run hierarchy and complete provenance tags;
- content-addressed fold/search/selection/bootstrap/analysis artifacts;
- exact signature, `skops` trusted-type inspection, digest, and prediction
  parity;
- wrong-run, wrong-snapshot, wrong-selection, or unsafe artifact rejection;
- registry remains empty;
- no credential, private URL, absolute path, or full prediction artifact;
- no Supabase mutation, Airflow training, registry, promotion, API, or
  deployment command; and
- dependency audit with no unresolved critical/high issue.

## Planned command groups

Phase 5 retains the Phase 4 local and CI commands and adds Phase 5 tests to the
existing non-cloud marker groups. The exact commands remain:

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

The actual FD001 Phase 5 command runs separately under `dataset` and `mlflow`.
Cleanup must target only disposable containers and generated local Phase 5
evidence.

## Exit criteria

All acceptance criteria and local gates pass; actual FD001 comparison,
selection, benchmark, MLflow, unsupervised, explanation, reproducibility,
security, and existing-container evidence is recorded; the real GitHub Actions
check passes; documentation matches behavior; and no critical/high issue
remains.
