# ADR 0013: FD001 raw identity and local overwrite denial

## Status

Accepted

## Date

2026-07-25

## Context

Phase 1 needs reproducible provenance for an extracted local FD001 copy. No
publisher-provided archive checksum or original ZIP is available, and Git must
not track raw data. A mutable filename alone is not enough to identify input
bytes.

## Decision

Identify the four required logical files by byte size and SHA-256. Derive one
source-set snapshot ID from the ordered file identities, contract version,
parser version, citation, and source URL. Copy exact bytes into a local ignored
snapshot with exclusive creation, post-copy verification, canonical metadata,
and verified idempotent reuse. Record the code revision that first created the
snapshot without making later code revisions duplicate identical raw bytes.

Call this application-enforced overwrite denial, not WORM storage.

## Consequences

Input identity is reproducible and tampering is detected. Generated snapshots
remain local and can still be deleted by a user with filesystem access. Byte
identity with the unavailable original archive cannot be claimed.

## Alternatives

- Commit raw files to Git: rejected because raw data is an external artifact.
- Trust filenames and modification times: rejected because they do not identify
  bytes.
- Require cloud object lock in Phase 1: rejected as unnecessary cloud scope.
- Include every code commit in raw identity: rejected because unchanged raw
  bytes should remain reusable while parser behavior is versioned separately.

## Verification

Integrity tests cover known hashes, exact-byte copies, changed inputs,
deterministic manifests, reuse, missing files, and destination or manifest
tampering. The local-real-data run records all four file digests.
