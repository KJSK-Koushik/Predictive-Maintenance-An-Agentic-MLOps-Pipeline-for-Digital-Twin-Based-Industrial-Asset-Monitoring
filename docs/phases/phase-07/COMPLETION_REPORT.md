# Phase 7 Completion Report

## Status

**IN PROGRESS**

Planning was authorized by `PLAN PHASE 7` on 2026-08-22. Implementation was
authorized by `START PHASE 7` on 2026-09-07. Phase 6 PR 12 was merged into
`main`, and Phase 7 PR 13 was retargeted from `codex/phase-6` to `main`.
GitHub Actions run `34081887096` passed all 28 steps on exact merge commit
`cdad44f8d3c4347c5aea46bf2e6ccc3381cca68c`. Phase 7 implementation and
validation evidence are still in progress. No model alias, deployment,
production, public-service, or paid-resource action is authorized.

## Implemented outcome

Typed Python monitoring separates data quality, feature shift, prediction
shift, bounded loopback service probes, and delayed-label performance. Canonical
reports, references, windows, investigations, candidate requests, and challenger
evaluations have immutable identities and private persistence. A thin manual
Airflow DAG calls the same direct monitoring path.

Prediction digests, verified target Parquet bytes, and content-addressed feature
manifests protect delayed-label attachment. Mixed release histories and repeated
replay sequences cannot establish persistent drift. Fixed optional RMSE/Brier
baselines belong to the policy identity; no caller boolean can assert degradation.
Unconfigured baselines disable performance-trigger comparison.

Candidates are evaluation-only. The implementation has no automatic training,
registration, alias, deployment, rollback, or production authority. Working UI,
agents, Auth, and Realtime remain excluded.

## Completion evidence

Final validation resumed on 2026-10-24. Docker Desktop 4.90.0 and Linux Engine
29.7.2 are healthy after recoverable runtime-socket folder backups. No factory
reset or Docker volume deletion was used.

| Evidence class                      | Command or check                                                        | Result                                                                                            |
| ----------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Local regression and coverage       | Full credential-free non-dataset selection with branch coverage         | 397 passed in 851.25 seconds; 90.86% branch-aware coverage                                        |
| Local PostgreSQL                    | Included in full selection; migration, role, restore, concurrency tests | 38 passed locally and in implementation CI                                                        |
| Local Airflow                       | `uv run pytest -m "airflow and not dataset and not cloud" -q`           | Slim 3.3.2: 10 passed in 195.98 seconds                                                           |
| Synthetic inference container       | `uv run pytest -m "deployment and not dataset and not cloud" -q`        | 1 passed                                                                                          |
| Approved actual inference container | Same smoke/parity test with the exact approved bundle                   | 1 passed                                                                                          |
| Static typing                       | `uv run mypy src tests`                                                 | 155 files passed                                                                                  |
| Dependency security                 | `uv run pip-audit` and `uv pip check`                                   | No known vulnerabilities; installed dependencies compatible                                       |
| Hosted schema                       | Apply reviewed Phase 7 SQL through project-scoped migration tool        | Applied as hosted version `20261024063026`                                                        |
| Hosted access                       | Six tables, RLS, client-role denial, narrow runtime grants              | Verified using catalog queries                                                                    |
| Hosted Storage                      | Three actual replay report objects                                      | SHA-256/size/download, repeat reuse, conflict denial, anonymous denial, and reconciliation passed |
| Hosted metadata                     | One reference, one window, original/attached report pair                | Recorded through project-scoped SQL; parent identity and object hashes verified                   |

The earlier implementation CI run `34705014305` failed coverage at 88.57%.
It is failure evidence, not completion evidence. After hardening and rejection
tests, [GitHub Actions run 56](https://github.com/KJSK-Koushik/Predictive-Maintenance-An-Agentic-MLOps-Pipeline-for-Digital-Twin-Based-Industrial-Asset-Monitoring/actions/runs/40097053901)
passed on commit `bf46aad45876a3bf0de803ca56866b595dc4fd1d`: 390 coverage-selected
tests, 90.82% branch-aware coverage, 37 PostgreSQL tests, 10 Airflow tests, and
the inference container check. Final policy-baseline and concurrency changes
are commit `8e75925b4393720e0de90767cb2ade0eb96da88d`.
[GitHub Actions run 57](https://github.com/KJSK-Koushik/Predictive-Maintenance-An-Agentic-MLOps-Pipeline-for-Digital-Twin-Based-Industrial-Asset-Monitoring/actions/runs/40097872887)
passed that exact revision: 397 coverage-selected tests, 90.85% branch-aware
coverage, 38 PostgreSQL tests, 10 Airflow tests, and the inference smoke check.
These runs predate the new installed-image security gates and are not evidence
that those later gates passed.

The security refresh updated affected locked transitive dependencies, including
PyJWT 2.15.1, Pillow 13.0.0, GitPython 3.2.1, and aiohttp 3.14.5. Python 3.11.9,
NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.9.0, skops 0.14.0, and MLflow 3.15.1
remain the modeling runtime. The previous local environment is recoverably
backed up under ignored monitoring artifacts.

The challenger evaluator now reuses the Phase 5 cycle-level RMSE/AP metrics,
2,000 whole-engine bootstrap samples, and practical guardrails. Omitted
external checks default to false. Synthetic passing checks remain fixtures;
they do not claim real artifact/security verification for a new challenger.

The hosted direct PostgreSQL adapter is not claimed as exercised: the
connector cannot assume the runtime role. Hosted metadata uses its own scoped
SQL access, while restricted-role adapter behavior is exercised locally.
Supabase Security Advisor reports zero findings. Performance Advisor retains
one earlier Phase 2 unindexed-foreign-key information notice, 26 unused-index
information notices, and one earlier Phase 3 overlapping-policy warning. These
are performance findings, not critical/high security findings. See Supabase's
[foreign-key index guidance](https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys),
[unused-index guidance](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index),
and [overlapping-policy guidance](https://supabase.com/docs/guides/database/database-linter?lint=0006_multiple_permissive_policies).

## Container security remediation

A separate audit of the old full Airflow image found 187 advisory records across
29 packages; the old inference image had 16 records across its three installer
packages (`pip`, `setuptools`, `wheel`). This was not visible in the development
lock audit. These are advisory records, not deduplicated CVE counts.

ADR 0033 replaces the full Airflow image with pinned slim 3.3.2 and a fully
pinned runtime inventory, including its required synchronous/asynchronous
PostgreSQL drivers. The patched image has 164 installed Python packages and
passes pip compatibility and advisory checks with zero known findings. The
patched synthetic inference image has 31 packages and also passes both checks.
Inference model-library versions and all approved model bytes remain unchanged.
The installer-only fix pins pip 26.2.2, setuptools 84.1.0, and wheel 0.47.0.

CI now audits both installed image inventories using a credential-free,
network-isolated inventory container and a separate advisory lookup. It does
not mount workstation credentials. uv 0.13.4 replaces affected older uv in both
workflow installers. The shared workstation binary is not overwritten; local
validation uses the workspace-owned copy under `artifacts/security-tools/`.
The uv certificate-root issue is documented in the
[maintainer advisory](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62).

The disposable local Airflow database was backed up before its patch migration.
The final slim runtime passed all 10 real DAG, retry, backfill, parity, and
idempotency tests in 195.98 seconds. A patched synthetic inference container
also passed the real contract/parity smoke test on a separate loopback port;
the temporary container was then removed. No dataset, model bundle, or unrelated
user container was deleted.

The approved actual staging service has **not** been rebuilt or restarted for
the security patch: owner confirmation is pending. Patched synthetic smoke
evidence does not prove that the old actual running image was repaired.
Until the authorized actual-image repair, real runtime recheck, and final CI
pass, Phase 7 remains in progress.

These are Python advisory checks, not an OS/native-library security audit or a
production-security certification.

## Actual FD001 evidence

The final actual replay used monitoring code commit
`bf46aad45876a3bf0de803ca56866b595dc4fd1d`, the refreshed monitoring lock, and
the unchanged approved release
`e230ac64e5fc3e3dd294067236210904376fe7591f776a25b03a2a6e614ccf22`.
The release package retains its original approved modeling provenance; the
monitoring reference/window bind the monitoring revision separately.

| Field                           | Value                                                              |
| ------------------------------- | ------------------------------------------------------------------ |
| Source                          | Already-observed NASA FD001 test partition; evaluation only        |
| Membership                      | 100 engines, 2,000 rows, maximum 20 rows per engine                |
| Reference                       | `44b2dd7e8b46a0f3c7b291de2452112c15813fe39cffabc9b9aab1ffbde65889` |
| Window                          | `bace708b430133dc2b067161491e046114c2d7cddfe979e1c607450a6bdbdcef` |
| Prediction report               | `e3c62fc1de526c9f6b9d226d481a106d2183f32083a478573e136052660f3f3e` |
| Performance child               | `d061a6cd4df9137c17727bce1e2b33a08b91be0e7b45d08632175c32cc236059` |
| Quality / service / performance | `pass` / `pass` / `pass`                                           |
| Feature / prediction shift      | `alert` / `alert`; distribution change, not failure                |
| Trigger / retraining            | `investigate` / `no_change`; no candidate and no fitting           |
| Repeat                          | Equal report identities; all three publications reused             |

The initial actual replay called the real loopback API. The repeat reused
release-bound prediction/service files so measured latency did not make the
same immutable report change. A fresh independent probe is new service evidence,
not an identity-preserving repeat. `pass` performance means valid metrics were
calculated, not that a new performance-baseline promotion gate passed.

## Hosted evidence and recovery

The reviewed local migration is
`supabase/migrations/20260907042647_phase_07_monitoring.sql`. The hosted connector
recorded the same SQL under migration version `20261024063026`; local history
was not rewritten. All six new tables are private and RLS-enabled; client roles
have no access and the runtime role cannot update or delete them.

Three final actual report/profile objects were uploaded to private `pm-derived`
monitoring prefixes. Download, size/SHA-256 verification, exact reuse,
different-byte conflict rejection, anonymous denial (HTTP 400), and reconciliation
passed. Three earlier historical objects were separately reverified and retained,
not silently deleted as orphans. Hosted totals are two references, two windows,
four reports, and six verified objects. Repeating scoped metadata SQL left these
counts unchanged; parent links, target digest, and report/object hashes match.

An earlier object-success/metadata-denial case (the connector could not assume
the runtime role) was recovered through reviewed scoped SQL, retaining the
verified objects. This is manual hosted recovery evidence, not an exercised
hosted runtime-role adapter or automatic hosted database retry. Local restricted
adapter, injected retry, reconciliation, and database/object recovery tests
remain separate evidence classes.

No actual candidate or challenger was fabricated merely to populate cloud
tables. Their passing/failing/blocked mechanics and metadata persistence are
synthetic/local evidence only.

## Reproduction commands

```powershell
uv sync --locked --dev
uv lock --check
uv run --no-sync ruff format --check .
uv run --no-sync ruff check .
uv run --no-sync mypy src tests
docker compose config --quiet
docker compose up -d --wait postgres
$env:PM_POSTGRES_DSN='postgresql://postgres:phase2-local-only@127.0.0.1:55432/predictive_maintenance'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
uv run --no-sync pytest -m 'not dataset and not airflow and not cloud and not deployment' --cov=src/predictive_maintenance --cov-branch --cov-report=term-missing --cov-report=json:artifacts/monitoring/coverage-phase7.json --cov-fail-under=90 -q
docker compose build airflow
$env:PM_SOURCE_SNAPSHOT_ID='a793898150be06e5079dc92a327ab3abe298ca5f3198c10aa9c0745f840b87e2'
$env:PM_CODE_REVISION='phase3-local'
docker compose up -d --wait airflow
uv run --no-sync pytest -m 'airflow and not dataset and not cloud' -q
uv run --no-sync pytest -m 'deployment and not dataset and not cloud' -q
uv run --no-sync mdformat --check README.md CONTRIBUTING.md docs
uv run --no-sync yamllint .
uv run --no-sync pip-audit
uv pip check
```

The approved actual bundle is supplied through ignored
`PM_CONTAINER_RELEASE_DIR` and `PM_RELEASE_ID`; the synthetic CI bundle is
tested separately. Actual replay command:

```powershell
uv run --no-sync python tests/integration/monitoring/run_actual_fd001_replay.py --release-dir $env:PM_CONTAINER_RELEASE_DIR --expected-release-id $env:PM_RELEASE_ID --code-revision bf46aad45876a3bf0de803ca56866b595dc4fd1d --output-dir artifacts/monitoring/actual-fd001-final-20261024
```

The guarded hosted publisher uses ignored `.env`, an explicitly supplied
approved project reference, `--publish-approved-phase7`, and optional prior
Storage evidence. It generates SQL for separate review; it does not assume or
grant a wider database role. Outputs remain ignored:

```text
artifacts/monitoring/actual-fd001-final-20261024/summary.json
artifacts/monitoring/actual-fd001-final-20261024/object-store/
artifacts/monitoring/hosted-phase7-final/storage-evidence.json
artifacts/monitoring/hosted-phase7-final/record-evidence.sql
artifacts/monitoring/coverage-phase7.json
```

Final local product coverage, repaired Airflow, patched synthetic inference,
and installed-image audits have passed. Actual staging security-patch approval
and completion GitHub Actions evidence remain pending.

## Known limitations and deferred work

- FD001 is static simulated telemetry, not a live source.
- NASA test results were already observed in earlier phases.
- FD001 supplies no genuinely new approved training population after Phase 5.
- The active service is loopback staging only.
- Phase 6 PR 12 is merged and its exact merged-revision CI run passed.
- Working UI, agents, production, public ingress, Auth, and Realtime remain
  outside Phase 7.

## Required next command

Owner action required: `APPROVE LOCAL STAGING SECURITY PATCH` to rebuild/restart
only the existing loopback staging container, preserving the exact already
approved model release. This is not approval for a new model, alias, cloud
deployment, public endpoint, or production operation.

After that repair, verify actual smoke/parity and the exact final GitHub check,
then request `APPROVE PHASE 7`. Phase 8 has not been planned or implemented.
