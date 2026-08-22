# ADR 0029: Loopback staging, CI separation, and rollback

## Status

Accepted

## Date

2026-08-22

## Context

Phase 6 must prove deployability and recovery without inventing a production
environment. Pull-request CI must validate packaging and containers without
credentials or authority to promote the actual selected models.

## Decision

Use Docker Compose as the owner-workstation staging target, bound only to
`127.0.0.1`. The image uses a digest-pinned Python 3.11 base, lock-derived
runtime requirements, a non-root user, one immutable release, an exec-form
command, and a readiness health check. Compose adds a read-only filesystem,
temporary `/tmp`, dropped capabilities, no-new-privileges, and bounded CPU,
memory, and process counts.

Pull-request CI builds and tests only a deterministic synthetic release and
has no cloud credentials or deployment authority. A separate manual workflow
uses the protected `staging` GitHub environment and accepts only a SHA-256
release ID plus the sole target `staging`. The actual FD001 release remains a
separate owner-approved local operation. A bad candidate is tested before
switching; rollback restores the recorded previous immutable pair and must be
measured against the five-minute local objective.

## Consequences

Local loopback validation proves packaging, HTTP behavior, container startup,
and recovery mechanics only. It does not prove TLS, public authentication,
autoscaling, SLA, high availability, production safety, or field performance.
The protected workflow cannot be claimed as passed until it is present on the
default branch and is actually approved and run.

## Alternatives

- Deploy from pull-request CI: rejected because code checks cannot approve a
  model or deployment.
- Publish a public staging API: rejected because authentication and ingress are
  outside this phase.
- Add Kubernetes: rejected as unnecessary complexity for the approved target.
- Configure a dormant production target: rejected because fail-closed absence
  is safer and clearer.

## Verification

Compose configuration, image inspection, loopback binding, synthetic startup,
readiness, OpenAPI, invalid-input behavior, direct/container parity, corrupted
candidate denial, explicit rollback, and workflow-contract tests provide the
Phase 6 evidence. GitHub and actual-release results are recorded separately.
