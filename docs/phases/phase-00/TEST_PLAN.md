# Phase 0 Test Plan

## Scope

Validate repository governance, documentation, configuration, CI design, and
secret boundaries. No data, model, service, Docker, database, or cloud
integration is exercised.

## Foundation tests

| Test                    | Expected result                                      |
| ----------------------- | ---------------------------------------------------- |
| Required files          | Every source-of-truth and Phase 0 file is non-empty  |
| Phase state             | Exactly Phase 0 is active with a permitted status    |
| ADR contract            | Sequential ADRs have all required sections           |
| Local links             | Relative links in controlled Markdown resolve        |
| Data exclusion          | `Data/` and future local data roots are ignored      |
| Feature exclusion       | No later-phase implementation root exists            |
| Environment example     | Only empty, safe-local, or placeholder values        |
| Repository independence | No path/dependency points to the separate repository |
| Claim vocabulary        | Charter contains required qualification terms        |

## Integration tests

| Test               | Expected result                                                 |
| ------------------ | --------------------------------------------------------------- |
| Workflow parse     | CI YAML loads successfully                                      |
| Permission         | Workflow declares read-only contents permission                 |
| Trigger            | Pull-request and main-branch push validation are configured     |
| Quality commands   | Lock, format, lint, typing, test, docs, YAML, audit run         |
| Action pinning     | Every `uses` value contains an immutable commit SHA             |
| No deployment      | CI contains no deploy, release, promote, or cloud mutation step |
| Status consistency | Workflow and phase acceptance criteria agree                    |

## Manual/local checks

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
git check-ignore Data/train_FD001.txt
git status --short
```

## Remote checks

After a GitHub remote exists:

1. Push a branch.
1. Open a pull request.
1. Confirm the Phase 0 quality job completes successfully.
1. Configure it as a required check.
1. Capture the run URL and branch-protection evidence.

Local output cannot satisfy these remote checks.

## Docker

Not applicable. Phase 0 creates no image, Compose file, application process, or
service contract. Docker validation begins when an owning phase introduces a
runnable container.

## Exit criteria

Every required command exits zero, remote evidence is recorded, and no
critical/high security issue is open.
