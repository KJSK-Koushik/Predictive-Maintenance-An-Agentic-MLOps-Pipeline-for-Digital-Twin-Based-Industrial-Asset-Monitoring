# Phase 4 Completion Report

## Status

**APPROVED**

Planning was authorized by `PLAN PHASE 4` and implementation by
`START PHASE 4` on 2026-08-14. Every acceptance criterion passed. The owner
issued `APPROVE PHASE 4` on 2026-08-14.

## Delivered scope

- Read-only loading of one explicit `fd001-candidate-features-v1` snapshot,
  including raw/processed/feature state, lineage, manifest, membership, size,
  SHA-256, Parquet schema, key alignment, and target checks.
- One canonical seeded engine split shared by both tasks: 80% of NASA training
  engines for fit, 20% for validation, and NASA test engines for final holdout.
- Median dummy and scaled fixed Ridge models for uncapped RUL.
- Prior dummy and scaled class-balanced fixed logistic models for inclusive
  30-cycle risk at threshold 0.5.
- Engine-balanced primary metrics, pooled and lifecycle/final-cycle secondary
  evidence, calibration/confusion/residual evidence, and prediction digests.
- Explicit local MLflow parent/child runs, aggregate reports, signatures,
  constructed schema-only examples, and verified `skops` artifacts.
- Direct sanitized `train-fd001-baselines` CLI and credential-free CI growth.

No tuning, registry version, alias, promotion, serving, deployment, monitoring,
retraining, agent, dashboard, Supabase mutation, or paid resource was added.

## Exact actual-FD001 evidence

| Item                 | Value                                                              |
| -------------------- | ------------------------------------------------------------------ |
| Raw snapshot         | `17d1db8dd823266b58b9c8d5b6da8edace17220980b733188756cd6b630e453d` |
| Processed snapshot   | `6ccb5b0df0e22e606f77bdb07658fd3b4e55869a9db1454e5db60cdc84614960` |
| Feature snapshot     | `84bbbff75f2e96cae055bd490c85da76ab0fe542763b50795ec85a99345d3eb0` |
| Split manifest       | `acce2be62a3d0e29e0a00c0567d2b33eb3f14f206e2acc52e32d81e19b93faed` |
| Source-train         | 20,631 rows; 100 engines                                           |
| Source-test          | 13,096 rows; 100 engines                                           |
| MLflow experiment    | `1`; local-only                                                    |
| Parent run           | `27fe5e1360db430d982867d8a8983fae`                                 |
| Regression candidate | `4d1d155dd2ee4d5fbd3e4d833d87a608`                                 |
| Classification model | `789f8447024b4687a468625e09982c1c`                                 |
| Local evidence size  | 1,075,115 bytes across 20 files                                    |

The retained run used a dirty working tree because it was produced before the
completion commit; the run records that fact. The clean completion commit is
validated separately by CI rather than misrepresenting this local run.

## Actual validation and final-holdout metrics

| Task           | Model     | Validation primary | Final test primary | Other final evidence               |
| -------------- | --------- | -----------------: | -----------------: | ---------------------------------- |
| RUL regression | Dummy     |       RMSE 63.4748 |       RMSE 64.6918 | Pooled RMSE 70.2892                |
| RUL regression | Candidate |       RMSE 36.3691 |       RMSE 44.0899 | Pooled RMSE 48.3773                |
| Failure risk   | Dummy     |         AP 0.15898 |         AP 0.01947 | Pooled AP 0.02535; ROC-AUC 0.5000  |
| Failure risk   | Candidate |         AP 0.96279 |         AP 0.76784 | Pooled AP 0.78990; ROC-AUC 0.98896 |

Both fixed candidates passed their predeclared relative validation gates. The
metrics are simulated FD001 research results, not production, physical-engine,
real-time, digital-twin, or autonomous-maintenance evidence.

## Local validation evidence

| Gate                         | Result                                                                 |
| ---------------------------- | ---------------------------------------------------------------------- |
| Unit/local/integration suite | 209 passed; 13 owner/later-environment tests deselected                |
| Branch-aware coverage        | 90.17%; required threshold 90%                                         |
| Real MLflow integration      | Log/query/load/parity/empty-registry/copy/restore passed               |
| Actual FD001 integration     | 1 passed in 39.03 seconds                                              |
| Actual direct tracked run    | 21.71 seconds; both candidates eligible                                |
| Strict typing                | 80 source/test files passed                                            |
| PostgreSQL 17                | Disposable local service healthy; existing tests passed                |
| MLflow runtime               | Loopback `127.0.0.1`; SQLite; local proxied artifacts                  |
| Docker/Airflow regression    | Image build, service health, and 6 retry/backfill tests passed         |
| Static/security gates        | Ruff, lock, Markdown, YAML, and audit passed; no known vulnerabilities |
| GitHub Actions               | Run `31773869033`, job `Phase 4 quality`, passed in 4m58s              |
| Versions                     | Python 3.11.9; NumPy 2.4.6; sklearn 1.9.0; skops 0.14.0; MLflow 3.15.1 |

The Windows checkout converts YAML files to CRLF, while the repository and CI
expect LF. YAML, Python, and Markdown formatting therefore also passed from a
clean LF-preserving local checkout. The Linux GitHub runner independently
passed the same required gates.

## Security and dependency decision

The full MLflow 3.15.1 metapackage was rejected because it constrains
`cryptography<50`; `pip-audit` identifies 49.0.0 as affected by
`PYSEC-2026-3552`, fixed in 50.0.0. The implemented topology uses the official
lightweight MLflow packages plus its published server dependencies and retains
`cryptography==50.0.0`. No vulnerability waiver is used.

Model loading is limited to exact run-owned artifacts after provenance,
SHA-256, signature, and trusted-type inspection. No pickle, joblib, or
cloudpickle loading path is provided.

## Known limitations and deferred work

- FD001 is simulated and represents one operating condition and fault mode.
- The split is one seeded holdout, not a tuned or cross-validated comparison.
- The linear candidates have no formal uncertainty or advanced explainability.
- MLflow is a single-user local process with no TLS, authentication, remote
  backup, or availability claim.
- Absolute promotion thresholds, tuning, ensembles, neural models, clustering,
  anomaly analysis, and deeper error analysis remain Phase 5 decisions.
- Registry, promotion, serving, and deployment remain Phase 6 work.

## GitHub and approval evidence

Implementation commit `a70ebf6abaaa7320023a7c57671586bbc5971121` passed
required GitHub Actions run `31773869033` in 4 minutes 58 seconds. Completion
commit `2138b187c7d33ca195abc56b343aa11cfb2448ac` independently passed run
`31774309963` in 4 minutes 56 seconds. Branch protection requires the strict
`Phase 4 quality` check, enforces administrators and resolved conversations,
and disables force pushes and branch deletion.

Phase 4 is owner-approved. Stop completely and wait for the only permitted
next phase-control command: `PLAN PHASE 5`.
