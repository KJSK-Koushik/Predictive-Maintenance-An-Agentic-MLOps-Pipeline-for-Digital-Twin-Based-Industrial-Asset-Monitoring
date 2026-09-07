# ADR 0027: Atomic two-model release governance

## Status

Accepted

## Date

2026-08-22

## Context

Phase 5 selected separate RUL-regression and failure-risk-classification
models. MLflow can register each model independently, but the service must not
serve an unapproved or mismatched pair. Registration is also not a human
approval or a deployment record.

## Decision

Register the two task models separately in the database-backed local MLflow
registry. Combine their immutable version, run, artifact, signature, feature,
selection, code, and dependency identities in one canonical release manifest.
The release ID is the SHA-256 of that manifest.

Operational PostgreSQL owns append-only candidate, human-decision, deployment,
and rollback evidence. A deterministic approval-request ID is included in the
manifest before the release ID is calculated. The later human decision
references both IDs; this avoids a circular hash. The decision itself is not
silently inserted into already-hashed manifest bytes.

Candidate registration creates no alias. Packaging and the two `staging`
alias changes require one current approval for the exact release. No
`production` alias or deployment target exists.

## Consequences

The serving image contains one fixed pair and does not resolve mutable aliases
per request. MLflow and operational PostgreSQL have distinct ownership, so
backup and reconciliation must cover both. One-person research governance is
auditable but is not organizational separation of duties.

## Alternatives

- Use one multi-output model: rejected because it was not the Phase 5 result.
- Treat registration as approval: rejected because registry writes are not
  safety or deployment decisions.
- Hash a later random approval event inside the manifest: rejected because it
  creates a circular release identity.
- Store all operational events in MLflow tags: rejected because tags are not
  the operational authority.

## Verification

Unit tests cover canonical identity changes, exact approval, expiry, rejection,
tamper denial, and packaging reuse. Real local MLflow tests cover candidate
versions, missing aliases before approval, exact staging aliases, and explicit
production denial. PostgreSQL 17 tests cover constraints, RLS, least grants,
idempotent decisions, and append-only deployment events.
