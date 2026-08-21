# ADR 0025: Bounded nonlinear search and whole-engine complexity gates

## Status

Accepted

## Date

2026-08-21

## Context

An advanced model should not replace a simpler Phase 4 baseline merely because
one point metric is slightly better. FD001 has only 100 source-training
engines, while its many correlated cycle rows can create false precision.
Unbounded tuning, multiple model families, or a neural network would add
researcher degrees of freedom without independent target information.

## Decision

Compare the exact Phase 4 Ridge and class-balanced logistic models with one
CPU-only family: scikit-learn histogram gradient boosting. Use one checked-in
eight-configuration grid per task, fixed seeds, disabled early stopping,
single-job execution, and canonical tie-breaking. Do not add a neural model or
ensemble by default.

Estimate model-difference uncertainty with 2,000 paired, fixed-seed bootstrap
replicates that resample whole engines. Label the interval evaluation
uncertainty; it is not per-prediction RUL uncertainty or a safety guarantee.

Prefer advanced regression only when engine-balanced RMSE improves by at least
3%, the 95% interval is above zero, and engine-balanced MAE and NASA score are
no worse than 5%. Prefer advanced classification only when engine-balanced
average precision improves by at least 0.005, its interval is above zero, and
engine-balanced Brier score is no worse by more than 0.01. Otherwise retain the
baseline. A failed gate is a valid Phase 5 result.

## Consequences

The protocol is reproducible and falsifiable, but the full two-run FD001 test
takes about 43 minutes on the owner workstation. It is an offline research
evaluation, not continuous training. Phase 5 selected histogram gradient
boosting for regression and retained logistic regression for classification.

The deterministic 30-cycle risk label is derived directly from RUL. A
multi-task neural model is therefore not justified without a separate approved
hypothesis, compute budget, independent supervision argument, and ablation
plan.

## Alternatives

- Bayesian or unbounded search: rejected due cost and selection-bias risk.
- Automatically select the best point score: rejected because tiny noisy
  differences do not justify complexity.
- Row-level bootstrap: rejected because cycles within an engine are correlated.
- Default multi-task neural model: rejected because the second target is
  deterministic from RUL and FD001 has only 100 training engines.

## Verification

Boundary tests cover every gate, fixed grids, deterministic tuning, complete
outer predictions, probability/RUL output rules, and paired bootstrap behavior.
The full FD001 repeat reproduced exact comparison, selection, interval, metric,
and benchmark evidence.
