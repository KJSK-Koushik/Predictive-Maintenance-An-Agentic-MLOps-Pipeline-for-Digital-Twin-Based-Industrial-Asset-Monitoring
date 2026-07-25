# Phase 1 Acceptance Criteria

## Source integrity and provenance

- [x] Only the owner-confirmed FD001 train, test, RUL, and readme inputs are in
  the required source set.
- [x] Every required source file has a recorded byte size and SHA-256 digest.
- [x] The NASA source URL and citation are recorded.
- [x] The absence of an original archive checksum is recorded as a provenance
  limitation rather than inferred away.
- [x] Source bytes are unchanged by ingestion.
- [x] Content-addressed raw copies verify their post-copy digest.
- [x] Existing valid copies are idempotently reused and overwrite attempts fail.
- [x] The canonical manifest is deterministic and contains no absolute private
  workstation path.
- [x] No raw or generated data artifact is tracked by Git.

## Parsing and validation

- [x] FD001 train and test rows parse to the named 26-column contract.
- [x] Parsing handles the source whitespace format without dropping columns.
- [x] Pandera enforces column order, numeric types, finiteness, and nullability.
- [x] Semantic checks enforce positive integral IDs/cycles, unique keys, and
  strictly increasing per-engine source order.
- [x] Cross-file validation proves one terminal RUL value per test engine.
- [x] Missing, corrupt, reordered, duplicate, non-finite, and wrong-width inputs
  fail with stable structured rule identifiers.
- [x] Validation failure prevents an accepted snapshot result.

## Labels and exploration

- [x] Uncapped training RUL equals the engine endpoint cycle minus source cycle.
- [x] Test RUL correctly combines the last observed cycle and supplied terminal
  RUL.
- [x] Label endpoint, off-by-one, and non-negative invariants are tested.
- [x] A 30-cycle primary failure-risk label is implemented and boundary-tested.
- [x] Failure-risk prevalence at 15, 30, and 45 cycles is documented.
- [x] Any capped RUL remains a separate explicit derivation and its decision is
  documented.
- [x] The exploration report records dimensions, engines, cycle lengths,
  missingness, duplicates, distributions, and constant/low-information signals.
- [x] Exploration findings are scoped to FD001 simulated telemetry.
- [x] Cycle observations are documented as historical telemetry without
  fabricated event timestamps or live-stream claims.

## Engineering and test evidence

- [x] Core logic is typed and independent of cloud or orchestration SDKs.
- [x] Unit, contract, malformed-input, and temporary-directory integration tests
  pass locally.
- [x] Actual owner-provided FD001 validation passes locally.
- [x] Product source meets at least 90% branch-aware coverage.
- [x] Ruff formatting/linting, mypy, Markdown, YAML, lockfile, and dependency
  security checks pass.
- [x] CI remains least-privilege and contains no deployment or cloud mutation.
- [x] The required GitHub Actions workflow passes on the Phase 1 commit.
- [x] Required branch protection is verified for the current quality context.
- [x] Docker is documented as not applicable because no service is introduced.

## Completion evidence

- [x] `docs/DATA_CONTRACT.md` contains the verified executable contract.
- [x] Phase architecture, test plan, exploration report, and completion report
  reflect exercised behavior.
- [x] `docs/PROJECT_STATUS.md` is updated to `AWAITING_APPROVAL`.
- [x] No critical or high-severity issue remains unresolved.
- [x] The completion handoff asks the owner for `APPROVE PHASE 1`.

All Phase 1 criteria are satisfied. Evidence and limitations are recorded in
`COMPLETION_REPORT.md`.
