# ADR-0007: MLflow Metadata Ownership and Topology

## Status

Accepted

## Date

2026-07-23

## Context

MLflow tracking and registry overlap superficially with operational metadata.
Duplicating experiments and model-version records would create inconsistent
authorities. A shared registry requires a database-backed store and controlled
artifact access.

## Decision

MLflow owns experiments, runs, parameters, metrics, run artifacts, registered
models, versions, aliases, and model signatures. Operational PostgreSQL owns
pipeline lineage, approval decisions, deployments, asset state, monitoring
windows, and agent audits, referencing MLflow identifiers where needed.

Phase 4 starts with a local database-backed MLflow setup. A remote topology is
adopted only after its database, artifact store, authentication, backup, and
network controls are verified. MLflow tables must not share the operational
application schema.

## Consequences

Approval evidence may snapshot selected immutable metrics while preserving the
MLflow reference. A remote tracking server becomes a privileged service and
requires access controls.

## Alternatives

- Store all experiment metadata in custom tables: rejected as duplicating
  MLflow.
- Put operational state inside MLflow tags: rejected because MLflow is not the
  application system of record.

## Verification

Later integration tests confirm cross-system identifiers, artifact retrieval,
registry transitions, and backup/restore behavior.
