"""Regression guard for the neutral static-chart theme wiring."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RENDER_STATIC = REPO / "viz" / "static" / "render_static.R"
INTERACTIVE_RUNTIME = REPO / "viz" / "interactive" / "src" / "runtime.ts"
AHS_CHART = REPO / "analyses" / "ahs-2023-severe-rent-burden-by-assistance" / "chart.yaml"


def test_editorial_theme_name_is_defined_and_wired() -> None:
    renderer = RENDER_STATIC.read_text()
    chart = AHS_CHART.read_text()

    assert "theme_editorial <- function" in renderer
    assert "if (use_editorial) theme_editorial()" in renderer
    legacy_theme_name = "theme_policy_" + "editorial"
    assert legacy_theme_name not in renderer
    assert "theme: editorial" in chart


def test_line_renderer_honors_declared_series_colors() -> None:
    renderer = RENDER_STATIC.read_text()

    assert "if (!is.null(config$color_map))" in renderer
    assert "unlist(config$color_map)" in renderer


def test_interactive_line_renderer_uses_direct_axis_labels_and_colors() -> None:
    renderer = INTERACTIVE_RUNTIME.read_text()

    assert renderer.count("x: { ...common.x, label: config.x_label ?? null }") >= 2
    assert renderer.count("label: config.y_label ?? null") >= 2
    assert renderer.count("marginBottom: config.x_label ? 60 : common.marginBottom") >= 2
    assert "color: { domain: groups, range: lineColors, legend: true }" in renderer


def test_interactive_reveal_stagger_is_capped_for_dense_series() -> None:
    renderer = INTERACTIVE_RUNTIME.read_text()

    assert "const MAX_STAGGER_MS = 3200" in renderer
    assert "Math.min(delay * D, MAX_STAGGER_MS)" in renderer


def test_ahs_dumbbell_semantics_match_declared_data_columns() -> None:
    chart = AHS_CHART.read_text()

    assert "chart_type: dumbbell" in chart
    assert "x: poverty_band" in chart
    assert "y: estimate" in chart
    assert "x_label: Households spending more than half of income on housing" in chart
    assert "y_min: 0" in chart
    assert "y_max: 1" in chart


def test_dumbbell_renderer_honors_declared_quantitative_domain() -> None:
    renderer = RENDER_STATIC.read_text()

    assert "limits = if (!is.null(config$y_min) && !is.null(config$y_max))" in renderer
    assert "c(config$y_min, config$y_max)" in renderer
