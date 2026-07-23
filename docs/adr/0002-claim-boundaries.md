# ADR-0002: Research Terminology and Claim Boundaries

## Status

Accepted

## Date

2026-07-23

## Context

The terms digital twin, real-time, autonomous, failure risk, and continuous
retraining carry stronger meanings than an offline simulated dataset can
support.

## Decision

The first system is described as an asset-health **digital shadow** inspired by
digital-twin architecture. Telemetry is processed offline or by cycle-level
replay. "Towards Autonomous" is aspirational; operational authority stays with
deterministic gates and humans. Failure risk is explicitly derived from an RUL
horizon. Retraining is trigger-based candidate evaluation, never an unattended
path to production.

Any stronger claim requires an exercised capability and measured objective in a
later accepted phase.

## Consequences

The project title may remain, but abstracts, diagrams, dashboards, and
conclusions must carry these qualifications. Results cannot be generalized to
physical fleets without external validation.

## Alternatives

- Use the stronger terms without qualification: rejected as academically
  overstated.
- Remove all twin and autonomy language: rejected because bounded versions are
  legitimate research subjects.

## Verification

Documentation reviews and repository tests check the core claim-boundary text.
Phase 10 audits every final claim against evidence.
