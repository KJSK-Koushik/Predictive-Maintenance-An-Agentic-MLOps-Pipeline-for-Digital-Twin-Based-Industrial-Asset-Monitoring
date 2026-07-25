# Manual Prerequisites

## Purpose

This checklist separates user-owned external actions from repository
automation. Do not paste credentials into chat, issues, pull requests, source
files, or completion reports.

## Phase 0 completion prerequisites

- [x] Select a repository license: Apache-2.0.
- [x] Provide or create the GitHub remote.
- [x] Confirm repository visibility: public.
- [x] Provide the GitHub user/team that should own changes.
- [x] Authenticate GitHub CLI with `gh auth login`.
- [x] Confirm GitHub Actions is enabled.
- [x] Configure branch protection after the first workflow is pushed:
  - require a pull request;
  - require the Phase 0 quality job;
  - prevent merging when it fails;
  - require conversation resolution; and
  - restrict bypass permission to named owners.
- [x] Provide a successful GitHub Actions run URL or grant access to inspect it.

The repository starts with Python 3.11.9, Git, `uv`, and Docker available
locally. Development tools are installed from the lockfile rather than assumed
globally.

## Phase 1 prerequisites

- [x] Record the authoritative NASA C-MAPSS repository and attribution.
- [x] Confirm the existing `Data/` files are the intended working source copy.
- [x] Record that no original archive is currently present in `Data/`; if one
  becomes available, preserve it without replacing the extracted files.
- [x] Do not rename, normalize, or edit the source files manually.
- [x] Limit Phase 1 data scope to FD001.

Phase 1 computed checksums and inspected only the confirmed FD001 logical
files. The raw source and generated local evidence remain ignored by Git.

## Phase 2 Supabase prerequisites

Phase 2 is planned but not started. A read-only connector check found one
inactive project in the connected account. It does not match the private
project URL supplied earlier. No project reference or private endpoint is
recorded in this repository.

- [ ] Confirm which exact Supabase project is the Phase 2 development/test
  target and resolve the mismatch above.
- [ ] Confirm that the target has no valuable or production data that Phase 2
  could affect.
- [ ] Explicitly approve any project activation, expected cost, and cloud
  mutation.
- [ ] Confirm the project region and retention expectations.
- [ ] Approve configurable names for one private raw bucket and one private
  derived bucket. Suggested names are `pm-raw` and `pm-derived`.
- [ ] Approve uploading the accepted FD001 raw snapshot after synthetic cloud
  tests pass.
- [ ] Record the project URL, direct database URL, secret key, and database
  credentials only in ignored local configuration or approved secret stores.
- [ ] Keep the private `ops` schema outside the Data API. If the Data API is
  enabled elsewhere, do not expose `ops`.
- [ ] Approve separate database and object-byte backup and recovery methods.
- [ ] Identify who may execute and approve database migrations.
- [ ] Confirm that cloud integration cleanup is limited to a generated
  `_integration/<run-id>/` prefix in the derived bucket.
- [x] Defer Supabase S3 protocol access and S3 credentials. The planned primary
  adapter uses the standard Storage API.

Never provide a Supabase secret/service-role key to browser code.

## Phase 4 MLflow prerequisites

- [ ] Approve the local or remote tracking topology.
- [ ] For a remote registry, approve a dedicated database-backed backend.
- [ ] Approve the artifact-store path and its backup policy.
- [ ] Define model approvers and immutable approval evidence.

## Phase 6 deployment prerequisites

- [ ] Choose a staging target.
- [ ] Define a production target or explicitly limit the project to staging.
- [ ] Define the model-promotion and deployment approvers.
- [ ] Configure protected deployment environments separately from CI.
- [ ] Approve rollback ownership and recovery objectives.

## Phase 8 agent prerequisites

- [ ] Select an LLM provider and approve its data-handling terms.
- [ ] Store provider credentials in an approved secret store.
- [ ] Define tool allowlists, rate/cost limits, and kill-switch ownership.
- [ ] Approve what data may leave the environment.
- [ ] Approve evaluation tasks before observing agent results.

## Phase 9 dashboard prerequisites

- [ ] Identify intended users and whether the dashboard is public.
- [ ] Decide whether Supabase Auth is necessary.
- [ ] If authentication is used, define roles in server-controlled
  `app_metadata`, not user-editable metadata.
- [ ] Decide whether Realtime offers a measured benefit over polling/replay.

## Prohibited manual actions

- Do not provision paid resources without explicit approval.
- Do not manually edit generated migrations or cloud state outside the recorded
  workflow.
- Do not upload unvalidated models to a production registry.
- Do not make a failed required check optional to merge a phase.
- Do not treat a local test as evidence that GitHub Actions passed.
