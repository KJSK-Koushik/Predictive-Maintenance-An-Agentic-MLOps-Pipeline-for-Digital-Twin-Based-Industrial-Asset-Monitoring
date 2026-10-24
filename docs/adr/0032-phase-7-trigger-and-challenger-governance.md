# ADR 0032: Deterministic triggers with no promotion authority

## Status

Accepted

## Date

2026-09-07

## Context

Monitoring may justify investigation or a candidate evaluation, but it cannot
safely authorize training success, model registration, alias mutation, or
deployment. FD001 also provides no genuinely new approved training population
after the existing benchmark work.

## Decision

Use a deterministic, versioned trigger policy. Data-quality and service
failures create investigations only. One adequate distribution alert also
creates only an investigation; persistent independent alerts or confirmed
delayed-label performance degradation may create an immutable,
evaluation-only candidate request. Unavailable or insufficient evidence
cannot trigger a request.

Performance degradation is calculated from fixed RMSE/Brier baselines in the
versioned policy thresholds, not accepted as a caller boolean. The request
records the policy digest, which includes configured baseline values. With no approved baseline, performance-trigger
evaluation stays inactive; an available performance metric alone is not a
degradation claim. Histories must share release, reference and partition and
use distinct increasing replay sequences with adequate, valid signals.

The optional `performance_baseline_rmse` and `performance_baseline_brier` must
both be present and valid to enable that comparison. Both null means disabled;
null optional values are omitted from policy-identity bytes to preserve the
existing default-policy identity. The actual demonstration leaves them unset
because no new comparable approved performance baseline is claimed.

Synthetic challengers are compared with the champion on identical whole-engine
evaluation rows using practical regression and classification guardrails and
all required release checks. Passing means only
`eligible_for_human_review`. The evaluator and trigger controller contain no
MLflow alias, registry, deployment, rollback, or production credential or
operation. Actual FD001 may honestly end as `no_change` or
`blocked_no_new_training_data`.

The evaluator consumes aligned cycle-level targets and both models' predictions,
then reuses the Phase 5 metrics and paired whole-engine bootstrap. The RUL gate
requires at least 3% RMSE improvement, a positive 95% interval, and MAE/NASA-score
non-inferiority within 5%. The risk gate requires at least 0.005 absolute AP
improvement, a positive interval, and no more than 0.01 Brier deterioration.
External release-check evidence must be supplied explicitly; an omitted check
is false. Synthetic check fixtures prove decision mechanics only. They do not
prove a real model passed signature, security, or reproducibility checks.

## Consequences

Phase 7 is human-governed monitoring and evaluation, not autonomous or
continuous retraining. Any future eligible actual challenger requires a new
explicit release approval and must reuse Phase 6 packaging, smoke, staging,
and rollback controls.

## Alternatives

- Automatically retrain on drift: rejected because shift is not proof of
  degraded performance.
- Automatically promote a passing challenger: rejected because deterministic
  checks do not replace human release approval.
- Train on NASA test rows: rejected as benchmark leakage.
- Invent new actual training data: rejected because no approved source exists.

## Verification

Trigger, deduplication, unavailable-evidence, synthetic challenger pass/fail,
promotion-denial, NASA-test exclusion, alias-immutability, and actual no-change
tests verify the decision.
