"""Immutable, versioned Phase 7 monitoring contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

from predictive_maintenance.release.models import FEATURE_COLUMNS, require_sha256

SignalStatus = Literal[
    "pass", "warning", "alert", "insufficient_data", "unavailable", "invalid"
]

REFERENCE_CONTRACT_VERSION = "fd001-monitor-reference-v1"
WINDOW_CONTRACT_VERSION = "fd001-monitoring-window-v1"
POLICY_CONTRACT_VERSION = "fd001-monitor-trigger-policy-v1"
REPORT_CONTRACT_VERSION = "fd001-monitor-report-v1"
LABEL_CONTRACT_VERSION = "fd001-delayed-performance-v1"
SERVICE_CONTRACT_VERSION = "fd001-service-probe-v1"

_CODE = re.compile(r"^[a-z][a-z0-9_.]{2,99}$")
_STATUS_VALUES = {
    "pass",
    "warning",
    "alert",
    "insufficient_data",
    "unavailable",
    "invalid",
}


class MonitoringError(Exception):
    """Stable, bounded monitoring failure safe for reports and logs."""

    def __init__(self, code: str, message: str) -> None:
        if not _CODE.fullmatch(code):
            raise ValueError("Monitoring error codes must be stable identifiers.")
        bounded = message[:1000]
        super().__init__(f"{code}: {bounded}")
        self.code = code
        self.message = bounded

    def to_dict(self) -> dict[str, str]:
        """Return bounded error evidence."""
        return {"code": self.code, "message": self.message}


def canonical_json_bytes(value: object) -> bytes:
    """Encode finite canonical JSON for content-addressed evidence."""
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise MonitoringError(
            "monitoring.invalid_json", "Monitoring evidence must be finite JSON."
        ) from error
    return (encoded + "\n").encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(payload).hexdigest()


def _require_finite(value: float, field: str) -> None:
    if not math.isfinite(value):
        raise MonitoringError("monitoring.nonfinite", f"{field} must be finite.")


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Thresholds fixed before evaluating a monitored window."""

    minimum_rows: int = 30
    minimum_engines: int = 3
    max_rows_per_engine: int = 100
    warning_psi: float = 0.10
    alert_psi: float = 0.25
    warning_location_shift: float = 0.50
    alert_location_shift: float = 1.00
    performance_rmse_ratio_alert: float = 1.10
    performance_brier_delta_alert: float = 0.05
    persistent_drift_windows: int = 2
    policy_contract_version: str = POLICY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.minimum_rows < 1 or self.minimum_engines < 1:
            raise MonitoringError(
                "policy.invalid_adequacy", "Minimum rows and engines must be positive."
            )
        if self.max_rows_per_engine < 1:
            raise MonitoringError(
                "policy.invalid_sampling", "Per-engine sample limit must be positive."
            )
        numeric = (
            self.warning_psi,
            self.alert_psi,
            self.warning_location_shift,
            self.alert_location_shift,
            self.performance_rmse_ratio_alert,
            self.performance_brier_delta_alert,
        )
        if not all(math.isfinite(value) and value >= 0 for value in numeric):
            raise MonitoringError(
                "policy.invalid_threshold", "Policy thresholds must be finite."
            )
        if self.warning_psi >= self.alert_psi:
            raise MonitoringError(
                "policy.invalid_threshold", "PSI warning must be below alert."
            )
        if self.warning_location_shift >= self.alert_location_shift:
            raise MonitoringError(
                "policy.invalid_threshold", "Location warning must be below alert."
            )
        if self.persistent_drift_windows < 2:
            raise MonitoringError(
                "policy.invalid_persistence", "Persistent drift requires two windows."
            )

    @property
    def policy_id(self) -> str:
        """Hash every governed policy field."""
        return sha256_bytes(canonical_json_bytes(asdict(self)))

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready policy evidence."""
        return {"policy_id": self.policy_id, **asdict(self)}


@dataclass(frozen=True, slots=True)
class FeatureReference:
    """Bounded distribution summary for one ordered model input."""

    name: str
    quantile_edges: tuple[float, ...]
    bin_probabilities: tuple[float, ...]
    minimum: float
    maximum: float
    median: float
    iqr: float

    def __post_init__(self) -> None:
        if self.name not in FEATURE_COLUMNS:
            raise MonitoringError(
                "reference.unknown_feature", "Reference contains an unknown feature."
            )
        values = (
            *self.quantile_edges,
            *self.bin_probabilities,
            self.minimum,
            self.maximum,
            self.median,
            self.iqr,
        )
        if not all(math.isfinite(value) for value in values):
            raise MonitoringError(
                "reference.nonfinite", "Reference summaries must be finite."
            )
        if tuple(sorted(set(self.quantile_edges))) != self.quantile_edges:
            raise MonitoringError(
                "reference.invalid_bins", "Reference edges must be unique and ordered."
            )
        if len(self.bin_probabilities) != len(self.quantile_edges) + 1:
            raise MonitoringError(
                "reference.invalid_bins", "Reference bin counts do not match edges."
            )
        if not math.isclose(sum(self.bin_probabilities), 1.0, abs_tol=1e-9):
            raise MonitoringError(
                "reference.invalid_bins", "Reference bin probabilities must sum to one."
            )


@dataclass(frozen=True, slots=True)
class ReferenceProfile:
    """Immutable engine-balanced source-training reference."""

    release_id: str
    feature_snapshot_id: str
    source_partition: Literal["train"]
    policy_id: str
    row_count: int
    engine_count: int
    sampled_row_count: int
    features: tuple[FeatureReference, ...]
    lifecycle_mix: dict[str, float]
    operating_setting_summary: dict[str, float]
    code_revision: str
    dependency_lock_sha256: str
    reference_contract_version: str = REFERENCE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field in (
            "release_id",
            "feature_snapshot_id",
            "policy_id",
            "dependency_lock_sha256",
        ):
            require_sha256(cast(str, getattr(self, field)), field)
        if tuple(item.name for item in self.features) != FEATURE_COLUMNS:
            raise MonitoringError(
                "reference.feature_order",
                "Reference must contain all 24 inputs in order.",
            )
        if self.row_count < self.sampled_row_count or self.engine_count < 1:
            raise MonitoringError(
                "reference.invalid_counts", "Reference counts are inconsistent."
            )
        if not self.code_revision or len(self.code_revision) > 100:
            raise MonitoringError(
                "reference.invalid_revision", "Code revision is invalid."
            )

    @property
    def reference_id(self) -> str:
        """Hash all governed reference content."""
        return sha256_bytes(canonical_json_bytes(asdict(self)))

    def to_dict(self) -> dict[str, Any]:
        """Return stored content with its derived identity."""
        return {"reference_id": self.reference_id, **asdict(self)}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored bytes."""
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True, slots=True)
class MonitoringWindow:
    """Immutable membership and lineage for one ordered replay window."""

    release_id: str
    reference_id: str
    policy_id: str
    raw_snapshot_id: str
    processed_snapshot_id: str
    feature_snapshot_id: str
    source_partition: Literal["train", "validation", "test", "synthetic"]
    membership_sha256: str
    row_count: int
    engine_count: int
    replay_sequence: int
    code_revision: str
    dependency_lock_sha256: str
    prediction_contract_version: str = "fd001-inference-v1"
    window_contract_version: str = WINDOW_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field in (
            "release_id",
            "reference_id",
            "policy_id",
            "raw_snapshot_id",
            "processed_snapshot_id",
            "feature_snapshot_id",
            "membership_sha256",
            "dependency_lock_sha256",
        ):
            require_sha256(cast(str, getattr(self, field)), field)
        if self.row_count < 1 or self.engine_count < 1 or self.replay_sequence < 1:
            raise MonitoringError(
                "window.invalid_counts", "Window counts and sequence must be positive."
            )
        if not self.code_revision or len(self.code_revision) > 100:
            raise MonitoringError(
                "window.invalid_revision", "Code revision is invalid."
            )

    @property
    def window_id(self) -> str:
        """Hash exact window membership and governed lineage."""
        return sha256_bytes(canonical_json_bytes(asdict(self)))

    def to_dict(self) -> dict[str, Any]:
        """Return stored content with identity."""
        return {"window_id": self.window_id, **asdict(self)}


@dataclass(frozen=True, slots=True)
class SignalResult:
    """One bounded monitoring section."""

    status: SignalStatus
    summary: dict[str, Any]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise MonitoringError("signal.invalid_status", "Signal status is invalid.")
        if len(self.reason_codes) > 50 or any(
            not _CODE.fullmatch(code) for code in self.reason_codes
        ):
            raise MonitoringError(
                "signal.invalid_reason", "Signal reasons must be bounded identifiers."
            )
        if len(canonical_json_bytes(self.summary)) > 256_000:
            raise MonitoringError(
                "signal.summary_too_large", "Signal summary exceeds its size limit."
            )


@dataclass(frozen=True, slots=True)
class MonitoringReport:
    """Canonical aggregate report with separated signal classes."""

    window: MonitoringWindow
    reference_id: str
    policy_id: str
    data_quality: SignalResult
    feature_shift: SignalResult
    prediction_shift: SignalResult
    service_health: SignalResult
    delayed_performance: SignalResult
    lifecycle_mix: dict[str, float]
    operating_setting_summary: dict[str, float]
    limitations: tuple[str, ...]
    parent_report_id: str | None = None
    label_snapshot_id: str | None = None
    report_contract_version: str = REPORT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        require_sha256(self.reference_id, "reference_id")
        require_sha256(self.policy_id, "policy_id")
        if self.reference_id != self.window.reference_id:
            raise MonitoringError(
                "report.reference_mismatch", "Report and window reference differ."
            )
        if self.policy_id != self.window.policy_id:
            raise MonitoringError(
                "report.policy_mismatch", "Report and window policy differ."
            )
        if self.parent_report_id is not None:
            require_sha256(self.parent_report_id, "parent_report_id")
        if self.label_snapshot_id is not None:
            require_sha256(self.label_snapshot_id, "label_snapshot_id")
        if len(self.limitations) > 20 or any(
            len(item) > 300 for item in self.limitations
        ):
            raise MonitoringError(
                "report.invalid_limitations", "Report limitations are not bounded."
            )
        if self.data_quality.status == "invalid" and any(
            signal.status not in {"invalid", "unavailable"}
            for signal in (
                self.feature_shift,
                self.prediction_shift,
                self.delayed_performance,
            )
        ):
            raise MonitoringError(
                "report.invalid_quality_flow",
                "Invalid data quality must block downstream monitoring signals.",
            )

    def identity_dict(self) -> dict[str, Any]:
        """Return exactly the fields that determine report identity."""
        return asdict(self)

    @property
    def report_id(self) -> str:
        """Hash the complete bounded report."""
        return sha256_bytes(canonical_json_bytes(self.identity_dict()))

    def to_dict(self) -> dict[str, Any]:
        """Return stored report content with identity."""
        return {"report_id": self.report_id, **self.identity_dict()}

    def canonical_bytes(self) -> bytes:
        """Return deterministic stored report bytes."""
        payload = canonical_json_bytes(self.to_dict())
        if len(payload) > 1_000_000:
            raise MonitoringError(
                "report.too_large", "Monitoring report exceeds one megabyte."
            )
        return payload
