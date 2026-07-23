# ADR-0005: Pandera as the Initial Contract Library

## Status

Accepted

## Date

2026-07-23

## Context

FD001 is a small, tabular dataset processed in Python. The project needs typed
columns, dataframe checks, semantic validation, reusable errors, and test
fixtures. It does not initially need a separate data-quality service.

## Decision

Phase 1 will use Pandera for executable DataFrame schemas plus ordinary Python
checks for cross-file and lineage invariants. Validation errors will be
converted into project-owned structured reports. Contract rules remain
independent of orchestration.

Great Expectations may be reconsidered only if later operational reporting or
multi-source requirements justify its additional concepts and runtime.

## Consequences

The initial validation surface is small and testable. Project-owned semantic
checks still require careful design. Changing validation libraries later must
preserve the data contract, not redefine it silently.

## Alternatives

- Great Expectations immediately: rejected as disproportionate for FD001.
- Ad hoc assertions only: rejected because schema intent and error reporting
  would be fragmented.

## Verification

Phase 1 will include schema, semantic, malformed-input, and contract-version
tests.
