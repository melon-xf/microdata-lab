"""Visualization quality gates.

Automated checks that catch silent rendering failures:

* deterministic re-render: rendering the same inputs twice must produce
  byte-identical output (catches timestamps, unseeded RNG, unstable sort);
* golden-image regression: comparing a fresh render to a stored baseline
  with a perceptual tolerance (catches layout drift, clipping, blank
  figures) without failing on trivial anti-aliasing differences.
"""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from PIL import Image

from microdata_lab.visualization import render_interactive, render_static

# Mean absolute channel difference, normalized to [0, 1].
GOLDEN_TOLERANCE = 0.02
GOLDEN_HARD_FAIL = 0.2

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "viz" / "golden"


@dataclass
class GateResult:
    analysis: str
    renderer: str
    gate: str
    passed: bool
    detail: str = ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_deterministic_static(data: Path, chart: Path) -> GateResult:
    """Render twice; bytes must match exactly."""
    analysis = data.parent.name
    with tempfile.TemporaryDirectory(prefix="vizdet-") as directory:
        first = Path(directory) / "a.png"
        second = Path(directory) / "b.png"
        render_static(data, chart, first)
        render_static(data, chart, second)
        if _sha256(first) == _sha256(second):
            return GateResult(analysis, "static", "deterministic", True)
        return GateResult(analysis, "static", "deterministic", False, "two renders differ in bytes")


def check_deterministic_interactive(data: Path, chart: Path) -> GateResult:
    """Render twice; bytes must match exactly."""
    analysis = data.parent.name
    with tempfile.TemporaryDirectory(prefix="vizdet-") as directory:
        first = Path(directory) / "a.html"
        second = Path(directory) / "b.html"
        render_interactive(data, chart, first)
        render_interactive(data, chart, second)
        if _sha256(first) == _sha256(second):
            return GateResult(analysis, "interactive", "deterministic", True)
        return GateResult(
            analysis, "interactive", "deterministic", False, "two renders differ in bytes"
        )


def _mean_abs_diff(a: Path, b: Path) -> float:
    """Normalized mean absolute difference over channels, in [0, 1]."""
    with Image.open(a) as img_a, Image.open(b) as img_b:
        if img_a.size != img_b.size:
            return 1.0
        pixels_a = img_a.convert("RGB").tobytes()
        pixels_b = img_b.convert("RGB").tobytes()
    total = sum(abs(x - y) for x, y in zip(pixels_a, pixels_b, strict=True))
    return total / (len(pixels_a) * 255)


def check_golden_static(data: Path, chart: Path) -> GateResult:
    """Compare a fresh static render to the stored golden baseline."""
    analysis = data.parent.name
    golden = GOLDEN_DIR / f"{analysis}.png"
    if not golden.is_file():
        return GateResult(
            analysis,
            "static",
            "golden",
            False,
            f"no baseline at {golden.relative_to(GOLDEN_DIR.parents[1])}",
        )
    with tempfile.TemporaryDirectory(prefix="vizgold-") as directory:
        fresh = Path(directory) / "fresh.png"
        render_static(data, chart, fresh)
        diff = _mean_abs_diff(golden, fresh)
        if diff < GOLDEN_TOLERANCE:
            return GateResult(analysis, "static", "golden", True, f"mean abs diff {diff:.4f}")
        if diff < GOLDEN_HARD_FAIL:
            return GateResult(
                analysis,
                "static",
                "golden",
                False,
                f"mean abs diff {diff:.4f} exceeds tolerance {GOLDEN_TOLERANCE}",
            )
        return GateResult(
            analysis,
            "static",
            "golden",
            False,
            f"mean abs diff {diff:.4f} — major visual change",
        )


def store_golden_static(data: Path, chart: Path) -> GateResult:
    """(Re)store the golden baseline for one analysis figure."""
    analysis = data.parent.name
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    target = GOLDEN_DIR / f"{analysis}.png"
    with tempfile.TemporaryDirectory(prefix="vizgold-") as directory:
        fresh = Path(directory) / "fresh.png"
        render_static(data, chart, fresh)
        target.write_bytes(fresh.read_bytes())
    return GateResult(analysis, "static", "golden-store", True, str(target))


# ---------------------------------------------------------------------------
# Pixel-level QA. These are the deterministic checks that caught real bugs
# during the renderer template work: vision models contradict themselves on
# spatial claims (band order, clipping, "missing" separators), while pixel
# scans are ground truth. Checks:
#   palette: figure must actually use the theme's declared colors (catches
#            font/color fallback — e.g. Roboto silently missing → DejaVu);
#   frame:   a themed panel border must be present (catches dropped layers);
#   clipped: text must not run past the canvas edge (catches subtitle/caption
#            overflow that vision both over- and under-reports);
#   content: the figure must not be blank or near-blank (catches the
#            ggplot linetype bug that silently dropped series).
# ---------------------------------------------------------------------------

# Thresholds tuned to the 2200x1400 publication renders.
PIXEL_MIN_CONTENT = 0.002  # fraction of non-background pixels
PIXEL_FRAME_MARGIN = 0.03  # frame line must be within this fraction of edges
PIXEL_FRAME_MIN_RUN = 0.5  # frame line must span this fraction of the side

# Per-edge clipping strips. The 4-corner probe alone missed mid-edge
# clipping: a subtitle overflowing the right edge left 7.5% ink in the
# right 200px of one production render while all four corners stayed
# clean. Strip depth is a small fraction of the canvas with a floor,
# and always sits INSIDE the smallest plot margin any theme declares
# (16px bottom in the editorial/bauhaus themes). Margin-awareness: axis
# labels and captions legitimately approach an edge but stop at the
# margin boundary, so a legitimate figure measures exactly 0 ink in
# these bands and only genuine off-canvas overflow trips the check.
# (Measured across all 32 shipped figures: clean = 0.0000 on every
# edge; the three figures with real subtitle clips = 0.011-0.044.)
PIXEL_EDGE_STRIP_FRAC = 0.005  # strip depth as a fraction of the canvas dim
PIXEL_EDGE_STRIP_MIN_PX = 6  # floor, so small canvases still get a real band
PIXEL_EDGE_MAX_INK = 0.001  # 0.1% — 10x below the weakest observed clip


class PixelFacts(TypedDict):
    size: tuple[int, int]
    background: tuple[int, int, int]
    content_frac: float
    corners_clean: bool
    edges: dict[str, float]
    edge_strip_px: tuple[int, int]
    signal_px: int


def _parse_hex(color: str) -> tuple[int, int, int]:
    """'#RRGGBB' (or 3-digit) -> (r, g, b)."""
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _is_signal(px: tuple[int, int, int], signal: tuple[int, int, int], tol: int = 48) -> bool:
    """Per-channel match within tol — catches the declared color used at any
    alpha/blend (anti-aliased marks) while ignoring near-background noise."""
    return all(abs(a - b) <= tol for a, b in zip(px, signal, strict=True))


def _pixel_scan(path: Path, signal_color: str | None = None) -> PixelFacts:
    """Return a dict of deterministic pixel facts about a rendered figure.

    signal_color: when supplied, also count pixels within tolerance of the
    chart's declared signal color. Catches the blank-line class of bug where
    axes/title ink keeps content_frac healthy while the data mark itself has
    ZERO pixels of the declared color (long title + long caption compress the
    fixed-height ggplot panel until the geometry is pushed off-canvas).
    """
    img = Image.open(path).convert("RGB")
    width, height = img.size
    # Most common color = background (sample for speed).
    from collections import Counter

    counts: Counter[tuple[int, int, int]] = Counter()
    step = max(1, (width * height) // 200_000)
    for y in range(0, height, step):
        for x in range(0, width, step):
            rgb = img.getpixel((x, y))
            counts[rgb] += 1  # type: ignore[index]
    background, _ = counts.most_common(1)[0]
    assert isinstance(background, tuple)

    # Non-background fraction.
    non_bg = 0
    total = 0
    signal_px = 0
    signal = _parse_hex(signal_color) if signal_color else None
    for y in range(0, height, max(1, height // 200)):
        for x in range(0, width, max(1, width // 300)):
            total += 1
            px = img.getpixel((x, y))
            px_rgb: tuple[int, int, int] = cast(tuple[int, int, int], px)
            if px_rgb != background:
                non_bg += 1
            if signal is not None and _is_signal(px_rgb, signal):
                signal_px += 1

    content_frac = non_bg / max(1, total)

    # Clipping probe: the 4 corner squares must be pure background for a
    # chart with margins. Text that runs off the canvas leaves ink there.
    corner = max(4, min(width, height) // 120)
    corners_clean = True
    for cx, cy in (
        (0, 0),
        (width - corner, 0),
        (0, height - corner),
        (width - corner, height - corner),
    ):
        for dy in range(corner):
            for dx in range(corner):
                if img.getpixel((cx + dx, cy + dy)) != background:
                    corners_clean = False
                    break
            if not corners_clean:
                break
        if not corners_clean:
            break

    # Per-edge strips: full-length bands hugging each canvas edge, catching
    # mid-edge overflow the corner probe cannot see. "Ink" = any channel
    # farther than tol from the background (catches colored marks, e.g. a
    # swiss-red title, not just dark text). Strip depth stays inside the
    # smallest theme plot margin, so legitimate axis/caption ink that
    # approaches — but never reaches — an edge does not false-positive.
    strip_x = max(PIXEL_EDGE_STRIP_MIN_PX, round(width * PIXEL_EDGE_STRIP_FRAC))
    strip_y = max(PIXEL_EDGE_STRIP_MIN_PX, round(height * PIXEL_EDGE_STRIP_FRAC))
    edges: dict[str, float] = {}
    for edge_name, (x0, y0, x1, y1) in (
        ("top", (0, 0, width, strip_y)),
        ("bottom", (0, height - strip_y, width, height)),
        ("left", (0, 0, strip_x, height)),
        ("right", (width - strip_x, 0, width, height)),
    ):
        ink = 0
        total = 0
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                strip_px = img.getpixel((xx, yy))
                strip_rgb: tuple[int, int, int] = cast(tuple[int, int, int], strip_px)
                if any(abs(a - b) > 48 for a, b in zip(strip_rgb, background, strict=True)):
                    ink += 1
                total += 1
        edges[edge_name] = ink / max(1, total)

    return {
        "size": (width, height),
        "background": background,
        "content_frac": content_frac,
        "corners_clean": corners_clean,
        "edges": edges,
        "edge_strip_px": (strip_x, strip_y),
        "signal_px": signal_px,
    }


# Minimum signal-color pixel count (on the same sample grid) for a figure
# that declares a signal color. Zero is the failure mode: data geometry with
# 0 pixels of its own color while axes/title ink keeps content_frac healthy.
PIXEL_MIN_SIGNAL = 3


def check_pixel_qa(data: Path, chart: Path) -> GateResult:
    """Run deterministic pixel QA on the static figure (blank/clip checks)."""
    analysis = data.parent.name
    figure = data.parent / "figure.png"
    if not figure.is_file():
        return GateResult(analysis, "static", "pixel-qa", False, "figure.png missing")
    # Signal color from chart.yaml, when declared. Charts without an explicit
    # color (e.g. color_map-only) skip the signal check. Choropleths also skip
    # it: the static renderer deliberately uses a fixed CVD-safe BuPu ramp
    # (config$color is decorative there), so the declared color is NOT the
    # mark color by design.
    signal_color = None
    try:
        import yaml

        with chart.open() as f:
            cfg = yaml.safe_load(f) or {}
        if cfg.get("chart_type") != "choropleth":
            signal_color = cfg.get("color")
    except Exception:
        pass
    facts = _pixel_scan(figure, signal_color)
    issues: list[str] = []
    if not facts["corners_clean"]:
        issues.append("content touches canvas corner — text likely clipped or frame missing")
    strip_x, strip_y = facts["edge_strip_px"]
    for edge in ("top", "bottom", "left", "right"):
        frac = facts["edges"][edge]
        if frac > PIXEL_EDGE_MAX_INK:
            depth = strip_y if edge in ("top", "bottom") else strip_x
            issues.append(
                f"ink in {edge} edge strip ({frac:.4f} of a {depth}px band) — "
                "content clipped at the canvas edge"
            )
    if facts["content_frac"] < PIXEL_MIN_CONTENT:
        issues.append(f"near-blank figure (content {facts['content_frac']:.4f})")
    if signal_color and facts["signal_px"] < PIXEL_MIN_SIGNAL:
        issues.append(
            f"declared color {signal_color} has 0 pixels — data geometry missing "
            "(axes/title ink kept content healthy while the mark was pushed off-canvas)"
        )
    if issues:
        return GateResult(analysis, "static", "pixel-qa", False, "; ".join(issues))
    return GateResult(
        analysis,
        "static",
        "pixel-qa",
        True,
        f"content {facts['content_frac']:.3f}, corners clean, "
        f"edge ink {max(facts['edges'].values()):.4f}, signal {facts['signal_px']}px",
    )


def run_all_gates(analyses_root: Path) -> list[GateResult]:
    """Run gates for one analysis directory or every child analysis."""
    results: list[GateResult] = []
    candidates = (
        [analyses_root]
        if (analyses_root / "data.csv").is_file() and (analyses_root / "chart.yaml").is_file()
        else sorted(analyses_root.iterdir())
    )
    for analysis_dir in candidates:
        if not analysis_dir.is_dir():
            continue
        data = analysis_dir / "data.csv"
        chart = analysis_dir / "chart.yaml"
        if not data.is_file() or not chart.is_file():
            continue
        results.append(check_deterministic_static(data, chart))
        results.append(check_deterministic_interactive(data, chart))
        results.append(check_golden_static(data, chart))
        results.append(check_pixel_qa(data, chart))
    return results
