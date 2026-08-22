# Project Roadmap

## Governance

Only one phase may be active. Planning a future phase requires approval of the
current phase followed by `PLAN PHASE <number>`. Implementation requires
`START PHASE <number>`.

Every phase directory contains an architecture, plan, acceptance criteria, test
plan, and completion report. A phase remains incomplete until local validation,
remote CI, documentation, evidence, and severity requirements are satisfied.

## Phase sequence

| Phase | Outcome                                                          | Entry dependency    | Explicit exclusions                           |
| ----- | ---------------------------------------------------------------- | ------------------- | --------------------------------------------- |
| 0     | Charter, architecture, decisions, threat model, CI foundation    | Owner start command | Feature code, data processing, cloud services |
| 1     | Local FD001 integrity, ingestion, contract, labels, exploration  | Approved Phase 0    | Supabase, Airflow, model training             |
| 2     | Cloud object zones, PostgreSQL migrations, lineage, idempotency  | Approved Phase 1    | ETL scheduling, model training                |
| 3     | Reproducible ETL wrapped by Airflow                              | Approved Phase 2    | Model development                             |
| 4     | Leakage-safe fixed baselines and local MLflow tracking           | Approved Phase 3    | Tuning, registry, serving, deployment         |
| 5     | Justified tuning, uncertainty, clustering, anomaly analysis      | Approved Phase 4    | Serving and production promotion              |
| 6     | Registry, API, staging rollback, and early UI design             | Approved Phase 5    | Frontend code or automatic production deploy  |
| 7     | Monitoring, retraining candidates, and stable monitor contracts  | Approved Phase 6    | Automatic promotion or frontend code          |
| 8     | Bounded agents, comparison, and stable recommendation contracts  | Approved Phase 7    | Approval authority or frontend code           |
| 9     | Incrementally connected asset-health dashboard and optional auth | Approved Phase 8    | Physical-twin or hard-real-time claims        |
| 10    | End-to-end evaluation, recovery demos, audits, final package     | Approved Phase 9    | Unvalidated scope expansion                   |

## Cross-phase quality-gate growth

| Gate                      | 0                    | 1-3                   | 4-5            | 6-7                | 8-10            |
| ------------------------- | -------------------- | --------------------- | -------------- | ------------------ | --------------- |
| Formatting/linting/typing | Foundation           | Required              | Required       | Required           | Required        |
| Unit tests                | Repository contracts | Data/ETL              | Model logic    | Service/monitoring | Agent/dashboard |
| Integration tests         | CI/config contracts  | Storage/database/ETL  | MLflow         | API/deployment     | End to end      |
| Coverage threshold        | Not meaningful       | Introduced            | Enforced       | Enforced           | Enforced        |
| Data-contract tests       | Design only          | Enforced              | Enforced       | Enforced           | Enforced        |
| Migration validation      | Not applicable       | Phase 2 onward        | Enforced       | Enforced           | Enforced        |
| Dependency/security scan  | Required             | Required              | Required       | Required           | Required        |
| Container smoke test      | Not applicable       | Airflow as applicable | As applicable  | Enforced           | Enforced        |
| Model performance gate    | Not applicable       | Not applicable        | Introduced     | Enforced           | Enforced        |
| Deployment smoke test     | Not applicable       | Not applicable        | Not applicable | Enforced           | Enforced        |
| Agent permission tests    | Not applicable       | Not applicable        | Not applicable | Not applicable     | Phase 8 onward  |

## Research-evaluation milestones

- Phase 1 establishes what the data can and cannot support.
- Phase 4 establishes non-agentic predictive baselines.
- Phase 4 uses one engine-disjoint split, fixed Ridge and logistic candidates,
  dummy-relative eligibility gates, and local MLflow. It is complete and
  owner-approved.
- Phase 5 determined whether bounded nonlinear complexity added measurable
  value. It selected histogram gradient boosting for RUL and retained logistic
  regression for failure risk.
- Phase 5 calls unsupervised outputs exploratory telemetry states and novelty
  scores because FD001 has no ground-truth health-state or anomaly labels.
- Phase 6 packages those two selected task models into one immutable,
  human-approved staging release. Local or ephemeral staging is not production.
- Phase 6 also establishes technology-neutral screen designs. It adds no
  frontend framework or working dashboard.
- Phase 7 is planned to establish a conventional monitored MLOps workflow over
  immutable FD001 cycle replay. It separates quality, distribution shift,
  service probes, and delayed performance; triggers create candidate requests,
  never automatic promotion.
- Phase 8 compares agents with that fixed conventional baseline.
- Phase 9 implements and connects one screen at a time, only after that screen's
  versioned backend contracts have passed their owning phases.
- Phase 10 reports exercised capabilities and avoids generalizing beyond FD001.

## UI delivery sequence

The source-of-truth screen designs and contract maturity rules are in
[`UI_ARCHITECTURE.md`](UI_ARCHITECTURE.md).

| Stage             | Meaning                                                              | Owning phases |
| ----------------- | -------------------------------------------------------------------- | ------------- |
| Design early      | Screen purpose, layout, states, wording, and dependencies exist      | 6             |
| Stabilize APIs    | Versioned backend contracts pass deterministic and integration tests | 6-8           |
| Build later       | The frontend shell and components are implemented                    | 9             |
| Connect safely    | Each screen is connected only to stable contracts                    | 9             |
| Verify end to end | Browser success, failure, security, and accessibility paths pass     | 9-10          |

## Deferred decisions

The following require evidence from earlier phases:

- whether a versioned capped RUL target is worth a separate later experiment;
- absolute promotion-level model-performance thresholds;
- whether any later dataset provides independent supervision that could
  justify a neural multi-task model;
- whether Evidently adds value beyond custom metrics;
- remote MLflow topology;
- staging and production hosting targets;
- dashboard authentication;
- LLM provider and model;
- latency and reliability objectives; and
- whether additional C-MAPSS subsets are academically useful.
