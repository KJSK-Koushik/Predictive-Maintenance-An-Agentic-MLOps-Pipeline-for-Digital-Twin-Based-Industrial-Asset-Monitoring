# Phase 1 Acceptance Criteria

## Source integrity and provenance

- [ ] Only the owner-confirmed FD001 train, test, RUL, and readme inputs are in
  the required source set.
- [ ] Every required source file has a recorded byte size and SHA-256 digest.
- [ ] The NASA source URL and citation are recorded.
- [ ] The absence of an original archive checksum is recorded as a provenance
  limitation rather than inferred away.
- [ ] Source bytes are unchanged by ingestion.
- [ ] Content-addressed raw copies verify their post-copy digest.
- [ ] Existing valid copies are idempotently reused and overwrite attempts fail.
- [ ] The canonical manifest is deterministic and contains no absolute private
  workstation path.
- [ ] No raw or generated data artifact is tracked by Git.

## Parsing and validation

- [ ] FD001 train and test rows parse to the named 26-column contract.
- [ ] Parsing handles the source whitespace format without dropping columns.
- [ ] Pandera enforces column order, numeric types, finiteness, and nullability.
- [ ] Semantic checks enforce positive integral IDs/cycles, unique keys, and
  strictly increasing per-engine source order.
- [ ] Cross-file validation proves one terminal RUL value per test engine.
- [ ] Missing, corrupt, reordered, duplicate, non-finite, and wrong-width inputs
  fail with stable structured rule identifiers.
- [ ] Validation failure prevents an accepted snapshot result.

## Labels and exploration

- [ ] Uncapped training RUL equals the engine endpoint cycle minus source cycle.
- [ ] Test RUL correctly combines the last observed cycle and supplied terminal
  RUL.
- [ ] Label endpoint, off-by-one, and non-negative invariants are tested.
- [ ] A 30-cycle primary failure-risk label is implemented and boundary-tested.
- [ ] Failure-risk prevalence at 15, 30, and 45 cycles is documented.
- [ ] Any capped RUL remains a separate explicit derivation and its decision is
  documented.
- [ ] The exploration report records dimensions, engines, cycle lengths,
  missingness, duplicates, distributions, and constant/low-information signals.
- [ ] Exploration findings are scoped to FD001 simulated telemetry.
- [ ] Cycle observations are documented as historical telemetry without
  fabricated event timestamps or live-stream claims.

## Engineering and test evidence

- [ ] Core logic is typed and independent of cloud or orchestration SDKs.
- [ ] Unit, contract, malformed-input, and temporary-directory integration tests
  pass locally.
- [ ] Actual owner-provided FD001 validation passes locally.
- [ ] Product source meets at least 90% branch-aware coverage.
- [ ] Ruff formatting/linting, mypy, Markdown, YAML, lockfile, and dependency
  security checks pass.
- [ ] CI remains least-privilege and contains no deployment or cloud mutation.
- [ ] The required GitHub Actions workflow passes on the Phase 1 commit.
- [ ] Required branch protection is verified for the current quality context.
- [ ] Docker is documented as not applicable because no service is introduced.

## Completion evidence

- [ ] `docs/DATA_CONTRACT.md` contains the verified executable contract.
- [ ] Phase architecture, test plan, exploration report, and completion report
  reflect exercised behavior.
- [ ] `docs/PROJECT_STATUS.md` is updated to `AWAITING_APPROVAL`.
- [ ] No critical or high-severity issue remains unresolved.
- [ ] The completion handoff asks the owner for `APPROVE PHASE 1`.

Unchecked criteria prevent Phase 1 completion.
