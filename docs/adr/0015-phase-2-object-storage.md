# ADR 0015: Phase 2 object-storage layout and adapter

## Status

Accepted

## Date

2026-07-26

## Context

Phase 2 needs private storage for exact FD001 raw files and must reserve future
processed and feature locations without implementing Phase 3 transformations.
Supabase offers both its standard Storage API and an S3-compatible protocol,
but S3 versioning and object lock are not available.

## Decision

Use two configurable private buckets: one raw bucket and one derived bucket.
Phase 2 stores exact FD001 files and their canonical manifest in the raw
bucket. The derived bucket contains only isolated integration-test objects.
Production processed and feature objects remain Phase 3 work.

Use the standard Supabase Storage API as the Phase 2 cloud adapter. Explicitly
disable upsert. Bind raw file keys to the Phase 1 snapshot ID, file SHA-256,
and logical filename. Verify every accepted object by downloading and
rehashing it. The normal object interface exposes no update or delete method.

These controls are application-enforced overwrite denial, not WORM.

## Consequences

Raw and derived retention can evolve separately. Duplicate publication can
reuse identical objects safely. An administrator with a privileged Storage
credential can still overwrite or delete objects, so credential isolation and
separate backup remain required.

## Alternatives

- One bucket with all prefixes: rejected because raw and derived retention and
  cleanup have different risk.
- Supabase S3 protocol: deferred because Phase 2 needs no S3-only operation.
- Object lock or versioning claims: rejected because Storage does not provide
  them.

## Verification

Shared filesystem and Supabase adapter tests cover first upload, exact reuse,
different-byte conflict, concurrent publication, private buckets, downloaded
SHA-256 verification, and absence of update/delete operations.
