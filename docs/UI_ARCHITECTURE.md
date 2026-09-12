# UI Architecture

## Status

This is an early, technology-neutral UI design. It defines what the dashboard
should communicate and which backend contract each screen depends on. It is not
a working UI and does not prove a backend integration.

The working dashboard remains Phase 9. Phase 6 may refine these designs while
it stabilizes model-release and inference contracts, but it must not add a
frontend framework, browser bundle, dashboard service, or live screen.

## Delivery rule

Every screen follows this order:

1. **Design**: define the user question, information hierarchy, states, safety
   wording, and accessibility behavior.
1. **Contract draft**: document the proposed backend fields, errors, freshness,
   authorization, and version.
1. **Contract stable**: implement and validate the backend contract in its
   owning phase.
1. **Connect**: connect the screen only after the contract is stable.
1. **Verify**: exercise the real screen-to-backend path and record the evidence.

A screen must not skip from design to connection. Static examples or mock data
may support design review, but they must be visibly labelled `DESIGN ONLY` and
cannot be reported as integration evidence.

## Meaning of a stable backend contract

A backend contract is stable enough for UI connection only when:

- its owning phase is implemented and owner-approved;
- the request, response, event, or read-model schema is versioned;
- field meaning, units, nullability, ordering, freshness, and provenance are
  documented;
- success, empty, stale, partial, unauthorized, unavailable, and error states
  are defined where relevant;
- deterministic validation and contract tests pass;
- at least one non-mocked integration test passes;
- the required GitHub Actions checks pass on the accepted commit; and
- security, permissions, logging, and failure behavior are documented.

Changing a stable contract incompatibly requires a new version. A UI may not
silently guess how to interpret a changed field.

## Product wording

The UI represents an **asset-health digital shadow** built from NASA C-MAPSS
cycle-level replay. It must not imply a live physical engine, bidirectional
control, hard real-time telemetry, autonomous maintenance, or safety
certification.

The shell must keep these facts visible:

- `Research prototype`;
- `FD001 simulated telemetry`;
- environment such as `Local staging`;
- last processed cycle and data freshness;
- immutable model release ID; and
- human approval status for maintenance recommendations.

## Navigation and information architecture

```text
Asset Health
├── Fleet Overview
├── Asset Detail
├── Monitoring
├── Maintenance Decisions
├── Models & Releases
└── Audit & Evidence
```

The browser must not read private `ops`, `twin`, or `audit` schemas, Supabase
Storage, or MLflow directly. Phase 9 will expose the smallest versioned read
contract required for each screen. Optional authentication is decided before
any non-loopback dashboard access.

## Shared shell

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Asset Health · Research prototype    FD001 replay    Local staging      │
│ Data cycle: <cycle> · Updated: <time> · Release: <short release ID>      │
├──────────────────┬───────────────────────────────────────────────────────┤
│ Fleet Overview   │                                                       │
│ Asset Detail     │                  Active screen                        │
│ Monitoring       │                                                       │
│ Maintenance      │                                                       │
│ Models/Releases  │                                                       │
│ Audit/Evidence   │                                                       │
└──────────────────┴───────────────────────────────────────────────────────┘
```

The global environment, freshness, and release indicators remain visible while
moving between screens. Red, amber, and green may support meaning but cannot be
the only signal; every state also needs text and an icon or pattern.

## Screen designs

### Fleet Overview

**User question:** Which replayed assets need attention first?

```text
┌ Summary: assets · high risk · stale · unavailable ┐
├ Filters: lifecycle band · risk · state · freshness ┤
├ Asset table                                         ┤
│ Engine │ Cycle │ RUL │ Risk │ State │ Anomaly │ Age │
└ Select an asset to open Asset Detail                ┘
```

Required behavior:

- ranking is deterministic and its sort rule is visible;
- stale and unavailable assets are not presented as healthy;
- uncertainty shows `Not available` until a valid per-prediction uncertainty
  contract exists; and
- the screen says `last processed cycle`, not `live` or `real-time`.

### Asset Detail

**User question:** What is the current replayed health evidence for one asset?

```text
┌ Engine identity · cycle · freshness · validation state ┐
├ RUL estimate ─ Risk probability ─ Risk label            ┤
├ Sensor/settings history with units and selected window  ┤
├ Exploratory telemetry state and novelty score           ┤
├ Model/release provenance                                ┤
└ Related maintenance recommendation and audit links      ┘
```

The RUL and risk values must identify their model versions, release, horizon,
threshold, and unavailable uncertainty status. Exploratory cluster and anomaly
outputs must not be presented as confirmed physical failure modes.

### Monitoring

**User question:** Is the data, prediction service, or model behavior changing?

```text
┌ Window and comparison reference ┐
├ Data quality · drift · service  ┤
├ Delayed-label performance       ┤
├ Trigger evaluation              ┤
└ Investigation evidence links    ┘
```

The screen distinguishes data-quality failures, statistical drift, service
health, and delayed-label model performance. A retraining trigger opens a
candidate evaluation; it never means automatic promotion.

### Maintenance Decisions

**User question:** What action is recommended, why, and who approved it?

```text
┌ Asset and current evidence summary                  ┐
├ Draft recommendation · rationale · confidence limits ┤
├ Deterministic rule results and conflicting evidence  ┤
├ Human decision: pending / approved / rejected         ┤
└ Agent/tool audit trail                                ┘
```

Recommendations are decision support only. The screen provides no physical
control, automatic work order, or autonomous approval action.

### Models & Releases

**User question:** Which model release is serving and how was it approved?

```text
┌ Active staging release · readiness · deployed time ┐
├ RUL model version · Risk model version             ┤
├ Selection, validation, and approval evidence       ┤
├ Candidate and failed deployment history            ┤
└ Previous release and rollback evidence             ┘
```

Candidate registration, human approval, alias movement, deployment, and
rollback appear as separate events. Local staging must not be labelled
production.

### Audit & Evidence

**User question:** What happened, who or what initiated it, and what evidence
supports it?

```text
┌ Filters: time · asset · release · actor · event type ┐
├ Append-only event timeline                           ┤
│ Time │ Actor │ Action │ Object │ Outcome │ Evidence  │
└ Selected event details with bounded safe metadata    ┘
```

Secrets, private endpoints, complete telemetry vectors, and unrestricted stack
traces must never be rendered.

## Screen-to-contract matrix

| Screen                | Design starts | Backend contract owners              | Earliest connection | Current state |
| --------------------- | ------------- | ------------------------------------ | ------------------- | ------------- |
| Fleet Overview        | Phase 6       | Phase 7 monitoring + Phase 9 shadow  | Phase 9             | Design only   |
| Asset Detail          | Phase 6       | Phases 6, 7, and 9                   | Phase 9             | Design only   |
| Monitoring            | Phase 6       | Phase 7                              | Phase 9             | Design only   |
| Maintenance Decisions | Phase 6       | Phase 8                              | Phase 9             | Design only   |
| Models & Releases     | Phase 6       | Phase 6 records + Phase 9 read model | Phase 9             | Design only   |
| Audit & Evidence      | Phase 6       | Phases 6 and 8 + Phase 9 read model  | Phase 9             | Design only   |

The `Current state` column is updated only with recorded evidence. Completing a
backend does not automatically change a screen to connected.

## Phase 6 inference contract snapshot

The following backend contract is implemented in Phase 6, but every screen
remains **Design only** until Phase 9 supplies an approved browser-facing read
model and real screen integration:

| Contract field                       | Meaning                                      |
| ------------------------------------ | -------------------------------------------- |
| `engine_id`, `cycle`                 | Positive replay identity; excluded from ML   |
| 3 settings + 21 sensors              | Exact finite cycle-level model input         |
| `rul_cycles`                         | Non-negative point estimate                  |
| `failure_risk_probability`           | Bounded probability in `[0, 1]`              |
| `failure_risk_label`                 | Threshold 0.5 for the 30-cycle horizon       |
| `release_id`                         | Immutable atomic two-model release identity  |
| model names, versions, runs, digests | Immutable task-model provenance              |
| `predictive_uncertainty_status`      | `not_available`; no interval may be invented |

The service can report `live` while returning `not ready` when its immutable
release fails verification. A later screen must preserve that difference and
must not turn unavailable readiness into a green health state.

## Phase 7 monitoring contract implementation

Phase 7 implements the future Monitoring screen input as one versioned,
immutable report. The backend contract is implemented but remains
`UNAPPROVED` until non-mocked integration, completion CI, owner approval, and
security checks pass. No screen is connected.

Implemented report sections are:

| Section             | Required meaning                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| Window              | immutable source, engine/cycle membership, replay order, release, policy, and freshness           |
| Data quality        | validation state, bounded rule counts, lineage, and blocking failures                             |
| Feature shift       | all 24 inputs, reference/current effect sizes, lifecycle mix, adequacy, and threshold identity    |
| Prediction shift    | RUL and risk distribution changes without claiming performance degradation                        |
| Service             | sampled readiness, status counts, and latency summaries without an SLA claim                      |
| Delayed performance | explicit unavailable/insufficient/available state plus aggregate metrics when exact labels exist  |
| Trigger             | investigation or candidate-request result, deterministic reason, evidence, and human-review state |

The UI must display `unavailable`, `insufficient_data`, and `invalid` as distinct
states. It must not render any of them as zero, green, healthy, or approved. A
drift alert must say `Distribution changed`; it must not say `Model failed`
unless matching delayed performance evidence supports that separate statement.

This remains a technology-neutral design contract. Phase 7 creates no browser
endpoint or screen connection.

### Monitoring field and state rules

| Field or state                                                     | Future-screen meaning                                                                          |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `window_id`, `reference_id`, `policy_id`, `release_id`             | Immutable provenance; never replace with friendly mutable names                                |
| `source_partition`, `row_count`, `engine_count`, `replay_sequence` | Replay scope; sequence is not time or freshness                                                |
| signal `status`                                                    | Exactly `pass`, `warning`, `alert`, `insufficient_data`, `unavailable`, or `invalid`           |
| `reason_codes`                                                     | Stable bounded identifiers suitable for help text, not executable instructions                 |
| `lifecycle_mix`, operating summaries                               | Context for interpreting shift; nullable/empty after invalid quality                           |
| `parent_report_id`, `label_snapshot_id`                            | Both null before labels; both present on an immutable delayed-performance child                |
| candidate request                                                  | Evaluation-only evidence with a fixed cutoff; not training, approval, promotion, or deployment |

Freshness must later be calculated by a Phase 9 read model from explicitly
stored observation/publication metadata. Phase 7 does not invent event time.
An absent report is `empty`; an unreadable or contract-mismatched report is an
`error`; a report with some unavailable sections is `partial`. A future stale
threshold must be versioned and owner-approved before connection.

## Cross-phase delivery

| Phase | UI responsibility                                                                         |
| ----- | ----------------------------------------------------------------------------------------- |
| 6     | Establish screen design; stabilize release and inference contracts; build no UI           |
| 7     | Stabilize monitoring/read-model inputs; update affected designs; build no UI              |
| 8     | Stabilize recommendation and agent-audit inputs; update affected designs; build no UI     |
| 9     | Select the frontend stack, implement the shell, and connect one eligible screen at a time |
| 10    | Run end-to-end usability, accessibility, failure-state, security, and recovery checks     |

Phase 9 may use temporary fixture data only for isolated component tests. A
screen becomes `CONNECTED` only after its real backend adapter passes. A screen
becomes `VERIFIED` only after browser-level success and failure paths pass in
the declared environment.

## Shared screen states

Every implemented data-bearing screen must define and test:

- loading;
- empty but valid;
- fresh data;
- stale data;
- partial data;
- backend unavailable;
- contract-version mismatch;
- validation failure;
- unauthorized or forbidden, when authentication exists; and
- safe retry behavior.

No state may silently replace unavailable data with zero, green, healthy, or
approved.

## Accessibility and responsive behavior

- Keyboard navigation and visible focus are required.
- Semantic headings, tables, labels, and status text are required.
- Color contrast must meet WCAG 2.2 AA targets.
- Charts require text summaries and accessible legends.
- Dense telemetry tables may scroll horizontally, but primary health and
  freshness evidence must remain understandable at narrow widths.
- Motion is optional and must respect reduced-motion preferences.

## Technology boundary

The frontend framework, chart library, component library, authentication flow,
and hosting target remain Phase 9 decisions. Early design must not create a
dependency on React, Next.js, Supabase Realtime, or any vendor-specific UI
platform.
