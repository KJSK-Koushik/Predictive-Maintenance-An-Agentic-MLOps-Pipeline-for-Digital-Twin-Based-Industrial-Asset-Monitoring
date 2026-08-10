# ADR 0018: Deterministic Parquet and separated candidate features

## Status

Accepted

## Date

2026-08-09

## Context

Phase 3 must convert validated FD001 rows into typed derived artifacts without
changing the Phase 1 label meaning or fitting transformations before an
engine-disjoint model split exists. Artifact hashes also need repeatable writer
behavior.

## Decision

Pin PyArrow 25.0.0 and write single-file Parquet with explicit Arrow types,
ordered columns, no stored DataFrame index, Zstandard level 3, disabled
dictionary encoding, fixed row-group size, Parquet 2.6, and fixed statistics
and data-page options. Canonical JSON uses sorted keys, compact separators,
ASCII output, finite values, and one trailing newline.

`fd001-processed-v1` preserves source row order and contains the 26 telemetry
columns plus uncapped `rul` and inclusive `failure_risk_30`.
`fd001-candidate-features-v1` stores keys and the 24 settings/sensors separately
from key-aligned target files. It fits no scaler, imputer, selector, PCA,
rolling statistic, target cap, or model-informed feature.

## Consequences

Repeated writes in the locked environment are byte-identical and target
leakage is structurally visible. A PyArrow upgrade is a serializer-version
change and requires new reproducibility evidence. Split-fitted preprocessing
remains Phase 4 work.

## Alternatives

- CSV: rejected because it weakens exact dtype preservation.
- Pickle or joblib: rejected because untrusted deserialization can execute
  code.
- Fitted or rolling features in Phase 3: rejected because leakage-safe model
  partitions and performance evidence do not exist yet.

## Verification

Pure tests compare two clean output trees byte for byte, read every Parquet
file, assert exact schema/order/dtypes, and prove targets never appear in
candidate-feature columns.
