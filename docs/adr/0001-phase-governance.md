# ADR-0001: Phase Governance and Bootstrap

## Status

Accepted

## Date

2026-07-23

## Context

The project spans data, cloud, modeling, deployment, monitoring, agents, and a
dashboard. Uncontrolled cross-phase implementation would make evidence and
claims difficult to audit. The initially empty repository could not identify
its current phase from a status document.

## Decision

Exactly one phase may be active. Planning, starting, completing, and approving a
phase are separate transitions controlled by explicit owner commands.
`docs/PROJECT_STATUS.md` is authoritative after bootstrap. The owner's initial
assignment plus `START PHASE 0` is the one-time bootstrap authority to create
the source-of-truth documents.

A phase cannot be marked complete until every acceptance criterion, local
check, applicable integration, remote CI check, documentation update, evidence
record, and severity requirement is satisfied.

## Consequences

Work may pause on external evidence such as GitHub Actions. Convenient later
work is deliberately deferred. Status transitions remain visible.

## Alternatives

- Implement an end-to-end prototype first: rejected because validation and
  governance would be retrofitted.
- Allow overlapping phases: rejected because ownership and evidence blur.

## Verification

Repository contract tests validate the current phase, required phase files, and
status vocabulary.
