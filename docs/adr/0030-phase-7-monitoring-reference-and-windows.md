# ADR 0030: Immutable monitoring references and replay windows

## Status

Accepted

## Date

2026-09-07

## Context

FD001 is a static simulated run-to-failure dataset. Calling repeated reads
"real-time monitoring" or treating every distribution change as degradation
would overstate the evidence. Long engine trajectories can also dominate
ordinary row-weighted statistics.

## Decision

Monitor explicit, immutable cycle-replay windows against a content-addressed
reference built only from the approved source-training feature snapshot and
the exact active release. Sampling and aggregate metrics are bounded and
engine-balanced. The policy fixes reference bins, adequacy rules, and practical
effect-size thresholds before a window is read. Reports keep data quality,
feature shift, prediction shift, service health, and delayed performance as
separate signals and record lifecycle and operating-setting composition.

Replay sequence is governance metadata, not telemetry cycle or event time.
Phase 7 uses the term `cycle replay`; it makes no live, field, real-time,
production, or full digital-twin claim.

## Consequences

Repeated governed inputs produce the same SHA-256 identity, while a release,
policy, data, membership, code, or dependency change produces new evidence.
Distribution alerts require interpretation alongside lifecycle mix and cannot
by themselves prove model error or physical degradation.

## Alternatives

- Row-weight every telemetry record: rejected because longer trajectories
  would dominate the evidence.
- Fit drift bins on every current window: rejected because thresholds would
  move after observing the evidence.
- Add a streaming platform: rejected because FD001 is static replay data.
- Add Evidently immediately: deferred because small project-owned metrics are
  sufficient and easier to validate deterministically.

## Verification

Contract, metric, adequacy, sampling, identity, replay, actual-FD001, and
failure-path tests verify the decision. The completion report records actual
and synthetic evidence separately.
