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

## Phase 0 suite

### Foundation contract tests

- required documents and phase files exist and are non-empty;
- project status contains one valid active phase;
- every ADR has required metadata and sections;
- local data paths are ignored;
- `.env.example` contains placeholders rather than credentials;
- no dependency or path references the separate repository;
- no later-phase implementation directory is introduced; and
- Markdown links to local source-of-truth documents resolve.

### Integration contract tests

- the GitHub workflow has least-privilege permissions;
- the workflow runs formatting, linting, typing, tests, and security checks;
- the workflow contains no deployment command or privileged environment;
- the workflow uses immutable action references; and
- Phase 0 status, plan, acceptance criteria, and workflow agree.

### Phase 0 commands

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy tests
uv run pytest
uv run pytest --cov=tests --cov-branch --cov-report=term-missing
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
```

Coverage in Phase 0 describes foundation test modules and is informational. A
product-code threshold becomes meaningful in Phase 1 and will be introduced
there.

## Phase growth

### Phase 1

- parser and checksum unit tests;
- schema and semantic property tests;
- label boundary tests;
- corrupt, missing, duplicate, and reordered input tests;
- a temporary-directory ingestion integration test; and
- a minimum product-code coverage threshold.

### Phase 2

- migration up/down or clean-apply validation;
- PostgreSQL constraint and RLS tests;
- object-store idempotency and overwrite-denial tests;
- local substitute tests; and
- separate, credentialed Supabase integration evidence.

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
