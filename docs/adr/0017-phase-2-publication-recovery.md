# ADR 0017: Staged publication, reconciliation, and separate recovery

## Status

Accepted

## Date

2026-07-26

## Context

Supabase Storage and PostgreSQL cannot participate in one atomic transaction.
An object upload can succeed before a database transaction fails. Database
backups also do not restore Storage object bytes.

## Decision

Use the accepted Phase 1 snapshot ID as the publication idempotency key.
Publish in this order:

1. detect an exact existing metadata record or a conflict;
1. upload or verify every content-addressed object without upsert;
1. download and verify its size and SHA-256;
1. commit all object, snapshot, file, lineage, and run metadata in one
   PostgreSQL transaction; and
1. reconcile metadata with object storage.

A database failure may leave verified orphan objects. Retry reuses matching
objects. Reconciliation reports orphaned, missing, and mismatched objects but
does not silently delete or repair them. A missing or mismatched referenced
object marks the snapshot inconsistent and blocks downstream use.

Back up PostgreSQL metadata and Storage bytes separately with a shared manifest
of identities and hashes.

## Consequences

The workflow converges after retry without pretending Storage and PostgreSQL
are atomic. Operators must understand and investigate reconciliation findings.
Recovery evidence needs both database and object restoration.

## Alternatives

- Delete uploaded objects after database failure: rejected because cleanup can
  race with another valid publisher and increases data-loss risk.
- Treat object upload as completion: rejected because lineage would be absent.
- Rely only on database backup: rejected because object bytes are separate.

## Verification

Tests inject storage-success/database-failure, retry, concurrent publication,
metadata conflict, tampering, missing objects, orphans, and a separate
metadata/object recovery exercise.
