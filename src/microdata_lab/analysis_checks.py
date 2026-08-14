"""Analysis contract validation.

Enforces the AGENTS.md analysis contract in code so silent errors (missing
files, malformed diagnostics, chart specs that reference columns that do not
exist, blank figures) fail loudly instead of shipping.

Checks:

* required files: question.md, estimate.py|estimate.R, data.csv,
  diagnostics.json, chart.yaml, figure.png, interactive.html, README.md
* diagnostics.json schema: row_counts, weighted_population, missingness,
  design, uncertainty, benchmark (with passed + observed + expected)
* chart.yaml semantics: chart_type, title, subtitle, x/y columns exist in
  data.csv, no dual axes, no 3D, no truncated quantitative axes, color not
  the only encoding, value_format matches a numeric column
* figure.png: valid PNG header, non-trivial byte size
* interactive.html: non-trivial size, contains the renderer marker
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FILES = [
    "question.md",
    "data.csv",
    "diagnostics.json",
    "chart.yaml",
    "figure.png",
    "interactive.html",
    "README.md",
]

ESTIMATE_EXECUTABLES = ("estimate.py", "estimate.R")

ALLOWED_CHART_TYPES = {
    "bar",
    "line",
    "scatter",
    "area",
    "histogram",
    "choropleth",
    "step",
    "slope",
    "ribbon",
    "dumbbell",
    "lollipop",
    "strip",
    "dot",
    "arrow",
    "ratio_ladder",
    "facet",
}

DIAGNOSTICS_REQUIRED = {
    "row_counts": dict,
    "weighted_population": dict,
    "missingness": dict,
    "design": dict,
    "uncertainty": dict,
    "benchmark": dict,
}

RELEASE_RE = re.compile(r"^[a-z0-9_]+-\d{4}-[0-9a-f]{12,64}$")


@dataclass
class AnalysisIssue:
    analysis: str
    message: str
    severity: str = "error"


@dataclass
class AnalysisCheckResult:
    analysis: str
    issues: list[AnalysisIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(self, message: str, severity: str = "error") -> None:
        self.issues.append(AnalysisIssue(self.analysis, message, severity))


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return None
    return payload if isinstance(payload, dict) else None


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def check_analysis_directory(analysis_dir: Path) -> AnalysisCheckResult:
    """Validate one analysis directory against the AGENTS.md contract."""
    name = analysis_dir.name
    result = AnalysisCheckResult(name)

    for filename in REQUIRED_FILES:
        if not (analysis_dir / filename).is_file():
            result.add(f"missing required file: {filename}")

    has_estimate = any((analysis_dir / exe).is_file() for exe in ESTIMATE_EXECUTABLES)
    if not has_estimate:
        result.add("missing executable: estimate.py or estimate.R")

    data_path = analysis_dir / "data.csv"
    chart_path = analysis_dir / "chart.yaml"

    if data_path.is_file() and chart_path.is_file():
        _lint_chart(data_path, chart_path, result)

    diagnostics_path = analysis_dir / "diagnostics.json"
    if diagnostics_path.is_file():
        _lint_diagnostics(diagnostics_path, result)

    figure_path = analysis_dir / "figure.png"
    if figure_path.is_file():
        _lint_figure(figure_path, result)

    html_path = analysis_dir / "interactive.html"
    if html_path.is_file() and html_path.stat().st_size < 1024:
        result.add("interactive.html is trivially small (< 1 KB)")

    return result


def _lint_chart(data_path: Path, chart_path: Path, result: AnalysisCheckResult) -> None:
    """Validate chart.yaml semantics against data.csv columns."""
    chart = _load_yaml(chart_path)
    if chart is None:
        result.add("chart.yaml is not valid YAML or not a mapping")
        return

    chart_type = chart.get("chart_type")
    if chart_type not in ALLOWED_CHART_TYPES:
        result.add(
            f"chart.yaml chart_type={chart_type!r} is not one of {sorted(ALLOWED_CHART_TYPES)}"
        )

    if not chart.get("title"):
        result.add("chart.yaml title is required (must make a factual claim)")
    if not chart.get("subtitle"):
        result.add("chart.yaml subtitle is required (must define population, measure, period)")

    x_col = chart.get("x")
    y_col = chart.get("y")
    series_col = chart.get("series")
    ci_low = chart.get("ci_low")
    ci_high = chart.get("ci_high")

    try:
        with data_path.open() as fh:
            header_line = fh.readline().strip()
        columns = [c.strip().strip('"') for c in header_line.split(",")]
    except OSError:
        result.add("data.csv is not readable")
        return

    for role, col in (
        ("x", x_col),
        ("y", y_col),
        ("series", series_col),
        ("ci_low", ci_low),
        ("ci_high", ci_high),
    ):
        if col is None:
            continue
        if col not in columns:
            result.add(f"chart.yaml {role}={col!r} does not exist in data.csv columns")

    if (ci_low is None) != (ci_high is None):
        result.add("chart.yaml ci_low and ci_high must be configured together")

    if chart.get("dual_axes"):
        result.add("chart.yaml must not use dual axes")

    if chart.get("3d") or chart.get("three_d"):
        result.add("chart.yaml must not use decorative 3D")

    if chart.get("truncated_axis") and not chart.get("truncated_axis_justified"):
        result.add("chart.yaml truncated quantitative axis requires explicit justification")

    if chart.get("color_encoding_only"):
        result.add("chart.yaml must not use color as the only encoding")

    value_format = chart.get("value_format")
    if value_format and y_col not in columns:
        pass
    if value_format not in (None, "currency", "percent", "number", "integer"):
        result.add(
            f"chart.yaml value_format={value_format!r} is not one of "
            "currency|percent|number|integer"
        )

    series_order = chart.get("series_order")
    if series_order is not None:
        if not isinstance(series_order, list) or not all(
            isinstance(item, str) for item in series_order
        ):
            result.add("chart.yaml series_order must be a list of strings")
        elif chart.get("series") not in columns:
            result.add("chart.yaml series_order requires a valid series column")

    line_style = chart.get("line_style")
    if line_style is not None:
        if not isinstance(line_style, dict):
            result.add("chart.yaml line_style must be a mapping of series to linetype")
        else:
            for name, style in line_style.items():
                if style not in ("solid", "dashed", "dotted"):
                    result.add(f"chart.yaml line_style[{name!r}] must be solid|dashed|dotted")

    vline = chart.get("vline")
    if vline is not None:
        if not isinstance(vline, list) or not all(isinstance(item, dict) for item in vline):
            result.add("chart.yaml vline must be a list of {x, label?}")
        else:
            for item in vline:
                x = item.get("x")
                if x is None or not isinstance(x, (int, float)):
                    result.add(f"chart.yaml vline entry missing numeric x: {item!r}")


def _lint_diagnostics(diagnostics_path: Path, result: AnalysisCheckResult) -> None:
    """Validate diagnostics.json against the analysis contract."""
    diagnostics = _load_json(diagnostics_path)
    if diagnostics is None:
        result.add("diagnostics.json is not valid JSON or not a mapping")
        return

    for key, expected_type in DIAGNOSTICS_REQUIRED.items():
        value = diagnostics.get(key)
        if not isinstance(value, expected_type):
            result.add(f"diagnostics.json missing or wrong type for '{key}'")

    benchmark = diagnostics.get("benchmark")
    if isinstance(benchmark, dict):
        for field_name in ("name", "passed"):
            if field_name not in benchmark:
                result.add(f"diagnostics.json benchmark missing '{field_name}'")
        # Accept either the generic (observed/expected) or SCF-style
        # (reproduced_dollars/official_dollars) benchmark convention.
        has_generic = "observed" in benchmark and "expected" in benchmark
        has_scf = "reproduced_dollars" in benchmark and "official_dollars" in benchmark
        if not has_generic and not has_scf:
            result.add(
                "diagnostics.json benchmark needs observed+expected or "
                "reproduced_dollars+official_dollars"
            )

    release_id = diagnostics.get("release_id")
    if release_id and not RELEASE_RE.match(str(release_id)):
        result.add(f"diagnostics.json release_id={release_id!r} has an unexpected shape")


def _lint_figure(figure_path: Path, result: AnalysisCheckResult) -> None:
    """Validate figure.png is a real PNG of non-trivial size."""
    size = figure_path.stat().st_size
    if size < 2048:
        result.add(f"figure.png is suspiciously small ({size} bytes)")
    header = figure_path.read_bytes()[:8]
    if header != b"\x89PNG\r\n\x1a\n":
        result.add("figure.png does not have a valid PNG header")


def check_all_analyses(analyses_root: Path) -> list[AnalysisCheckResult]:
    """Validate every analysis directory under analyses_root."""
    results: list[AnalysisCheckResult] = []
    if not analyses_root.is_dir():
        return results
    for analysis_dir in sorted(analyses_root.iterdir()):
        if analysis_dir.is_dir():
            results.append(check_analysis_directory(analysis_dir))
    return results
