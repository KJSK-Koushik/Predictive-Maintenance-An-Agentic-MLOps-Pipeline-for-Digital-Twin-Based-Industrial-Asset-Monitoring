# ADR-0012: Digital-Shadow State and Replay Semantics

## Status

Accepted

## Date

2026-07-23

## Context

C-MAPSS provides offline simulated trajectories. A dashboard over model output
does not create a bidirectional physical twin or prove live industrial
operation.

## Decision

The project implements a versioned asset-health digital shadow. Cycle-level
replay supplies validated telemetry to the inference boundary. State includes
asset/cycle identity, input and feature provenance, RUL and uncertainty,
failure-risk horizon/probability, optional cluster/anomaly results, model
release, freshness, validation status, and audit references.

Replay timestamps and ingestion timestamps remain distinguishable. The state
cannot issue physical commands. Any future near-real-time claim requires an
exercised live source plus defined and measured latency/reliability objectives.

## Consequences

The dashboard can demonstrate state evolution honestly but cannot claim
physical synchronization. The state contract must be implemented before the
dashboard so serving, monitoring, and audit share semantics.

## Alternatives

- Call any telemetry dashboard a digital twin: rejected as imprecise.
- Delay all state design until the dashboard: rejected because upstream
  contracts would diverge.

## Verification

Later contract tests validate provenance, freshness, replay ordering, model
version, uncertainty, and inability to produce control actions.
