# Phase 2 Test Plan

## Evidence classes

| Class                      | Environment                                  | What it can prove                                               |
| -------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| Unit/contract              | Python and temporary directories             | Pure identities, states, interfaces, and failures               |
| PostgreSQL integration     | Pinned local PostgreSQL 17 container         | Migrations, SQL constraints, roles, grants, RLS, transactions   |
| Local object integration   | Temporary filesystem                         | Shared put-if-absent, verification, and reconciliation contract |
| Supabase cloud integration | Explicit approved project and test namespace | Hosted Storage and PostgreSQL behavior                          |
| GitHub CI                  | Credential-free runner                       | Reproducible local gates; not cloud success                     |

No evidence class may be reported as another.

## Unit and contract tests

### Configuration

- missing required variable;
- valid local versus cloud configuration;
- secret values never appear in `repr`, errors, logs, or reports;
- bucket and object keys reject traversal, empty segments, and invalid hashes;
  and
- configuration does not infer an environment from a credential.

### Object repository

- deterministic raw and derived key generation;
- known SHA-256 and byte-size vectors;
- first put, exact reuse, and different-byte conflict;
- bounded streaming upload/download;
- no overwrite or raw delete method on the normal interface;
- concurrent same-key behavior; and
- filesystem and cloud adapters share one contract suite.

### Publication state

- exact snapshot rerun returns existing identity;
- partial file set never becomes available;
- object success plus database failure is retryable;
- metadata conflict fails closed;
- missing/mismatched/orphaned reconciliation findings;
- stable error codes and bounded sanitized details; and
- available state requires verified objects and committed metadata.

## Migration and PostgreSQL tests

Run against a clean pinned PostgreSQL 17 container:

1. apply all repository migrations in order;
1. inspect the exact schemas, tables, columns, constraints, indexes, and roles;
1. exercise valid and invalid inserts;
1. verify foreign keys and lineage constraints;
1. prove `PUBLIC`, `anon`, and `authenticated` denial;
1. set the runtime role and prove only intended operations work;
1. test RLS separately from object grants where enabled;
1. reset the database and apply the same migrations again;
1. compare the resulting schema fingerprint; and
1. confirm no custom object exists in Supabase-managed schemas.

Migrations are forward-only. Phase 2 validates clean apply and reset/reapply,
not a misleading production "down migration." Any destructive reset is limited
to the disposable local database.

## Local integration tests

- publish a valid synthetic snapshot through filesystem plus PostgreSQL;
- rerun it and verify no duplicate object, snapshot, file, edge, or run;
- fail after one object and then retry;
- tamper with a filesystem object and detect the mismatch;
- delete a referenced local object and detect inconsistent state;
- create an orphan and report it without automatic deletion;
- restore test metadata/object backup and verify the same hashes; and
- publish the ignored actual FD001 snapshot locally under the `dataset` marker.

## Supabase cloud integration tests

Cloud tests use a `cloud` marker and require explicit environment configuration.
They are excluded from ordinary CI.

The approved run must:

1. preflight and record a sanitized project/environment identity;
1. verify the raw and derived buckets are private;
1. verify the repository migration history;
1. upload or reuse every real FD001 raw object without upsert;
1. download and rehash every object;
1. rerun and prove idempotent metadata and objects;
1. attempt different bytes at an existing integration key and prove denial;
1. verify direct PostgreSQL metadata and lineage;
1. inject or observe one safe integration-prefix inconsistency and reconcile it;
1. clean only the generated derived `_integration/<run-id>` prefix;
1. leave approved durable raw FD001 objects untouched;
1. run Security and Performance Advisors; and
1. record that the test was real Supabase, not local or mocked.

If credentials or the approved target are unavailable, the cloud test is
reported as blocked and Phase 2 cannot complete.

## Backup and recovery test

The owner-approved procedure must cover operational PostgreSQL and Storage
object bytes separately. A safe exercise will:

- export the Phase 2 metadata and an integration-prefix object;
- verify backup hashes and a manifest;
- restore into a disposable local database and integration object key;
- re-run metadata/object reconciliation; and
- remove only the disposable restored integration object.

No raw durable object is deleted to demonstrate recovery.

## CI quality commands

Exact commands and pinned versions are finalized after `START PHASE 2`. The
planned gates are:

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
docker compose config
docker compose up -d postgres
uv run pytest -m "not dataset and not cloud"
uv run pytest --cov=src/predictive_maintenance --cov-branch --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
```

The implementation will add deterministic container health waiting and cleanup;
it will not depend on fixed sleeps.

## Security tests

- secret/private-endpoint pattern scan;
- no credentials in Git history changes, reports, exception text, or logs;
- operational schema absent from exposed Data API schemas;
- denied roles cannot read or mutate operational metadata;
- cloud bucket is not public;
- raw update/delete unavailable through the normal interface;
- managed Supabase schemas contain no custom objects;
- SQL inputs are parameterized; and
- malicious object keys cannot escape their logical prefix.

## Exit criteria

All acceptance tests and local gates pass, actual FD001 local publication
passes, the approved real Supabase verification passes, advisors and
backup/recovery evidence are recorded, the required GitHub workflow passes, and
no critical/high issue remains.
