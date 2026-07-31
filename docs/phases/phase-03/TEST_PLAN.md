# Phase 3 Test Plan

## Evidence classes

| Class                      | Environment                                  | What it can prove                                               |
| -------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| Unit/contract              | Python, memory, temporary directories        | Pure ETL, schemas, identity, quality, failure rules             |
| PostgreSQL integration     | Pinned local PostgreSQL 17 container         | Migration, grants, RLS, run states, lineage, transactions       |
| Object integration         | Temporary filesystem                         | Derived put-if-absent, hashes, retry, reconciliation            |
| Airflow import/structure   | Pinned Airflow image                         | DAG parse safety, graph, schedule, retries, timeouts            |
| Airflow execution/backfill | Airflow LocalExecutor plus local substitutes | Task execution, retry, run history, direct/DAG parity, backfill |
| Actual dataset             | Ignored owner-provided FD001 files           | Real local data behavior; not CI or cloud evidence              |
| Supabase cloud integration | Explicit approved project                    | Hosted derived Storage and PostgreSQL behavior                  |
| GitHub CI                  | Credential-free runner                       | Reproducible local gates; not hosted cloud success              |

No evidence class may be reported as another.

## Unit and contract tests

### Source gate

- available source accepted;
- unknown or inconsistent source rejected;
- missing or mismatched referenced raw object rejected;
- unexpected contract/parser version rejected; and
- Phase 1 validation failure blocks transformation.

### Processed transformation

- exact train/test row counts and row order;
- exact column order and dtypes;
- finite settings/sensors and non-null keys/targets;
- unique `(engine_id, cycle)` keys;
- unchanged Phase 1 RUL and `failure_risk_30` values;
- no implicit sort, drop, imputation, scale, cap, or timestamp; and
- empty, malformed, duplicate, reordered, and non-finite input failures.

### Candidate features and targets

- exact key alignment between feature and target files;
- settings and sensors are the only candidate-feature columns;
- RUL/risk are absent from feature columns;
- RUL/risk are present in target files with declared dtypes;
- no learned/fitted state is created; and
- feature-specification version participates in identity.

### Serialization and identity

- known canonical JSON vectors;
- Parquet round-trip preserves schema, values, order, and dtypes;
- two clean serializations produce the same hashes under the locked writer;
- manifest field and file ordering is deterministic;
- changed source, contract, feature version, or output changes identity;
- timestamps and Airflow logical dates do not change content identity;
- traversal, invalid hashes, unsafe filenames, and oversized metadata fail;
  and
- pickle or executable object serialization is absent.

### Data-quality report

- passing report with expected aggregate counts;
- stable rule IDs for each failure;
- no more than five examples per rule;
- bounded message and report size;
- no raw row dump, absolute path, credential, URL, or secret; and
- failed status prevents derived availability.

## Migration and PostgreSQL tests

Against a clean PostgreSQL 17 container:

1. apply Phase 2 and Phase 3 migrations in filename order;
1. inspect approved schemas, tables, columns, constraints, indexes, and roles;
1. exercise valid and invalid derived snapshots, files, and run states;
1. verify raw-parent and derived-object foreign keys;
1. verify duplicate identity and illegal state-transition denial;
1. verify lineage relationships and self-link denial;
1. prove `PUBLIC`, `anon`, and `authenticated` denial;
1. prove the runtime role has only required operations;
1. test RLS separately from grants;
1. verify Airflow metadata tables are absent from `ops`;
1. reset and reapply all migrations; and
1. compare schema fingerprints and repository migration history.

The reset is destructive only to the disposable local database. It is not a
production down migration.

## Pure ETL local integration

- materialize and reverify a synthetic raw snapshot;
- run the complete direct pipeline through filesystem plus PostgreSQL;
- download and rehash every processed, feature, target, manifest, and report
  object;
- read Parquet outputs and revalidate their contracts;
- rerun and prove identical snapshot IDs and no duplicate rows/objects/edges;
- inject object success plus metadata failure, then retry;
- inject a quality failure and prove no available processed/features;
- remove or modify one referenced derived object and detect inconsistency;
- create an orphan and report it without deletion;
- restore metadata and object bytes into disposable targets and reconcile; and
- run the ignored actual FD001 source under the `dataset` marker.

## Airflow import and structure tests

In the pinned Airflow image:

- `airflow dags list-import-errors` reports none;
- the exact DAG ID is present;
- task IDs and edges match the approved graph;
- schedule is daily, normal catchup is disabled, and active runs are bounded;
- retries, exponential backoff, and execution timeouts are declared;
- DAG import performs no database, network, Storage, or filesystem mutation;
- configuration is read safely without secret values at parse time;
- task callables delegate to application functions; and
- XCom payload schemas permit only bounded identifiers and status data.

## Airflow execution, retry, and backfill tests

Using committed synthetic fixtures and local substitutes:

1. run the direct CLI and record output identities;
1. run the DAG for one logical date and compare every identity;
1. inject a retryable failure after verified object publication;
1. allow the task retry and prove convergence without duplicates;
1. inject a non-retryable contract failure and prove fail-closed status;
1. run a backfill dry run for at least two logical dates;
1. run the bounded backfill with declared reprocessing behavior;
1. prove Airflow records distinct DAG runs while project artifacts are reused;
1. verify no DataFrame, raw telemetry, secret, or temporary path enters XCom;
   and
1. stop containers and remove only disposable volumes.

The backfill test does not claim time-partitioned source data. Both logical
dates point to the same explicit immutable FD001 source.

## Hosted Supabase integration

Hosted tests remain explicitly marked `cloud` and excluded from ordinary CI.
After target and mutation confirmation, the run must:

1. verify the project and private derived bucket;
1. verify repository migration history;
1. publish or reuse approved processed, feature, target, manifest, and report
   objects;
1. download and verify size and SHA-256 for every object;
1. verify PostgreSQL derived snapshot, file, run, and lineage metadata;
1. rerun and prove exact reuse;
1. reconcile metadata and objects;
1. test a generated integration-prefix conflict without touching durable data;
1. clean only the generated integration prefix;
1. run Security and Performance Advisors; and
1. record whether Storage and database paths were one end-to-end Python run or
   separately exercised because of network limits.

If the exact target or approval is missing, the cloud run is blocked. A skipped
hosted check cannot satisfy the cloud acceptance criteria.

## Security tests

- secret, token, connection-string, and private-endpoint scan;
- no credentials in Git, image layers, build arguments, logs, XCom, reports, or
  exception messages;
- loopback-only local Airflow and PostgreSQL ports;
- development Airflow credentials are placeholders or ignored;
- malicious object keys and filenames cannot escape approved prefixes;
- untrusted pickle/joblib deserialization is absent;
- Parquet/JSON input and output sizes are bounded;
- no network or mutation during DAG parsing;
- denied database roles cannot access new objects; and
- cloud cleanup cannot target raw or durable derived prefixes.

## Planned local and CI commands

Exact commands are finalized after `START PHASE 3`. Planned gates include:

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
docker compose config --quiet
docker compose build airflow
docker compose up -d --wait postgres airflow
uv run pytest -m "not integration and not dataset and not postgres and not airflow and not cloud"
uv run pytest -m "integration and not dataset and not postgres and not airflow and not cloud"
uv run pytest -m "postgres and not dataset and not cloud"
docker compose exec airflow airflow dags list-import-errors
uv run pytest -m "airflow and not dataset and not cloud"
uv run pytest -m "not dataset and not cloud" --cov=src/predictive_maintenance --cov-branch --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
docker compose down --volumes
```

Fixed sleeps are prohibited. Container health checks or bounded polling must
control readiness. Cleanup runs even after a failed check.

## Performance and resource observations

Phase 3 does not set a production throughput service-level objective. It will
record:

- direct and DAG execution duration for synthetic and actual FD001 runs;
- output object sizes;
- peak or bounded-memory evidence where practical;
- Airflow container startup time; and
- whether repeated/backfill runs reuse artifacts.

These are engineering observations, not real-time or fleet-scale claims.

## Exit criteria

All acceptance criteria and local gates pass; deterministic repeated-build,
actual FD001, PostgreSQL, filesystem, Airflow execution/backfill, recovery,
approved hosted Supabase, advisors, and GitHub Actions evidence are recorded;
and no critical/high issue remains unresolved.
