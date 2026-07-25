# Architecture Decision Records

ADRs record decisions that constrain implementation across phases.

## Status values

- **Proposed:** awaiting a phase decision.
- **Accepted:** binding until superseded.
- **Deprecated:** retained for history but discouraged.
- **Superseded:** replaced by another ADR.

## Required sections

Each ADR contains Status, Date, Context, Decision, Consequences, Alternatives,
and Verification.

## Index

| ADR                                          | Decision                                  | Status   |
| -------------------------------------------- | ----------------------------------------- | -------- |
| [0001](0001-phase-governance.md)             | Phase governance and bootstrap            | Accepted |
| [0002](0002-claim-boundaries.md)             | Research terminology and claim boundaries | Accepted |
| [0003](0003-modular-monolith-local-first.md) | Modular monolith and local-first delivery | Accepted |
| [0004](0004-python-toolchain.md)             | Python toolchain and dependency locking   | Accepted |
| [0005](0005-data-validation.md)              | Pandera as initial contract library       | Accepted |
| [0006](0006-supabase-boundary.md)            | Supabase storage/database boundary        | Accepted |
| [0007](0007-mlflow-metadata.md)              | MLflow metadata ownership and topology    | Accepted |
| [0008](0008-airflow-orchestration.md)        | Airflow as deferred batch orchestrator    | Accepted |
| [0009](0009-ci-cd-and-approval.md)           | CI/CD and promotion separation            | Accepted |
| [0010](0010-agent-authority.md)              | Agent authority and audit boundary        | Accepted |
| [0011](0011-monitoring-retraining.md)        | Monitoring and retraining semantics       | Accepted |
| [0012](0012-digital-shadow.md)               | Digital-shadow state and replay semantics | Accepted |
| [0013](0013-fd001-raw-identity.md)           | FD001 raw identity and overwrite denial   | Accepted |
| [0014](0014-fd001-label-semantics.md)        | RUL and risk-label semantics              | Accepted |

New ADRs use the next four-digit identifier. Existing ADR content is not
rewritten to hide a changed decision; create a superseding ADR instead.
