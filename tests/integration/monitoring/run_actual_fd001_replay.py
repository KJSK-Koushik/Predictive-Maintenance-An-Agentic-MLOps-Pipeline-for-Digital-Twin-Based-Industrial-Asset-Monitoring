"""Generate separately classified actual FD001 replay evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, cast

import pandas as pd

from predictive_maintenance.cloud.object_store import FilesystemObjectRepository
from predictive_maintenance.etl.models import (
    ColumnContract,
    DerivedManifest,
    ManifestFile,
)
from predictive_maintenance.monitoring.models import (
    MonitoringPolicy,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.monitoring.pipeline import (
    attach_delayed_labels,
    build_monitoring_report,
    create_window,
)
from predictive_maintenance.monitoring.publication import (
    publish_monitoring_report,
    publish_reference_profile,
)
from predictive_maintenance.monitoring.reference import (
    build_reference_profile,
    engine_balanced_sample,
)
from predictive_maintenance.monitoring.service import probe_loopback_service
from predictive_maintenance.monitoring.triggers import evaluate_triggers
from predictive_maintenance.release.packaging import verify_release_bundle

ROOT = Path(__file__).resolve().parents[3]
RELEASE_DIR = ROOT / "artifacts/inference-release"
_FEATURE_ROOT = (
    ROOT
    / "artifacts/phase6-actual-retry/objects/pm-derived/features/fd001"
    / "fd001-candidate-features-v1"
    / "56ad2caebf04dbbadbf658634f2b4d4d82059852074adadc12a61e8cd80b3008"
)
FEATURE_ROOT = (
    Path("\\\\?\\" + str(_FEATURE_ROOT)) if os.name == "nt" else _FEATURE_ROOT
)
OUTPUT = ROOT / "artifacts/monitoring/actual-fd001"


def _file(name: str) -> Path:
    matches = tuple(FEATURE_ROOT.rglob(name))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {name} in approved feature evidence.")
    return matches[0]


def _verified_feature_manifest(expected_snapshot_id: str) -> DerivedManifest:
    value = json.loads(_file("manifest.json").read_bytes())
    files = []
    for entry in value["files"]:
        entry = dict(entry)
        entry["columns"] = tuple(
            ColumnContract(**column) for column in entry["columns"]
        )
        record = ManifestFile(**entry)
        payload = _file(record.logical_filename).read_bytes()
        if len(payload) != record.byte_size or sha256_bytes(payload) != record.sha256:
            raise RuntimeError("Feature snapshot file failed integrity verification.")
        files.append(record)
    manifest = DerivedManifest(
        **{
            key: value[key]
            for key in (
                "artifact_kind",
                "source_snapshot_id",
                "parent_snapshot_id",
                "contract_version",
                "transformation_version",
                "serializer_version",
                "code_revision",
            )
        },
        files=tuple(files),
    )
    if manifest.snapshot_id != expected_snapshot_id:
        raise RuntimeError(
            "Feature manifest differs from the approved release snapshot."
        )
    return manifest


def _load_or_probe(
    name: str,
    frame: pd.DataFrame,
    *,
    release_id: str,
    base_url: str,
    output_dir: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    prediction_path = output_dir / f"{name}-predictions.parquet"
    service_path = output_dir / f"{name}-service.json"
    if prediction_path.exists() and service_path.exists():
        service = cast(
            dict[str, Any], json.loads(service_path.read_text(encoding="ascii"))
        )
        if service.get("release_id") != release_id:
            raise RuntimeError(
                "Cached predictions do not bind the expected release; "
                "use a new output directory."
            )
        return (
            pd.read_parquet(prediction_path),
            service,
        )
    result = probe_loopback_service(
        frame, base_url=base_url, expected_release_id=release_id
    )
    if not result.readiness or len(result.predictions) != len(frame):
        raise RuntimeError(
            "The exact approved loopback release did not serve all rows."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    result.predictions.to_parquet(prediction_path, index=False)
    service_path.write_bytes(
        canonical_json_bytes({"release_id": release_id, **result.service_evidence})
    )
    return result.predictions, result.service_evidence


def main() -> int:
    """Run reference, replay, delayed labels, trigger, and exact reuse."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=RELEASE_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--expected-release-id", required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    output = args.output_dir
    manifest = verify_release_bundle(args.release_dir)
    if manifest.release_id != args.expected_release_id:
        raise RuntimeError(
            "Replay package differs from the explicitly approved release."
        )
    policy = MonitoringPolicy(max_rows_per_engine=20)
    feature_manifest = _verified_feature_manifest(manifest.feature_snapshot_id)
    lock_sha256 = sha256_bytes((ROOT / "uv.lock").read_bytes())
    train_features = pd.read_parquet(_file("train_features.parquet"))
    train_targets = pd.read_parquet(_file("train_targets.parquet"))
    test_features = pd.read_parquet(_file("test_features.parquet"))
    train = train_features.merge(
        train_targets, on=["engine_id", "cycle"], validate="one_to_one"
    )
    reference = build_reference_profile(
        train,
        release_id=manifest.release_id,
        feature_snapshot_id=manifest.feature_snapshot_id,
        policy=policy,
        code_revision=args.code_revision,
        dependency_lock_sha256=lock_sha256,
    )
    reference_rows = engine_balanced_sample(train_features, policy.max_rows_per_engine)
    replay_rows = engine_balanced_sample(test_features, policy.max_rows_per_engine)
    base_url = "http://127.0.0.1:18000"
    reference_predictions, _ = _load_or_probe(
        "reference",
        reference_rows,
        release_id=manifest.release_id,
        base_url=base_url,
        output_dir=output,
    )
    current_predictions, service_evidence = _load_or_probe(
        "replay",
        replay_rows,
        release_id=manifest.release_id,
        base_url=base_url,
        output_dir=output,
    )
    window = create_window(
        replay_rows,
        reference=reference,
        policy=policy,
        raw_snapshot_id=manifest.raw_snapshot_id,
        processed_snapshot_id=manifest.processed_snapshot_id,
        feature_snapshot_id=manifest.feature_snapshot_id,
        source_partition="test",
        replay_sequence=1,
        code_revision=args.code_revision,
        dependency_lock_sha256=lock_sha256,
    )
    original = build_monitoring_report(
        replay_rows,
        current_predictions,
        reference_predictions,
        window=window,
        reference=reference,
        policy=policy,
        service_evidence=service_evidence,
    )
    attached = attach_delayed_labels(
        original,
        current_predictions,
        label_payload=_file("test_targets.parquet").read_bytes(),
        feature_manifest=feature_manifest,
        expected_source_partition="test",
    )
    repeated = build_monitoring_report(
        replay_rows,
        current_predictions,
        reference_predictions,
        window=window,
        reference=reference,
        policy=policy,
        service_evidence=service_evidence,
    )
    if repeated.report_id != original.report_id:
        raise RuntimeError("Repeated actual replay did not preserve report identity.")
    objects = FilesystemObjectRepository(output / "object-store")
    reference_put = publish_reference_profile(
        reference, bucket="pm-derived-phase7-local", repository=objects
    )
    original_put = publish_monitoring_report(
        original, bucket="pm-derived-phase7-local", repository=objects
    )
    attached_put = publish_monitoring_report(
        attached, bucket="pm-derived-phase7-local", repository=objects
    )
    trigger = evaluate_triggers((attached,), policy=policy)
    summary = {
        "evidence_class": "actual_fd001_static_cycle_replay",
        "release_id": manifest.release_id,
        "reference_id": reference.reference_id,
        "window_id": window.window_id,
        "prediction_report_id": original.report_id,
        "performance_report_id": attached.report_id,
        "rows": len(replay_rows),
        "engines": int(replay_rows["engine_id"].nunique()),
        "rows_per_engine_maximum": int(replay_rows.groupby("engine_id").size().max()),
        "statuses": {
            "data_quality": attached.data_quality.status,
            "feature_shift": attached.feature_shift.status,
            "prediction_shift": attached.prediction_shift.status,
            "service": attached.service_health.status,
            "performance": attached.delayed_performance.status,
        },
        "trigger_status": trigger.status,
        "candidate_request_id": (
            trigger.candidate_request.request_id if trigger.candidate_request else None
        ),
        "actual_retraining_outcome": "no_change",
        "nasa_test_used_for_training": False,
        "repeated_report_identity_equal": True,
        "publication_reused": {
            "reference": reference_put.reused,
            "prediction_report": original_put.reused,
            "performance_report": attached_put.reused,
        },
        "limitations": [
            "Already-observed NASA benchmark; not new blind or field evidence.",
            "Static simulated cycle replay; not live or real-time telemetry.",
            "NASA test rows were evaluated only and never used for training.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_bytes(canonical_json_bytes(summary))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
