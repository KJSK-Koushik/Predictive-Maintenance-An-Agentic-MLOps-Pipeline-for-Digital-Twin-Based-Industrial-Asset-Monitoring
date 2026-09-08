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

Synthetic challengers are compared with the champion on identical whole-engine
evaluation rows using practical regression and classification guardrails and
all required release checks. Passing means only
`eligible_for_human_review`. The evaluator and trigger controller contain no
MLflow alias, registry, deployment, rollback, or production credential or
operation. Actual FD001 may honestly end as `no_change` or
`blocked_no_new_training_data`.

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
