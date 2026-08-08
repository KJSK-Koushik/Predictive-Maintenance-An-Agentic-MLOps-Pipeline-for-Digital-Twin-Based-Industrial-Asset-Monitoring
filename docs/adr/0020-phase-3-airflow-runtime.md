# ADR 0020: Thin Airflow LocalExecutor runtime for static batch evidence

## Status

Accepted

## Date

2026-08-09

## Context

Phase 3 needs scheduled execution, bounded retry, failure, and backfill
evidence. The repository does not need a distributed worker fleet, and FD001
contains static simulated cycles rather than timestamped incoming telemetry.

## Decision

Extend the official Apache Airflow 3.3.0 Python 3.11 image pinned by digest.
Use `LocalExecutor`, at most two local tasks, one active DAG run, and an
Airflow-owned database/user separate from the application database. Bind the
development API/UI only to loopback. Do not add Celery, Redis, Kubernetes,
Helm, or a managed service.

The `fd001_derived_pipeline` DAG declares four stable tasks, a daily schedule,
`catchup=False`, bounded exponential retry, and execution timeouts. It calls
the same application service as the direct CLI. DAG parsing performs no
network, database, Storage, or generated-file operation. XCom contains only
SHA-256 snapshot identifiers and a boolean reuse status.

Airflow logical dates are execution metadata and do not enter artifact
identity. Backfill over the same explicit immutable FD001 snapshot creates
separate Airflow runs but reuses one derived artifact set.

## Consequences

The application publishes processed, feature, report, and lineage metadata as
one idempotent unit. The `publish_processed` Airflow task calls that complete
service; later named tasks are identifier-only verification checkpoints. This
is intentional because splitting the application transaction across task-local
files would weaken retry and recovery behavior.

Business logic remains testable without Airflow. The local Compose topology is
development/integration evidence and supplies no production security or
availability claim. The daily schedule demonstrates orchestration, not new
daily telemetry or real-time processing.

## Alternatives

- CeleryExecutor and Redis: rejected as unnecessary distributed complexity.
- SQLite with SequentialExecutor: rejected because retry/concurrency evidence
  and metadata isolation need the declared PostgreSQL/LocalExecutor topology.
- Put ETL logic in the DAG file: rejected because it would couple validation
  and identity to the orchestrator.

## Verification

Static tests inspect the digest, dependencies, topology, task graph, schedule,
timeouts, and identifier-only contract. Container checks build the image,
start the runtime, inspect configuration, import the DAG, execute it, inject a
retryable failure, and run a bounded two-date backfill.
