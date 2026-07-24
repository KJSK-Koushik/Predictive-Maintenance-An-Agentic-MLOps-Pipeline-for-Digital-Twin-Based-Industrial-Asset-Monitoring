# Phase 1 Test Plan

## Test boundaries

CI uses small committed synthetic fixtures and never downloads or commits the
NASA dataset. The actual ignored FD001 files are exercised locally and reported
as local-real-data evidence. A fixture pass is not represented as validation of
the owner-provided files.

## Unit tests

| Area        | Required cases                                                        |
| ----------- | --------------------------------------------------------------------- |
| Integrity   | Known SHA-256 vector, bounded reads, changed bytes, copy verification |
| Manifest    | Stable canonical serialization, snapshot identity, sanitized paths    |
| Parser      | Valid whitespace, trailing whitespace, wrong width, non-numeric token |
| RUL labels  | Train endpoint, test endpoint, off-by-one, non-negative result        |
| Risk labels | RUL 29/30/31 at the 30-cycle decision boundary                        |
| Reports     | Stable rule IDs, bounded examples, JSON-serializable values           |

## Contract and semantic tests

- exactly 26 ordered columns with three settings and 21 sensors;
- expected numeric and integral domains;
- null, NaN, positive/negative infinity rejection;
- positive engine and cycle identifiers;
- unique `(engine_id, cycle)` keys;
- strictly increasing cycles in source order;
- missing cycle and reordered-cycle behavior;
- train/test/RUL required-file checks;
- one RUL value per contiguous ordered test engine ID; and
- failure reports that block acceptance.

## Integration tests

Temporary-directory tests exercise:

1. ingesting a valid synthetic FD001 source set;
1. verifying exact-byte content-addressed raw copies;
1. rerunning the identical source idempotently;
1. detecting a tampered destination;
1. rejecting a partial or missing source set;
1. rejecting corrupt data without publishing acceptance; and
1. producing deterministic manifest and validation report content.

## Actual-data validation

After `START PHASE 1`, a dedicated command will run against:

```text
Data/train_FD001.txt
Data/test_FD001.txt
Data/RUL_FD001.txt
Data/readme.txt
```

The evidence records exact digests, counts, validation outcome, aggregate
profile, label distributions, command, runtime versions, and code revision. It
does not commit raw rows or absolute workstation paths.

## Quality commands

The implementation phase will finalize exact commands. The intended gates are:

```shell
uv sync --locked --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -m "not integration and not dataset"
uv run pytest -m integration
uv run pytest --cov=src/predictive_maintenance --cov-branch --cov-fail-under=90
uv run mdformat --check README.md CONTRIBUTING.md docs
uv run yamllint .
uv run pip-audit
```

The real-data test marker is local-only unless an approved, immutable dataset
source is deliberately made available to CI. It is never silently skipped in
the completion report.

## Failure and security tests

- raw source mutation detection;
- destination tampering and overwrite denial;
- path traversal or unexpected filename rejection;
- oversized validation examples remain bounded;
- reports exclude absolute paths and secret-like values;
- generated raw snapshots remain ignored; and
- no cloud SDK, credential, deployment, model, or agent behavior is exercised.

## Docker

Not applicable. Phase 1 adds a local Python library and CLI, not a service or
container runtime.

## Exit criteria

All acceptance tests and quality checks pass locally, the actual FD001 files
pass the approved contract, the required GitHub workflow passes remotely, and
no critical/high issue remains open.
