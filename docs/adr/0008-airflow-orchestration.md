# ADR-0008: Airflow as a Deferred Batch Orchestrator

## Status

Accepted

## Date

2026-07-23

## Context

Airflow is appropriate for scheduled, finite batch workflows but adds a
scheduler, API server, metadata database, and deployment concerns. Embedding
business logic directly in DAG files would make local testing harder.

## Decision

Phases 1 and 2 expose pipeline behavior through ordinary Python functions and
CLI entry points. Phase 3 wraps those functions in thin Airflow DAGs. DAGs
define schedules, dependencies, retry policy, timeouts, and observability; they
do not own parsing, validation, feature, or lineage logic.

Airflow is not used as a streaming system or as an inference request path.

## Consequences

ETL can be tested without starting Airflow. Phase 3 must still test DAG import,
backfill, idempotency, and failure semantics. Airflow version changes remain
isolated from domain functions.

## Alternatives

- Introduce Airflow in Phase 1: rejected because it would obscure basic
  ingestion behavior.
- Use Airflow for real-time inference: rejected because it is batch-oriented.
- Build a custom scheduler: rejected as undifferentiated infrastructure.

## Verification

Phase 3 compares direct-function and DAG-triggered outputs for identical inputs.
