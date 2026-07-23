# Security and Secrets

## Security objectives

1. Preserve dataset, feature, model, and lineage integrity.
1. Prevent credential disclosure and unauthorized cloud access.
1. Keep model promotion, deployment, and maintenance decisions human-governed.
1. Make data, model, deployment, and agent actions attributable.
1. Fail closed when validation, identity, evidence, or approval is missing.

## Protected assets

| Asset                                   | Primary concern                             |
| --------------------------------------- | ------------------------------------------- |
| Raw datasets and checksums              | Integrity and provenance                    |
| Processed data and features             | Integrity, reproducibility, lineage         |
| Models and evaluation reports           | Integrity and unauthorized substitution     |
| Registry aliases and approvals          | Unauthorized promotion                      |
| Inference inputs/outputs                | Integrity, confidentiality where applicable |
| Operational metadata                    | Integrity and availability                  |
| Supabase and deployment credentials     | Confidentiality                             |
| GitHub tokens and environments          | Confidentiality and authorization           |
| Agent prompts, tools, and audit records | Injection, misuse, non-repudiation          |

## Trust boundaries

- workstation to GitHub;
- GitHub Actions to external services;
- backend services to Supabase;
- MLflow clients to tracking and artifact stores;
- API clients to inference;
- dashboard/browser to exposed application APIs;
- agent runtime to tools and external models; and
- model/agent recommendation to the human decision maker.

## Threat model

| Threat                   | Example                                | Required controls                                                 |
| ------------------------ | -------------------------------------- | ----------------------------------------------------------------- |
| Spoofing                 | Untrusted actor triggers deployment    | Protected identity, environment approval, audit                   |
| Tampering                | Raw file or model artifact is replaced | SHA-256 identity, immutable paths, signed evidence where feasible |
| Repudiation              | Agent or approver denies an action     | Append-only audit event with actor and evidence                   |
| Information disclosure   | Service key appears in CI log          | Secret stores, redaction, least privilege, scanning               |
| Denial of service        | Malformed telemetry exhausts API       | Size limits, schema validation, timeouts, rate limits             |
| Elevation of privilege   | Agent changes production alias         | Tool allowlist, isolated credentials, server-side authorization   |
| Prompt injection         | Report text directs an agent to deploy | Treat content as data, structured tools, no approval capability   |
| Supply-chain compromise  | Dependency or action is replaced       | Lockfile, pinned actions, dependency scanning                     |
| Training poisoning       | Modified source changes model behavior | Source checksum, validation, lineage, approval evidence           |
| Inference/model mismatch | API loads unintended model             | Release manifest, signature validation, startup/readiness checks  |

## Secret classification

### Secrets

- Supabase secret/service-role keys.
- Supabase S3 access key and secret.
- PostgreSQL connection strings containing credentials.
- GitHub tokens beyond the ephemeral runner token.
- Deployment platform tokens.
- LLM provider API keys.
- Signing keys and webhook secrets.

### Configuration, not secrets

- local log level;
- public model/version identifiers;
- public documentation URLs; and
- a Supabase publishable key only when deliberately used with RLS.

Even non-secret project identifiers should not be committed when the owner has
classified the service URL as private.

## Environment-variable policy

- `.env.example` contains names and empty or local-only placeholder values.
- `.env` and all environment-specific variants are ignored.
- Production secrets come from protected environment secret stores.
- Applications validate that required variables exist without printing values.
- Logs must redact authorization headers, credentials, tokens, signed URLs, and
  connection strings.
- Secret rotation must not require a source-code change.

## Supabase controls

- Prefer private, non-exposed schemas for operational and audit data.
- If the Data API is unused, disable it.
- If an API schema is exposed, apply explicit least-privilege grants and RLS to
  every exposed table or view.
- Do not use user-editable metadata for authorization.
- Never expose a secret/service-role key in a client.
- Supabase S3 access keys are server-only and bypass RLS.
- S3 compatibility does not supply versioning or object lock; raw immutability
  is enforced by checksummed object identity, denied overwrites, and audit.
- Use Storage APIs for object operations; do not manipulate storage metadata
  rows as if that also manipulates object bytes.
- Verify grants separately from RLS.
- Prefer `SECURITY INVOKER`; any `SECURITY DEFINER` function requires explicit
  security review and restricted execution.
- Run database advisors and integration tests before accepting migrations.

## Agent controls

| Capability                         | Default                       |
| ---------------------------------- | ----------------------------- |
| Read approved reports/metrics      | Allowed                       |
| Query sanitized metadata           | Allowed                       |
| Draft recommendation               | Allowed in isolated namespace |
| Change source data or labels       | Denied                        |
| Change test or validation outcome  | Denied                        |
| Promote a model                    | Denied                        |
| Deploy or rollback                 | Denied                        |
| Execute maintenance                | Denied                        |
| Access unrestricted shell/database | Denied                        |
| Read secrets                       | Denied                        |

Each agent event records the actor/model, prompt/template version, approved input
references, tool name and arguments with redaction, output, deterministic
validation result, human disposition, cost, and timestamps.

## CI/CD controls

- CI receives read-only repository permissions by default.
- Pull-request CI has no production credentials.
- Actions are pinned to immutable commits.
- Deployment is a separate workflow protected by an environment approval.
- A model is not deployable merely because code checks pass.
- Fork-originated pull requests never receive privileged secrets.
- Required checks may not be silently skipped.

## Incident response

When exposure or tampering is suspected:

1. Stop the affected workflow or service.
1. Revoke/rotate the credential or alias first.
1. Preserve logs and identify the first affected version.
1. Assess data, model, storage, and deployment impact.
1. Restore from a verified artifact or roll back.
1. Add a regression test and update the threat model.
1. Record the incident without copying secret values.

Deleting a secret from Git history does not revoke it.

## Phase 0 verification

Phase 0 performs repository contract tests, dependency auditing, ignored-data
verification, and secret-pattern checks. Cloud controls remain architectural
requirements until their owning phase exercises them.

## References

- [Supabase API security](https://supabase.com/docs/guides/api/securing-your-api)
- [Supabase secure data access](https://supabase.com/docs/guides/database/secure-data)
- [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication)
- [Supabase S3 compatibility](https://supabase.com/docs/guides/storage/s3/compatibility)
