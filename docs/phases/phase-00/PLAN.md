# Phase 0 Plan

## Authorization

Authorized on 2026-07-23 by explicit `START PHASE 0`.

## Objective

Establish the project foundation and architecture without feature
implementation or service initialization.

## Work breakdown

1. Inspect repository and toolchain without touching the separate repository.
1. Establish the bootstrap phase status.
1. Create the charter, master architecture, roadmap, prerequisites, security,
   test strategy, and Phase 0 data-contract boundary.
1. Record binding architecture decisions as ADRs.
1. Add project metadata, ignore rules, placeholder environment configuration,
   and a locked development toolchain.
1. Add repository foundation and CI integration contract tests.
1. Add verification-only GitHub Actions CI.
1. Run local formatting, linting, typing, tests, coverage, dependency/security,
   and configuration checks.
1. Record exact evidence and remaining external blockers.

## Files expected to change

- root governance/configuration files;
- `.github/workflows/ci.yml`;
- the eight required source-of-truth documents;
- `docs/adr/` and accepted Phase 0 ADRs;
- all five files in `docs/phases/phase-00/`;
- foundation and integration tests; and
- the dependency lockfile.

No `src/`, service, migration, DAG, model, dashboard, or agent implementation is
permitted.

## Test approach

- foundation tests enforce documents, status, boundaries, ignores, and secrets;
- integration tests parse the CI workflow and enforce verification-only design;
- quality tools run from the locked `uv` environment; and
- GitHub Actions must repeat the same required checks remotely.

## Completion conditions

All criteria in `ACCEPTANCE_CRITERIA.md` must be checked. The completion report
must contain local and GitHub evidence. Docker is not applicable because Phase
0 has no runnable service.

## Known external dependencies

- license selection;
- GitHub remote and access;
- code-owner identity;
- Actions enablement; and
- required branch protection.
