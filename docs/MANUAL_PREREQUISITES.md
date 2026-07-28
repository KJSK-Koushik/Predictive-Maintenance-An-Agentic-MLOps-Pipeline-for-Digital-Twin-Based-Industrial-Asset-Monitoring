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

Phase 2 hosted prerequisites were completed on 2026-07-28. The exact
development/test project was confirmed through both the dashboard and the
project-scoped connector. A read-only preflight found no application tables,
Storage buckets or objects, Auth users, or migration history. The project was
healthy on the Free plan in Singapore (`ap-southeast-1`); no paid resource or
IPv4 add-on was provisioned. No project reference or private endpoint is
recorded in this repository.

- [x] Confirm the exact Supabase development/test target.
- [x] Confirm that the target contains no valuable or production data.
- [x] Approve phase-scoped cloud mutation with no paid provisioning.
- [x] Confirm the project region and retain the accepted raw snapshot until a
  separately approved retention operation.
- [x] Approve `pm-raw` and `pm-derived` as configurable private bucket names.
- [x] Approve uploading the accepted FD001 raw snapshot after the synthetic
  Storage probe passed.
- [x] Record the project URL, database URL, secret key, and database
  credentials only in ignored local configuration or approved secret stores.
- [x] Keep the private `ops` schema outside the Data API. If the Data API is
  enabled elsewhere, do not expose `ops`.
- [x] Approve separate database-metadata and object-byte backup methods.
- [x] The project owner approves migrations; the implementation owner executes
  only the reviewed repository migration during an active phase.
- [x] Confirm that cloud integration cleanup is limited to a generated
  `_integration/<run-id>/` prefix in the derived bucket.
- [x] Defer Supabase S3 protocol access and S3 credentials. The planned primary
  adapter uses the standard Storage API.

Never provide a Supabase secret/service-role key to browser code.

### Phase 2 local validation

The local database is disposable and binds only to loopback port `55432`.
PowerShell commands are:

```powershell
docker compose config --quiet
docker compose up -d --wait postgres
$env:PM_POSTGRES_DSN = "postgresql://postgres:phase2-local-only@127.0.0.1:55432/predictive_maintenance"
uv run pytest -m "not cloud"
docker compose down --volumes
Remove-Item Env:PM_POSTGRES_DSN
```

`docker compose down --volumes` permanently removes only this container's
disposable test metadata. FD001 source files and ignored Phase 1 artifacts are
not mounted into the database container and are not removed.

The local recovery exercise uses this procedure:

1. publish a snapshot to the filesystem substitute and local PostgreSQL;
1. export `ops` rows with `pg_dump --data-only --schema=ops`;
1. create a disposable restore database and apply the repository migration;
1. restore the database dump;
1. copy each object byte stream to a new local object root while rechecking its
   SHA-256 and size;
1. reconcile the restored database and objects; and
1. drop only the disposable restore database.

For hosted recovery, export the private `ops` schema with `pg_dump` from an
IPv6-capable host or the documented Supavisor session pooler, encrypt the
result, and record its SHA-256. Export Storage separately by listing each
approved bucket, downloading every object through the Storage API, and writing
a manifest of bucket, key, byte size, and SHA-256. Restore first into a
disposable PostgreSQL database and disposable object prefix, then run
reconciliation before replacing any governed state. A database backup alone
does not contain Storage bytes.

The Free project reported no provider-managed downloadable backup. Phase 2
therefore records the procedure above, the existing local `pg_dump` restore
exercise, and a real hosted Storage export of five objects with all hashes
verified. The temporary hosted export copy was removed; durable raw objects
were not deleted.

### Phase 2 hosted validation gate

Place values only in an ignored local `.env` or process environment:

```text
APP_ENV=cloud
SUPABASE_URL=<approved-project-url>
SUPABASE_SECRET_KEY=<server-only-secret>
SUPABASE_DB_URL=<direct-postgresql-url>
PM_RAW_BUCKET=pm-raw
PM_DERIVED_BUCKET=pm-derived
PM_CLOUD_TEST_APPROVAL=I_CONFIRM_THIS_IS_THE_APPROVED_PHASE_2_TEST_PROJECT
```

The approval phrase is an accidental-execution guard, not a credential. It
does not replace the explicit project and cost approval in this checklist.
After the migration is deliberately applied to the confirmed project, run:

```powershell
uv run pytest -m cloud
```

Then run the Supabase Security and Performance Advisors and provide the
sanitized results. Do not copy project references, endpoints, credentials, or
signed URLs into the completion report.

The Phase 2 workstation could not open outbound PostgreSQL ports `5432` or
`6543`. Hosted database verification therefore used the authenticated,
project-scoped Supabase migration and SQL tools. Do not purchase the IPv4
add-on solely for this phase. The direct PostgreSQL adapter remains covered by
the PostgreSQL 17 local integration suite.

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
