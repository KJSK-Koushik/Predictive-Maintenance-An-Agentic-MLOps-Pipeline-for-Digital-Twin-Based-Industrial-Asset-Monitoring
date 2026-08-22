"""Shared fail-closed skops trusted-type inspection without MLflow imports."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import skops.io as sio  # type: ignore[import-untyped]

from predictive_maintenance.release.models import ReleaseError

_TRUSTED_TYPE_PREFIXES = ("builtins.", "numpy.", "sklearn.")


def trusted_types(path: Path) -> tuple[str, ...]:
    """Return inspected types or reject anything outside the approved families."""
    unknown = tuple(sorted(sio.get_untrusted_types(file=path)))
    prohibited = [
        item for item in unknown if not item.startswith(_TRUSTED_TYPE_PREFIXES)
    ]
    if prohibited:
        raise ReleaseError(
            "model.untrusted_type", "Model artifact contains a prohibited type."
        )
    return unknown


def dump_deterministic(model: object, path: Path) -> None:
    """Write skops bytes with stable internal IDs, ordering, and ZIP metadata."""
    sio.dump(model, path)
    try:
        with zipfile.ZipFile(path, "r") as archive:
            entries = {
                item.filename: archive.read(item.filename)
                for item in archive.infolist()
            }
        schema: Any = json.loads(entries.pop("schema.json"))
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise ReleaseError(
            "model.serialization_failed", "Skops output could not be normalized."
        ) from error

    identities: dict[int, int] = {}

    def stable_id(value: int) -> int:
        if value not in identities:
            identities[value] = len(identities) + 1
        return identities[value]

    def normalize(value: Any) -> None:
        if isinstance(value, dict):
            identifier = value.get("__id__")
            if isinstance(identifier, int):
                value["__id__"] = stable_id(identifier)
            filename = value.get("file")
            if isinstance(filename, str) and filename.endswith(".npy"):
                stem = filename.removesuffix(".npy")
                if stem.isdigit():
                    value["file"] = f"{stable_id(int(stem))}.npy"
            for item in value.values():
                normalize(item)
        elif isinstance(value, list):
            for item in value:
                normalize(item)

    normalize(schema)
    normalized_entries: dict[str, bytes] = {
        "schema.json": json.dumps(
            schema,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    }
    for filename, payload in entries.items():
        stem = filename.removesuffix(".npy")
        normalized = (
            f"{stable_id(int(stem))}.npy"
            if filename.endswith(".npy") and stem.isdigit()
            else filename
        )
        normalized_entries[normalized] = payload

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".phase6-skops-", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for filename in sorted(normalized_entries):
                info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o600 << 16
                archive.writestr(info, normalized_entries[filename])
        os.replace(temporary, path)
    except OSError as error:
        raise ReleaseError(
            "model.serialization_failed", "Deterministic skops output failed."
        ) from error
    finally:
        temporary.unlink(missing_ok=True)
