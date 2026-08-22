# ADR 0028: Immutable verified FastAPI inference contract

## Status

Accepted

## Date

2026-08-22

## Context

The selected models need a narrow serving contract. C-MAPSS identities are
useful provenance but must not enter the model matrix. Unsafe serialized
objects, malformed batches, or mismatched model pairs must fail before
inference. Phase 5 did not produce valid per-prediction uncertainty intervals.

## Decision

FastAPI exposes only liveness, readiness, release metadata, and versioned
prediction endpoints. The application loads one release during lifespan
startup, verifies canonical manifest bytes, all SHA-256 values, inspected
`skops` trusted types, the exact 24-feature contract, and a non-circular model
output parity fixture.

Prediction accepts 1-128 observations. Positive `engine_id` and `cycle` values
remain provenance; the three settings and 21 sensors form an ordered
`float64` matrix. Extra, missing, Boolean, non-finite, oversized, and
wrong-content-type inputs fail with bounded stable errors before prediction.
RUL is floored at zero, risk probability is bounded to `[0, 1]`, and the label
uses the approved 30-cycle horizon and 0.5 threshold. Responses state
`predictive_uncertainty_status: not_available`.

## Consequences

Readiness is stronger than process liveness. The runtime needs no MLflow,
Supabase, or PostgreSQL credential. This is a synchronous local research API,
not public, hard-real-time, highly available, or safety certified.

## Alternatives

- Load the current registry alias per request: rejected because a mutable alias
  could silently change behavior.
- Include engine and cycle in the model matrix: rejected as a contract and
  leakage error.
- Return a fabricated confidence interval: rejected because Phase 5 produced
  evaluation uncertainty, not prediction intervals.
- Load pickle/joblib artifacts: rejected because the trusted `skops` boundary
  is already established.

## Verification

API and model-loader tests cover valid batches, all boundary sizes, exact
OpenAPI paths, stable errors, provenance, output bounds, startup parity,
tampered artifacts, liveness/readiness separation, and production denial.
Container smoke tests compare direct and HTTP predictions exactly.
