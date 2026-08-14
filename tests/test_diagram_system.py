"""Regression gates for the repository-local diagram-design integration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "viz" / "diagrams" / "check.py"
HTML = REPO / "docs" / "diagrams" / "microdata-evidence-flow.html"
PNG = REPO / "docs" / "diagrams" / "microdata-evidence-flow.png"


def test_canonical_diagram_passes_static_contract() -> None:
    subprocess.run(
        [sys.executable, str(CHECK), str(HTML)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_diagram_checker_rejects_diagonal_connectors(tmp_path: Path) -> None:
    source = HTML.read_text()
    broken = source.replace(
        '<line x1="300" y1="270" x2="324" y2="270"',
        '<line x1="300" y1="270" x2="324" y2="280"',
        1,
    )
    path = tmp_path / "diagonal.html"
    path.write_text(broken)
    result = subprocess.run([sys.executable, str(CHECK), str(path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "is diagonal" in result.stderr


def test_diagram_png_matches_readme_preset() -> None:
    with Image.open(PNG) as image:
        assert image.size == (1920, 1200)
        assert image.mode == "RGB"


def test_diagram_source_and_license_are_pinned() -> None:
    source = HTML.read_text()
    notices = (REPO / "THIRD_PARTY_NOTICES.md").read_text()
    assert 'data-diagram-design-version="2.3"' in source
    assert "a5e3978088cf89c7caff5c20cabd99fbc2a301de" in source
    assert "Copyright (c) 2025 Cathryn Lavery" in notices
    assert "MIT License" in notices


def test_browser_renderer_checks_geometry_before_capture() -> None:
    source = (REPO / "viz" / "interactive" / "render-diagram.mjs").read_text()
    assert "getBBox()" in source
    assert "elements outside viewBox" in source
    assert "aspect ratio differs from viewBox" in source
