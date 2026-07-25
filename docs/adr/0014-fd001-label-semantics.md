# ADR 0014: Canonical uncapped RUL and inclusive risk horizons

## Status

Accepted

## Date

2026-07-25

## Context

C-MAPSS supports different RUL target conventions. Silent capping or an unclear
risk boundary would make later experiments difficult to reproduce and could
hide off-by-one errors.

## Decision

Use uncapped integer RUL as the canonical Phase 1 target. Training RUL is the
engine endpoint cycle minus the observation cycle. Test RUL combines the final
observed cycle with the supplied terminal RUL. Define horizon risk inclusively:
`failure_risk_H = 1` when `rul <= H`. Use 30 cycles as the primary horizon and
report sensitivity at 15 and 45 cycles.

Do not create a capped target in Phase 1. A later cap must be a separate,
versioned derivation and cannot replace the canonical label silently.

## Consequences

Endpoint RUL is zero for run-to-failure training trajectories. Risk labels are
reproducible derived targets, not observed failures. The test label uses
ground-truth terminal RUL and is therefore for evaluation, not an online input.

## Alternatives

- Cap RUL at a common heuristic value: deferred because Phase 1 has no model
  evidence to justify a cap.
- Use `rul < H`: rejected because the declared boundary is inclusive.
- Treat test terminal RUL as a feature: rejected as target leakage.

## Verification

Unit tests cover endpoints, off-by-one behavior, non-negativity, test-vector
mapping, the 29/30/31 risk boundary, and invalid horizons. Exploration records
15-, 30-, and 45-cycle prevalence.
