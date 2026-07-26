# Test Strategy

## Principles

- Test deterministic business logic below orchestration and infrastructure.
- Make every defect reproducible with the smallest relevant test.
- Distinguish unit, contract, integration, smoke, performance, and security
  evidence.
- Mark cloud tests explicitly and never report a mock as cloud verification.
- Preserve test commands, versions, and results in the phase completion report.
- A local pass cannot substitute for a GitHub Actions pass.

## Test layers

| Layer             | Purpose                                                      | Typical dependencies           |
| ----------------- | ------------------------------------------------------------ | ------------------------------ |
| Unit              | Pure transformations, calculations, decisions                | None                           |
| Contract          | Data, API, model signature, config, repository invariants    | Local schemas                  |
| Integration-local | Database/object/API interaction with local substitutes       | Containers as needed           |
| Integration-cloud | Exercise named external service and test namespace           | Approved credentials           |
| Smoke             | Confirm packaged service starts and serves a known request   | Built artifact                 |
| End to end        | Exercise the approved lifecycle across components            | Staging topology               |
| Failure/recovery  | Verify retry, quarantine, rollback, and fail-closed behavior | Controlled faults              |
| Performance       | Evaluate latency, throughput, and resource objectives        | Representative load            |
| Security          | Secrets, dependencies, permissions, auth, input abuse        | Scanners and adversarial cases |

## Foundation suite

### Foundation contract tests

- required documents and phase files exist and are non-empty;
- project status contains one valid active phase;
- every ADR has required metadata and sections;
- local data paths are ignored;
- `.env.example` contains placeholders rather than credentials;
- no dependency or path references the separate repository;
- no post-Phase 1 implementation root is introduced; and
- Markdown links to local source-of-truth documents resolve.

### Integration contract tests

- the GitHub workflow has least-privilege permissions;
- the workflow runs formatting, linting, typing, tests, and security checks;
- the workflow contains no deployment command or privileged environment;
- the workflow uses immutable action references; and
- Phase 0 status, plan, acceptance criteria, and workflow agree.

### Phase 1 commands

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -m "not integration and not dataset"
uv run pytest -m "integration and not dataset"
uv run pytest -m dataset
uv run pytest -m "not dataset" --cov=src/predictive_maintenance --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
```

The `dataset` command requires the ignored owner-provided FD001 files and is
local-real-data evidence. CI runs committed synthetic fixtures and excludes
that marker. Product source has a 90% branch-aware coverage gate.

## Phase growth

### Phase 1 implemented coverage

- parser and checksum unit tests;
- schema and semantic property tests;
- label boundary tests;
- corrupt, missing, duplicate, and reordered input tests;
- a temporary-directory ingestion integration test; and
- a minimum product-code coverage threshold;
- stable structured rule IDs and bounded-example checks;
- byte-for-byte snapshot, reuse, changed-input, and tampering checks; and
- a separate actual FD001 contract test.

### Phase 2

- forward-only migration clean-apply, reset, and history validation;
- PostgreSQL constraint, grant, role, and RLS tests;
- filesystem and Supabase object-contract tests;
- idempotency, concurrency, overwrite-denial, partial-failure, and
  reconciliation tests;
- PostgreSQL 17 and filesystem local-integration evidence;
- separate, credentialed Supabase integration evidence;
- database and object-byte backup/recovery evidence; and
- Supabase Security and Performance Advisor results.

The implemented local commands are:

```shell
docker compose config --quiet
docker compose up -d --wait postgres
uv run pytest -m "not integration and not dataset and not postgres and not cloud"
uv run pytest -m "integration and not dataset and not postgres and not cloud"
PM_POSTGRES_DSN=<local-test-dsn> uv run pytest -m "postgres and not dataset and not cloud"
PM_POSTGRES_DSN=<local-test-dsn> uv run pytest -m "dataset and not cloud"
PM_POSTGRES_DSN=<local-test-dsn> uv run pytest -m "not cloud" --cov=src/predictive_maintenance --cov-branch --cov-fail-under=90
docker compose down --volumes
```

On PowerShell, set `PM_POSTGRES_DSN` with
`$env:PM_POSTGRES_DSN='<local-test-dsn>'` before running the command. The local
DSN is documented in the Phase 2 test plan and CI because it is valid only for
the loopback-bound disposable container.

Hosted tests require `APP_ENV=cloud`, ignored credentials, and the exact
`PM_CLOUD_TEST_APPROVAL` phrase defined in the test module. They remain marked
`cloud` and excluded from ordinary CI. A skipped or mocked hosted test is not
cloud evidence.

### Phase 3

- pure ETL tests outside Airflow;
- DAG import/structure tests;
- retry, failure, backfill, and idempotency integration tests; and
- data-quality report validation.

### Phases 4-5

- engine-disjoint split assertions;
- deterministic training tests;
- metric and threshold tests;
- model serialization and signature tests;
- performance/robustness gates on a fixed evaluation set; and
- comparison and uncertainty validation.

### Phases 6-7

- registry transition tests;
- API schema and error-contract tests;
- container build and smoke tests;
- staging deployment and rollback;
- drift and retraining-trigger tests; and
- champion/challenger promotion-denial tests.

### Phases 8-10

- agent tool permission and prompt-injection tests;
- complete agent audit-event tests;
- deterministic guardrail tests;
- dashboard authorization and provenance tests;
- end-to-end failure/recovery scenarios; and
- predeclared agentic versus non-agentic evaluation.

## Test data

- Raw NASA data is not committed.
- Small synthetic fixtures encode only the minimum required shape and edge
  cases.
- Integration tests use temporary directories and isolated database schemas or
  object prefixes.
- Cloud tests clean only their explicit test namespace.
- Evaluation sets are versioned and protected from tuning leakage.

## CI and CD

Pull-request CI performs verification only. Deployment and model promotion use
separate workflows and protected environments. CI success is one input to a
deployment decision; it is never the deployment decision.

## Flaky tests

A flaky required check remains a failure. It may be quarantined only through a
documented, time-bounded issue with owner approval, without representing the
phase as fully validated.

## Evidence standard

Completion reports record:

- exact command;
- tool/runtime version;
- exit status and concise result;
- whether the test was local, CI, cloud, staging, or mocked;
- artifact or run URL where available; and
- deviations, skipped checks, and open severity.
