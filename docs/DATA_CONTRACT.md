# Data Contract

## Status

**Phase 1 planning specification.** The executable FD001 contract, source
checksums, verified columns, validation results, labels, and exploration
evidence require `START PHASE 1`. This document does not claim that the
user-provided data has been parsed or validated.

## Purpose

The data contract will define the boundary between an identified C-MAPSS source
artifact and every processed dataset, feature snapshot, model run, prediction,
and monitoring report derived from it.

## Contract identity

Each accepted dataset snapshot will eventually record:

- dataset family and subset;
- authoritative source and retrieval date;
- original filenames and byte sizes;
- SHA-256 digest for each source file;
- contract version;
- parser version and code revision;
- validation status and report reference; and
- immutable snapshot identifier.

The digest, not a mutable filename, identifies raw content.

## Planned FD001 structural contract

Phase 1 must verify rather than assume:

- the required train, test, and test-RUL files;
- whitespace parsing behavior and absence/presence of trailing columns;
- engine identifier and cycle domains;
- operating-setting and sensor column count/order;
- numeric types, finite values, missingness, and duplicates;
- per-engine cycle ordering and uniqueness; and
- correspondence between test engines and supplied terminal RUL values.

Column names and types will be added only after source verification.

## Planned semantic invariants

- engine identifiers are positive integers;
- cycles are positive and unique within an engine;
- cycles are monotonic after deterministic ordering;
- sensor and setting values are finite;
- train trajectories reach the supplied run-to-failure endpoint semantics;
- test RUL has exactly one value per test engine;
- no engine appears in more than one model partition; and
- transformations do not infer a new raw value silently.

Ranges learned from this finite dataset are monitoring references, not universal
physical limits.

## Labels

### RUL regression

The uncapped target is canonical. A capped target, if later justified, is a
separate configured derivation with a versioned cap and rationale; it may not
silently replace uncapped RUL. Training and evaluation targets must not be
inferred using information unavailable at the prediction cycle.

### Failure-risk classification

Failure risk will be derived from a declared RUL horizon. Phase 1 uses 30 cycles
as the primary classification horizon and reports 15- and 45-cycle sensitivity:

```text
failure_risk_30 = 1 when RUL <= 30, otherwise 0
```

This is a derived label, not an independently observed failure event.

### Health state and anomaly

Unsupervised outputs are model-dependent analytical results, not ground-truth
labels. Cluster numbers must not be assigned physical meanings without
supporting evidence.

## Snapshot and lineage rules

- Raw files are never modified in place.
- Processed and feature outputs are written to new versioned paths.
- Every derived artifact references all direct parents.
- A contract failure prevents publication into an accepted zone.
- Quarantined artifacts remain distinguishable from accepted artifacts.
- Re-running identical code/configuration over identical parents should produce
  the same content digest, subject to documented deterministic-format rules.

## Split contract

Model splits are engine-disjoint. Any temporal validation within an engine must
still prevent future-cycle information from entering features or preprocessing.
Scaling, selection, imputation, and tuning fit on training data only.

## Privacy and sensitivity

C-MAPSS is simulated telemetry and is not expected to contain personal data.
Credentials, filesystem usernames, signed URLs, and private service identifiers
must not be attached to dataset metadata.

## Phase 1 completion additions

Phase 1 must add:

- verified source citation and checksums;
- exact columns, types, order, and nullability;
- executable Pandera schema;
- all semantic checks and failure behavior;
- label parameters and boundary examples;
- exploration findings and constant/low-information sensors;
- fixture definitions; and
- validation evidence for the actual FD001 files.
