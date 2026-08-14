# ADR 0021: One engine-disjoint split and fixed final holdout

## Status

Accepted

## Date

2026-08-14

## Context

FD001 contains many cycle rows for each engine. A row-level random split would
place cycles from the same simulated engine in training and evaluation and
would therefore leak engine-specific trajectory information. NASA train and
test partitions also reuse numeric engine IDs.

## Decision

Use the NASA train partition only for development. Sort its engine IDs, then
apply `GroupShuffleSplit(test_size=0.2, random_state=42)` once to create 80
training engines and 20 validation engines for actual FD001. Keep the NASA
test partition as the untouched final holdout. Treat `(source_partition, engine_id)` as the engine identity.

Create one canonical `fd001-engine-split-v1` manifest shared by regression and
classification. It binds raw, processed, and feature snapshot IDs; engine
lists; row counts; class prevalence; feature and target order; library
versions; and the seed. Its SHA-256 is the split identity. No final-test result
may change features, model settings, class weights, threshold, or eligibility.

## Consequences

The two tasks are directly comparable and no engine crosses development
partitions. The split is a single seeded holdout, not cross-validation, so its
sampling variability must be considered during later Phase 5 comparison.
Overlapping numeric IDs in source train and source test remain distinct.

## Alternatives

- Row-level random split: rejected because it leaks engine trajectories.
- Randomly split both NASA partitions: rejected because it destroys the
  published final-holdout role.
- Hyperparameter cross-validation: deferred to Phase 5 because Phase 4 fixes
  one reproducible baseline protocol.

## Verification

Unit tests prove 80/20 engine membership, zero overlap, complete row coverage,
row-order independence, source-partition separation, canonical manifest bytes,
and identical split use by both tasks. The actual FD001 test verifies 100
source-train engines and 100 source-test engines.
