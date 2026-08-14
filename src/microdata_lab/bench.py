"""Benchmark re-run.

Re-executes every implemented adapter's source-specific validation
(including official benchmarks) against the current immutable release
without fetching anything from the network.

Outputs a machine-readable summary suitable for CI gates and the
status report.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from microdata_lab.adapters import enabled_source_slugs, get_adapter
from microdata_lab.storage import validate_current_release


@dataclass
class BenchRow:
    survey: str
    year: int
    release_id: str
    checks: int
    passed_checks: int
    benchmark_passed: bool | None
    benchmark_name: str | None = None
    benchmark_observed: float | None = None
    benchmark_expected: float | None = None


def run_bench(data_root: Path) -> list[BenchRow]:
    """Re-run benchmark gates for every enabled adapter's current release."""
    rows: list[BenchRow] = []
    for slug in enabled_source_slugs():
        adapter = None
        try:
            adapter = get_adapter(slug)
            manifest, _ = validate_current_release(data_root, slug, adapter=adapter)
        except Exception:
            rows.append(
                BenchRow(
                    survey=slug,
                    year=0,
                    release_id="unavailable",
                    checks=0,
                    passed_checks=0,
                    benchmark_passed=None,
                )
            )
            continue
        finally:
            if adapter is not None:
                adapter.close()

        checks = manifest.validation.checks
        passed = sum(1 for ok in checks.values() if ok)
        benchmark_passed: bool | None = None
        benchmark_name: str | None = None
        observed: float | None = None
        expected: float | None = None
        for name, ok in checks.items():
            # Generic benchmark checks AND the SCF-style check name.
            if "benchmark" in name or "net_worth_within" in name:
                benchmark_passed = ok
                benchmark_name = name
        notes = manifest.validation.notes or []
        for note in notes:
            if "benchmark" in note or "reproduced versus" in note:
                if benchmark_name is None:
                    benchmark_name = note[:80]
                # SCF note: "$192,084 reproduced versus $192,900 official"
                m = re.search(r"\$([\d,]+) reproduced versus \$([\d,]+)", note)
                if m:
                    observed = float(m.group(1).replace(",", ""))
                    expected = float(m.group(2).replace(",", ""))

        rows.append(
            BenchRow(
                survey=slug,
                year=manifest.year,
                release_id=manifest.release_id,
                checks=len(checks),
                passed_checks=passed,
                benchmark_passed=benchmark_passed,
                benchmark_name=benchmark_name,
                benchmark_observed=observed,
                benchmark_expected=expected,
            )
        )
    return rows


def bench_to_json(rows: list[BenchRow]) -> str:
    return json.dumps([asdict(row) for row in rows], indent=2)
