"""Backfill runner.

Deterministic, rate-limited, resumable backfill across enabled adapters.

* Discovers which years are missing from the lake for each source.
* Syncs missing years one at a time with a configurable delay between
  requests (provider-friendly).
* Tracks progress in a JSON state file so an interrupted run resumes
  where it left off instead of re-fetching completed years.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from microdata_lab.adapters import enabled_source_slugs, get_adapter
from microdata_lab.storage import sync_release

DEFAULT_DELAY_SECONDS = 5.0


@dataclass
class BackfillResult:
    source: str
    year: int
    status: str  # promoted | already-current | failed
    release_id: str | None = None
    error: str | None = None


def _state_path(data_root: Path) -> Path:
    return data_root / "logs" / "backfill-state.json"


def _load_state(data_root: Path) -> dict[str, Any]:
    path = _state_path(data_root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(data_root: Path, state: dict[str, Any]) -> None:
    path = _state_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def _promoted_years(data_root: Path, survey: str) -> set[int]:
    release_root = data_root / "releases" / survey
    if not release_root.is_dir():
        return set()
    years: set[int] = set()
    for year_dir in release_root.iterdir():
        if year_dir.is_dir():
            try:
                years.add(int(year_dir.name))
            except ValueError:
                continue
    return years


def plan_backfill(data_root: Path) -> dict[str, list[int]]:
    """Return {source: [missing years]} for every enabled adapter."""
    plan: dict[str, list[int]] = {}
    for slug in enabled_source_slugs():
        adapter = get_adapter(slug)
        try:
            available = adapter.available_years()
            promoted = _promoted_years(data_root, slug)
            missing = sorted(y for y in available if y not in promoted)
            if missing:
                plan[slug] = missing
        finally:
            adapter.close()
    return plan


def run_backfill(
    data_root: Path,
    *,
    delay: float = DEFAULT_DELAY_SECONDS,
    sources: list[str] | None = None,
    resume: bool = True,
) -> list[BackfillResult]:
    """Run backfill for missing years, resuming from the state file."""
    results: list[BackfillResult] = []
    plan = plan_backfill(data_root)
    if sources:
        plan = {slug: years for slug, years in plan.items() if slug in sources}
    state = _load_state(data_root) if resume else {}
    done = state.get("_done", [])

    for slug, years in plan.items():
        adapter = get_adapter(slug)
        try:
            for year in years:
                if f"{slug}:{year}" in done:
                    continue
                try:
                    release = adapter.discover(year=year)
                    result = sync_release(
                        release,
                        data_root,
                        adapter=adapter,
                        client=adapter.download_client(),
                    )
                    status = "promoted" if result.changed else "already-current"
                    results.append(BackfillResult(slug, year, status, result.manifest.release_id))
                except Exception as error:  # one bad year must not stop the run
                    results.append(BackfillResult(slug, year, "failed", error=str(error)))
                done.append(f"{slug}:{year}")
                state["_done"] = done
                _save_state(data_root, state)
                time.sleep(delay)
        finally:
            adapter.close()
    return results


def reset_backfill_state(data_root: Path) -> None:
    """Clear the backfill state file (after a source changed, for example)."""
    path = _state_path(data_root)
    if path.is_file():
        path.unlink()
