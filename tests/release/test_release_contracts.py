"""Release identity, approval, packaging, and tamper tests."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from phase6_support import SyntheticRelease

from predictive_maintenance.release.gates import require_current_approval
from predictive_maintenance.release.models import (
    FEATURE_COLUMNS,
    ApprovalDecision,
    ModelReference,
    ReleaseError,
    canonical_json_bytes,
)
from predictive_maintenance.release.packaging import (
    parse_manifest,
    verify_release_bundle,
)
from predictive_maintenance.release.trust import dump_deterministic


def test_release_manifest_is_canonical_and_sensitive(
    synthetic_release: SyntheticRelease,
) -> None:
    manifest = synthetic_release.manifest
    assert parse_manifest(manifest.canonical_bytes()) == manifest
    assert len(manifest.release_id) == 64
    assert (
        replace(manifest, code_revision="different").release_id != manifest.release_id
    )
    assert (
        replace(manifest, previous_release_id="a" * 64).release_id
        != manifest.release_id
    )


def test_approval_is_exact_current_and_rejected_failures_are_bounded(
    synthetic_release: SyntheticRelease,
) -> None:
    manifest = synthetic_release.manifest
    approval = synthetic_release.approval
    require_current_approval(manifest, approval, now=approval.decided_at)
    cases = (
        (None, "approval.missing"),
        (replace(approval, release_id="f" * 64), "approval.release_mismatch"),
        (replace(approval, decision="rejected"), "approval.rejected"),
    )
    for decision, code in cases:
        with pytest.raises(ReleaseError, match=re.escape(code)):
            require_current_approval(manifest, decision, now=approval.decided_at)
    with pytest.raises(ReleaseError, match=r"approval\.expired"):
        require_current_approval(
            manifest, approval, now=approval.expires_at + timedelta(seconds=1)
        )


def test_bundle_reuse_and_tamper_detection(
    synthetic_release: SyntheticRelease,
) -> None:
    assert verify_release_bundle(synthetic_release.bundle) == synthetic_release.manifest
    model = synthetic_release.bundle / "rul" / "model.skops"
    model.write_bytes(model.read_bytes() + b"tamper")
    with pytest.raises(ReleaseError, match=r"release\.regression_digest_mismatch"):
        verify_release_bundle(synthetic_release.bundle)


def test_approval_contract_rejects_bad_time_and_reason(
    synthetic_release: SyntheticRelease,
) -> None:
    manifest = synthetic_release.manifest
    now = datetime.now(UTC)
    with pytest.raises(ReleaseError, match=r"approval\.invalid_reason"):
        ApprovalDecision(
            manifest.approval_request_id,
            manifest.release_id,
            "approved",
            "owner",
            "",
            "a" * 64,
            now,
            now + timedelta(minutes=1),
        )


def test_no_release_files_are_written_without_approval(tmp_path: Path) -> None:
    assert list(tmp_path.iterdir()) == []


def test_skops_serialization_bytes_are_deterministic(tmp_path: Path) -> None:
    from sklearn.linear_model import Ridge  # type: ignore[import-untyped]

    model = Ridge().fit([[0.0], [1.0]], [0.0, 1.0])
    first = tmp_path / "first.skops"
    second = tmp_path / "second.skops"
    dump_deterministic(model, first)
    dump_deterministic(model, second)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"registered_name": "wrong"}, "release.registered_name_mismatch"),
        ({"version": "0"}, "release.invalid_version"),
        ({"source_run_id": ""}, "release.invalid_run"),
        ({"artifact_sha256": "bad"}, "release.invalid_identity"),
        ({"feature_columns": ("wrong",)}, "release.feature_contract_mismatch"),
        ({"feature_dtype": "float32"}, "release.feature_dtype_mismatch"),
        ({"selected_family": "ridge"}, "release.selected_family_mismatch"),
    ],
)
def test_model_reference_rejects_contract_drift(
    synthetic_release: SyntheticRelease, change: dict[str, Any], code: str
) -> None:
    with pytest.raises(ReleaseError, match=re.escape(code)):
        replace(synthetic_release.manifest.regression, **change)


def test_release_and_approval_validation_failure_paths(
    synthetic_release: SyntheticRelease,
) -> None:
    manifest = synthetic_release.manifest
    approval = synthetic_release.approval
    with pytest.raises(ReleaseError, match=r"release\.task_mismatch"):
        replace(manifest, regression=manifest.classification)
    with pytest.raises(ReleaseError, match=r"release\.invalid_code_revision"):
        replace(manifest, code_revision="")
    with pytest.raises(ReleaseError, match=r"release\.invalid_identity"):
        replace(manifest, previous_release_id="bad")
    with pytest.raises(ReleaseError, match=r"approval\.request_mismatch"):
        require_current_approval(
            manifest,
            replace(approval, approval_request_id="f" * 64),
            now=approval.decided_at,
        )
    with pytest.raises(ReleaseError, match=r"approval\.naive_timestamp"):
        require_current_approval(
            manifest, approval, now=approval.decided_at.replace(tzinfo=None)
        )
    with pytest.raises(ReleaseError, match=r"approval\.invalid_actor"):
        replace(approval, actor="")
    with pytest.raises(ReleaseError, match=r"approval\.invalid_expiry"):
        replace(approval, expires_at=approval.decided_at)


def test_canonical_error_and_manifest_parse_failures(
    synthetic_release: SyntheticRelease,
) -> None:
    with pytest.raises(ReleaseError, match=r"release\.invalid_json"):
        canonical_json_bytes({"bad": float("nan")})
    with pytest.raises(ValueError, match="stable identifiers"):
        ReleaseError("BAD CODE", "message")
    bounded = ReleaseError("release.test", "x" * 2_000)
    assert len(bounded.to_dict()["message"]) == 1_000
    with pytest.raises(ReleaseError, match=r"release\.invalid_manifest"):
        parse_manifest(b"not-json")
    payload = synthetic_release.manifest.canonical_bytes().replace(
        synthetic_release.manifest.release_id.encode("ascii"), b"f" * 64, 1
    )
    with pytest.raises(ReleaseError, match=r"release\.manifest_identity_mismatch"):
        parse_manifest(payload)


def test_bundle_rejects_wrong_expected_id_and_other_tampering(
    synthetic_release: SyntheticRelease,
) -> None:
    bundle = synthetic_release.bundle
    with pytest.raises(ReleaseError, match=r"release\.unexpected_id"):
        verify_release_bundle(bundle, expected_release_id="f" * 64)
    (bundle / "risk" / "model.skops").write_bytes(b"tamper")
    with pytest.raises(ReleaseError, match=r"release\.classification_digest_mismatch"):
        verify_release_bundle(bundle)


def test_model_reference_accepts_exact_classification_contract() -> None:
    reference = ModelReference(
        task="classification",
        registered_name="fd001-failure-risk-classification",
        version="1",
        source_run_id="run",
        artifact_sha256="a" * 64,
        selected_family="class_balanced_logistic_regression",
        selected_parameters={},
        trusted_types=(),
        feature_columns=FEATURE_COLUMNS,
    )
    assert reference.task == "classification"
