# ADR 0016: Private operational PostgreSQL and forward-only migrations

## Status

Accepted

## Date

2026-07-26

## Context

Dataset identity, object metadata, publication runs, and lineage need one
transactional owner. These internal records do not need browser or Data API
access. Supabase grants and RLS are separate controls, and its managed schemas
must not contain project-owned objects.

## Decision

Create only project-owned objects in the private `ops` schema. Connect directly
to PostgreSQL and immediately use the no-login
`predictive_maintenance_runtime` role through `SET ROLE`. Explicitly revoke
`PUBLIC`, `anon`, and `authenticated`; grant only required operations; and
enable role-specific RLS policies as defense in depth.

Keep `ops` outside the Data API schema list. Do not create custom objects in
`auth`, `storage`, or `realtime`. Store state values as checked text rather than
PostgreSQL enum types.

Use forward-only CLI-generated migrations. Verify clean application and
reset/reapplication against PostgreSQL 17. Do not describe a destructive reset
as a production down migration.

## Consequences

Application queries require direct database credentials and an explicit role
switch. Schema changes remain reviewable and repeatable. Local PostgreSQL tests
must bootstrap the standard Supabase roles before applying the same migration.

## Alternatives

- Public tables through the Data API: rejected as unnecessary exposure.
- An ORM-managed schema: rejected because the schema is small and SQL security
  behavior must remain visible.
- Hand-written down migrations: rejected because destructive rollback would
  provide misleading safety.

## Verification

Migration tests inspect schemas, constraints, indexes, policies, privileges,
role attributes, clean reapplication, and denial for `PUBLIC`, `anon`, and
`authenticated`.
