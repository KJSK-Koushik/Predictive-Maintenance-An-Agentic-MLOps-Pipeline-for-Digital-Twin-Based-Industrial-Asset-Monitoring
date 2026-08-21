# ADR 0026: Label-free exploratory telemetry states and novelty scores

## Status

Accepted

## Date

2026-08-21

## Context

C-MAPSS FD001 provides run-to-failure trajectories and derived RUL/risk labels,
but it does not provide ground-truth health-state classes, fault-event labels,
or anomaly annotations. Clustering or anomaly detection can still describe
telemetry structure, but supervised accuracy claims would be fabricated.

## Decision

For clustering, sample at most 100 ordered cycles per source-training engine,
standardize the 24 telemetry inputs, retain 95% PCA variance, and evaluate
KMeans counts two through six with seeds 42, 43, and 44. Require mean pairwise
adjusted Rand index of at least 0.80, then choose the stable candidate with the
best mean silhouette and canonicalize its labels. RUL is used only after
selection for bounded descriptive lifecycle associations.

For novelty scoring, fit the scaler and `IsolationForest` only on the first 20%
of each source-training engine's declared lifecycle. Use
`contamination="auto"`, fixed seeds, and report score stability and bounded
lifecycle summaries. Do not use RUL or risk to tune the detector.

Call the outputs exploratory telemetry states and novelty scores. Do not report
health-state accuracy, anomaly precision/recall, detection delay, maintenance
authority, or a validated physical-fault claim. Explanation outputs are
post-selection evidence and cannot trigger hidden feature selection or tuning.

## Consequences

Stable structure may support visualization and hypotheses, but it is not a
validated state taxonomy. On FD001, two clusters met the stability rule and
showed a descriptive lifecycle association; this does not turn the system into
a physical digital twin. The novelty score rose later in simulated
trajectories, but no ground-truth anomaly performance is available.

## Alternatives

- Name clusters healthy/degraded/failed: rejected without ground-truth states.
- Tune contamination from RUL/risk: rejected because it leaks derived labels.
- Report anomaly classification metrics: rejected because FD001 has no anomaly
  annotations.
- Let explanations automatically select features: rejected as hidden retuning.

## Verification

Tests prove engine-balanced sampling, bounded cluster counts/seeds, PCA and
stability rules, canonical labels, label-independent cluster selection,
first-20%-only novelty fitting, score stability, bounded outputs, and the
absence of fabricated anomaly metrics. The full FD001 test reproduced both
analysis records exactly.
