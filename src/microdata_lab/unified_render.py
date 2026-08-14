"""Unified chart renderer: one HTML → interactive + PNG.

Replaces the dual-renderer system (R static + TS interactive). Now every
chart renders from the same TS/Plot HTML and is rasterized to PNG via
headless Playwright at 2× DPI.

Pipeline:
  data.csv + chart.yaml
    → render.mjs (esbuild + Plot) → interactive.html
    → rasterize.mjs (Playwright headless) → figure.png

Guarantees:
  • Identical layout, colors, labels in both outputs (same SVG).
  • QA layer runs inside the HTML (console.warn on NaN, overlap, etc.).
  • No R dependency, no ggplot, no second codebase to keep in sync.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from microdata_lab.visualization import load_chart_inputs

REPO = Path(__file__).resolve().parent.parent.parent
VIZ = REPO / "viz" / "interactive"


def render_chart(
    data_path: Path,
    config_path: Path,
    output_dir: Path,
    *,
    width: int = 1120,
    scale: int = 2,
) -> dict[str, Path]:
    """Render both interactive HTML and static PNG for one chart.

    Returns {"html": path, "png": path}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "interactive.html"
    png_path = output_dir / "figure.png"

    config, _ = load_chart_inputs(data_path, config_path)

    # render.mjs expects JSON (not YAML), so write a temp config.json
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=str(output_dir)
    ) as tf:
        json.dump(config.model_dump(mode="json"), tf, indent=2)
        temp_config = Path(tf.name)

    # 1. Build the interactive HTML (same as before)
    result = subprocess.run(
        [
            "node",
            str(VIZ / "render.mjs"),
            "--input",
            str(data_path.resolve()),
            "--config",
            str(temp_config),
            "--output",
            str(html_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(VIZ),
    )
    if result.returncode != 0:
        raise RuntimeError(f"render.mjs failed:\n{result.stderr}")

    # 2. Rasterize to PNG via headless Playwright (2× DPI)
    result2 = subprocess.run(
        [
            "node",
            str(VIZ / "rasterize.mjs"),
            "--input",
            str(html_path.resolve()),
            "--output",
            str(png_path),
            "--scale",
            str(scale),
            "--width",
            str(width),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(VIZ),
    )
    if result2.returncode != 0:
        raise RuntimeError(f"rasterize.mjs failed:\n{result2.stderr}")

    # Clean up temp config
    temp_config.unlink(missing_ok=True)

    return {"html": html_path, "png": png_path}
