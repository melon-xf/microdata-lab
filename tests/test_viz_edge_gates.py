"""Tests for the per-edge clipping strips in the pixel-QA gate.

The 4-corner probe missed mid-edge clipping (a subtitle running off the
right edge left 7.5% ink in the right 200px while the corners stayed
clean). These tests build synthetic figures with PIL — no R render
needed — and exercise _pixel_scan/check_pixel_qa directly.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from microdata_lab import viz_gates

BG = (252, 252, 250)
INK = (23, 33, 43)
SIZE = (800, 500)


def _make_analysis(tmp_path: Path, ink_boxes: list[tuple[int, int, int, int]]) -> Path:
    """Write a minimal analysis dir (data.csv, chart.yaml, figure.png)."""
    analysis = tmp_path / "synthetic"
    analysis.mkdir()
    (analysis / "data.csv").write_text("x,y\na,1\n")
    (analysis / "chart.yaml").write_text("chart_type: bar\n")
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    # Interior content so the near-blank check stays quiet.
    draw.rectangle((200, 150, 600, 350), fill=(0, 140, 149))
    for box in ink_boxes:
        draw.rectangle(box, fill=INK)
    img.save(analysis / "figure.png")
    return analysis


def _pixel_qa(tmp_path: Path, ink_boxes: list[tuple[int, int, int, int]]):
    analysis = _make_analysis(tmp_path, ink_boxes)
    return viz_gates.check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")


def test_clean_figure_passes_all_edge_strips(tmp_path: Path) -> None:
    result = _pixel_qa(tmp_path, [])
    assert result.passed, result.detail
    assert "edge ink 0.0000" in result.detail


def test_mid_edge_ink_fails_even_with_clean_corners(tmp_path: Path) -> None:
    # Ink hugging the right edge at mid-height: the corner squares stay
    # clean, so the legacy gate passed; the right strip must catch it.
    w, h = SIZE
    strip = max(viz_gates.PIXEL_EDGE_STRIP_MIN_PX, round(w * viz_gates.PIXEL_EDGE_STRIP_FRAC))
    result = _pixel_qa(tmp_path, [(w - strip, h // 2 - 40, w, h // 2 + 40)])
    facts = viz_gates._pixel_scan(tmp_path / "synthetic" / "figure.png")
    assert facts["corners_clean"], "test premise: corners must stay clean"
    assert not result.passed
    assert "right edge strip" in result.detail


def test_ink_just_inside_bottom_margin_passes(tmp_path: Path) -> None:
    # Axis labels legitimately approach the bottom edge but stop at the
    # plot-margin boundary: ink that never enters the strip must pass.
    _, h = SIZE
    strip = max(viz_gates.PIXEL_EDGE_STRIP_MIN_PX, round(h * viz_gates.PIXEL_EDGE_STRIP_FRAC))
    result = _pixel_qa(tmp_path, [(100, h - strip - 22, 700, h - strip - 2)])
    assert result.passed, result.detail


def test_ink_touching_bottom_edge_fails(tmp_path: Path) -> None:
    result = _pixel_qa(tmp_path, [(100, SIZE[1] - 3, 700, SIZE[1])])
    assert not result.passed
    assert "bottom edge strip" in result.detail


def test_colored_ink_at_edge_fails_not_just_dark_text(tmp_path: Path) -> None:
    # Clipped content can be colored (e.g. a swiss-red eyebrow): the strip
    # measures distance-from-background, not darkness.
    analysis = _make_analysis(tmp_path, [])
    img = Image.open(analysis / "figure.png").convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 200, 2, 260), fill=(227, 6, 19))  # red, left edge
    img.save(analysis / "figure.png")
    result = viz_gates.check_pixel_qa(analysis / "data.csv", analysis / "chart.yaml")
    assert not result.passed
    assert "left edge strip" in result.detail
