"""Deterministic investigation and retraining-candidate rules."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from predictive_maintenance.monitoring.models import (
    MonitoringError,
    MonitoringPolicy,
    MonitoringReport,
    canonical_json_bytes,
    sha256_bytes,
)
from predictive_maintenance.release.models import require_sha256

TRIGGER_CONTRACT_VERSION = "fd001-retraining-trigger-v1"
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_.]{2,99}$")


@dataclass(frozen=True, slots=True)
class Investigation:
    """A bounded review request that grants no training authority."""

    report_id: str
    category: Literal["data_quality", "service", "distribution_shift"]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        require_sha256(self.report_id, "report_id")
        if self.category not in {
            "data_quality",
            "service",
            "distribution_shift",
        }:
            raise MonitoringError(
                "trigger.invalid_category", "Investigation category is invalid."
            )
        if not 1 <= len(self.reason_codes) <= 50 or any(
            not _REASON_CODE.fullmatch(code) for code in self.reason_codes
        ):
            raise MonitoringError(
                "trigger.invalid_reason_codes",
                "Investigation reasons must be bounded identifiers.",
            )

    @property
    def investigation_id(self) -> str:
        """Hash exact investigation evidence."""
        return sha256_bytes(canonical_json_bytes(asdict(self)))


@dataclass(frozen=True, slots=True)
class CandidateRequest:
    """Immutable request to evaluate a candidate, never to train or promote it."""

    release_id: str
    policy_id: str
    requested_task: Literal["regression", "classification", "both"]
    data_cutoff_window_id: str
    evidence_report_ids: tuple[str, ...]
    reason: Literal["persistent_shift", "performance_degradation"]
    authority: Literal["evaluation_only"] = "evaluation_only"
    trigger_contract_version: str = TRIGGER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field in ("release_id", "policy_id", "data_cutoff_window_id"):
            require_sha256(str(getattr(self, field)), field)
        if not 1 <= len(self.evidence_report_ids) <= 20:
            raise MonitoringError(
                "trigger.missing_evidence",
                "Candidate request requires one to twenty report identities.",
            )
        for report_id in self.evidence_report_ids:
            require_sha256(report_id, "evidence_report_id")
        if len(set(self.evidence_report_ids)) != len(self.evidence_report_ids):
            raise MonitoringError(
                "trigger.duplicate_evidence", "Candidate evidence must be unique."
            )
        if self.requested_task not in {"regression", "classification", "both"}:
            raise MonitoringError("trigger.invalid_task", "Candidate task is invalid.")
        if self.reason not in {"persistent_shift", "performance_degradation"}:
            raise MonitoringError(
                "trigger.invalid_reason", "Candidate reason is invalid."
            )
        if self.authority != "evaluation_only":
            raise MonitoringError(
                "trigger.invalid_authority",
                "Candidate requests have evaluation-only authority.",
            )

    @property
    def request_id(self) -> str:
        """Hash exact evidence, cutoff, and policy."""
        return sha256_bytes(canonical_json_bytes(asdict(self)))

    def to_dict(self) -> dict[str, Any]:
        """Return stored request content with identity."""
        return {"request_id": self.request_id, **asdict(self)}


@dataclass(frozen=True, slots=True)
class TriggerDecision:
    """Complete rule result with no side-effect authority."""

    investigations: tuple[Investigation, ...]
    candidate_request: CandidateRequest | None
    status: Literal["no_action", "investigate", "candidate_requested"]


def evaluate_triggers(
    reports: tuple[MonitoringReport, ...],
    *,
    policy: MonitoringPolicy,
    performance_degraded: bool = False,
) -> TriggerDecision:
    """Apply fail-closed deterministic trigger semantics."""
    if not reports:
        raise MonitoringError("trigger.no_reports", "At least one report is required.")
    if any(report.policy_id != policy.policy_id for report in reports):
        raise MonitoringError(
            "trigger.policy_mismatch", "Every report must use the trigger policy."
        )
    latest = reports[-1]
    investigations: list[Investigation] = []
    if latest.data_quality.status in {"invalid", "alert"}:
        investigations.append(
            Investigation(
                latest.report_id,
                "data_quality",
                latest.data_quality.reason_codes or ("quality.investigation",),
            )
        )
        return TriggerDecision(tuple(investigations), None, "investigate")
    if latest.service_health.status in {"invalid", "alert", "unavailable"}:
        investigations.append(
            Investigation(
                latest.report_id,
                "service",
                latest.service_health.reason_codes or ("service.investigation",),
            )
        )
        return TriggerDecision(tuple(investigations), None, "investigate")

    shifted = (
        latest.feature_shift.status == "alert"
        or latest.prediction_shift.status == "alert"
    )
    if shifted:
        investigations.append(
            Investigation(
                latest.report_id,
                "distribution_shift",
                ("shift.investigation",),
            )
        )
    adequate_history = reports[-policy.persistent_drift_windows :]
    persistent = len(adequate_history) == policy.persistent_drift_windows and all(
        report.data_quality.status == "pass"
        and (
            report.feature_shift.status == "alert"
            or report.prediction_shift.status == "alert"
        )
        for report in adequate_history
    )
    available_performance = latest.delayed_performance.status == "pass"
    if not persistent and not (performance_degraded and available_performance):
        return TriggerDecision(
            tuple(investigations),
            None,
            "investigate" if investigations else "no_action",
        )
    reason: Literal["persistent_shift", "performance_degradation"] = (
        "performance_degradation"
        if performance_degraded and available_performance
        else "persistent_shift"
    )
    evidence = (
        (latest.report_id,)
        if reason == "performance_degradation"
        else tuple(report.report_id for report in adequate_history)
    )
    request = CandidateRequest(
        release_id=latest.window.release_id,
        policy_id=policy.policy_id,
        requested_task="both",
        data_cutoff_window_id=latest.window.window_id,
        evidence_report_ids=evidence,
        reason=reason,
    )
    return TriggerDecision(tuple(investigations), request, "candidate_requested")
