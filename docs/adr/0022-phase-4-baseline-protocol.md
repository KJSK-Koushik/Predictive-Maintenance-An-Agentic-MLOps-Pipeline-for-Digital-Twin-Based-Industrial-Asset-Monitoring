# ADR 0022: Fixed linear baselines and relative eligibility gates

## Status

Accepted

## Date

2026-08-14

## Context

Phase 4 needs credible, reproducible reference models without turning baseline
work into tuning. Long engine trajectories can dominate pooled metrics, and
the inclusive 30-cycle risk target is imbalanced.

## Decision

Use exactly the three operating settings and 21 sensors. Exclude engine ID,
cycle, RUL, and failure-risk target columns from the model matrix. Fit all
preprocessing only on the 80 training-engine groups.

For uncapped RUL, compare `DummyRegressor(strategy="median")` with
`StandardScaler` plus `Ridge(alpha=1.0)`. Floor output predictions at zero and
record the clipped count. The primary metric is engine-balanced RMSE.

For inclusive 30-cycle risk, compare `DummyClassifier(strategy="prior")` with
`StandardScaler` plus class-balanced `LogisticRegression` using `liblinear`,
`max_iter=1000`, seed 42, and threshold 0.5. The primary metric is
engine-balanced average precision.

A candidate is eligible only when it beats its dummy on the primary validation
metric. Final-test metrics are reported afterward without configuration
changes. Pooled, lifecycle, final-cycle, calibration, confusion, residual, and
NASA asymmetric evidence remains secondary. No absolute production gate is
invented.

## Consequences

The baselines are understandable and leakage-safe but deliberately simple.
Eligibility means only that the fixed candidate beat a trivial reference on
this simulated-data protocol. It does not mean registry approval, field
validity, deployment readiness, or maintenance authority.

## Alternatives

- Target capping, tuning, ensembles, neural models, and threshold optimization:
  deferred to Phase 5.
- Pooled metrics only: rejected because longer trajectories would receive more
  influence.
- Accuracy as the classification gate: rejected because it obscures class
  imbalance.

## Verification

Tests cover estimator parameters, train-only scaler state, mutation resistance
for validation/test rows, output flooring, the fixed threshold, known-vector
metrics, prediction digests, reproducibility, and both dummy-relative gates on
synthetic and actual FD001.
