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
- [ ] Confirm GitHub Actions is enabled.
- [ ] Configure branch protection after the first workflow is pushed:
  - require a pull request;
  - require the Phase 0 quality job;
  - prevent merging when it fails;
  - require conversation resolution; and
  - restrict bypass permission to named owners.
- [ ] Provide a successful GitHub Actions run URL or grant access to inspect it.

The repository starts with Python 3.11.9, Git, `uv`, and Docker available
locally. Development tools are installed from the lockfile rather than assumed
globally.

## Phase 1 prerequisites

- [ ] Confirm the authoritative NASA C-MAPSS download source and attribution.
- [ ] Confirm the existing `Data/` files are the intended source copy.
- [ ] Preserve the original archive if available.
- [ ] Do not rename, normalize, or edit the source files manually.
- [ ] Approve which files are in Phase 1 scope; the default is FD001 only.

Phase 1 will compute checksums and inspect content. Phase 0 deliberately does
not.

## Phase 2 Supabase prerequisites

Perform these only after Phase 1 approval and Phase 2 planning:

- [ ] Approve any expected cost and choose a Supabase organization/project.
- [ ] Choose project region and retention expectations.
- [ ] Create separate development/test resources or an approved test namespace.
- [ ] Record the project URL and database/storage credentials only in local
  environment configuration or approved secret stores.
- [ ] Enable S3 protocol access only if the selected adapter needs it.
- [ ] Store S3 access keys server-side; they bypass Storage RLS.
- [ ] Approve an object backup and recovery method because database backups do
  not by themselves protect Storage object bytes.
- [ ] Decide whether the Data API is disabled. If enabled, expose only a
  dedicated API schema with explicit grants and RLS.
- [ ] Identify who may execute and approve database migrations.

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
