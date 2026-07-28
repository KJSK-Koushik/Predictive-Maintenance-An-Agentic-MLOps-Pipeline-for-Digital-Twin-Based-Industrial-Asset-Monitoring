# Phase 2 Completion Report

## Status

**COMPLETE — AWAITING OWNER APPROVAL**

Phase 2 acceptance criteria are satisfied. Phase 3 has not been planned or
started.

## Authorization and target safety

`PLAN PHASE 2` was received on 2026-07-25 and `START PHASE 2` on 2026-07-26.
On 2026-07-28 the owner confirmed the exact Supabase development/test project
and instructed the implementation owner to finish Phase 2. The confirmed
project was healthy on the Free plan in Singapore (`ap-southeast-1`); no paid
resource or IPv4 add-on was provisioned.

A read-only preflight found:

- no application table outside provider-managed schemas;
- no Storage bucket or object;
- no Auth user; and
- no migration history.

No project reference, private endpoint, credential, signed URL, or raw dataset
content is recorded in this report.

## Delivered foundation

- one CLI-generated, forward-only PostgreSQL migration;
- a private `ops` schema with five Phase 2 tables;
- explicit grants, RLS policies, and a restricted no-login runtime role;
- private raw and derived Supabase Storage buckets;
- content-addressed raw keys and application-enforced overwrite denial;
- filesystem and Supabase Storage adapters with the same narrow contract;
- transactional snapshot, object, file, lineage, and ingestion-run metadata;
- idempotent publication and partial-failure recovery;
- missing, mismatched, and orphan reconciliation;
- separate database-metadata and Storage-byte recovery procedures; and
- CI gates for migrations, containers, security, recovery, coverage, and
  ordinary engineering quality.

No transformation, processed dataset, feature generation, Airflow component,
model, MLflow integration, service, monitoring job, agent, or dashboard was
implemented.

## Local and Docker evidence

Evidence recorded on 2026-07-28:

| Evidence                       | Result                                                             |
| ------------------------------ | ------------------------------------------------------------------ |
| Runtime                        | Python 3.11.9; `uv` 0.11.8                                         |
| Migration tooling              | Supabase CLI 2.109.1                                               |
| Container                      | PostgreSQL 17; loopback-only disposable Compose service            |
| Compose configuration/start    | Passed; health-based startup                                       |
| Full non-cloud suite           | 125 passed; 2 hosted tests deselected                              |
| CI-compatible suite            | 123 passed; 4 dataset/cloud tests deselected                       |
| Actual FD001 local publication | Passed                                                             |
| PostgreSQL integration         | 18 passed                                                          |
| Migration reset/reapply        | Equivalent schema fingerprints passed                              |
| Recovery                       | `pg_dump`, restore database, object restore, reconciliation passed |
| Product coverage               | 90.82% branch-aware                                                |
| Formatting and lint            | Ruff passed                                                        |
| Static typing                  | Strict mypy passed for 37 source files                             |
| Dependency lock                | `uv sync --locked` and `uv lock --check` passed                    |

The local PostgreSQL and filesystem evidence is not reported as hosted
Supabase evidence.

## Hosted Supabase evidence

The approved hosted development/test project passed:

- migration history version `20260726144446` with name
  `phase_02_cloud_metadata`;
- exactly five private `ops` tables with RLS enabled;
- no operational schema access for `PUBLIC`, `anon`, or `authenticated`;
- a restricted runtime role with `ops` usage;
- no Phase 2 custom table in `auth`, `storage`, or `realtime`;
- private `pm-raw` and `pm-derived` buckets;
- five accepted raw FD001 objects in `pm-raw`;
- zero durable objects in `pm-derived`;
- download and SHA-256 verification of every raw object;
- exact Storage rerun reuse;
- different-byte overwrite denial;
- one dataset snapshot, five object records, four snapshot-file links, four
  manifest lineage edges, and one available ingestion run;
- an idempotent metadata retry that created no duplicate;
- zero missing metadata objects and zero raw-prefix orphans; and
- cleanup limited to the generated derived `_integration/<run-id>/` object.

The hosted Storage adapter initially exposed a real compatibility defect:
duplicate uploads are currently reported as status `409`, while the adapter
recognized only the older wrapped `400` form. The adapter now accepts either
status only when the error identifies an existing object, then downloads and
rehashes the stored bytes. The regression test passes locally and on GitHub.

## Advisor and severity evidence

Supabase Security Advisor returned no findings.

Supabase Performance Advisor returned five informational findings:

- one unindexed foreign key on the snapshot manifest reference; and
- four unused-index notices on a newly created, very small dataset.

These are `INFO`, not critical or high severity. The unused-index notices are
expected before Phase 3 query workloads exist. Index changes are deferred until
measured access patterns justify them. No critical or high-severity issue
remains unresolved.

## Backup and recovery evidence

Database metadata and Storage bytes are treated as separate recovery assets.
The local recovery integration test restored an `ops` dump and separately
restored object bytes before reconciliation.

The real hosted Storage export downloaded all five raw objects, covering
5,748,146 bytes, and verified every SHA-256. The temporary export copy was
removed; durable raw objects were untouched. The Free project reported no
provider-managed downloadable backup. The approved ongoing procedure is to:

1. export `ops` with `pg_dump` from an IPv6-capable host or the Supavisor
   session pooler;
1. encrypt and hash the database export;
1. separately download Storage objects with a bucket/key/size/SHA-256
   manifest; and
1. restore into disposable targets and reconcile before replacing governed
   state.

## GitHub CI evidence

GitHub Actions run
[`30329590112`](https://github.com/KJSK-Koushik/Predictive-Maintenance-An-Agentic-MLOps-Pipeline-for-Digital-Twin-Based-Industrial-Asset-Monitoring/actions/runs/30329590112)
passed for commit `f9dbbdc`. The required `Phase 0 quality` job passed every
step, including locked dependencies, formatting, linting, strict typing,
Compose validation, PostgreSQL startup, unit, integration, migration/recovery,
coverage, Markdown, YAML, dependency audit, and cleanup.

The job name is historical; its Phase 2 steps and evidence are current.
Ordinary CI contains no cloud credential and performs no deployment.

## Known limitations and deferred work

- This workstation could not open outbound PostgreSQL ports `5432` or `6543`.
  Hosted PostgreSQL was therefore exercised through authenticated,
  project-scoped Supabase migration and SQL tools. The Python direct-PostgreSQL
  adapter is proven against PostgreSQL 17 locally but is not claimed as a
  hosted adapter test.
- Raw immutability is application-enforced, not WORM. A privileged project
  administrator can still replace or delete objects.
- The Free plan has no recorded downloadable provider backup; external
  database and Storage exports remain operational responsibilities.
- Processed and feature zones are reserved but empty. Their formats and ETL
  belong to Phase 3.
- The performance advisor information findings are deferred until workload
  evidence exists.

## Handoff

Phase 2 is complete and no Phase 3 work has started.

Required owner command:

`APPROVE PHASE 2`
