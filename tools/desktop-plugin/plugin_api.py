"""microdata-lab desktop plugin backend.

Exposes repo state (analyses, gate status, tests) to the desktop plugin via
the /api/plugins/microdata-lab namespace. Commands run inside the cloned
repo (auto-detected; override with MICRODATA_LAB_REPO) using the project venv.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO = Path(os.environ.get("MICRODATA_LAB_REPO", str(Path.home() / "microdata-lab")))
UV = "uv"

# Long-running commands the backend is allowed to execute (allowlist).
_ALLOWED = {
    "status": [],
    "sources": ["microdata", "sources"],
    "gates": ["microdata", "viz", "gates"],
    "check": ["microdata", "check-analysis"],
    "tests": ["pytest", "-q"],
    "new": None,  # special-cased (takes an argument)
}


def _run(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    proc = subprocess.run(
        [UV, "run", *cmd],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout + proc.stderr)[-20000:]


def _status() -> dict:
    code, out = _run(["microdata", "check-analysis"], timeout=300)
    passed = out.count("✓")
    failed = out.count("✗")
    branch_out = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=REPO, capture_output=True, text=True
    )
    return {
        "repo": str(REPO),
        "branch_tip": branch_out.stdout.strip() or "(detached)",
        "contract_passed": passed,
        "contract_failed": failed,
        "raw_tail": out[-2000:],
        "ok": code == 0,
    }


def handle(req: dict) -> dict:
    action = req.get("action")
    if action == "status":
        return {"result": _status()}
    if action == "run":
        which = req.get("which")
        if not isinstance(which, str):
            return {"error": "missing 'which'"}
        cmd = _ALLOWED.get(which)
        if cmd is None:
            return {"error": f"unknown command: {which}"}
        args = list(cmd)
        if which == "new":
            slug = str(req.get("slug", "")).strip()
            if not slug or any(c in slug for c in "/\\") or ".." in slug:
                return {"error": "invalid slug"}
            args = ["microdata", "new", slug]
        try:
            code, out = _run(args, timeout=900)
        except subprocess.TimeoutExpired:
            return {"error": "timed out"}
        return {"exit": code, "output": out}
    return {"error": f"unsupported action: {action}"}
