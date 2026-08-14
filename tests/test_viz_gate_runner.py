"""Tests for visualization gate directory selection."""

from pathlib import Path

from microdata_lab import viz_gates
from microdata_lab.viz_gates import GateResult


def test_run_all_gates_accepts_one_analysis_directory(tmp_path: Path, monkeypatch) -> None:
    analysis = tmp_path / "one-analysis"
    analysis.mkdir()
    (analysis / "data.csv").write_text("x,y\na,1\n")
    (analysis / "chart.yaml").write_text("chart_type: bar\n")

    def passed(data: Path, _chart: Path) -> GateResult:
        return GateResult(data.parent.name, "test", "stub", True)

    monkeypatch.setattr(viz_gates, "check_deterministic_static", passed)
    monkeypatch.setattr(viz_gates, "check_deterministic_interactive", passed)
    monkeypatch.setattr(viz_gates, "check_golden_static", passed)
    monkeypatch.setattr(viz_gates, "check_pixel_qa", passed)

    results = viz_gates.run_all_gates(analysis)

    assert len(results) == 4
    assert {result.analysis for result in results} == {"one-analysis"}
