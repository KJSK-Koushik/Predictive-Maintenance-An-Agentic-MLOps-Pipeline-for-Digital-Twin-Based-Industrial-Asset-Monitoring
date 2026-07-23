# ADR-0009: CI, Deployment, and Model Promotion Separation

## Status

Accepted

## Date

2026-07-23

## Context

Passing code tests does not validate a model for production. Combining pull
request CI with deployment or model promotion would grant excessive authority
to routine code changes.

## Decision

Pull-request CI performs formatting, linting, typing, tests, contract checks,
dependency/security scanning, and phase-appropriate build validation. It has
read-only repository permissions and no production credentials.

Deployment is a separate workflow using protected environments and explicit
human approval. Model promotion is a separate domain decision backed by
evaluation evidence. Production deployment requires both an approved model
release and an approved deployment.

Actions are pinned to immutable commits, dependencies are locked, and required
checks block merging.

## Consequences

More than one approval may be required. A GitHub remote and branch-protection
configuration are external prerequisites. Local success cannot prove CI
success.

## Alternatives

- Deploy on merge: rejected because code validity is not model validity.
- Let MLflow alias changes trigger production automatically: rejected because
  aliases can be changed independently of deployment evidence.

## Verification

Repository integration tests reject deployment commands in the CI workflow.
Later phases test protected deployment and rollback workflows.
