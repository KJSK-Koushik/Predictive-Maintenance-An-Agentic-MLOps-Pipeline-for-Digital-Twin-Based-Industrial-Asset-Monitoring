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
owner-approved. **Phase 2: Cloud data foundation** is planned but not started.
The repository still contains no cloud resources, trained models, or deployable
services.

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
