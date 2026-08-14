from __future__ import annotations

from pathlib import Path

import pytest

import microdata_lab.bench as bench_module
from microdata_lab.bench import BenchRow, run_bench
from microdata_lab.comparability import (
    ComparabilityRow,
    run_comparability,
)


def _fake_manifest(data_root: Path, survey: str, year: int) -> Path:
    """Write a minimal valid release + current pointer for bench/comparability."""
    release_dir = data_root / "releases" / survey / str(year) / ("a" * 64)
    (release_dir / "normalized").mkdir(parents=True)
    import json

    manifest = {
        "schema_version": 1,
        "survey": survey,
        "year": year,
        "release_id": f"{survey}-{year}-{'b' * 12}",
        "landing_page": "https://example.com",
        "artifacts": [],
        "normalized_assets": [],
        "source_metadata": {},
        "validation": {"checks": {"benchmark_ok": True, "other": True}, "notes": []},
    }
    (release_dir / "manifest.json").write_text(json.dumps(manifest))
    (data_root / "current").mkdir(exist_ok=True)
    (data_root / "current" / f"{survey}.json").write_text(
        json.dumps(
            {
                "survey": survey,
                "year": year,
                "release_id": f"{survey}-{year}-{'b' * 12}",
                "release_path": str(release_dir),
            }
        )
    )
    return release_dir


def test_run_bench_reports_checks_and_benchmark(tmp_path: Path) -> None:
    _fake_manifest(tmp_path, "eurostat", 2023)
    # The eurostat adapter validates against its config; this test only
    # asserts the plumbing returns a row (live data may or may not be present).
    rows = run_bench(tmp_path)
    assert isinstance(rows, list)
    assert all(isinstance(r, BenchRow) for r in rows)


def test_run_bench_reports_unavailable_when_adapter_needs_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bench_module, "enabled_source_slugs", lambda: ["credentialed"])

    def missing_credentials(_slug: str) -> None:
        raise RuntimeError("credential unavailable")

    monkeypatch.setattr(bench_module, "get_adapter", missing_credentials)

    assert run_bench(tmp_path) == [
        BenchRow(
            survey="credentialed",
            year=0,
            release_id="unavailable",
            checks=0,
            passed_checks=0,
            benchmark_passed=None,
        )
    ]


def test_bench_row_defaults() -> None:
    row = BenchRow(
        survey="x",
        year=2024,
        release_id="x-2024-abcdef123456",
        checks=3,
        passed_checks=3,
        benchmark_passed=True,
    )
    assert row.benchmark_name is None
    assert row.benchmark_observed is None


def test_comparability_returns_rows(tmp_path: Path) -> None:
    _fake_manifest(tmp_path, "acs_pums", 2023)
    _fake_manifest(tmp_path, "cps_asec", 2024)
    rows = run_comparability(tmp_path)
    assert isinstance(rows, list)
    assert all(isinstance(r, ComparabilityRow) for r in rows)
    # Missing normalized parquet => checks report skipped or failed, not crash.
    for row in rows:
        assert row.check
