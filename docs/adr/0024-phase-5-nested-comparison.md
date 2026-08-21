# ADR 0024: Nested engine comparison and locked known benchmark

## Status

Accepted

## Date

2026-08-21

## Context

Phase 5 compares model families on 100 C-MAPSS FD001 source-training engines.
Cycle rows from one engine are correlated, and the NASA test metrics were
already observed in Phase 4. Treating cycles as independent samples or calling
the NASA test a new blind holdout would overstate the evidence.

## Decision

Use five deterministic outer `GroupKFold` folds for model comparison and four
inner `GroupKFold` folds for tuning. Split only by engine. Bind the exact
engine membership, source identities, Phase 4 split identity, feature/target
contract, package versions, seed, and search version in a canonical SHA-256
comparison manifest.

The tuning boundary accepts source-training frames only and has no NASA test
fields. Every source-training row receives one outer out-of-fold prediction.
After development, write a canonical locked-selection record containing the
chosen family/configuration and all parent identities. Benchmark code rejects
an unlocked, tampered, stale, version-mismatched, or wrong-manifest record.

Call the NASA test partition a previously observed locked benchmark, not a
blind holdout. Fit the locked winner on all source-training engines and run the
benchmark in a separate function that cannot tune or change the selection.

## Consequences

Nested evaluation is materially slower than a single split but reduces
selection bias and engine leakage. The benchmark remains useful for comparable
FD001 research evidence but cannot support a claim of untouched final-test
performance. A future genuinely blind dataset needs a new versioned protocol.

## Alternatives

- Cycle-level random folds: rejected because they leak engine trajectories.
- Reuse only the Phase 4 80/20 split: rejected because it is weak evidence for
  choosing among advanced configurations.
- Treat NASA test as blind again: rejected because Phase 4 already reported it.
- Tune on NASA test: rejected as benchmark leakage.

## Verification

Unit tests prove canonical fold identity, full coverage, zero engine overlap,
row-order-independent membership, no benchmark fields in the tuning boundary,
selection tamper rejection, and comparison-manifest verification. Synthetic
and actual FD001 tests run development before the separate locked benchmark.
