# FD001 Data Exploration

## Scope

This report describes the verified owner-provided FD001 copy only. It contains
simulated historical cycle telemetry. Results are descriptive properties of
this finite dataset, not universal limits for physical turbofan engines.

## Dataset dimensions

| Measure                     | Train  | Test   |
| --------------------------- | ------ | ------ |
| Telemetry rows              | 20,631 | 13,096 |
| Telemetry columns           | 26     | 26     |
| Engines                     | 100    | 100    |
| Missing values              | 0      | 0      |
| Duplicate engine-cycle keys | 0      | 0      |

Two derived columns, `rul` and `failure_risk_30`, are added only after
validation, producing 28 columns in each accepted in-memory labeled view.

## Trajectory lengths

| Cycle-length statistic | Train  | Test   |
| ---------------------- | ------ | ------ |
| Minimum                | 128    | 31     |
| Maximum                | 362    | 303    |
| Mean                   | 206.31 | 130.96 |
| Median                 | 199.0  | 133.5  |

Train RUL ranges from 0 to 361 cycles. Test RUL ranges from 7 to 340 cycles
after combining observed endpoints with `RUL_FD001.txt`.

## Operating settings

- `setting_1` and `setting_2` vary over narrow numeric ranges.
- `setting_3` is constant at 100 in both partitions.
- These values are dataset observations and are not declared physical limits.

## Constant and low-information sensors

The following sensors are constant in both train and test:

```text
sensor_1, sensor_5, sensor_10, sensor_16, sensor_18, sensor_19
```

Using the Phase 1 descriptive rule—at most two unique values or standard
deviation at most `1e-8`—the following are low-information in both partitions:

```text
sensor_1, sensor_5, sensor_6, sensor_10, sensor_16, sensor_18, sensor_19
```

This is exploration evidence, not an automatic feature-removal decision.
Feature selection belongs to a later modelling phase and must be fit without
validation/test leakage.

## Failure-risk prevalence

The inclusive rule is `failure_risk_H = 1` when `rul <= H`.

| Horizon | Train prevalence | Test prevalence |
| ------- | ---------------- | --------------- |
| 15      | 7.7553%          | 0.4582%         |
| 30      | 15.0259%         | 2.5351%         |
| 45      | 22.2965%         | 5.6200%         |

The difference reflects the truncated test trajectories and supplied terminal
RUL values. It is not evidence of a deployment population's failure rate.

## Interpretation boundary

`cycle` has no wall-clock unit in this pipeline. Calling the rows telemetry does
not make them a live stream. Any later replay must preserve original engine,
cycle, and snapshot identity and keep replay time separate from source time.
