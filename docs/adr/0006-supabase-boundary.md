# ADR-0006: Supabase Storage and PostgreSQL Boundary

## Status

Accepted

## Date

2026-07-23

## Context

Supabase is proposed for object storage and operational PostgreSQL. Its Storage
service supports an S3-compatible subset but not S3 versioning or object lock.
Server-side S3 credentials bypass RLS. Exposed database objects require both
grants and RLS.

## Decision

Supabase is introduced in Phase 2 behind project-owned object and metadata
interfaces. Private file buckets hold logical raw, processed, feature, model,
and report zones. Raw immutability is enforced through SHA-256-addressed object
names, denied upserts, manifests, and deletion governance; it is not called
WORM.

Operational tables use private schemas. The Data API is disabled unless a later
client needs it. An exposed `api` schema uses explicit grants and RLS. Secret,
service-role, database, and S3 credentials remain server-side. Object bytes
receive a separate backup plan.

## Consequences

S3 client compatibility must be verified against the operations actually used.
Cloud integration tests are distinct from local substitutes. Supabase is not
treated as a feature store or lakehouse by default.

## Alternatives

- Direct cloud SDK calls throughout domain code: rejected due lock-in and weak
  testability.
- Public-schema tables with broad grants: rejected due unnecessary exposure.
- Claim Storage versioning/locking: rejected because those features are absent.

## Verification

Phase 2 tests exercise overwrite denial, idempotency, grants, RLS, lineage,
backup procedure evidence, and a real approved cloud namespace.
