# Project Roadmap

## Governance

Only one phase may be active. Planning a future phase requires approval of the
current phase followed by `PLAN PHASE <number>`. Implementation requires
`START PHASE <number>`.

Every phase directory contains an architecture, plan, acceptance criteria, test
plan, and completion report. A phase remains incomplete until local validation,
remote CI, documentation, evidence, and severity requirements are satisfied.

## Phase sequence

| Phase | Outcome                                                         | Entry dependency    | Explicit exclusions                           |
| ----- | --------------------------------------------------------------- | ------------------- | --------------------------------------------- |
| 0     | Charter, architecture, decisions, threat model, CI foundation   | Owner start command | Feature code, data processing, cloud services |
| 1     | Local FD001 integrity, ingestion, contract, labels, exploration | Approved Phase 0    | Supabase, Airflow, model training             |
| 2     | Cloud object zones, PostgreSQL migrations, lineage, idempotency | Approved Phase 1    | ETL scheduling, model training                |
| 3     | Reproducible ETL wrapped by Airflow                             | Approved Phase 2    | Model development                             |
| 4     | Leakage-safe regression/classification baselines and MLflow     | Approved Phase 3    | Deep learning, deployment                     |
| 5     | Justified tuning, uncertainty, clustering, anomaly analysis     | Approved Phase 4    | Serving and production promotion              |
| 6     | Registry gates, release packaging, FastAPI, staging rollback    | Approved Phase 5    | Automatic production deployment               |
| 7     | Data/model/service monitoring and retraining candidates         | Approved Phase 6    | Automatic promotion                           |
| 8     | Bounded agents and non-agentic comparison                       | Approved Phase 7    | Approval or maintenance authority             |
| 9     | Asset-health dashboard and optional authentication              | Approved Phase 8    | Claims of physical twin or hard real time     |
| 10    | End-to-end evaluation, recovery demos, audits, final package    | Approved Phase 9    | Unvalidated scope expansion                   |

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
- Phase 5 determines whether complexity adds measurable value.
- Phase 7 establishes a conventional monitored MLOps workflow.
- Phase 8 compares agents with that fixed conventional baseline.
- Phase 10 reports exercised capabilities and avoids generalizing beyond FD001.

## Deferred decisions

The following require evidence from earlier phases:

- exact RUL cap and failure-risk horizon;
- model-performance thresholds;
- whether a neural multi-task model is justified;
- whether Evidently adds value beyond custom metrics;
- remote MLflow topology;
- staging and production hosting targets;
- dashboard authentication;
- LLM provider and model;
- latency and reliability objectives; and
- whether additional C-MAPSS subsets are academically useful.
