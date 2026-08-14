# Towards Autonomous Predictive Maintenance

An agent-assisted, human-governed MLOps research prototype for predictive
maintenance using NASA C-MAPSS turbofan telemetry.

The project will address:

- remaining useful life regression;
- horizon-based failure-risk classification;
- exploratory health-state clustering and anomaly detection;
- cycle-level asset-health state monitoring; and
- bounded AI-assisted model and maintenance decision support.

**Phase 0: Project foundation and architecture** is complete and owner-approved.
**Phase 1: Local dataset ingestion and data contract** is complete and
owner-approved. **Phase 2: Cloud data foundation** is also complete and
owner-approved. **Phase 3: ETL and orchestration** is complete and
owner-approved. **Phase 4: Baseline model development** is complete and
awaiting owner approval.
Leakage-safe Ridge and logistic candidates, dummy references, aggregate
evaluation, and local SQLite-backed MLflow tracking are implemented and have
passed local synthetic and actual-FD001 checks. Required GitHub Actions run
`31773869033` also passed every Phase 4 quality gate. No model has been
registered, promoted, served, or deployed.

Phase 2 local development uses a loopback-only PostgreSQL 17 container and a
filesystem Storage substitute. The approved hosted Supabase project has passed
private-bucket, raw-object, checksum, overwrite-denial, metadata, lineage,
idempotency, reconciliation, migration-history, and advisor checks. Hosted
credentials remain outside Git and ordinary CI.

## Phase 1 local validation

After placing the confirmed FD001 files in the ignored `Data/` directory:

```shell
uv sync --locked --dev
uv run validate-fd001 --source-dir Data
```

The command verifies exact source bytes, creates or reuses an ignored
content-addressed raw snapshot, enforces the executable contract, derives
labels, and writes aggregate reports under ignored `artifacts/`. It does not
upload data or contact a cloud service.

## Phase 3 local ETL

After publishing an accepted raw snapshot to the local Phase 2 substitute, run
the deterministic ETL with its explicit snapshot ID:

```shell
uv run run-fd001-etl --source-snapshot-id <64-character-sha256>
```

The command produces typed Parquet processed data, separate candidate-feature
and target files, canonical manifests, a bounded JSON quality report, and
PostgreSQL lineage. Exact reruns verify and reuse the same content-addressed
objects. The command performs no model fitting.

The Phase 3 Airflow development runtime is loopback-only:

```shell
docker compose build airflow
docker compose up -d --wait postgres airflow
docker compose exec -T airflow airflow dags list-import-errors --output json
```

Set `PM_SOURCE_SNAPSHOT_ID` before starting Airflow for a scheduled static-batch
run. Airflow logical dates are orchestration metadata; they are not telemetry
event time and do not make FD001 real-time data.

## Phase 4 local baseline run

Start MLflow on loopback with its SQLite database and artifacts below ignored
`artifacts/mlflow/`, then run:

```shell
uv run train-fd001-baselines \
  --feature-snapshot-id <explicit-phase-3-feature-snapshot-id> \
  --code-revision <git-revision> \
  --tracking-uri http://127.0.0.1:5000
```

The command verifies raw, processed, and feature lineage plus every referenced
object hash before training. It uses 24 ordered telemetry inputs, an
engine-disjoint 80/20 development split, and the NASA test partition only as
the final holdout. Outputs are simulated research evidence, not a deployed
model or physical digital twin.

## Claim boundaries

The initial system is a digital-twin-inspired **asset-health digital shadow**,
not a validated bidirectional physical twin. C-MAPSS telemetry is processed
offline or through cycle-level replay; this is not a hard real-time system.
Agents may analyze evidence and draft recommendations, but deterministic checks
and human approvals retain authority over deployment, model promotion, and
maintenance decisions.

## Source of truth

- [Project charter](docs/PROJECT_CHARTER.md)
- [Master architecture](docs/MASTER_ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Manual prerequisites](docs/MANUAL_PREREQUISITES.md)
- [Security and secrets](docs/SECURITY_AND_SECRETS.md)
- [Test strategy](docs/TEST_STRATEGY.md)
- [Data contract](docs/DATA_CONTRACT.md)
- [Architecture decision records](docs/adr/README.md)
- [Phase 0 plan](docs/phases/phase-00/PLAN.md)
- [Phase 1 plan](docs/phases/phase-01/PLAN.md)
- [Phase 2 plan](docs/phases/phase-02/PLAN.md)
- [Phase 3 plan](docs/phases/phase-03/PLAN.md)
- [Phase 4 plan](docs/phases/phase-04/PLAN.md)

## Development

The foundation environment uses Python 3.11 and `uv`.

```shell
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
```

Do not add datasets, credentials, private service URLs, model artifacts, or
monitoring outputs to Git.

## License

Licensed under the Apache License 2.0. See `LICENSE`.

## Phase governance

Only the phase identified in `docs/PROJECT_STATUS.md` may be active. A phase
requires an explicit `START PHASE <number>` command before implementation and an
explicit `APPROVE PHASE <number>` command after its completion report.
