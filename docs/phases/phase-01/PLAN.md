# Phase 1 Plan

## Authorization

Planning was authorized on 2026-07-24 by explicit `PLAN PHASE 1`.
Implementation was authorized on 2026-07-25 by explicit `START PHASE 1`.

## Objective

Implement and exercise local FD001 integrity, immutable raw snapshotting,
parsing, validation, labels, and aggregate exploration with reproducible
evidence and no cloud dependency.

## Implemented work breakdown

1. Reconfirm repository status and source-file inventory without changing data.
1. Add the minimal runtime dependencies: Pandera with its pandas backend.
1. Create the typed `predictive_maintenance.data` package.
1. Implement streaming SHA-256, content-addressed exact-byte copies, canonical
   manifests, overwrite denial, and idempotent reuse.
1. Implement the 26-column FD001 whitespace parser without silent
   normalization.
1. Implement Pandera structural validation and Python cross-row/cross-file
   semantic rules with stable failure codes.
1. Implement uncapped train/test RUL and parameterized failure-risk labels,
   using 30 cycles as the primary classification horizon.
1. Add synthetic fixtures and unit, contract, failure, and local integration
   tests alongside each component.
1. Exercise the pipeline against the owner-confirmed FD001 files.
1. Record checksums, validation results, aggregate exploration, constant or
   low-information signals, label distributions, and provenance limitations.
1. Expand CI to run product typing, tests, contract checks, coverage, and
   security gates while keeping it verification-only.
1. Update architecture, data contract, test strategy, status, and completion
   evidence.

## Expected implementation files

```text
src/predictive_maintenance/
  __init__.py
  data/
    __init__.py
    contract.py
    integrity.py
    parser.py
    validation.py
    labels.py
    exploration.py
    pipeline.py
    cli.py
tests/
  fixtures/cmapss/
  data/
docs/phases/phase-01/
  ARCHITECTURE.md
  PLAN.md
  ACCEPTANCE_CRITERIA.md
  TEST_PLAN.md
  DATA_EXPLORATION.md
  COMPLETION_REPORT.md
```

Existing files changed during implementation include
`pyproject.toml`, `uv.lock`, `.gitignore`, `.github/workflows/ci.yml`,
`docs/DATA_CONTRACT.md`, `docs/MASTER_ARCHITECTURE.md`,
`docs/TEST_STRATEGY.md`, `docs/MANUAL_PREREQUISITES.md`, and
`docs/PROJECT_STATUS.md`.

The final module list follows these responsibilities. No
generic framework, database adapter, event broker, notebook-only pipeline, or
service tree is planned.

## Source provenance

The authoritative citation is A. Saxena and K. Goebel (2008), “Turbofan Engine
Degradation Simulation Data Set,” NASA Prognostics Data Repository, NASA Ames
Research Center. NASA currently publishes the archive from its Prognostics
Center of Excellence repository:

<https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/>

The owner has selected the existing extracted files in `Data/` as the working
source. No original ZIP archive is present. Phase 1 will therefore hash and
identify the exact local files and record that it cannot prove byte identity
with an unrecorded original archive checksum.

## CI growth

The Phase 1 workflow adds:

- typing for product source and tests;
- fixture-based parser, contract, semantic, and label tests;
- local temporary-directory ingestion tests;
- at least 90% product-code branch-aware coverage;
- checks that raw data and generated snapshots remain untracked; and
- dependency/security auditing.

GitHub CI will not download the NASA archive or receive the local dataset.
Actual FD001 validation is separate local-real-data evidence. Branch protection
must be updated safely if the required job context is renamed to a
phase-neutral name.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. Local fixture and actual-data
evidence, GitHub Actions evidence, documentation, and the absence of
critical/high issues are all required. Docker remains not applicable because
Phase 1 introduces no runnable service.

## Planning risks

| Risk                                                                      | Planned treatment                                                       |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Local files cannot be proven identical to an unavailable archive checksum | Record exact local digests, NASA citation, and provenance limitation    |
| Parser silently normalizes malformed telemetry                            | Preserve row order and fail on invalid shape, type, key, or ordering    |
| Test RUL vector is mapped to the wrong engine                             | Require contiguous ordered test IDs and one RUL value per engine        |
| Labels leak future information into later modeling                        | Isolate label derivation and prohibit labels from feature inputs        |
| Dataset-derived ranges are presented as physical limits                   | Treat ranges as FD001 profile statistics only                           |
| CI cannot access ignored real data                                        | Use committed synthetic fixtures in CI and separate local-real evidence |
| “Telemetry” implies a live stream                                         | Document historical cycle observations and defer replay                 |
| Local immutability is overstated                                          | Call it content-addressed overwrite denial, not WORM                    |
