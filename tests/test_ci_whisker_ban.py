"""CI whisker ban — user directive 2026-08.

CI whiskers / error bars / CI bands are permanently banned from all charts.
Point estimates only; interval bounds live in the fallback data table.

This gate fails if any chart config or renderer reintroduces them:
  - chart.yaml must not draw whiskers (no ci_low/ci_high in the visual spec
    beyond the data-table columns, and no annotation that labels a CI bound);
  - the interactive renderer must not emit ruleX/ruleY/dot marks keyed on
    ci_low/ci_high;
  - the static R renderer must not call geom_errorbar.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ANALYSES = REPO / "analyses"
RUNTIME = REPO / "viz" / "interactive" / "src" / "runtime.ts"
RENDER_STATIC = REPO / "viz" / "static" / "render_static.R"


def _chart_dirs() -> list[Path]:
    return sorted(p for p in ANALYSES.iterdir() if (p / "chart.yaml").is_file())


def test_no_ci_whisker_marks_in_interactive_renderer() -> None:
    src = RUNTIME.read_text()
    # The renderer may still carry ci_low/ci_high in the config schema and the
    # fallback-table builder, but must not draw marks from them.
    assert "Plot.ruleX(data, {" not in src or "x1: config.ci_low" not in src, (
        "runtime.ts draws CI whisker marks (ruleX keyed on ci_low) — banned"
    )
    assert "Plot.ruleY(data, {" not in src or "x1: config.ci_low" not in src, (
        "runtime.ts draws CI whisker marks (ruleY keyed on ci_low) — banned"
    )
    assert "x: config.ci_low" not in src, (
        "runtime.ts draws CI endpoint dots (x: config.ci_low) — banned"
    )
    assert "y: config.ci_low" not in src, (
        "runtime.ts draws CI endpoint dots (y: config.ci_low) — banned"
    )


def test_no_errorbar_in_static_renderer() -> None:
    src = RENDER_STATIC.read_text()
    assert "geom_errorbar" not in src, "render_static.R draws geom_errorbar — banned"


def test_no_ci_annotations_in_chart_configs() -> None:
    """Chart configs must not carry annotations that label CI bounds.

    Legitimate annotations (positional notes like "No significant
    difference", "16-pt gap — widest") are fine. Banned: an annotation
    whose x is a bare number on the value axis AND whose text is a bare
    number — that is a CI endpoint label (5b's old 11.7/16.5).
    """
    import re

    for d in _chart_dirs():
        raw = (d / "chart.yaml").read_text()
        if "annotations" not in raw:
            continue
        # crude parse: each "- x: <val>" block; flag numeric x + numeric text
        blocks = re.findall(r"- x: ([^\n]+)\n(?:.*\n)*?\s+text: '?([^'\n]+)'?", raw)
        for x, text in blocks:
            x = x.strip().strip('"')
            text = text.strip().strip("'").strip('"')
            try:
                float(x)
            except ValueError:
                continue  # positional band reference, not a CI label
            try:
                float(text)
            except ValueError:
                continue  # prose annotation, not a CI label
            raise AssertionError(
                f"{d.name}: annotation at numeric x={x} with bare-number text "
                f"'{text}' is a CI endpoint label — banned"
            )


def test_no_whisker_references_in_subtitles() -> None:
    """Subtitles must not promise whiskers that are no longer drawn."""
    for d in _chart_dirs():
        raw = (d / "chart.yaml").read_text()
        assert "whisker" not in raw.lower(), (
            f"{d.name}: subtitle/config references whiskers — banned"
        )


def test_ci_bounds_still_in_fallback_table() -> None:
    """The ban removes whiskers from the visual, not the data. Charts that
    carry CI columns must still expose them in the fallback table."""
    runtime = RUNTIME.read_text()
    assert "columns.push(config.ci_low, config.ci_high)" in runtime, (
        "fallback table must keep exposing CI bounds (ban is visual-only)"
    )
