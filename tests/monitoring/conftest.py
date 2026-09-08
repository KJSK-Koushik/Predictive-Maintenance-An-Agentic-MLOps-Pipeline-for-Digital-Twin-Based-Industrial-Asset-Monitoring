"""Deterministic Phase 7 monitoring fixtures."""

from __future__ import annotations

import pandas as pd
import pytest
from phase7_support import identity, telemetry_frame

from predictive_maintenance.monitoring.models import MonitoringPolicy, ReferenceProfile
from predictive_maintenance.monitoring.reference import build_reference_profile


@pytest.fixture
def policy() -> MonitoringPolicy:
    """Return the fixed synthetic policy."""
    return MonitoringPolicy()


@pytest.fixture
def reference_frame() -> pd.DataFrame:
    """Return source-training telemetry."""
    return telemetry_frame()


@pytest.fixture
def reference(
    reference_frame: pd.DataFrame, policy: MonitoringPolicy
) -> ReferenceProfile:
    """Return an immutable synthetic reference."""
    return build_reference_profile(
        reference_frame,
        release_id=identity("release"),
        feature_snapshot_id=identity("feature"),
        policy=policy,
        code_revision="phase7-tests",
        dependency_lock_sha256=identity("lock"),
    )
