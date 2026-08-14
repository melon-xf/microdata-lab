"""Regression gates for the code-rendered public demo media."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

REPO = Path(__file__).resolve().parents[1]
INTERACTIVE_RUNTIME = REPO / "viz" / "interactive" / "src" / "runtime.ts"
MEDIA = {
    "low-tax-illusion": (11.0, 110),
    "housing-assistance": (12.0, 120),
    "public-power": (13.0, 130),
    "hormuz-watch": (13.0, 130),
}
FOLDERS = {
    "low-tax-illusion": "demo1-low-tax-illusion",
    "housing-assistance": "demo2-housing-assistance",
    "public-power": "demo3-public-power",
    "hormuz-watch": "demo4-hormuz-watch",
}


def media_path(name: str, suffix: str) -> Path:
    return REPO / "demos" / FOLDERS[name] / "media" / f"{name}.{suffix}"


@pytest.mark.parametrize("name", MEDIA)
def test_demo_png_has_native_editorial_geometry(name: str) -> None:
    with Image.open(media_path(name, "png")) as image:
        assert image.size == (1600, 900)
        assert image.mode == "RGB"


def test_low_tax_demo_draws_nordic_average_as_a_full_bar() -> None:
    """The Nordic comparison must remain visible after GitHub downscaling."""
    with Image.open(media_path("low-tax-illusion", "png")) as image:
        row = [image.getpixel((x, 585)) for x in range(235, 1200)]

    assert row.count((8, 127, 122)) > 800


def test_hormuz_demo_compares_flow_with_spare_bypass_capacity() -> None:
    """The chokepoint panel must encode both quantities on one scale."""
    diagnostics = json.loads(
        (REPO / "analyses" / "energy-2026-hormuz-inflation-watch" / "diagnostics.json").read_text()
    )
    design = diagnostics["design"]
    expected_share = design["estimated_spare_bypass_mbd"] / design["hormuz_exposure_mbd_2024"]

    with Image.open(media_path("hormuz-watch", "png")) as image:
        through = [x for x in range(340, 1060) if image.getpixel((x, 284)) == (229, 168, 54)]
        bypass = [x for x in range(340, 1060) if image.getpixel((x, 316)) == (8, 127, 122)]

    assert len(through) > 650
    assert len(bypass) > 60
    assert len(bypass) / len(through) == pytest.approx(expected_share, abs=0.02)


@pytest.mark.parametrize(
    ("name", "expected_seconds", "expected_frames"),
    [(key, *value) for key, value in MEDIA.items()],
)
def test_demo_gif_has_readable_duration_and_stable_holds(
    name: str, expected_seconds: float, expected_frames: int
) -> None:
    with Image.open(media_path(name, "gif")) as image:
        assert image.size == (1280, 720)
        assert getattr(image, "n_frames", 1) == expected_frames
        durations = []
        sampled = {}
        indices = {0, 9, expected_frames // 2, expected_frames - 20, expected_frames - 1}
        for index in range(expected_frames):
            image.seek(index)
            durations.append(image.info.get("duration", 0))
            if index in indices:
                sampled[index] = image.convert("RGB").copy()
    assert sum(durations) / 1000 == pytest.approx(expected_seconds, abs=0.05)
    assert ImageChops.difference(sampled[0], sampled[9]).getbbox() is None
    closing_difference = ImageChops.difference(
        sampled[expected_frames - 20], sampled[expected_frames - 1]
    )
    assert closing_difference.getbbox() is None
    assert ImageChops.difference(sampled[0], sampled[expected_frames // 2]).getbbox() is not None
    assert ImageChops.difference(sampled[0], sampled[expected_frames - 1]).getbbox() is not None


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not installed")
@pytest.mark.parametrize(
    ("name", "expected_seconds", "_frames"),
    [(key, *value) for key, value in MEDIA.items()],
)
def test_demo_webm_matches_gif_geometry_and_timing(
    name: str, expected_seconds: float, _frames: int
) -> None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,width,height:format=duration",
            "-of",
            "json",
            str(media_path(name, "webm")),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    assert stream == {"codec_name": "vp9", "width": 1280, "height": 720}
    assert float(payload["format"]["duration"]) == pytest.approx(expected_seconds, abs=0.15)


@pytest.mark.parametrize("name", MEDIA)
def test_demo_webm_has_stable_track_uids(name: str) -> None:
    payload = media_path(name, "webm").read_bytes()
    cluster = payload.find(b"\x1f\x43\xb6\x75")
    assert cluster > 0
    expected = hashlib.sha256(f"microdata-lab:{name}".encode()).digest()[:8]
    for marker in (b"\x73\xc5\x88", b"\x63\xc5\x88"):
        offset = payload.find(marker, 0, cluster)
        assert offset > 0
        assert payload.find(marker, offset + len(marker), cluster) == -1
        assert payload[offset + len(marker) : offset + len(marker) + 8] == expected


def test_demo_generator_has_no_camera_crop_or_aspect_change() -> None:
    source = (REPO / "demos" / "scripts" / "build_media.py").read_text()
    assert ".crop(" not in source
    assert "zoom_frames" not in source
    assert "Canvas must be 16:9" in source
    assert "Text escapes canvas" in source
    assert "progress_for_frame" in source


def test_horizontal_comparison_forms_reserve_right_label_margin() -> None:
    source = INTERACTIVE_RUNTIME.read_text()

    assert '"dumbbell"' in source
    assert "marginRight: needsCatMargin ? mR : 28" in source


def test_obsolete_demo_copy_and_paths_are_gone() -> None:
    copy = (REPO / "demos" / "README.md").read_text()
    for obsolete in (
        "Wonky econometrics",
        "Article claim test",
        "Ongoing monitor",
        "demo1-ce-electricity-regression",
        "demo2-heritage-rps-claim-test",
        "demo3-cron-energy-price-monitor",
    ):
        assert obsolete not in copy


def test_energy_watch_labels_come_from_analysis_outputs() -> None:
    source = (REPO / "demos" / "scripts" / "build_media.py").read_text()

    for stale_literal in ("+30.8%", "+36.4%", "−19 bp", "$93.26 / barrel"):
        assert stale_literal not in source
    assert 'diagnostics["latest"]' in source
    assert 'diagnostics["design"]["hormuz_exposure_mbd_2024"]' in source
