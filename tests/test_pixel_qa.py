"""Regression tests for pixel-level viz QA."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from microdata_lab.viz_gates import GateResult, _pixel_scan, check_pixel_qa


def _analysis_dir(tmp_path: Path, name: str, make_figure: bool = True) -> Path:
    """A minimal analysis directory: data.csv + figure.png (or not)."""
    analysis = tmp_path / name
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / "data.csv").write_text("x,y\n1,2\n")
    if make_figure:
        img = Image.new("RGB", (2200, 1400), (255, 255, 255))
        img.save(analysis / "figure.png")
    return analysis


def test_pixel_scan_blank(tmp_path: Path) -> None:
    analysis = _analysis_dir(tmp_path, "blank")
    facts = _pixel_scan(analysis / "figure.png")
    assert facts["content_frac"] < 0.001
    assert facts["corners_clean"] is True


def test_pixel_scan_corner_ink(tmp_path: Path) -> None:
    analysis = _analysis_dir(tmp_path, "corner")
    img = Image.open(analysis / "figure.png")
    img.putpixel((10, 10), (17, 17, 17))  # ink in the top-left corner square
    img.save(analysis / "figure.png")
    facts = _pixel_scan(analysis / "figure.png")
    assert facts["corners_clean"] is False


def test_check_pixel_qa_blank_fails(tmp_path: Path) -> None:
    analysis = _analysis_dir(tmp_path, "blank")
    result = check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert "near-blank" in result.detail


def test_check_pixel_qa_corner_fails(tmp_path: Path) -> None:
    analysis = _analysis_dir(tmp_path, "corner")
    img = Image.open(analysis / "figure.png")
    img.putpixel((10, 10), (17, 17, 17))
    img.save(analysis / "figure.png")
    result = check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert "corner" in result.detail


def test_check_pixel_qa_missing_figure_fails(tmp_path: Path) -> None:
    analysis = _analysis_dir(tmp_path, "no-figure", make_figure=False)
    result = check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert "missing" in result.detail


def test_pixel_scan_counts_signal_color(tmp_path: Path) -> None:
    """The signal-color check must catch the blank-line defect class: axes/title
    ink keeps content_frac healthy while the data mark has zero pixels of the
    chart's declared color (fixed-height ggplot panel pushed off-canvas)."""
    analysis = _analysis_dir(tmp_path, "signal")
    img = Image.open(analysis / "figure.png")
    # Axes/title-style ink: healthy non-background content, no signal color.
    # Thick band like a real ggplot mark (1.8 linewidth @144dpi ~= 18px).
    for x in range(100, 500):
        for y in range(190, 225):
            img.putpixel((x, y), (60, 60, 60))
    img.save(analysis / "figure.png")
    facts = _pixel_scan(analysis / "figure.png", "#E30613")
    assert facts["content_frac"] > 0.001  # looks like a figure...
    assert facts["signal_px"] < 3  # ...but the mark is missing


def test_pixel_scan_detects_signal_pixels(tmp_path: Path) -> None:
    """A rendered mark in the declared color must count toward signal_px."""
    analysis = _analysis_dir(tmp_path, "signal-ok")
    img = Image.open(analysis / "figure.png")
    for x in range(100, 300):
        for y in range(400, 450):
            img.putpixel((x, y), (227, 6, 19))  # #E30613
    img.save(analysis / "figure.png")
    facts = _pixel_scan(analysis / "figure.png", "#E30613")
    assert facts["signal_px"] >= 3


def test_check_pixel_qa_declared_color_zero_pixels_fails(tmp_path: Path) -> None:
    """chart.yaml declares a color; figure has none of it -> gate must fail,
    even though content_frac and corners are healthy."""
    analysis = _analysis_dir(tmp_path, "missing-mark")
    img = Image.open(analysis / "figure.png")
    for x in range(100, 500):
        for y in range(190, 225):
            img.putpixel((x, y), (60, 60, 60))  # grey ink: looks rendered
    img.save(analysis / "figure.png")
    (analysis / "chart.yaml").write_text("chart_type: line\ncolor: '#E30613'\nx: x\ny: y\n")
    result = check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert "declared color" in result.detail


def test_check_pixel_qa_no_color_skips_signal_check(tmp_path: Path) -> None:
    """No declared color -> the signal check is skipped (e.g. color_map-only)."""
    analysis = _analysis_dir(tmp_path, "no-color")
    img = Image.open(analysis / "figure.png")
    for x in range(100, 500):
        for y in range(190, 225):
            img.putpixel((x, y), (60, 60, 60))  # healthy ink, no signal color
    img.save(analysis / "figure.png")
    (analysis / "chart.yaml").write_text("chart_type: bar\nx: x\ny: y\n")
    result = check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert isinstance(result, GateResult)
    assert result.passed is True


def test_check_pixel_qa_choropleth_skips_signal_check(tmp_path: Path) -> None:
    """Choropleths use a fixed CVD-safe BuPu ramp — config$color is decorative
    there, so the declared color must NOT be required as mark ink."""
    analysis = _analysis_dir(tmp_path, "choropleth")
    img = Image.open(analysis / "figure.png")
    # The actual ramp colors (BuPu): light blue to deep purple.
    for x in range(100, 500):
        for y in range(190, 225):
            img.putpixel((x, y), (140, 150, 198))  # #8C96C6 midpoint
    img.save(analysis / "figure.png")
    (analysis / "chart.yaml").write_text(
        "chart_type: choropleth\ncolor: '#E87D20'\nx: stusps\ny: share\n"
    )
    result = check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert isinstance(result, GateResult)
    assert result.passed is True
