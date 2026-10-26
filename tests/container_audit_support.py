"""Audit installed Python packages in a built image without mounting credentials."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def inventory_requirements(packages: list[dict[str, str]]) -> str:
    """Render a complete pinned inventory; exclude only our non-PyPI package."""
    requirements = []
    for package in packages:
        name, version = package["name"], package["version"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not re.fullmatch(
            r"[A-Za-z0-9!+_.-]+", version
        ):
            raise ValueError("Container inventory contains an invalid package entry.")
        if name.lower().replace("_", "-") != "predictive-maintenance-mlops":
            requirements.append(f"{name}=={version}")
    if not requirements:
        raise ValueError("Container inventory is empty.")
    return "\n".join(sorted(requirements, key=str.lower)) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "python",
        args.image,
    ]
    subprocess.run([*command, "-m", "pip", "check"], check=True, timeout=120)
    result = subprocess.run(
        [*command, "-m", "pip", "list", "--format=json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    requirements = inventory_requirements(json.loads(result.stdout))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    inventory = args.output_dir / "requirements.txt"
    inventory.write_text(requirements, encoding="utf-8")
    image_id = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", args.image],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    (args.output_dir / "image.json").write_text(
        json.dumps({"image": args.image, "image_id": image_id}) + "\n", encoding="utf-8"
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--disable-pip",
            "--no-deps",
            "-r",
            str(inventory),
            "--format=json",
            "--output",
            str(args.output_dir / "audit.json"),
        ],
        check=False,
        timeout=600,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
