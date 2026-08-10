# ADR 0019: Content-addressed derived publication and lineage

## Status

Accepted

## Date

2026-08-09

## Context

Processed, feature, target, manifest, and quality objects must be reproducible
and traceable to the accepted raw snapshot. Object Storage and PostgreSQL still
cannot share one transaction.

## Decision

Derive each snapshot ID from a canonical manifest containing its raw source,
derived parent, contract, transformation, serializer, code revision, ordered
file hashes, sizes, schemas, and column roles. Airflow logical dates and run
IDs are excluded. Store bytes under content-addressed private derived keys with
put-if-absent and downloaded verification.

Add private `ops.derived_snapshots`, `ops.derived_snapshot_files`, and
`ops.transformation_runs` tables through one forward-only migration. Reuse
`ops.data_objects` and `ops.lineage_edges` as the object and lineage
authorities. Upload all objects first, then commit the three derived snapshots,
their files, object-level lineage, and completed transformation run in one
PostgreSQL transaction. Retry reuses matching orphans; reconciliation reports
but never silently deletes or repairs them.

## Consequences

Storage success followed by database failure converges safely. Metadata and
object bytes still require separate backup and restore. A code-revision change
creates new derived identities even when table bytes remain the same, making
the producing code explicit provenance.

## Alternatives

- Mutable keys with overwrite: rejected because rerun conflicts would be
  hidden.
- Delete objects after database failure: rejected because cleanup can race
  with another valid run.
- Store row-level telemetry in PostgreSQL: rejected because object artifacts
  are the approved data plane and operational tables own metadata only.

## Verification

Unit and PostgreSQL tests cover exact reuse, different-metadata conflict,
partial failure and retry, raw-to-processed and processed-to-feature lineage,
report edges, constraints, grants, RLS, missing objects, mismatch blocking,
orphans, and recovery.
