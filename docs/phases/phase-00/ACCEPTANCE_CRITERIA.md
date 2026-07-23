# Phase 0 Acceptance Criteria

## Architecture and governance

- [x] Required source-of-truth documents exist.
- [x] Phase 0 architecture and all five phase files exist.
- [x] Charter records scope, non-goals, requirements, constraints, and success.
- [x] Master architecture records data, control, trust, and approval boundaries.
- [x] Roadmap preserves exactly one active phase.
- [x] Terminology limits digital twin, real-time, autonomous, and retraining
  claims.
- [x] Accepted ADRs record the important decisions and alternatives.
- [x] Threat model and secret-management policy exist.
- [x] Manual owner prerequisites are explicit.
- [x] Phase 0 contains no feature or cloud implementation.

## Repository and tests

- [x] Raw/local data paths are ignored.
- [x] `.env.example` contains no credential value or private service URL.
- [x] Development dependencies are lockable and reproducible.
- [x] Foundation tests accompany the repository implementation.
- [x] Integration tests enforce the CI/configuration contract.
- [x] Formatting passes locally.
- [x] Linting passes locally.
- [x] Static typing passes locally.
- [x] Unit/foundation tests pass locally.
- [x] Integration tests pass locally.
- [x] Dependency/security checks pass locally.
- [x] Lockfile validation passes locally.

## CI and external evidence

- [x] Pull-request CI is verification-only and least-privilege.
- [x] CI and deployment/model promotion are architecturally separate.
- [ ] GitHub Actions required workflow passes on GitHub.
- [ ] Required branch protection is configured and evidenced.
- [x] Repository license is selected.
- [x] `CODEOWNERS` identifies the approved GitHub user/team.

## Completion evidence

- [x] `COMPLETION_REPORT.md` records exact local commands and results.
- [x] No critical or high-severity issue remains unresolved.
- [x] Docker validation is documented as not applicable in Phase 0.
- [ ] `PROJECT_STATUS.md` is updated to `AWAITING_APPROVAL`.
- [ ] The owner is asked for `APPROVE PHASE 0`.

Unchecked criteria prevent Phase 0 completion.
