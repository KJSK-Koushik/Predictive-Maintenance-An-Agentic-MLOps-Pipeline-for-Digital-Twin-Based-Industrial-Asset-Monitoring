"""Build ignored synthetic release bytes for CI and container smoke tests."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from phase6_support import build_synthetic_release


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.name != "inference-release":
        parser.error("Output directory must be named inference-release.")
    with tempfile.TemporaryDirectory(prefix="phase6-container-") as temporary:
        release = build_synthetic_release(Path(temporary))
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(release.bundle, output)
        print(release.manifest.release_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
