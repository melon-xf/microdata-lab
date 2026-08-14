from __future__ import annotations

import json
from pathlib import Path

import yaml

from microdata_lab.analysis_checks import (
    check_all_analyses,
    check_analysis_directory,
)


def _write_analysis(
    root: Path,
    name: str,
    *,
    omit: list[str] | None = None,
    bad_chart: bool = False,
    bad_diagnostics: bool = False,
    bad_figure: bool = False,
) -> Path:
    analysis = root / name
    analysis.mkdir(parents=True)
    omit = omit or []
    files: dict[str, str | bytes] = {
        "question.md": "# Question\nEstimand: test.\n",
        "estimate.py": "print('ok')\n",
        "data.csv": "group,estimate,ci_low,ci_high\nA,1.0,0.5,1.5\nB,2.0,1.0,3.0\n",
        "diagnostics.json": json.dumps(
            {
                "analysis": name,
                "release_id": "test-2024-abcdef123456",
                "row_counts": {"rows": 2},
                "weighted_population": {"pop": 100},
                "missingness": {"estimate": 0},
                "design": {"main_weight": "w"},
                "uncertainty": {"method": "none"},
                "benchmark": {
                    "name": "test",
                    "observed": 1.0,
                    "expected": 1.0,
                    "passed": True,
                },
            }
        ),
        "chart.yaml": yaml.safe_dump(
            {
                "chart_type": "bar",
                "title": "Test chart",
                "subtitle": "Test population, measure, 2024",
                "x": "group",
                "y": "estimate",
                "ci_low": "ci_low",
                "ci_high": "ci_high",
                "value_format": "number",
            }
        ),
        "figure.png": b"\x89PNG\r\n\x1a\n" + b"0" * 4096,
        "interactive.html": "<!DOCTYPE html>" + "x" * 2048,
        "README.md": "# Results\n",
    }
    for filename, content in files.items():
        if filename in omit:
            continue
        if filename == "figure.png" and bad_figure:
            content = b"not a png"
        target = analysis / filename
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content)

    if bad_chart:
        (analysis / "chart.yaml").write_text(
            yaml.safe_dump(
                {
                    "chart_type": "bar",
                    "x": "missing_column",
                    "y": "estimate",
                    "ci_low": "ci_low",
                    "value_format": "not-a-format",
                }
            )
        )
    if bad_diagnostics:
        (analysis / "diagnostics.json").write_text("{not json")
    return analysis


def test_valid_analysis_passes(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "good-analysis")
    result = check_analysis_directory(tmp_path / "good-analysis")
    assert result.passed
    assert result.issues == []


def test_missing_required_file_fails(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "missing-readme", omit=["README.md"])
    result = check_analysis_directory(tmp_path / "missing-readme")
    assert not result.passed
    assert any("README.md" in issue.message for issue in result.issues)


def test_missing_estimate_fails(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "no-estimate", omit=["estimate.py"])
    result = check_analysis_directory(tmp_path / "no-estimate")
    assert not result.passed
    assert any("estimate.py or estimate.R" in issue.message for issue in result.issues)


def test_chart_lint_catches_bad_column_and_format(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "bad-chart", bad_chart=True)
    result = check_analysis_directory(tmp_path / "bad-chart")
    assert not result.passed
    messages = [issue.message for issue in result.issues]
    assert any("missing_column" in message for message in messages)
    assert any("value_format" in message for message in messages)
    assert any("ci_low and ci_high" in message for message in messages)


def test_chart_lint_requires_title_and_subtitle(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "no-title")
    chart_path = tmp_path / "no-title" / "chart.yaml"
    chart = yaml.safe_load(chart_path.read_text())
    chart.pop("title")
    chart.pop("subtitle")
    chart_path.write_text(yaml.safe_dump(chart))
    result = check_analysis_directory(tmp_path / "no-title")
    assert not result.passed
    messages = [issue.message for issue in result.issues]
    assert any("title" in message for message in messages)
    assert any("subtitle" in message for message in messages)


def test_diagnostics_lint_catches_malformed_json(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "bad-diag", bad_diagnostics=True)
    result = check_analysis_directory(tmp_path / "bad-diag")
    assert not result.passed
    assert any("diagnostics.json" in issue.message for issue in result.issues)


def test_figure_lint_catches_bad_png(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "bad-figure", bad_figure=True)
    result = check_analysis_directory(tmp_path / "bad-figure")
    assert not result.passed
    assert any("PNG" in issue.message for issue in result.issues)


def test_check_all_analyses_scans_directories(tmp_path: Path) -> None:
    _write_analysis(tmp_path, "ok-a")
    _write_analysis(tmp_path, "ok-b")
    results = check_all_analyses(tmp_path)
    assert len(results) == 2
    assert all(result.passed for result in results)


def test_scf_style_benchmark_accepted(tmp_path: Path) -> None:
    analysis = _write_analysis(tmp_path, "scf-style")
    diag = json.loads((analysis / "diagnostics.json").read_text())
    diag["benchmark"] = {
        "name": "2022 median net worth",
        "reproduced_dollars": 192084,
        "official_dollars": 192900,
        "passed": True,
    }
    (analysis / "diagnostics.json").write_text(json.dumps(diag))
    result = check_analysis_directory(analysis)
    assert result.passed
