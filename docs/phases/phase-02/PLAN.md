# Phase 2 Plan

## Authorization

Planning was authorized on 2026-07-25 by explicit `PLAN PHASE 2`.
Implementation was authorized on 2026-07-26 by explicit `START PHASE 2`.
The exact development/test project was subsequently confirmed, and the owner's
2026-07-28 command to finish Phase 2 authorized the phase-scoped hosted
mutation. The confirmed project remained on the Free plan; no paid resource or
add-on was provisioned.

## Objective

Implement and exercise the minimal cloud data foundation that persists the
accepted FD001 raw snapshot and its operational metadata with deterministic
identity, idempotency, lineage, reconciliation, and honest local-versus-cloud
evidence.

## Work breakdown after start authorization

1. Confirm the exact Supabase development/test project and record a sanitized
   target identity.
1. Pin the Supabase CLI and Python cloud/PostgreSQL dependencies after checking
   current official releases.
1. Initialize only the repository-owned Supabase configuration and generate
   migration filenames through the CLI.
1. Add the private `ops` schema migration, least-privilege role, constraints,
   grants, and RLS checks.
1. Add a PostgreSQL 17 local container and clean migration-apply validation.
1. Define narrow typed object and metadata repository protocols.
1. Implement the filesystem object substitute and PostgreSQL metadata adapter.
1. Implement the Supabase Storage adapter using non-upsert uploads and
   download-based SHA-256 verification.
1. Implement publication ordering, idempotent reuse, partial-failure behavior,
   and reconciliation.
1. Add a sanitized CLI for publishing the accepted Phase 1 snapshot.
1. Add unit, migration, security, local integration, concurrency, and failure
   tests alongside implementation.
1. Exercise the approved cloud namespace with synthetic integration content and
   the owner-approved FD001 snapshot.
1. Run Supabase Security and Performance Advisors and resolve all introduced
   critical/high findings.
1. Exercise and document the approved metadata/object backup and recovery
   procedure.
1. Expand CI with migration, container, secret, and local integration gates
   without adding cloud credentials or deployment authority.
1. Update architecture, security, data-contract, manual-prerequisite, test, and
   completion evidence.

## Expected implementation files

```text
compose.yaml
supabase/
  config.toml
  migrations/
src/predictive_maintenance/cloud/
  __init__.py
  config.py
  models.py
  object_store.py
  metadata.py
  publication.py
  cli.py
tests/
  cloud/
  integration/postgres/
  integration/supabase/
```

Existing files expected to change include:

```text
.env.example
.github/workflows/ci.yml
.gitignore
README.md
pyproject.toml
uv.lock
docs/DATA_CONTRACT.md
docs/MASTER_ARCHITECTURE.md
docs/MANUAL_PREREQUISITES.md
docs/SECURITY_AND_SECRETS.md
docs/TEST_STRATEGY.md
docs/PROJECT_STATUS.md
docs/adr/
docs/phases/phase-02/
tests/foundation/test_repository_contract.py
tests/integration/test_ci_contract.py
```

The exact module list may be reduced if the responsibilities remain clear.
Phase 2 will not introduce a generic storage framework, an ORM, an event broker,
or a service process.

## Architecture decisions to record

Implementation must add or update ADRs for:

1. two private buckets versus one bucket with prefixes;
1. Supabase Storage API as the primary Phase 2 adapter and S3 protocol deferral;
1. private `ops` schema, direct PostgreSQL access, and Data API non-exposure;
1. forward-only migration and clean-reset verification strategy;
1. snapshot ID as the idempotency identity;
1. staged object/database publication and reconciliation after partial failure;
1. application-enforced raw overwrite/deletion denial rather than WORM; and
1. separate database and object-byte backup/recovery.

Related choices may be combined into a small number of focused ADRs.

## Documentation basis

Current official Supabase guidance confirms:

- standard uploads reject an existing path unless upsert is enabled;
- private buckets are the default;
- service/secret and S3 access keys bypass Storage RLS and remain server-side;
- S3 versioning, object lock, and several checksum headers are unsupported;
- Data API grants and RLS are separate controls;
- new public tables are moving to explicit Data API grants;
- custom objects must not be created in managed `auth`, `storage`, or
  `realtime` schemas; and
- local CLI behavior can differ from the hosted platform, so real cloud
  verification remains mandatory.

## CI growth

Phase 2 CI will add:

- clean migration apply against PostgreSQL 17;
- database constraint, role, grant, and RLS tests;
- filesystem object contract and PostgreSQL integration tests;
- partial-failure, retry, conflict, and reconciliation tests;
- Docker Compose startup, health, and cleanup validation;
- secret scanning suitable for new cloud configuration; and
- the existing formatting, linting, strict typing, coverage, lock, dependency,
  documentation, and least-privilege workflow checks.

The `cloud` test marker is excluded from pull-request CI. No Supabase secret is
added to ordinary CI. Cloud results are run deliberately and recorded
separately.

## Completion conditions

Every item in `ACCEPTANCE_CRITERIA.md` must pass. Local substitutes, PostgreSQL
container evidence, real Supabase evidence, migration history, advisors,
backup/recovery exercise, GitHub Actions, documentation, and severity review
are all required.

## Planning risks

| Risk                                             | Planned treatment                                                              |
| ------------------------------------------------ | ------------------------------------------------------------------------------ |
| Wrong or valuable Supabase project is modified   | Require explicit target confirmation and a development/test-only preflight     |
| Inactive project activation creates cost         | Require owner approval before reactivation or provisioning                     |
| Object upload succeeds but metadata commit fails | Reuse content-addressed orphan objects and reconcile; never assume atomicity   |
| Service secret bypasses Storage RLS              | Backend-only secret, narrow adapter, no delete/upsert interface, redacted logs |
| Raw object is overwritten or deleted             | Unique content key, upsert disabled, conflict tests, no normal deletion method |
| Storage lacks versioning/object lock             | Honest application-enforced controls plus separate backup/recovery             |
| Local substitute differs from Supabase           | Separate real cloud test; never promote substitute evidence                    |
| Data API exposes internal metadata               | Private schema, explicit revokes, no exposed schema, catalog tests             |
| Managed Supabase schema is changed directly      | Keep custom objects in `ops`; use Storage APIs for buckets/objects             |
| Migration drift is hidden                        | CLI-generated migration, clean apply/reset, migration-list comparison          |
| Cloud test cleanup deletes durable data          | Cleanup only a generated derived integration prefix; never raw                 |
| Phase 3 ETL leaks into Phase 2                   | Derived zones remain empty except synthetic integration evidence               |
