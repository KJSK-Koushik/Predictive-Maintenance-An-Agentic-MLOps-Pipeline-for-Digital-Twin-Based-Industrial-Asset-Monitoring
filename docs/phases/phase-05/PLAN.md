# Phase 5 Plan

## Authorization

Planning was authorized on 2026-08-20 by the explicit command
`PLAN PHASE 5`, after Phase 4 was owner-approved and merged.

Implementation was authorized on 2026-08-21 by the explicit command
`START PHASE 5`. This authorizes only the local Phase 5 implementation,
evidence, tests, CI changes, and documentation described here. It does not
authorize cloud mutation, deployment, promotion, or later-phase work.

## Objective

Run a reproducible and leakage-controlled comparison between the approved
Phase 4 linear baselines and one bounded nonlinear scikit-learn family per
task. Quantify evaluation uncertainty, add exploratory telemetry-state and
novelty analysis, and produce explainability/error evidence without claiming
ground-truth health states or autonomous maintenance.

## Refined scope

Phase 5 will:

- reuse the exact approved FD001 feature snapshot and target semantics;
- create a versioned nested engine-group cross-validation manifest over NASA
  source-training engines;
- rerun the Phase 4 Ridge and logistic candidates under that comparison
  protocol;
- tune one histogram-gradient-boosting family per task with a finite checked-in
  grid of at most 12 configurations;
- compare paired outer-fold predictions with engine-balanced metrics and 2,000
  engine-bootstrap replicates;
- lock the preferred family before one separate NASA test benchmark run;
- measure classification calibration without inventing a production threshold;
- run one bounded KMeans telemetry-state study and one Isolation Forest novelty
  study;
- produce fold-stable permutation importance and lifecycle/engine error
  analysis;
- record explicit local MLflow evidence with trusted model artifacts;
- use synthetic fixtures in CI and actual FD001 only as separate local
  evidence; and
- update contracts, ADRs, CI, security, architecture, and completion evidence.

Phase completion does not require the nonlinear candidate to win. It requires
the predeclared decision rule to be applied honestly.

## Work breakdown after start authorization

1. Reconfirm the approved Phase 4 input snapshot, local MLflow topology,
   ignored evidence paths, CPU budget, and locked-benchmark discipline.
1. Verify the current locked scikit-learn/MLflow APIs and security audit before
   changing dependencies; prefer no new runtime dependency.
1. Add canonical Phase 5 fold-manifest, search-space, comparison,
   bootstrap, selection-record, clustering, novelty, and explanation contracts.
1. Implement five outer and four inner engine-group folds with deterministic
   identity, complete coverage, and zero overlap.
1. Separate tuning from NASA benchmark evaluation in both code and CLI.
1. Reuse the exact Phase 4 baselines and implement one bounded
   histogram-gradient-boosting search per task.
1. Generate outer out-of-fold predictions and apply the predeclared
   regression/classification complexity gates.
1. Create an immutable selection record and refuse benchmark evaluation when
   it is missing, inconsistent, or does not match the current evidence.
1. Fit the locked winner on all source-training engines and run the NASA test
   benchmark once without post-test changes.
1. Implement paired engine bootstrap intervals and clearly label them as
   evaluation uncertainty, not per-prediction uncertainty.
1. Implement training-only, engine-balanced KMeans/PCA stability analysis and
   Isolation Forest novelty scoring with no anomaly-accuracy claim.
1. Implement fold-based coefficients/permutation importance and bounded error
   slices that cannot feed back into feature selection.
1. Generalize explicit MLflow logging for Phase 5 runs while keeping the
   registry empty and artifacts trusted through `skops`.
1. Add unit, contract, integration, leakage, reproducibility, security,
   actual-FD001, and failure-path tests alongside the code.
1. Add credential-free GitHub Actions gates for the synthetic Phase 5 path and
   retain all applicable earlier gates.
1. Record actual FD001 metrics, confidence intervals, clustering stability,
   novelty limitations, explanations, runtime, and artifact sizes.
1. Update the source-of-truth documents and focused ADRs.
1. Run every local gate, push the implementation branch, and inspect the real
   GitHub Actions result before claiming completion.

## Expected new files

```text
src/predictive_maintenance/modeling/
  advanced.py
  comparison.py
  analysis.py
  unsupervised.py
  phase5_pipeline.py
  phase5_cli.py

tests/modeling/
  test_advanced.py
  test_comparison.py
  test_analysis.py
  test_unsupervised.py
  test_phase5_pipeline.py

tests/integration/model_tracking/
  test_phase5_tracking.py
  test_actual_fd001_phase5.py

docs/adr/0024-*.md
docs/adr/0025-*.md
docs/adr/0026-*.md
```

Files may be combined when that gives a smaller and clearer design. Phase 5
will not create top-level `models/`, `agents/`, `monitoring/`, `api/`, or
dashboard packages.

## Existing files expected to change

```text
.github/workflows/ci.yml
.gitignore
README.md
pyproject.toml
uv.lock
src/predictive_maintenance/modeling/
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
docs/phases/phase-05/
```

`pyproject.toml` and `uv.lock` change only if an existing dependency or CLI
entry point requires it. The preferred plan uses the already locked
scikit-learn, NumPy, pandas, matplotlib, MLflow, and skops stack. Supabase,
Airflow, ETL, migration, and deployment files are not expected to change.

## Architecture decisions to document

Implementation must create focused ADRs for:

1. nested engine-group model comparison, locked selection evidence, and the
   honest status of the previously observed NASA test benchmark;
1. bounded histogram-gradient-boosting search, paired engine-bootstrap
   uncertainty, and complexity gates that may retain the baseline; and
1. exploratory cluster/novelty semantics, label-free selection, and rejection
   of ground-truth health-state or anomaly-detection claims.

The multi-task neural option will be recorded as not justified unless a
separate approved amendment supplies an independent hypothesis, compute
budget, and ablation plan.

## Manual prerequisites before implementation

- Continue using only the approved FD001 snapshot and local-only MLflow
  topology.
- Keep generated search, model, plot, and analysis evidence ignored by Git.
- Accept the finite CPU-only search budget; no GPU or paid resource is needed.
- Accept that the NASA test benchmark is not scientifically blind because its
  Phase 4 results are already known.
- Keep NASA test inputs unavailable to tuning code until the selection record
  is locked.
- Confirm that no Supabase mutation, remote MLflow, registry action,
  deployment, or deep-learning framework is authorized.
- Confirm the project owner remains the human reviewer; Phase 6 owns any later
  promotion decision.

Sending `START PHASE 5` approves these listed local prerequisites unless the
owner changes one first. It does not approve a neural-network amendment.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. The comparison may select the
linear baseline. Completion additionally requires actual FD001 evidence,
reproducible local MLflow evidence, all local quality/security/container
regression gates, the real required GitHub Actions pass, updated documents, and
no unresolved critical/high issue.

## Planning risks

| Risk                                     | Planned treatment                                                                                         |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Known test scores influence choices      | Use nested source-train CV, a separate locked selection record, and state that the benchmark is not blind |
| Cycles from one engine leak across folds | Split by engine and assert zero group overlap at both nested levels                                       |
| Search overfits a small dataset          | One nonlinear family, finite grid, nested CV, paired engine bootstrap                                     |
| More complex is assumed better           | Require practical and confidence-interval gates; retain baseline on failure                               |
| Long engines dominate evidence           | Engine-balanced metrics, sampling, and whole-engine bootstrap                                             |
| AP improves while probabilities degrade  | Keep Brier non-inferiority as a classifier guardrail                                                      |
| Cluster IDs are called health states     | Use label-free selection and the term exploratory telemetry state                                         |
| Novelty scores are called fault alarms   | Report no precision/recall and prohibit maintenance-action integration                                    |
| Explanations drive hidden retuning       | Produce explanations after fold predictions and prohibit feedback into search                             |
| Neural multi-task learning is overstated | Default rejection because risk is derived from RUL; require an approved amendment                         |
| Search exhausts the workstation          | CPU-only finite grid, bounded parallelism, synthetic CI path                                              |
| Phase 5 drifts into deployment           | Keep registry, FastAPI, containers for serving, promotion, and staging in Phase 6                         |

## Stop condition

Planning changes only architecture, governance, and Phase 5 plan records. Stop
completely after planning checks and remote CI are verified. Do not implement,
train, tune, start MLflow, or run analysis until the owner sends:

`START PHASE 5`
