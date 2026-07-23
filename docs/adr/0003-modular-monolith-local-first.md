# ADR-0003: Modular Monolith and Local-First Delivery

## Status

Accepted

## Date

2026-07-23

## Context

The proposed stack contains several deployable systems. Beginning with
microservices would add networking, versioning, and operational failure modes
before component boundaries are stable.

## Decision

Project logic will start as a typed Python modular monolith. Pure domain and
application functions sit behind explicit repository/adaptor interfaces.
Local filesystem and temporary/local service substitutes precede cloud
adapters. A component becomes a separately deployed service only when a phase
requires an independent runtime boundary, such as the inference API or Airflow.

## Consequences

Local tests remain fast and cloud-independent. Modules need disciplined imports
and ownership to avoid a monolith without boundaries. Infrastructure is added
later but with less speculative design.

## Alternatives

- Microservices from Phase 1: rejected as unnecessary operational complexity.
- Notebook-only implementation: rejected because reuse, typing, testing, and
  serving boundaries would be weak.

## Verification

Architecture tests prohibit later-phase service trees during Phase 0. Future
tests will enforce dependency direction and adapter contracts.
