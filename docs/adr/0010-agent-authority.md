# ADR-0010: Agent Authority and Audit Boundary

## Status

Accepted

## Date

2026-07-23

## Context

Agents can synthesize reports and propose investigations, but are
non-deterministic, vulnerable to prompt injection, and capable of tool misuse.
Granting approval or unrestricted mutation authority would undermine safety.

## Decision

Agents are bounded decision-support workers. Default tools are read-only and
operate on approved, sanitized evidence. Any write is limited to a draft
recommendation namespace. Agents cannot edit source data, validation outcomes,
tests, production aliases, deployments, approval records, or maintenance
systems.

Deterministic schemas validate tool inputs and outputs. An append-only audit
records model/prompt version, evidence references, redacted tool calls, result,
cost, guardrail outcome, and human disposition. Rate, cost, and iteration limits
plus a human-controlled kill switch are mandatory.

## Consequences

Agents may be less convenient than unrestricted automation. Recommendations
remain useful because they are attributable and independently testable.
Evaluation must compare against a non-agentic workflow.

## Alternatives

- Autonomous deployment/maintenance agents: rejected as unsafe and unsupported.
- No agents: rejected because bounded agent value is a research question.

## Verification

Phase 8 permission, prompt-injection, schema, denial, audit, and kill-switch
tests must pass before any agent comparison.
