"""Immutable domain contracts for a two-model Phase 6 release."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

FEATURE_COLUMNS = tuple(f"setting_{index}" for index in range(1, 4)) + tuple(
    f"sensor_{index}" for index in range(1, 22)
)

RELEASE_CONTRACT_VERSION = "fd001-two-model-release-v1"
APPROVAL_CONTRACT_VERSION = "fd001-staging-approval-v1"
REGRESSION_REGISTERED_NAME = "fd001-rul-regression"
CLASSIFICATION_REGISTERED_NAME = "fd001-failure-risk-classification"
STAGING_ALIAS = "staging"
RISK_HORIZON_CYCLES = 30
RISK_THRESHOLD = 0.5

_CODE = re.compile(r"^[a-z][a-z0-9_.]{2,99}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(value: object) -> bytes:
    """Encode finite canonical JSON without a training-runtime dependency."""
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise ReleaseError(
            "release.invalid_json", "Release evidence must be finite JSON."
        ) from error
    return (text + "\n").encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(payload).hexdigest()


class ReleaseError(Exception):
    """Stable, bounded release failure safe for reports and API responses."""

    def __init__(self, code: str, message: str) -> None:
        if not _CODE.fullmatch(code):
            raise ValueError("Release error codes must be stable identifiers.")
        bounded = message[:1000]
        super().__init__(f"{code}: {bounded}")
        self.code = code
        self.message = bounded

    def to_dict(self) -> dict[str, str]:
        """Return a sanitized representation."""
        return {"code": self.code, "message": self.message}


def require_sha256(value: str, field: str) -> None:
    """Require one lowercase SHA-256 identity."""
    if not _SHA256.fullmatch(value):
        raise ReleaseError("release.invalid_identity", f"{field} is not a SHA-256.")


@dataclass(frozen=True, slots=True)
class ModelReference:
    """Exact registry and artifact identity for one task model."""

    task: Literal["regression", "classification"]
    registered_name: str
    version: str
    source_run_id: str
    artifact_sha256: str
    selected_family: str
    selected_parameters: dict[str, Any]
    trusted_types: tuple[str, ...]
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS
    feature_dtype: str = "float64"

    def __post_init__(self) -> None:
        expected_name = (
            REGRESSION_REGISTERED_NAME
            if self.task == "regression"
            else CLASSIFICATION_REGISTERED_NAME
        )
        if self.registered_name != expected_name:
            raise ReleaseError(
                "release.registered_name_mismatch",
                "The registered name does not match the task contract.",
            )
        if not self.version.isdigit() or int(self.version) < 1:
            raise ReleaseError("release.invalid_version", "Model version is invalid.")
        if not self.source_run_id or len(self.source_run_id) > 100:
            raise ReleaseError("release.invalid_run", "Source run ID is invalid.")
        require_sha256(self.artifact_sha256, "artifact_sha256")
        if self.feature_columns != FEATURE_COLUMNS:
            raise ReleaseError(
                "release.feature_contract_mismatch",
                "Model features differ from the approved ordered contract.",
            )
        if self.feature_dtype != "float64":
            raise ReleaseError(
                "release.feature_dtype_mismatch", "Model input dtype must be float64."
            )
        expected_family = (
            "histogram_gradient_boosting"
            if self.task == "regression"
            else "class_balanced_logistic_regression"
        )
        if self.selected_family != expected_family:
            raise ReleaseError(
                "release.selected_family_mismatch",
                "Model family differs from the owner-approved Phase 5 selection.",
            )


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Canonical governed content for one atomic two-model release."""

    feature_snapshot_id: str
    processed_snapshot_id: str
    raw_snapshot_id: str
    split_id: str
    comparison_id: str
    selection_id: str
    regression: ModelReference
    classification: ModelReference
    verification_fixture_sha256: str
    code_revision: str
    python_version: str
    dependency_lock_sha256: str
    approval_request_id: str
    previous_release_id: str | None = None
    release_contract_version: str = RELEASE_CONTRACT_VERSION
    risk_horizon_cycles: int = RISK_HORIZON_CYCLES
    risk_threshold: float = RISK_THRESHOLD
    predictive_uncertainty_status: str = "not_available"

    def __post_init__(self) -> None:
        for field_name in (
            "feature_snapshot_id",
            "processed_snapshot_id",
            "raw_snapshot_id",
            "split_id",
            "comparison_id",
            "selection_id",
            "verification_fixture_sha256",
            "dependency_lock_sha256",
            "approval_request_id",
        ):
            require_sha256(str(getattr(self, field_name)), field_name)
        if self.previous_release_id is not None:
            require_sha256(self.previous_release_id, "previous_release_id")
        if self.regression.task != "regression":
            raise ReleaseError(
                "release.task_mismatch", "Regression reference is invalid."
            )
        if self.classification.task != "classification":
            raise ReleaseError(
                "release.task_mismatch", "Classification reference is invalid."
            )
        if not self.code_revision or len(self.code_revision) > 100:
            raise ReleaseError(
                "release.invalid_code_revision", "Code revision is invalid."
            )

    def identity_dict(self) -> dict[str, Any]:
        """Return exactly the governed fields used to derive the release ID."""
        return asdict(self)

    @property
    def release_id(self) -> str:
        """Return the SHA-256 identity of canonical governed content."""
        return sha256_bytes(canonical_json_bytes(self.identity_dict()))

    def to_dict(self) -> dict[str, Any]:
        """Return stored canonical content with its derived release ID."""
        return {"release_id": self.release_id, **self.identity_dict()}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored bytes."""
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """Append-only human decision over one exact release request."""

    approval_request_id: str
    release_id: str
    decision: Literal["approved", "rejected"]
    actor: str
    reason: str
    evidence_sha256: str
    decided_at: datetime
    expires_at: datetime
    approval_contract_version: str = APPROVAL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        require_sha256(self.approval_request_id, "approval_request_id")
        require_sha256(self.release_id, "release_id")
        require_sha256(self.evidence_sha256, "evidence_sha256")
        if not self.actor or len(self.actor) > 100:
            raise ReleaseError("approval.invalid_actor", "Approval actor is invalid.")
        if not self.reason or len(self.reason) > 500:
            raise ReleaseError("approval.invalid_reason", "Approval reason is invalid.")
        if self.decided_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ReleaseError(
                "approval.naive_timestamp", "Approval timestamps require a timezone."
            )
        if self.expires_at <= self.decided_at:
            raise ReleaseError(
                "approval.invalid_expiry", "Approval expiry must follow its decision."
            )

    def canonical_bytes(self) -> bytes:
        """Return deterministic approval evidence bytes."""
        value = asdict(self)
        value["decided_at"] = self.decided_at.isoformat()
        value["expires_at"] = self.expires_at.isoformat()
        return canonical_json_bytes(value)


def approval_request_id(request_fields: dict[str, Any]) -> str:
    """Derive the request ID before the release ID, avoiding a circular hash."""
    return sha256_bytes(
        canonical_json_bytes(
            {
                "approval_contract_version": APPROVAL_CONTRACT_VERSION,
                "request": request_fields,
            }
        )
    )
