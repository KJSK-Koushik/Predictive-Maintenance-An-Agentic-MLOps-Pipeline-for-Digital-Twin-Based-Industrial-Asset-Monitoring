# Project Charter

## Identity

**Title:** Towards Autonomous Predictive Maintenance: An Agentic MLOps Pipeline
for Digital Twin-Based Industrial Asset Monitoring

**Delivery framing:** A human-governed, agent-assisted MLOps research prototype
for cycle-level asset-health monitoring using simulated NASA C-MAPSS telemetry.

**Repository independence:** This repository is independent. It must not read
from, copy from, modify, import, or create a dependency on the separate
ML-Agent-Factory repository without explicit future authorization.

## Problem statement

Predictive-maintenance research often evaluates model accuracy in isolation.
This project instead evaluates whether a complete, reproducible MLOps lifecycle
can turn simulated run-to-failure telemetry into governed asset-health evidence,
while using AI agents only where recommendations can be independently checked.

## Research questions

1. Can a reproducible, leakage-safe pipeline support RUL regression,
   horizon-based failure-risk classification, and exploratory health-state
   analysis on C-MAPSS FD001?
1. What operational evidence is required to move a model from experiment to a
   rollback-capable staging service?
1. Can bounded agents improve investigation or recommendation effort without
   weakening deterministic validation, human approval, or auditability?
1. How does the agent-assisted workflow compare with the same workflow without
   agents in quality, time, reliability, and operator effort?

## Scope

### In scope

- NASA C-MAPSS FD001 as the initial dataset.
- Checksum-addressed raw data and versioned derived artifacts.
- Schema, semantic, and lineage validation.
- RUL regression and derived failure-risk classification.
- Exploratory clustering and anomaly detection in a later phase.
- Leakage-safe engine-level model evaluation.
- MLflow tracking and model-registry workflows.
- Gated FastAPI model serving with containerized local/staging validation.
- Batch monitoring, drift investigation, and retraining candidate generation.
- A cycle-level asset-health digital-shadow state.
- Bounded, audited agent recommendations.
- GitHub Actions CI and separately approved deployment.

### Out of scope

- Safety-critical control or automatic execution of maintenance work.
- A validated bidirectional physical twin.
- Hard real-time or streaming guarantees.
- Automatic model promotion or production deployment.
- Online learning or unattended continuous retraining.
- Production claims based only on synthetic telemetry.
- Kafka, Kubernetes, a feature-store product, or a microservice decomposition
  without a measured need.
- Paid cloud provisioning without explicit approval.

## Terminology and claim boundaries

### Digital twin

The first implementation is a **digital-twin-inspired asset-health digital
shadow**: a versioned software state derived from telemetry and model outputs.
It is not bidirectionally connected to a physical engine and does not establish
physics-calibrated twin fidelity.

### Real-time

The project uses offline processing and cycle-level replay. Any later
"near-real-time" claim requires a measured latency objective and an exercised
live ingestion path. No hard real-time claim is permitted.

### Autonomous

"Towards Autonomous" describes a research direction. The delivered controls
remain human-governed. Agents can inspect approved evidence and draft
recommendations; they cannot waive checks, approve models, deploy releases, or
execute maintenance.

### Continuous retraining

The supported pattern is **monitor-triggered retraining evaluation**. A trigger
may request a candidate run. Promotion still requires deterministic data,
performance, security, and human-approval gates.

Failure risk is a derived label based on an approved RUL horizon, not an
independently observed failure event.

## Functional requirements

| ID     | Requirement                                                           |
| ------ | --------------------------------------------------------------------- |
| FR-001 | Ingest an explicitly identified FD001 source and verify its checksum. |
| FR-002 | Reject data that violates the approved schema or semantic contract.   |
| FR-003 | Produce versioned processed data and feature snapshots reproducibly.  |
| FR-004 | Define RUL and failure-risk labels with tested, documented semantics. |
| FR-005 | Train and evaluate models without engine or temporal leakage.         |
| FR-006 | Track experiment inputs, code, parameters, metrics, and artifacts.    |
| FR-007 | Promote only models satisfying deterministic criteria and approval.   |
| FR-008 | Serve a versioned inference contract with provenance and uncertainty. |
| FR-009 | Monitor data, predictions, service behavior, and delayed performance. |
| FR-010 | Create retraining candidates without automatic production promotion.  |
| FR-011 | Represent each replayed asset's current health state and provenance.  |
| FR-012 | Audit every agent input, tool call, recommendation, and disposition.  |
| FR-013 | Compare agent-assisted work against a non-agentic baseline.           |

## Non-functional requirements

| ID      | Requirement                                                              |
| ------- | ------------------------------------------------------------------------ |
| NFR-001 | Reproducibility: pinned dependencies, immutable inputs, and seeded runs. |
| NFR-002 | Security: least privilege, secret isolation, and no credentials in Git.  |
| NFR-003 | Reliability: idempotency, retry boundaries, failure evidence, rollback.  |
| NFR-004 | Testability: core logic independent of orchestration and cloud SDKs.     |
| NFR-005 | Auditability: lineage across data, code, model, deployment, and agents.  |
| NFR-006 | Portability: documented local development with container validation.     |
| NFR-007 | Maintainability: modular monolith and explicit component ownership.      |
| NFR-008 | Honesty: mocked, emulated, and real integrations reported separately.    |
| NFR-009 | Cost control: no paid resource provisioning without approval.            |
| NFR-010 | Governance: exactly one active phase and explicit phase transitions.     |

## Stakeholders and authority

| Role                        | Authority                                                      |
| --------------------------- | -------------------------------------------------------------- |
| Project owner               | Scope, phase start/approval, cloud spend, production decisions |
| Principal MLOps engineer    | Implementation, evidence, risk escalation, documentation       |
| Model approver              | Model promotion decision based on deterministic evidence       |
| Deployment approver         | Production deployment and rollback authorization               |
| Maintenance domain reviewer | Interpretation of maintenance recommendations                  |
| Agent                       | Recommendation only; no approval authority                     |

One person may hold multiple human roles, but approval events remain explicit
and auditable.

## Success measures

- Every phase meets its recorded acceptance criteria and evidence requirements.
- Data and model results are reproducible from immutable inputs.
- Baselines and advanced approaches use identical leakage-safe evaluation.
- Rollback and failure behavior are demonstrated rather than asserted.
- Agent-assisted comparisons use predeclared tasks and non-agentic controls.
- Research claims distinguish simulation, replay, staging, and production.
- No critical or high-severity issue is unresolved at phase completion.

## Constraints and assumptions

- C-MAPSS is simulated telemetry and is not evidence of field performance.
- Failure-risk labels are derived from RUL horizons, not observed event classes.
- C-MAPSS does not provide maintenance interventions or maintenance costs.
- Supabase, MLflow, Airflow, and agents are introduced only in their phases.
- GitHub Actions evidence requires an accessible GitHub remote.
- Project source and documentation are licensed under Apache-2.0.

## Governance

The roadmap, status document, ADRs, phase plan, acceptance criteria, test plan,
and completion report form the controlled record. If documents conflict,
`PROJECT_STATUS.md` controls the current phase, accepted ADRs control technical
decisions, and the current phase acceptance criteria control completion.
