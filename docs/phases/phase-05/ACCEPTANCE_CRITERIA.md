# Phase 5 Acceptance Criteria

## Authorization and scope

- [x] `START PHASE 5` is received before implementation begins.
- [x] Local-only MLflow, CPU budget, FD001-only input, benchmark exposure, and
  no-cloud/no-deployment prerequisites are reconfirmed.
- [x] Work remains limited to advanced comparison, evaluation uncertainty,
  exploratory clustering/novelty, explainability, tests, CI, and documents.
- [x] No registry, promotion, serving, deployment, monitoring, retraining,
  agent, dashboard, Supabase mutation, or paid resource is introduced.

## Inputs and leakage control

- [ ] One explicit verified `fd001-candidate-features-v1` snapshot is required.
- [ ] Phase 4 lineage, object, schema, key-alignment, and target checks remain
  enforced.
- [ ] Inputs remain exactly three settings plus 21 sensors; keys and targets
  are excluded.
- [ ] RUL remains uncapped and risk remains inclusive at 30 cycles.
- [ ] Five outer and four inner deterministic engine-group folds have canonical
  identities, complete coverage, and zero engine overlap.
- [ ] Fitted preprocessing and tuning use only the relevant inner/outer
  training engines.
- [ ] The tuning path cannot access NASA test features, targets, or metrics.
- [ ] Benchmark evaluation requires a matching locked-selection record and
  cannot change the selected configuration.
- [ ] The completion report states that NASA test is a previously observed
  benchmark, not a blind holdout.

## Supervised comparison

- [ ] The unchanged Phase 4 Ridge and logistic candidates are re-evaluated on
  the same outer folds as their advanced counterparts.
- [ ] One finite histogram-gradient-boosting grid of at most 12 configurations
  per task is checked in and versioned.
- [ ] Search seeds, folds, metrics, tie-breaking, and parallelism are fixed.
- [ ] Every source-training row receives exactly one outer out-of-fold
  prediction per compared model.
- [ ] Primary and guardrail metrics are finite, engine-balanced, and
  reproducible within declared tolerances.
- [ ] Paired 95% intervals use 2,000 fixed-seed whole-engine bootstrap samples.
- [ ] Regression preference requires at least 3% RMSE improvement, an interval
  above zero, and the MAE/NASA-score guardrails.
- [ ] Classification preference requires at least 0.005 AP improvement, an
  interval above zero, and the Brier guardrail.
- [ ] A failed advanced gate retains the baseline and does not block honest
  phase completion.
- [ ] A simple ensemble is retained only if it improves on the best single
  model under the same gate and uses no test information.
- [ ] No neural dependency or model is added without the separately approved
  hypothesis, budget, ablation, and plan amendment.

## Benchmark and uncertainty

- [ ] The preferred family/configuration is locked before benchmark access.
- [ ] The final selected model is fit on all NASA source-training engines and
  evaluated once on the NASA test benchmark.
- [ ] No post-benchmark feature, target, threshold, hyperparameter, family, or
  gate change occurs.
- [ ] Point metrics and paired confidence intervals are both reported.
- [ ] Bootstrap intervals are labelled evaluation uncertainty, not
  per-prediction RUL uncertainty or a safety guarantee.
- [ ] Calibration and reliability evidence is reported without claiming a
  physical failure probability or production threshold.

## Exploratory unsupervised analysis

- [ ] KMeans/PCA fitting and cluster-count selection use source-training
  features only with engine-balanced sampling.
- [ ] PCA retains 95% variance, sampling is capped at 100 cycles per engine,
  and the fixed cluster range, seeds, silhouette rule, and 0.80 stability rule
  are versioned and reproducible.
- [ ] RUL and risk labels do not fit or select clusters.
- [ ] Post-hoc lifecycle/RUL associations are clearly descriptive.
- [ ] The result permits the conclusion that no stable telemetry-state
  structure was found.
- [ ] Isolation Forest uses `contamination="auto"` and only the declared first
  20% lifecycle reference rows from source-training engines.
- [ ] Labels do not tune novelty parameters or contamination.
- [ ] Novelty output is not reported with fabricated anomaly precision,
  recall, detection delay, or maintenance authority.

## Explainability and error analysis

- [ ] Linear coefficients and nonlinear permutation importance are produced
  from leakage-safe fold evidence.
- [ ] Feature-ranking stability across outer folds is reported.
- [ ] Regression and classification errors are sliced by engine and lifecycle
  bands with bounded summaries.
- [ ] Explanation output cannot silently cause feature selection or retuning.
- [ ] Reports contain no complete telemetry or prediction dump.

## Tracking, security, and reproducibility

- [ ] MLflow remains loopback-only with local SQLite and ignored artifacts.
- [ ] Runs bind snapshot, fold, search, model, bootstrap, analysis, code,
  dependency, and seed identities.
- [ ] Locked-selection and benchmark records are content-addressed and
  provenance-checked.
- [ ] Trusted `skops` artifact controls, signatures, digests, and prediction
  parity remain enforced.
- [ ] The registry is empty; no alias, approval, promotion, or deployment
  record exists.
- [ ] Repeated locked runs reproduce folds, chosen configuration, decision,
  predictions, metrics, intervals, cluster stability, and novelty scores
  within declared tolerances.
- [ ] Generated evidence, credentials, private endpoints, absolute paths, and
  unsafe serialized objects remain outside Git and reports.

## Tests, engineering, and CI

- [ ] Unit tests cover nested folds, search/tie rules, bootstrap, complexity
  gates, selection records, clustering, novelty, explanations, and failures.
- [ ] Integration tests cover the complete synthetic comparison, separate
  locked benchmark, MLflow log/retrieve/load, and fail-closed paths.
- [ ] The ignored owner-provided actual FD001 snapshot passes the complete
  local Phase 5 path.
- [ ] All applicable Phase 0-4 regression tests continue to pass.
- [ ] Formatting, linting, strict typing, lock, Markdown, YAML, dependency,
  secret, migration, and container regression checks pass.
- [ ] Product code maintains at least 90% branch-aware coverage.
- [ ] Ordinary CI uses synthetic data, no cloud credentials, and no promotion
  or deployment action.
- [ ] The required GitHub Actions workflow passes on the completion commit.
- [ ] Branch protection remains enforced and no critical/high issue remains.

## Documentation and completion

- [ ] Master, roadmap, data contract, security, test, manual-prerequisite,
  ADR, and Phase 5 documents match exercised behavior.
- [ ] The completion report distinguishes unit, local integration, MLflow,
  actual FD001, Docker, CI, and unexercised cloud/deployment evidence.
- [ ] Results and limitations use the terms simulated telemetry, exploratory
  telemetry states, novelty score, and evaluation uncertainty correctly.
- [ ] `docs/PROJECT_STATUS.md` becomes `AWAITING_APPROVAL` only after every
  required criterion passes.
- [ ] The completion handoff asks for `APPROVE PHASE 5` and stops completely.
