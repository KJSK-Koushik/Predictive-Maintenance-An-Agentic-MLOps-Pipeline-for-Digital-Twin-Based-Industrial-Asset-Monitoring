# Phase 4 Plan

## Authorization

Planning was authorized on 2026-08-14 by explicit `PLAN PHASE 4` after Phase 3
was owner-approved and merged.

Implementation was authorized on 2026-08-14 by the explicit command
`START PHASE 4`. This authorizes the local-only modeling, MLflow, tests, CI,
and documentation described here. It does not authorize later-phase work.

## Objective

Implement leakage-safe, reproducible FD001 baselines for uncapped RUL
regression and inclusive 30-cycle failure-risk classification. Both tasks will
use one engine-disjoint split manifest and fixed scikit-learn pipelines, with
aggregate evaluation and provenance recorded in a local database-backed MLflow
tracking server.

## Refined scope

Phase 4 will:

- consume one explicit, available, reconciled Phase 3 feature snapshot;
- verify feature/target schemas, hashes, lineage, and key alignment;
- exclude `engine_id`, `cycle`, RUL, and risk labels from model inputs;
- split NASA training engines into one seeded 80/20 train/validation division;
- preserve the NASA test partition as the final holdout;
- fit all preprocessing only on training engines;
- train one dummy and one fixed linear candidate per task;
- evaluate engine-balanced, pooled, lifecycle-band, and final-cycle metrics;
- introduce a simple relative-to-dummy validation gate;
- record explicit runs, inputs, metrics, reports, signatures, and trusted model
  artifacts in local MLflow;
- exercise actual FD001 locally and deterministic synthetic fixtures in CI;
  and
- update quality gates, ADRs, documentation, and completion evidence.

Phase 4 will not tune models after seeing validation or test results. It will
not register, promote, deploy, serve, monitor, retrain, or agentically select a
model.

## Work breakdown after start authorization

1. Complete the Phase 4 manual prerequisites and confirm the local-only MLflow
   topology and evidence-retention policy.
1. Verify current Python 3.11 compatibility for scikit-learn, MLflow, skops,
   NumPy, SciPy, pandas, and the locked project dependencies using official
   sources.
1. Add only the reviewed modeling/tracking dependencies and inspect the
   complete lockfile and security-audit diff.
1. Define versioned training-input, split-manifest, model-configuration,
   evaluation-report, and prediction-digest contracts.
1. Implement a loader that verifies one explicit Phase 3 feature snapshot and
   never reads mutable source data directly.
1. Implement one seeded engine-level development split and the fixed NASA test
   holdout, with deterministic manifest identity and zero-overlap assertions.
1. Implement shared feature-column selection and train-only scaling through
   scikit-learn `Pipeline` objects.
1. Implement the RUL dummy and fixed Ridge candidate with non-negative output
   flooring.
1. Implement the risk prior dummy and fixed class-balanced logistic candidate
   with a fixed 0.5 threshold.
1. Implement engine-balanced and pooled metrics, lifecycle bands, final-cycle
   summaries, and the relative-to-dummy eligibility gates.
1. Implement explicit MLflow logging with local SQLite metadata and local
   artifacts, model signatures, schema-only input examples, and `skops`
   serialization.
1. Add a direct, sanitized baseline-training CLI; do not add an Airflow DAG.
1. Add unit, contract, integration, security, reproducibility, failure, and
   actual-dataset tests alongside the implementation.
1. Add credential-free GitHub Actions gates for synthetic baseline training,
   MLflow round-trip, coverage, and artifact-ignore checks.
1. Exercise actual FD001 locally and record metrics without changing the fixed
   protocol after test evaluation.
1. Update the source-of-truth documents, focused ADRs, and completion report.
1. Run every local gate, push the implementation branch, and verify the actual
   GitHub Actions result before claiming completion.

## Expected new files

```text
src/predictive_maintenance/modeling/
  __init__.py
  models.py
  loading.py
  splitting.py
  preprocessing.py
  baselines.py
  metrics.py
  evaluation.py
  tracking.py
  pipeline.py
  cli.py

tests/modeling/
tests/integration/model_tracking/

docs/adr/0021-*.md
docs/adr/0022-*.md
docs/adr/0023-*.md
```

Related modules and ADRs may be combined when that preserves a clearer,
smaller boundary. Phase 4 will not create top-level `models/`, `services/`,
`monitoring/`, `agents/`, or dashboard implementation roots.

## Existing files expected to change

```text
.env.example
.github/workflows/ci.yml
.gitignore
README.md
pyproject.toml
uv.lock
src/predictive_maintenance/cloud/
tests/fixtures/
tests/foundation/test_repository_contract.py
tests/integration/test_ci_contract.py
docs/DATA_CONTRACT.md
docs/MASTER_ARCHITECTURE.md
docs/MANUAL_PREREQUISITES.md
docs/PROJECT_STATUS.md
docs/ROADMAP.md
docs/SECURITY_AND_SECRETS.md
docs/TEST_STRATEGY.md
docs/adr/
docs/phases/phase-04/
```

Existing cloud code may change only to expose a narrow read-only feature
snapshot query required by the modeling loader. No Supabase migration or cloud
write is planned. Any file outside this list needs a written Phase 4
justification.

## Architecture decisions to document

Implementation must add focused ADRs for:

1. the NASA train/validation/test roles, shared engine-disjoint split manifest,
   and holdout discipline;
1. the fixed Ridge/logistic baselines, train-only scaling, metrics, and
   relative-to-dummy eligibility gates; and
1. the local SQLite-backed MLflow topology, explicit logging, trusted `skops`
   artifacts, and registry deferral.

Existing accepted ADRs are not rewritten to hide a changed decision.

## Planned CI growth

Phase 4 CI will retain every applicable Phase 3 gate and add:

- feature/target input-boundary and lineage tests;
- engine-disjoint split, manifest identity, full-coverage, and overlap tests;
- preprocessing leakage tests proving validation/test changes do not alter
  fitted state;
- deterministic Ridge, logistic, dummy, metric, threshold, and output-floor
  tests;
- fixed synthetic performance-gate tests with known signal;
- repeated-run prediction and metric tolerance tests;
- temporary SQLite-backed MLflow server health, log, retrieve, signature, and
  trusted-model round-trip tests;
- generated-artifact and secret scanning; and
- the existing minimum 90% branch-aware product coverage gate.

Ordinary CI uses only committed synthetic fixtures. It will not train on the
owner dataset, contact Supabase, create a registered model, promote a model, or
deploy anything.

## Manual prerequisites before implementation

- approve `127.0.0.1:5000` as the local-only MLflow endpoint;
- approve SQLite metadata and local artifacts under ignored
  `artifacts/mlflow/` for Phase 4;
- accept that this is reproducible research evidence, not a durable shared
  tracking service, and require a local copy/restore exercise before
  completion;
- confirm the project owner is the Phase 4 evaluation reviewer while model
  promotion authority remains deferred to Phase 6;
- keep all generated MLflow state, artifacts, credentials, and private paths
  outside Git;
- confirm no remote MLflow, Supabase mutation, paid resource, or production
  model registry is authorized; and
- keep the final NASA test partition unavailable to fitting and configuration
  decisions.

Sending `START PHASE 4` approves this documented local topology and these
phase-scoped prerequisites unless the owner changes a listed item first.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. This includes deterministic
split and training behavior, leakage tests, both relative-to-dummy validation
gates, actual FD001 evidence, local MLflow integration and restore evidence,
all local quality gates, the required GitHub Actions run, updated documents,
and no unresolved critical/high issue.

## Planning risks

| Risk                                         | Planned treatment                                                             |
| -------------------------------------------- | ----------------------------------------------------------------------------- |
| Rows from one engine leak across splits      | Group only by engine; assert zero overlap and canonical engine lists          |
| NASA train/test engine numbers collide       | Use source partition plus engine ID as identity                               |
| Scaling learns validation/test statistics    | Put scaling inside fitted pipelines and test fitted state                     |
| Test results influence model choices         | Fix configuration and gate on validation before final evaluation              |
| Long trajectories dominate metrics           | Make engine-balanced metrics primary and report pooled metrics separately     |
| Class imbalance hides poor risk behavior     | Use average precision as primary; report calibration and confusion evidence   |
| Capped RUL improves scores opportunistically | Keep canonical uncapped RUL; defer versioned cap experiments to Phase 5       |
| MLflow duplicates operational metadata       | MLflow owns experiment evidence; operational `ops` is unchanged               |
| MLflow adds unnecessary infrastructure       | Use loopback SQLite and local artifacts; no remote database or object store   |
| Model loading executes untrusted code        | Use explicit `skops`; load only verified run-owned artifacts                  |
| Reproducibility is overstated                | Compare predictions/metrics with tolerance, not model-file byte identity      |
| Actual dataset makes CI slow or unavailable  | Use synthetic CI fixtures and record actual FD001 as separate local evidence  |
| Baseline scope turns into tuning             | One fixed candidate per task; no search, ensembles, or threshold optimization |
| A baseline is mistaken for deployable        | No registry, promotion, API, deployment, or production claim                  |

## Stop condition

Planning may update only architecture, governance, and phase-plan records. Stop
completely after the plan branch passes its documentation/governance checks.
Do not add dependencies, start MLflow, train a model, or create generated
artifacts until the owner sends:

`START PHASE 4`
