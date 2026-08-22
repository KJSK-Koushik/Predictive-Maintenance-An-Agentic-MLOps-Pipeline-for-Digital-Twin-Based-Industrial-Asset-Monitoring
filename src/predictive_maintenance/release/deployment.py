"""Minimal fail-safe local staging pointer and rollback mechanics."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from predictive_maintenance.release.models import ReleaseError, require_sha256


@dataclass(frozen=True, slots=True)
class RolloutResult:
    """Bounded local rollout or rollback result."""

    active_release_id: str
    previous_release_id: str | None
    elapsed_seconds: float


class LocalStagingController:
    """Change one local pointer only after candidate validation succeeds."""

    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file

    def active_release_id(self) -> str | None:
        """Read and validate the current immutable release pointer."""
        try:
            value = self._state_file.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ReleaseError(
                "deployment.state_unreadable", "Staging state could not be read."
            ) from error
        require_sha256(value, "active_release_id")
        return value

    def _write(self, release_id: str) -> None:
        require_sha256(release_id, "release_id")
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=".phase6-staging-", dir=self._state_file.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as stream:
                stream.write(f"{release_id}\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._state_file)
        except OSError as error:
            raise ReleaseError(
                "deployment.state_write_failed", "Staging state could not be written."
            ) from error
        finally:
            temporary.unlink(missing_ok=True)

    def activate(
        self, release_id: str, *, smoke: Callable[[str], bool]
    ) -> RolloutResult:
        """Keep the old pointer when candidate smoke validation fails."""
        require_sha256(release_id, "release_id")
        started = time.monotonic()
        previous = self.active_release_id()
        if not smoke(release_id):
            raise ReleaseError(
                "deployment.candidate_smoke_failed",
                "Candidate failed smoke checks; staging was unchanged.",
            )
        self._write(release_id)
        return RolloutResult(release_id, previous, time.monotonic() - started)

    def rollback(
        self, previous_release_id: str, *, smoke: Callable[[str], bool]
    ) -> RolloutResult:
        """Restore a known previous release and verify it after the switch."""
        current = self.active_release_id()
        result = self.activate(previous_release_id, smoke=smoke)
        return RolloutResult(result.active_release_id, current, result.elapsed_seconds)
