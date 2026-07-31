# Data Contract

## Status

**Executable FD001 contract version `fd001-v1`.** The implementation is in
`src/predictive_maintenance/data/` and is exercised by synthetic CI fixtures
and the ignored owner-provided FD001 files.

## Scope and provenance

Phase 1 accepts exactly these logical inputs:

| Logical file      | Purpose                                  |
| ----------------- | ---------------------------------------- |
| `train_FD001.txt` | Run-to-failure training telemetry        |
| `test_FD001.txt`  | Truncated test telemetry                 |
| `RUL_FD001.txt`   | RUL at each test engine's observed end   |
| `readme.txt`      | Documentation shipped with the data copy |

FD002-FD004 and the supporting PDF are not Phase 1 tabular inputs. The source
is Saxena and Goebel (2008), *Turbofan Engine Degradation Simulation Data Set*,
NASA Ames Prognostics Data Repository. The current repository page is
<https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/>.

The working directory contains extracted files but no original distribution
archive or publisher-provided checksum. The exact local files are identified
below, but byte identity with an unavailable original archive cannot be proven.

| File              | Bytes     | SHA-256                                                            |
| ----------------- | --------- | ------------------------------------------------------------------ |
| `train_FD001.txt` | 3,515,356 | `963b5e22825b34d8b21c69e1aeb4af3e647050eb672ee8834ba4b5d91d2de0f8` |
| `test_FD001.txt`  | 2,228,855 | `3cda7109ce17bafb5443f2ac926cfcf88154b941b8c4cf95eb55d1ddd6f52851` |
| `RUL_FD001.txt`   | 429       | `a19c8ec94931949d0485bdc35118206e9c81c4547b422efb9cf86f4ceddbceca` |
| `readme.txt`      | 2,442     | `4f5270554b775c67e73aff383c5436fd329d6e4cc3d3a116913276fae511269b` |

The verified source-set snapshot ID is
`17d1db8dd823266b58b9c8d5b6da8edace17220980b733188756cd6b630e453d`.

## Raw identity and immutability

- SHA-256 and byte size are calculated with bounded-memory streaming.
- The source is opened read-only and checked again after copying.
- A snapshot path is derived from the required file identities, contract,
  parser, citation, and source URL.
- Files are created exclusively, then their copied digests are verified.
- An existing snapshot is reused only after its canonical manifest and every
  file pass verification.
- Tampered content, malformed metadata, or an overwrite attempt fails closed.
- The manifest contains logical filenames, not private absolute paths.

This is application-enforced, content-addressed local overwrite denial. It is
not storage-level WORM.

## Telemetry schema

Each train or test row has exactly 26 ordered columns:

| Position | Name                                  | Parsed dtype | Null | Domain           |
| -------- | ------------------------------------- | ------------ | ---- | ---------------- |
| 1        | `engine_id`                           | `int64`      | No   | Positive integer |
| 2        | `cycle`                               | `int64`      | No   | Positive integer |
| 3-5      | `setting_1`, `setting_2`, `setting_3` | `float64`    | No   | Finite numeric   |
| 6-26     | `sensor_1` through `sensor_21`        | `float64`    | No   | Finite numeric   |

The parser accepts variable ASCII whitespace and trailing whitespace. It
preserves source row order. It does not silently sort, impute, drop, or accept
wrong-width/non-numeric rows. Pandera enforces ordered columns, exact parsed
dtypes, nullability, and strict extra-column rejection.

## Semantic and cross-file rules

- `(engine_id, cycle)` is unique.
- Each engine starts at cycle 1.
- Cycles increase by exactly one in source row order for each engine.
- Every setting and sensor value is present and finite.
- Test engine IDs form the contiguous ordered range `1..N`.
- `RUL_FD001.txt` contains one finite non-negative integer for each test engine.
- A failed parse, schema rule, semantic rule, or cross-file rule prevents an
  accepted ingestion result.

Stable project rule IDs identify failures. Reports include error severity,
logical filenames, counts, and at most five value examples. They do not include
raw absolute paths.

## Labels

The canonical Phase 1 RUL is uncapped.

For a training observation:

```text
rul = max_train_cycle_for_engine - cycle
```

For a test observation, the supplied value is RUL at the final observed cycle:

```text
rul = max_test_cycle_for_engine + terminal_rul - cycle
```

The inclusive risk label is:

```text
failure_risk_H = 1 when rul <= H, otherwise 0
```

The primary horizon is 30 cycles. Exploration also reports 15- and 45-cycle
sensitivity. These are derived labels, not independently observed failure
events. No capped RUL is produced in Phase 1; any later cap must be a separate,
versioned derivation with a documented rationale.

## Telemetry meaning

FD001 rows are simulated historical telemetry observations. `cycle` is an
ordered sequence coordinate, not a timestamp. Phase 1 creates no synthetic
event time and makes no live or real-time ingestion claim.

## Split and leakage rules for later phases

Future model partitions must be engine-disjoint. Preprocessing and feature
fitting use training data only. RUL and failure-risk labels are targets and
must never be included as model input features.

## Privacy

C-MAPSS is simulated telemetry and is not expected to contain personal data.
Credentials, filesystem usernames, signed URLs, and private service identifiers
must not be attached to dataset metadata.

## Phase 2 publication identity

Phase 2 does not change the Phase 1 contract or calculate a new snapshot ID. It
publishes the accepted snapshot under the same
`17d1db8dd823266b58b9c8d5b6da8edace17220980b733188756cd6b630e453d`
identity.

The raw object contract is:

```text
fd001/<snapshot-id>/<file-sha256>/<logical-filename>
fd001/<snapshot-id>/manifest.json
```

An object identity is the tuple `(bucket_name, object_key, zone, sha256, byte_size, content_type)`. Bucket names are environment configuration and do
not change the dataset snapshot identity. Every accepted object is verified
against its expected size and SHA-256 after writing. The Supabase adapter
performs this verification by downloading the object.

The private PostgreSQL `ops` schema records:

- one `dataset_snapshots` row per Phase 1 snapshot ID;
- one `data_objects` row per bucket and object key;
- the ordered logical files in `snapshot_files`;
- manifest-to-file relationships in `lineage_edges`; and
- one idempotent lifecycle record in `ingestion_runs`.

Snapshot metadata becomes `available` only after every required object is
verified and the complete metadata transaction commits. Missing or mismatched
referenced objects change the snapshot to `inconsistent`, which blocks
downstream use. Orphan objects are reported for investigation and are not
silently deleted.

Phase 2 created no production processed or feature artifact.

## Phase 3 planned derived contracts

These contracts are approved for planning but are not executable until Phase 3
implementation passes its acceptance criteria.

`fd001-processed-v1` will store separate train and test Parquet files with
source row order, exact Phase 1 telemetry columns, uncapped `rul`, and inclusive
`failure_risk_30`. It will not sort, drop, impute, scale, cap, or synthesize an
event timestamp.

`fd001-candidate-features-v1` will store key-aligned candidate-feature and
target files. Candidate features are limited to the three settings and 21
sensors; `engine_id` and `cycle` remain keys. Targets contain `rul` and
`failure_risk_30`, which are prohibited from candidate-feature columns. No
fitted preprocessing or model-informed feature choice belongs to Phase 3.

Each derived identity will bind its parent snapshot, contract/specification and
serializer versions, ordered file schemas, sizes, SHA-256 values, and column
roles in a canonical manifest. A canonical JSON data-quality report will record
bounded aggregate contract evidence. Airflow logical dates and run IDs are
execution metadata and do not change derived content identity.
