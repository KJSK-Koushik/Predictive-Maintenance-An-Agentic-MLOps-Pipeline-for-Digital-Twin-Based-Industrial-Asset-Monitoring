# ADR 0033: Audit container dependencies and use minimal Airflow

## Status

Accepted

Phase 7 security remediation is authorized within the current phase. Real
Airflow and actual/synthetic inference checks are recorded separately below.

## Date

2026-10-24

## Context

The refreshed development environment passes pip-audit, but that does not prove
the separately installed container environments are safe. An explicit inventory
audit of the existing full Airflow 3.3.0 image found 187 advisory records across
29 packages. Some records are aliases/duplicates, not distinct vulnerabilities.
Unused provider integrations also brought unnecessary cloud, SSH, and LLM
dependencies into the orchestration image.

## Decision

Use the official slim Airflow 3.3.2 Python 3.11 image pinned by its registry
manifest digest. Add only the existing project's required packages and targeted
security fixes. Keep LocalExecutor, loopback access, private application
credentials, thin DAGs, and the same data contracts. Do not add new providers,
agents, services, or production authority.

Audit the installed Python package inventories of both built application images,
separately from the development lock. Fail CI on known dependency findings.
Run pip compatibility checks and all existing ETL, retry, backfill, monitoring,
and inference smoke tests after remediation. Back up the disposable local
Airflow database before its patch-version migration. Hosted application schemas
and approved model releases are not changed by this repair.

This supersedes only the active Airflow image/version choice in ADR 0020.
Historical completion evidence is not rewritten as if it used the newer image.

## Consequences

The DAG runtime imports project source through an explicit `PYTHONPATH`. It
does not install misleading full-project package metadata while deliberately
omitting MLflow/serving-only dependencies. Its installed third-party packages
must still pass pip compatibility and advisory checks. The inference image
continues to own the separate exact model-serving dependency set.

## Alternatives

- Keep the full image and ignore unused vulnerable packages: rejected.
- Install every project training/registry dependency in the DAG runtime:
  rejected because these tools do not belong to scheduled monitoring.
- Treat a development-environment audit as a container audit: rejected because
  these environments have different installed package inventories.

## Verification

Installed-image inventories, advisory audit JSON, pip compatibility results,
image identifiers, and real DAG/container regression results are recorded in
ignored validation artifacts and the Phase 7 completion report. The Airflow
image (164 packages), synthetic inference image (31), and approved actual
inference image (31) passed compatibility and Python advisory audits with zero
known findings. All 10 real Airflow tests passed after remediation. The actual
same-release staging repair was explicitly owner-approved and passed exact
release, API, and prediction parity on 2026-10-25. Required GitHub Actions run
`40100809272` also passed both new installed-image audit gates. Acceptance of
this decision is not approval for a new model or production deployment.

## Limits

pip-audit checks published Python advisories. It is not an OS-image, native
library, penetration-test, or production-security certification. A known finding
cannot be silently ignored to close Phase 7.

## References

- [Official slim image documentation](https://airflow.apache.org/docs/docker-stack/index.html)
- [Airflow security patch policy](https://airflow.apache.org/docs/apache-airflow/stable/security/releasing_security_patches.html)
- [Airflow 3.3.2 release announcement](https://airflow.apache.org/announcements/)
