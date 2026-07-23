# ADR-0011: Monitoring and Retraining Semantics

## Status

Accepted

## Date

2026-07-23

## Context

Feature or prediction drift does not prove model degradation, and labels may be
delayed or absent. Automatic retraining and promotion from a drift threshold
can amplify noise or data-quality failures.

## Decision

Monitoring separately reports data quality, feature drift, prediction drift,
service health, and performance when labels exist. A trigger opens an
investigation or candidate-training request. It never changes the deployed
model.

A candidate uses an immutable data cutoff and passes data, leakage,
reproducibility, performance, robustness, security, and human approval gates.
Champion/challenger comparison uses a fixed approved evaluation protocol.

## Consequences

The system may continue serving the champion while an alert is unresolved.
Missing labels are reported as unavailable evidence. Thresholds need
calibration and may produce false positives.

## Alternatives

- Scheduled unconditional retraining: rejected as wasteful and weakly governed.
- Drift-to-production automation: rejected because drift is not a sufficient
  promotion signal.

## Verification

Phase 7 tests trigger creation, deduplication, failed-candidate containment,
promotion denial, and rollback.
