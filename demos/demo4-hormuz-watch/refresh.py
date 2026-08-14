#!/usr/bin/env python3
"""Refresh the Hormuz watch and stay quiet when the release is unchanged."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analyses" / "energy-2026-hormuz-inflation-watch"


def current_release_id() -> str | None:
    from microdata_lab.config import resolve_data_root

    pointer = resolve_data_root(None) / "current" / "energy_watch.json"
    if not pointer.is_file():
        return None
    return str(json.loads(pointer.read_text()).get("release_id"))


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if the release is unchanged",
    )
    args = parser.parse_args()

    before = current_release_id()
    run(["uv", "run", "microdata", "sync", "energy_watch", "--year", "2026"])
    after = current_release_id()
    if before == after and not args.force:
        return

    run(["uv", "run", "python", str(ANALYSIS / "estimate.py")])
    run(
        [
            "uv",
            "run",
            "microdata",
            "viz",
            "static",
            str(ANALYSIS / "data.csv"),
            str(ANALYSIS / "chart.yaml"),
            str(ANALYSIS / "figure.png"),
        ]
    )
    run(
        [
            "uv",
            "run",
            "microdata",
            "viz",
            "interactive",
            str(ANALYSIS / "data.csv"),
            str(ANALYSIS / "chart.yaml"),
            str(ANALYSIS / "interactive.html"),
        ]
    )
    run(["uv", "run", "python", "demos/scripts/build_media.py"])
    print(f"Hormuz watch rebuilt from {after}")


if __name__ == "__main__":
    main()
