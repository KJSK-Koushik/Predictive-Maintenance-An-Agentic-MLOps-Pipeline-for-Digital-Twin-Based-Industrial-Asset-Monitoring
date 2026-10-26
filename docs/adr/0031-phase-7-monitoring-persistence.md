# ADR 0031: Private immutable monitoring persistence

## Status

Accepted

## Date

2026-09-07

## Context

Monitoring evidence must survive retries and delayed labels without allowing
silent overwrite, public access, or complete telemetry dumps in operational
tables. Object publication and metadata insertion can fail independently.

## Decision

Store bounded canonical JSON under private, content-addressed derived-bucket
keys and store only identifiers, statuses, lineage, and verified object
references in private `ops` tables. Use put-if-absent, byte/hash verification,
exact-reuse checks, and conflict rejection. A delayed-label attachment creates
a child report referencing the immutable prediction report; it never updates
the original.

The Phase 7 migration is forward-only, changes only private `ops` objects,
enables RLS, denies `PUBLIC`, `anon`, and `authenticated`, and grants the
runtime role only `SELECT` and `INSERT`. Object and database recovery remain
separate and reconciliation reports gaps without silently deleting evidence.

## Consequences

Retries can converge after either object or metadata failure. Append-only
evidence uses more objects and rows, but auditability and deterministic
recovery are clearer. Full telemetry, complete predictions, credentials,
private endpoints, and absolute workstation paths are excluded from reports.

## Alternatives

- Mutable latest-report rows: rejected because they destroy audit history.
- PostgreSQL binary report payloads: rejected because Storage is the governed
  artifact plane and PostgreSQL is the operational metadata plane.
- Public tables or browser access: rejected because the UI read contract is a
  later phase.
- Delete orphan objects automatically: rejected because repair requires an
  explicit, reviewed decision.

## Verification

Filesystem conflict/retry tests, PostgreSQL clean/reapply/restore tests,
hosted object rehashing, RLS/grant checks, client-role denial, migration
history, and Supabase advisor results provide the evidence.
