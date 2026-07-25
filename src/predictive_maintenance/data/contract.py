"""Stable FD001 contract constants and project-owned errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DATASET_FAMILY = "NASA C-MAPSS"
DATASET_SUBSET = "FD001"
CONTRACT_VERSION = "fd001-v1"
PARSER_VERSION = "fd001-whitespace-v1"
SOURCE_URL = (
    "https://www.nasa.gov/intelligent-systems-division/"
    "discovery-and-systems-health/pcoe/pcoe-data-set-repository/"
)
SOURCE_CITATION = (
    "Saxena, A. and Goebel, K. (2008), Turbofan Engine Degradation "
    "Simulation Data Set, NASA Ames Prognostics Data Repository."
)

TRAIN_FILENAME = "train_FD001.txt"
TEST_FILENAME = "test_FD001.txt"
RUL_FILENAME = "RUL_FD001.txt"
README_FILENAME = "readme.txt"
REQUIRED_FILENAMES = (
    TRAIN_FILENAME,
    TEST_FILENAME,
    RUL_FILENAME,
    README_FILENAME,
)

IDENTIFIER_COLUMNS = ("engine_id", "cycle")
SETTING_COLUMNS = tuple(f"setting_{index}" for index in range(1, 4))
SENSOR_COLUMNS = tuple(f"sensor_{index}" for index in range(1, 22))
TELEMETRY_COLUMNS = IDENTIFIER_COLUMNS + SETTING_COLUMNS + SENSOR_COLUMNS

PRIMARY_RISK_HORIZON = 30
SENSITIVITY_RISK_HORIZONS = (15, 30, 45)


@dataclass(frozen=True, slots=True)
class ContractError(Exception):
    """A stable, structured contract failure."""

    rule_id: str
    message: str
    logical_file: str | None = None
    line: int | None = None
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        location = f" in {self.logical_file}" if self.logical_file else ""
        line = f" at line {self.line}" if self.line is not None else ""
        return f"{self.rule_id}{location}{line}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without workstation paths."""
        result: dict[str, Any] = {
            "rule_id": self.rule_id,
            "message": self.message,
        }
        if self.logical_file is not None:
            result["logical_file"] = self.logical_file
        if self.line is not None:
            result["line"] = self.line
        if self.details:
            result["details"] = self.details
        return result
