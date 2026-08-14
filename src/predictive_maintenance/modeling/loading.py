"""Verified, read-only loading of an explicit Phase 3 feature snapshot."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
import pandas as pd

from predictive_maintenance.cloud.metadata import MetadataRepository
from predictive_maintenance.cloud.models import ObjectIdentity, StoredSnapshot
from predictive_maintenance.cloud.object_store import ObjectRepository
from predictive_maintenance.etl.metadata import DerivedMetadataRepository
from predictive_maintenance.etl.models import (
    FEATURE_SPEC_VERSION,
    PROCESSED_CONTRACT_VERSION,
    StoredDerivedSnapshot,
)
from predictive_maintenance.etl.serialization import (
    FEATURE_COLUMNS as STORED_FEATURE_COLUMNS,
)
from predictive_maintenance.etl.serialization import (
    TARGET_COLUMNS as STORED_TARGET_COLUMNS,
)
from predictive_maintenance.modeling.models import (
    ModelingError,
    TrainingDataset,
    sha256_bytes,
)

_FILES = (
    "train_features.parquet",
    "train_targets.parquet",
    "test_features.parquet",
    "test_targets.parquet",
)


def _verified_payload(objects: ObjectRepository, identity: ObjectIdentity) -> bytes:
    payload = objects.read(identity.bucket_name, identity.object_key)
    if len(payload) != identity.byte_size or sha256_bytes(payload) != identity.sha256:
        raise ModelingError(
            "input.object_identity_mismatch",
            "A referenced object does not match its recorded size and SHA-256.",
        )
    return payload


def _verify_snapshot_objects(
    objects: ObjectRepository,
    snapshot: StoredSnapshot | StoredDerivedSnapshot,
) -> tuple[bytes, ...]:
    if not snapshot.identities:
        raise ModelingError(
            "input.empty_snapshot", "Snapshot has no object identities."
        )
    return tuple(_verified_payload(objects, item) for item in snapshot.identities)


def _require_derived(
    repository: DerivedMetadataRepository,
    snapshot_id: str,
    *,
    kind: str,
    contract: str,
) -> StoredDerivedSnapshot:
    snapshot = repository.get_derived_snapshot(snapshot_id)
    if snapshot is None:
        raise ModelingError(
            "input.snapshot_unknown", "Explicit snapshot was not found."
        )
    if snapshot.state != "available":
        raise ModelingError(
            "input.snapshot_unavailable", "Explicit snapshot is not available."
        )
    if snapshot.artifact_kind != kind or snapshot.contract_version != contract:
        raise ModelingError(
            "input.snapshot_contract",
            "Snapshot kind or contract does not match the Phase 4 input contract.",
        )
    return snapshot


def _manifest(payload: bytes, snapshot: StoredDerivedSnapshot) -> Mapping[str, Any]:
    if sha256_bytes(payload) != snapshot.manifest_sha256:
        raise ModelingError(
            "input.manifest_identity_mismatch",
            "Manifest SHA-256 does not match metadata.",
        )
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ModelingError(
            "input.invalid_manifest", "Derived manifest is not valid JSON."
        ) from error
    if not isinstance(value, dict):
        raise ModelingError(
            "input.invalid_manifest", "Derived manifest must be an object."
        )
    if value.get("derived_snapshot_id") != snapshot.derived_snapshot_id:
        raise ModelingError(
            "input.manifest_snapshot_mismatch",
            "Manifest and metadata snapshot identities differ.",
        )
    return cast(Mapping[str, Any], value)


def _files_by_name(
    snapshot: StoredDerivedSnapshot,
    manifest: Mapping[str, Any],
) -> dict[str, ObjectIdentity]:
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != len(snapshot.identities) - 1:
        raise ModelingError(
            "input.file_membership", "Manifest file membership is incomplete."
        )
    result: dict[str, ObjectIdentity] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ModelingError(
                "input.invalid_manifest", "Invalid manifest file entry."
            )
        name = row.get("logical_filename")
        identity = snapshot.identities[index]
        if (
            not isinstance(name, str)
            or row.get("file_position") != index
            or row.get("sha256") != identity.sha256
            or row.get("byte_size") != identity.byte_size
            or not identity.object_key.endswith("/" + name)
            or name in result
        ):
            raise ModelingError(
                "input.file_membership", "Manifest and metadata file membership differ."
            )
        result[name] = identity
    return result


def _read_frame(payload: bytes, columns: Sequence[str]) -> pd.DataFrame:
    try:
        frame = pd.read_parquet(io.BytesIO(payload))
    except (OSError, ValueError) as error:
        raise ModelingError(
            "input.invalid_parquet", "Feature object is not valid Parquet."
        ) from error
    if tuple(frame.columns) != tuple(columns) or frame.empty:
        raise ModelingError(
            "input.frame_contract", "Feature table columns or row count are invalid."
        )
    expected = {
        "engine_id": "int64",
        "cycle": "int64",
        "rul": "int64",
        "failure_risk_30": "int8",
    }
    for column in columns:
        if str(frame[column].dtype) != expected.get(column, "float64"):
            raise ModelingError("input.frame_dtype", "Feature table dtype is invalid.")
    if frame.duplicated(["engine_id", "cycle"]).any() or bool(frame.isna().any().any()):
        raise ModelingError("input.frame_values", "Feature keys or values are invalid.")
    numeric = frame.to_numpy(dtype="float64", copy=False)
    if not bool(np.isfinite(numeric).all()):
        raise ModelingError("input.frame_values", "Feature values must be finite.")
    return frame


def _validate_pair(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    feature_keys = features.loc[:, ["engine_id", "cycle"]].reset_index(drop=True)
    target_keys = targets.loc[:, ["engine_id", "cycle"]].reset_index(drop=True)
    if not feature_keys.equals(target_keys):
        raise ModelingError(
            "input.key_mismatch", "Feature and target keys are not exactly aligned."
        )
    if bool((targets["rul"] < 0).any()) or not set(
        targets["failure_risk_30"].unique().tolist()
    ) <= {0, 1}:
        raise ModelingError("input.target_values", "Target semantics are invalid.")
    expected_risk = (targets["rul"] <= 30).astype("int8")
    if not targets["failure_risk_30"].equals(expected_risk):
        raise ModelingError(
            "input.target_semantics", "Failure risk must equal inclusive RUL <= 30."
        )


def load_training_dataset(
    feature_snapshot_id: str,
    objects: ObjectRepository,
    raw_metadata: MetadataRepository,
    derived_metadata: DerivedMetadataRepository,
) -> TrainingDataset:
    """Load one explicit verified feature snapshot; never choose latest implicitly."""
    if not feature_snapshot_id:
        raise ModelingError(
            "input.explicit_snapshot_required", "A feature snapshot ID is required."
        )
    feature = _require_derived(
        derived_metadata,
        feature_snapshot_id,
        kind="feature",
        contract=FEATURE_SPEC_VERSION,
    )
    if feature.parent_derived_snapshot_id is None:
        raise ModelingError(
            "input.parent_missing", "Feature parent lineage is missing."
        )
    processed = _require_derived(
        derived_metadata,
        feature.parent_derived_snapshot_id,
        kind="processed",
        contract=PROCESSED_CONTRACT_VERSION,
    )
    if processed.source_snapshot_id != feature.source_snapshot_id:
        raise ModelingError("input.lineage_mismatch", "Derived source lineage differs.")
    raw = raw_metadata.get_snapshot(feature.source_snapshot_id)
    if raw is None or raw.state != "available":
        raise ModelingError(
            "input.raw_unavailable", "Raw source snapshot is unavailable."
        )

    feature_payloads = _verify_snapshot_objects(objects, feature)
    processed_payloads = _verify_snapshot_objects(objects, processed)
    raw_payloads = _verify_snapshot_objects(objects, raw)
    feature_manifest = _manifest(feature_payloads[0], feature)
    if (
        feature_manifest.get("parent_snapshot_id") != processed.derived_snapshot_id
        or feature_manifest.get("source_snapshot_id") != raw.snapshot_id
        or feature_manifest.get("contract_version") != FEATURE_SPEC_VERSION
    ):
        raise ModelingError(
            "input.lineage_mismatch", "Feature manifest lineage differs."
        )
    identities = _files_by_name(feature, feature_manifest)
    if set(identities) != set(_FILES):
        raise ModelingError("input.file_membership", "Required feature files differ.")
    processed_manifest = _manifest(processed_payloads[0], processed)
    if (
        processed_manifest.get("source_snapshot_id") != raw.snapshot_id
        or processed_manifest.get("parent_snapshot_id") != raw.snapshot_id
        or set(_files_by_name(processed, processed_manifest))
        != {"train.parquet", "test.parquet"}
    ):
        raise ModelingError(
            "input.lineage_mismatch", "Processed manifest lineage differs."
        )
    if (
        raw.manifest_sha256 != raw.identities[0].sha256
        or raw.required_file_count != len(raw.identities) - 1
    ):
        raise ModelingError(
            "input.raw_membership", "Raw snapshot membership metadata differs."
        )
    try:
        raw_manifest = json.loads(raw_payloads[0])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ModelingError(
            "input.invalid_manifest", "Raw manifest is invalid."
        ) from error
    if (
        not isinstance(raw_manifest, dict)
        or raw_manifest.get("snapshot_id") != raw.snapshot_id
    ):
        raise ModelingError("input.raw_membership", "Raw manifest identity differs.")

    frames = {
        name: _read_frame(
            _verified_payload(objects, identities[name]),
            STORED_FEATURE_COLUMNS if "features" in name else STORED_TARGET_COLUMNS,
        )
        for name in _FILES
    }
    train_features = frames["train_features.parquet"]
    train_targets = frames["train_targets.parquet"]
    test_features = frames["test_features.parquet"]
    test_targets = frames["test_targets.parquet"]
    _validate_pair(train_features, train_targets)
    _validate_pair(test_features, test_targets)
    return TrainingDataset(
        raw.snapshot_id,
        processed.derived_snapshot_id,
        feature.derived_snapshot_id,
        train_features,
        train_targets,
        test_features,
        test_targets,
    )
