#!/usr/bin/env python3
"""Build the four editorial demo stories as native 16:9 PNG/GIF/WebM media.

Every frame is code-rendered from committed analysis outputs. Motion reveals
evidence in reading order; it never crops, pans, zooms, or changes aspect ratio.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEMOS = ROOT / "demos"
ANALYSES = ROOT / "analyses"
FONT_DIR = ROOT / "viz" / "assets" / "fonts"

INK = "#17212B"
MUTED = "#65727E"
GRID = "#D9DEE2"
PAPER = "#F7F5EF"

TEAL = "#087F7A"
RED = "#D64B5E"
GOLD = "#E5A836"
BLUE = "#356AA0"
SOFT_TEAL = "#D8ECE9"
SOFT_GOLD = "#F3E8CA"

BASE_W = 1600
BASE_H = 900
VIDEO_W = 1280
VIDEO_H = 720
FPS = 10


@dataclass(frozen=True)
class SceneData:
    tax: dict[str, float]
    housing: dict[tuple[str, str], float]
    electrification: list[tuple[int, float]]
    power: dict[str, float]
    energy: dict[str, list[tuple[int, float, float]]]
    energy_metrics: dict[str, float]
    energy_latest_date: str


class Canvas:
    """Scaled drawing helpers for a 16:9 editorial canvas."""

    def __init__(self, width: int, height: int) -> None:
        if width * 9 != height * 16:
            raise ValueError(f"Canvas must be 16:9, got {width}x{height}")
        self.width = width
        self.height = height
        self.scale = width / BASE_W
        self.image = Image.new("RGB", (width, height), PAPER)
        self.draw = ImageDraw.Draw(self.image)

    def x(self, value: float) -> int:
        return round(value * self.scale)

    def y(self, value: float) -> int:
        return round(value * self.scale)

    def font(self, size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
        files = {
            "regular": "Jost-Regular.ttf",
            "medium": "Jost-Medium.ttf",
            "semibold": "Jost-SemiBold.ttf",
            "bold": "Jost-Bold.ttf",
            "black": "Jost-Black.ttf",
        }
        return ImageFont.truetype(str(FONT_DIR / files[weight]), max(10, self.x(size)))

    def text(
        self,
        xy: tuple[float, float],
        value: str,
        *,
        size: int,
        weight: str = "regular",
        fill: str = INK,
        anchor: str | None = None,
    ) -> None:
        point = (self.x(xy[0]), self.y(xy[1]))
        font = self.font(size, weight)
        self.draw.text(point, value, font=font, fill=fill, anchor=anchor)
        bbox = self.draw.textbbox(point, value, font=font, anchor=anchor)
        if bbox[0] < -2 or bbox[1] < -2 or bbox[2] > self.width + 2 or bbox[3] > self.height + 2:
            raise ValueError(f"Text escapes canvas: {value!r} at {bbox}")

    def wrapped(
        self,
        xy: tuple[float, float],
        value: str,
        *,
        size: int,
        max_width: float,
        weight: str = "regular",
        fill: str = INK,
        spacing: int = 8,
    ) -> float:
        font = self.font(size, weight)
        limit = self.x(max_width)
        lines: list[str] = []
        for paragraph in value.split("\n"):
            words = paragraph.split()
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if self.draw.textlength(candidate, font=font) <= limit:
                    current = candidate
                else:
                    if not current:
                        raise ValueError(f"Single word exceeds wrap width: {word}")
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)
        y = self.y(xy[1])
        line_height = self.draw.textbbox((0, 0), "Ag", font=font)[3]
        for line in lines:
            self.draw.text((self.x(xy[0]), y), line, font=font, fill=fill)
            bbox = self.draw.textbbox((self.x(xy[0]), y), line, font=font)
            if bbox[2] > self.width - self.x(40):
                raise ValueError(f"Wrapped line escapes canvas: {line!r}")
            y += line_height + self.y(spacing)
        return y / self.scale

    def line(self, xy: tuple[float, float, float, float], *, fill: str, width: int) -> None:
        self.draw.line(tuple(self.x(v) for v in xy), fill=fill, width=max(1, self.x(width)))

    def rectangle(
        self,
        xy: tuple[float, float, float, float],
        *,
        fill: str,
        outline: str | None = None,
        width: int = 1,
        radius: int = 0,
    ) -> None:
        coords = tuple(self.x(v) for v in xy)
        if radius:
            self.draw.rounded_rectangle(
                coords,
                radius=self.x(radius),
                fill=fill,
                outline=outline,
                width=max(1, self.x(width)),
            )
        else:
            self.draw.rectangle(coords, fill=fill, outline=outline, width=max(1, self.x(width)))

    def circle(
        self,
        xy: tuple[float, float],
        radius: float,
        *,
        fill: str,
        outline: str | None = None,
    ) -> None:
        x, y = xy
        self.draw.ellipse(
            (self.x(x - radius), self.y(y - radius), self.x(x + radius), self.y(y + radius)),
            fill=fill,
            outline=outline,
            width=max(1, self.x(2)),
        )


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def phase(progress: float, start: float, end: float) -> float:
    return ease((progress - start) / (end - start))


def mix(left: float, right: float, progress: float) -> float:
    return left + (right - left) * progress


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_data() -> SceneData:
    tax_rows = load_rows(ANALYSES / "oecd-tax-wedge-esi-single" / "data.csv")
    tax = {
        row["country"]: float(row["avg_tax_wedge"])
        for row in tax_rows
        if int(row["wage_pct"]) == 100
    }
    housing_rows = load_rows(
        ANALYSES / "ahs-2023-severe-rent-burden-by-assistance" / "all-groups.csv"
    )
    housing = {(row["poverty_band"], row["group"]): float(row["estimate"]) for row in housing_rows}
    electrification = [
        (int(row["year"]), float(row["percent"]))
        for row in load_rows(ANALYSES / "rea-1930-1960-rural-electrification" / "data.csv")
    ]
    power = {
        row["category"].replace("\n", " "): float(row["cents_per_kwh"])
        for row in load_rows(ANALYSES / "public-vs-iou-power-cost" / "data.csv")
    }
    energy: dict[str, list[tuple[int, float, float]]] = {}
    for row in load_rows(ANALYSES / "energy-2026-hormuz-inflation-watch" / "data.csv"):
        energy.setdefault(row["series_id"], []).append(
            (int(row["days_since_event"]), float(row["index"]), float(row["value"]))
        )
    diagnostics = json.loads(
        (ANALYSES / "energy-2026-hormuz-inflation-watch" / "diagnostics.json").read_text()
    )
    latest = diagnostics["latest"]
    energy_metrics = {
        "brent_change_pct": float(latest["DCOILBRENTEU"]["percent_change"]),
        "brent_latest": float(latest["DCOILBRENTEU"]["latest_value"]),
        "gas_change_pct": float(latest["GASREGW"]["percent_change"]),
        "gas_latest": float(latest["GASREGW"]["latest_value"]),
        "inflation_change_bp": float(latest["T5YIE"]["absolute_change"]) * 100,
        "inflation_latest": float(latest["T5YIE"]["latest_value"]),
        "hormuz_flow_mbd": float(diagnostics["design"]["hormuz_exposure_mbd_2024"]),
        "bypass_mbd": float(diagnostics["design"]["estimated_spare_bypass_mbd"]),
    }
    latest_date = max(str(series["latest_date"]) for series in latest.values())
    required_tax = {
        "United States",
        "United States + Health Insurance",
        "Denmark",
        "Finland",
        "Norway",
        "Sweden",
    }
    if not required_tax.issubset(tax):
        raise ValueError(f"Missing tax rows: {sorted(required_tax - set(tax))}")
    if set(energy) != {"DCOILBRENTEU", "GASREGW", "T5YIE"}:
        raise ValueError(f"Missing energy-watch series: {sorted(energy)}")
    return SceneData(
        tax=tax,
        housing=housing,
        electrification=electrification,
        power=power,
        energy=energy,
        energy_metrics=energy_metrics,
        energy_latest_date=latest_date,
    )


def draw_header(c: Canvas, eyebrow: str, title: str, subtitle: str) -> None:
    c.text((100, 58), eyebrow.upper(), size=20, weight="semibold", fill=TEAL)
    title_bottom = c.wrapped((100, 94), title, size=54, max_width=1390, weight="black", spacing=2)
    c.wrapped((100, title_bottom + 9), subtitle, size=25, max_width=1380, fill=MUTED, spacing=2)


def draw_footer(c: Canvas, source: str, note: str) -> None:
    c.line((100, 815, 1500, 815), fill=GRID, width=2)
    c.wrapped((100, 828), f"Source: {source}", size=20, max_width=1400, fill=MUTED, spacing=1)
    c.wrapped((100, 856), note, size=18, max_width=1400, fill=MUTED, spacing=1)


def draw_tax_scene(data: SceneData, progress: float, size: tuple[int, int]) -> Image.Image:
    c = Canvas(*size)
    draw_header(
        c,
        "Demo 1 · the low-tax illusion",
        "Health premiums erase America’s low-tax advantage",
        "Average labor-cost wedge at the average wage, single adult, 2025",
    )
    x0, x1 = 235.0, 1460.0
    y_us, y_nordic = 400.0, 585.0
    max_value = 45.0
    for tick in (0, 10, 20, 30, 40):
        x = mix(x0, x1, tick / max_value)
        c.line((x, 315, x, 690), fill=GRID, width=2)
        c.text((x, 708), f"{tick}%", size=19, fill=MUTED, anchor="ma")
    c.text((205, y_us), "United States", size=24, weight="semibold", anchor="rm")
    c.text((205, y_nordic), "Nordics", size=24, weight="semibold", anchor="rm")

    official = data.tax["United States"]
    adjusted = data.tax["United States + Health Insurance"]
    nordics = [data.tax[name] for name in ("Denmark", "Finland", "Norway", "Sweden")]
    nordic_min, nordic_max = min(nordics), max(nordics)
    nordic_avg = sum(nordics) / len(nordics)

    official_p = phase(progress, 0.05, 0.28)
    nordic_p = phase(progress, 0.20, 0.44)
    premium_p = phase(progress, 0.49, 0.72)
    callout_p = phase(progress, 0.70, 0.86)

    official_x = mix(x0, x1, official / max_value)
    adjusted_x = mix(x0, x1, adjusted / max_value)
    shown_official_x = mix(x0, official_x, official_p)
    c.rectangle((x0, y_us - 30, shown_official_x, y_us + 30), fill=BLUE, radius=9)
    if official_p > 0.65 and premium_p < 0.05:
        c.text(
            (shown_official_x + 18, y_us),
            f"{official:.1f}%",
            size=24,
            weight="bold",
            anchor="lm",
        )

    avg_x = mix(x0, x1, nordic_avg / max_value)
    shown_nordic_avg = mix(x0, avg_x, nordic_p)
    if nordic_p > 0:
        c.rectangle(
            (x0, y_nordic - 30, shown_nordic_avg, y_nordic + 30),
            fill=TEAL,
            radius=9,
        )
    if nordic_p > 0.75:
        c.text(
            (shown_nordic_avg + 18, y_nordic),
            f"{nordic_avg:.1f}% avg",
            size=22,
            weight="semibold",
            anchor="lm",
        )
        c.text(
            (x0, y_nordic + 58),
            f"Four-country range: {nordic_min:.1f}–{nordic_max:.1f}%",
            size=17,
            fill=MUTED,
            anchor="la",
        )

    if premium_p > 0:
        premium_right = mix(official_x, adjusted_x, premium_p)
        c.rectangle((official_x, y_us - 30, premium_right, y_us + 30), fill=GOLD, radius=9)
        c.text(
            (official_x - 12, y_us + 58),
            f"{official:.1f}% tax",
            size=18,
            weight="semibold",
            fill=BLUE,
            anchor="rs",
        )
        if premium_p > 0.70:
            c.text(
                (premium_right + 18, y_us),
                f"{adjusted:.1f}%",
                size=24,
                weight="bold",
                anchor="lm",
            )
            c.text(
                ((official_x + adjusted_x) / 2, y_us - 50),
                "+ average single premium",
                size=18,
                weight="semibold",
                fill="#8A5B00",
                anchor="ms",
            )

    if callout_p > 0.15:
        c.rectangle((875, 655, 1460, 775), fill=SOFT_GOLD, radius=16)
        headline_bottom = c.wrapped(
            (910, 664),
            "'Low tax' leaves out a compulsory cost of work.",
            size=22,
            max_width=520,
            weight="bold",
            spacing=1,
        )
        c.wrapped(
            (910, headline_bottom + 6),
            (
                f"The $9,325 premium is not legally a tax, but counting it adds "
                f"{adjusted - official:.1f} points and puts the U.S. within one "
                f"point of the Nordic average ({nordic_avg:.1f}%)."
            ),
            size=16,
            max_width=520,
            fill=INK,
            spacing=1,
        )

    draw_footer(
        c,
        "OECD Tax Wages 2025; KFF Employer Health Benefits Survey 2025",
        (
            "Premiums are normalized as compulsory labor costs for comparison; "
            "they are not literally taxes. Point estimates; average single coverage."
        ),
    )
    return c.image


def draw_housing_scene(data: SceneData, progress: float, size: tuple[int, int]) -> Image.Image:
    c = Canvas(*size)
    draw_header(
        c,
        "Demo 2 · housing beyond the market",
        "Severe housing burden is lower with assistance",
        (
            "Share spending more than half of income on housing; below 50% of poverty, "
            "every arrangement still exceeds 87%, AHS 2023"
        ),
    )
    x0, x1 = 380.0, 1480.0
    y_top, row_gap = 340.0, 115.0
    bands = ["≤50%", "51–100%", "101–150%", "151–200%"]
    series = [
        ("No assistance", RED, phase(progress, 0.05, 0.30)),
        ("Voucher", GOLD, phase(progress, 0.32, 0.58)),
        ("Public housing", TEAL, phase(progress, 0.60, 0.82)),
    ]
    for tick in (0, 25, 50, 75, 100):
        x = mix(x0, x1, tick / 100)
        c.line((x, 300, x, 755), fill=GRID, width=2)
        c.text((x, 778), f"{tick}%", size=18, fill=MUTED, anchor="ma")
    for index, band in enumerate(bands):
        y = y_top + index * row_gap
        c.text((330, y), band, size=23, weight="semibold", anchor="rm")
        c.line((x0, y, x1, y), fill="#E7E9E8", width=2)
        visible_values = [
            data.housing[(band, name)] * 100 for name, _, reveal in series if reveal > 0.1
        ]
        if len(visible_values) > 1:
            c.line(
                (
                    mix(x0, x1, min(visible_values) / 100),
                    y,
                    mix(x0, x1, max(visible_values) / 100),
                    y,
                ),
                fill="#9AA3AA",
                width=5,
            )
        offsets = {"No assistance": -28, "Voucher": 34, "Public housing": -28}
        for name, color, reveal in series:
            if reveal <= 0:
                continue
            value = data.housing[(band, name)] * 100
            x = mix(x0, x1, value / 100)
            c.circle((x, y), 12 * reveal, fill=color)
            if reveal > 0.74:
                c.text(
                    (x, y + offsets[name]),
                    f"{value:.0f}",
                    size=17,
                    weight="semibold",
                    fill=color,
                    anchor="mm",
                )
    legend_x = 420.0
    for name, color, _ in series:
        c.circle((legend_x, 255), 9, fill=color)
        c.text((legend_x + 18, 255), name, size=19, weight="medium", anchor="lm")
        legend_x += 315 if name != "Public housing" else 0

    draw_footer(
        c,
        "U.S. Census Bureau and HUD, 2023 American Housing Survey National PUF",
        (
            "Occupied renter households with positive income at ≤200% of poverty. "
            "WEIGHT + 160 replicate weights. RENTSUB is respondent-reported. "
            "Descriptive, not causal; intervals are in the table."
        ),
    )
    return c.image


def draw_power_scene(data: SceneData, progress: float, size: tuple[int, int]) -> Image.Image:
    c = Canvas(*size)
    draw_header(
        c,
        "Demo 3 · public capacity",
        "Public power built rural access and still charges less",
        "Farm electrification, 1930–1963, and residential utility prices by ownership, 2024",
    )
    c.text((100, 275), "BUILDING ACCESS", size=19, weight="semibold", fill=TEAL)
    c.text((950, 275), "OWNERSHIP TODAY", size=19, weight="semibold", fill=TEAL)

    # Left panel: rural electrification timeline.
    lx0, lx1, ly0, ly1 = 135.0, 780.0, 710.0, 330.0
    for tick in (0, 25, 50, 75, 100):
        y = mix(ly0, ly1, tick / 100)
        c.line((lx0, y, lx1, y), fill=GRID, width=2)
        c.text((lx0 - 20, y), f"{tick}%", size=17, fill=MUTED, anchor="rm")
    for year in (1930, 1940, 1950, 1960):
        x = mix(lx0, lx1, (year - 1930) / 33)
        c.text((x, 742), str(year), size=17, fill=MUTED, anchor="ma")
    rea_x = mix(lx0, lx1, (1935 - 1930) / 33)
    c.line((rea_x, ly0, rea_x, ly1), fill=GOLD, width=3)
    c.text((rea_x + 12, 316), "REA chartered · 1935", size=17, weight="semibold", fill="#8A5B00")

    timeline_p = phase(progress, 0.05, 0.48)
    points = data.electrification
    reveal_year = mix(points[0][0], points[-1][0], timeline_p)
    shown: list[tuple[float, float]] = []
    for year, value in points:
        if year <= reveal_year:
            shown.append((year, value))
    if shown and shown[-1][0] < reveal_year:
        for (year_a, value_a), (year_b, value_b) in pairwise(points):
            if year_a <= reveal_year <= year_b:
                fraction = (reveal_year - year_a) / (year_b - year_a)
                shown.append((reveal_year, mix(value_a, value_b, fraction)))
                break
    mapped = [
        (mix(lx0, lx1, (year - 1930) / 33), mix(ly0, ly1, value / 100)) for year, value in shown
    ]
    if len(mapped) > 1:
        c.draw.line(
            [(c.x(x), c.y(y)) for x, y in mapped],
            fill=TEAL,
            width=c.x(8),
            joint="curve",
        )
    for x, y in mapped:
        c.circle((x, y), 7, fill=TEAL)
    if timeline_p > 0.90:
        c.text((lx1 - 4, ly1 + 34), "97.9%", size=24, weight="bold", fill=TEAL, anchor="ra")
        c.text((lx0 + 10, mix(ly0, ly1, 9.1 / 100) + 26), "9.1%", size=20, weight="bold", fill=TEAL)

    # Right panel: present-day utility ownership.
    px0, px1 = 1080.0, 1480.0
    rows = [
        ("TVA-area public power", 12.43, TEAL),
        ("Municipal", 13.53, TEAL),
        ("U.S. average", 15.41, MUTED),
        ("Investor-owned", 16.50, RED),
    ]
    bars_p = phase(progress, 0.54, 0.80)
    for index, (label, value, color) in enumerate(rows):
        y = 360 + index * 92
        c.text((1055, y), label, size=19, weight="medium", anchor="rm")
        c.rectangle(
            (px0, y - 20, mix(px0, px1, (value / 18) * bars_p), y + 20),
            fill=color,
            radius=8,
        )
        if bars_p > 0.72:
            c.text(
                (mix(px0, px1, value / 18) + 12, y),
                f"{value:.2f}¢",
                size=19,
                weight="bold",
                fill=color,
                anchor="lm",
            )
    for tick in (0, 6, 12, 18):
        x = mix(px0, px1, tick / 18)
        c.line((x, 330, x, 670), fill=GRID, width=2)
        c.text((x, 696), str(tick), size=17, fill=MUTED, anchor="ma")
    c.text(
        (1255, 728),
        "Residential cents per kWh",
        size=18,
        weight="semibold",
        fill=MUTED,
        anchor="ma",
    )
    if phase(progress, 0.80, 0.92) > 0.2:
        c.rectangle((1000, 750, 1480, 805), fill=SOFT_TEAL, radius=14)
        c.text(
            (1240, 778),
            "Municipal power: 18% below investor-owned utilities",
            size=19,
            weight="bold",
            anchor="mm",
        )
    draw_footer(
        c,
        "USDA Agricultural Statistics; U.S. EIA Form 861 (2024)",
        (
            "Historical access and current ownership prices are separate descriptive "
            "comparisons. Utility service areas differ; current price differences are "
            "not causal estimates."
        ),
    )
    return c.image


def draw_energy_scene(data: SceneData, progress: float, size: tuple[int, int]) -> Image.Image:
    c = Canvas(*size)
    latest_date = datetime.strptime(data.energy_latest_date, "%Y-%m-%d")
    draw_header(
        c,
        "Demo 4 · live economic research",
        "Oil and gasoline are up 30%. Inflation expectations held.",
        (
            "Strait of Hormuz shock watch · latest official observations through "
            f"{latest_date:%b}. {latest_date.day}, {latest_date.year}"
        ),
    )

    exposure_p = phase(progress, 0.02, 0.16)
    bypass_p = phase(progress, 0.08, 0.20)
    flow_mbd = data.energy_metrics["hormuz_flow_mbd"]
    bypass_mbd = data.energy_metrics["bypass_mbd"]
    bypass_share = clamp(bypass_mbd / flow_mbd)
    c.rectangle((100, 238, 1500, 338), fill=SOFT_GOLD, radius=18)
    c.text((130, 255), "HORMUZ CHOKEPOINT", size=14, weight="bold", fill="#7A5100", anchor="lm")
    c.text((130, 284), "THROUGH STRAIT", size=15, weight="bold", fill="#7A5100", anchor="lm")
    c.text((130, 316), "SPARE BYPASS", size=15, weight="bold", fill=TEAL, anchor="lm")
    c.rectangle((350, 274, 1050, 294), fill="#E6D8B5", radius=6)
    c.rectangle((350, 274, mix(350, 1050, exposure_p), 294), fill=GOLD, radius=6)
    c.rectangle((350, 306, 1050, 326), fill="#E6D8B5", radius=6)
    bypass_end = mix(350, 1050, bypass_share)
    c.rectangle((350, 306, mix(350, bypass_end, bypass_p), 326), fill=TEAL, radius=6)
    if exposure_p > 0.65:
        c.text(
            (1080, 284),
            f"{flow_mbd:.1f}M b/d through",
            size=17,
            weight="bold",
            anchor="lm",
        )
    if bypass_p > 0.65:
        c.text(
            (1080, 316),
            f"{bypass_mbd:.1f}M b/d spare capacity",
            size=16,
            fill=TEAL,
            anchor="lm",
        )

    cards = [
        (
            "DCOILBRENTEU",
            "BRENT CRUDE",
            RED,
            phase(progress, 0.14, 0.44),
            f"{data.energy_metrics['brent_change_pct']:+.1f}%".replace("-", "−"),
            f"${data.energy_metrics['brent_latest']:.2f} / barrel",
        ),
        (
            "GASREGW",
            "U.S. REGULAR GAS",
            GOLD,
            phase(progress, 0.39, 0.69),
            f"{data.energy_metrics['gas_change_pct']:+.1f}%".replace("-", "−"),
            f"${data.energy_metrics['gas_latest']:.3f} / gallon",
        ),
        (
            "T5YIE",
            "5-YEAR INFLATION EXPECTATIONS",
            TEAL,
            phase(progress, 0.64, 0.88),
            f"{data.energy_metrics['inflation_change_bp']:+.0f} bp".replace("-", "−"),
            f"{data.energy_metrics['inflation_latest']:.2f}%",
        ),
    ]
    for index, (series_id, label, color, reveal, change, latest) in enumerate(cards):
        x0 = 100 + index * 475
        x1 = x0 + 450
        y0, y1 = 352, 735
        c.rectangle((x0, y0, x1, y1), fill="#FFFFFF", outline="#D9D5CE", width=2, radius=18)
        c.text((x0 + 28, y0 + 38), label, size=17, weight="bold", fill=color, anchor="lm")
        if reveal > 0.72:
            c.text((x0 + 28, y0 + 92), change, size=38, weight="bold", fill=INK, anchor="lm")
            c.text((x1 - 28, y0 + 92), latest, size=19, weight="semibold", fill=MUTED, anchor="rm")

        sx0, sx1, sy0, sy1 = x0 + 28, x1 - 28, y1 - 42, y0 + 145
        for tick in (100, 150, 200):
            y = mix(sy0, sy1, (tick - 80) / 120)
            c.line((sx0, y, sx1, y), fill=GRID, width=2)
            if tick == 100:
                c.text((sx0, y - 14), "pre-disruption = 100", size=14, fill=MUTED, anchor="la")

        rows = data.energy[series_id]
        min_day = min(day for day, _, _ in rows)
        max_day = max(day for day, _, _ in rows)
        cutoff = mix(min_day, max_day, reveal)
        shown = [(day, value) for day, value, _ in rows if day <= cutoff]
        mapped = [
            (
                mix(sx0, sx1, (day - min_day) / (max_day - min_day)),
                mix(sy0, sy1, clamp((value - 80) / 120)),
            )
            for day, value in shown
        ]
        if len(mapped) > 1:
            c.draw.line(
                [(c.x(x), c.y(y)) for x, y in mapped],
                fill=color,
                width=c.x(6),
                joint="curve",
            )
        if mapped:
            c.circle(mapped[-1], 6, fill=color)
        c.text((sx0, y1 - 14), "Feb. 27", size=14, fill=MUTED, anchor="la")
        c.text((sx1, y1 - 14), "latest", size=14, fill=MUTED, anchor="ra")

    if phase(progress, 0.88, 0.97) > 0.15:
        inflation_change = data.energy_metrics["inflation_change_bp"]
        inflation_direction = "fell" if inflation_change < 0 else "rose"
        c.rectangle((500, 756, 1500, 804), fill=SOFT_TEAL, radius=14)
        c.text(
            (1000, 780),
            (
                "Oil and gasoline rose sharply. Five-year inflation expectations "
                f"{inflation_direction} {abs(inflation_change):.0f} basis points."
            ),
            size=20,
            weight="bold",
            anchor="mm",
        )
    draw_footer(
        c,
        "U.S. EIA; FRED (EIA and U.S. Treasury series), retrieved Aug. 14, 2026",
        (
            "Last observation on or before Feb. 27 = 100. Native daily/weekly frequency. "
            "Descriptive event watch—not a causal pass-through estimate."
        ),
    )
    return c.image


def progress_for_frame(
    index: int,
    total: int,
    opening_hold: int = 10,
    closing_hold: int = 20,
) -> float:
    if index < opening_hold:
        return 0.0
    if index >= total - closing_hold:
        return 1.0
    return (index - opening_hold) / (total - opening_hold - closing_hold - 1)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def stabilize_webm_uids(path: Path, name: str) -> None:
    """Replace FFmpeg's random Matroska track UIDs with a stable nonzero value."""
    payload = bytearray(path.read_bytes())
    cluster = payload.find(b"\x1f\x43\xb6\x75")
    if cluster < 0:
        raise RuntimeError(f"WebM cluster not found: {path}")
    uid = hashlib.sha256(f"microdata-lab:{name}".encode()).digest()[:8]
    for marker in (b"\x73\xc5\x88", b"\x63\xc5\x88"):
        offsets: list[int] = []
        start = 0
        while True:
            offset = payload.find(marker, start, cluster)
            if offset < 0:
                break
            offsets.append(offset)
            start = offset + len(marker)
        if len(offsets) != 1:
            raise RuntimeError(f"Expected one {marker.hex()} UID in {path}, found {len(offsets)}")
        value_start = offsets[0] + len(marker)
        payload[value_start : value_start + len(uid)] = uid
    path.write_bytes(payload)


def encode_animation(
    name: str,
    output_dir: Path,
    frame_count: int,
    scene: Callable[[float, tuple[int, int]], Image.Image],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"microdata-{name}-") as temp:
        frames = Path(temp)
        for index in range(frame_count):
            progress = progress_for_frame(index, frame_count)
            scene(progress, (VIDEO_W, VIDEO_H)).save(frames / f"frame_{index:04d}.png")
        input_pattern = str(frames / "frame_%04d.png")
        gif_path = output_dir / f"{name}.gif"
        webm_path = output_dir / f"{name}.webm"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                input_pattern,
                "-filter_complex",
                "split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5",
                "-loop",
                "0",
                str(gif_path),
            ]
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                input_pattern,
                "-fflags",
                "+bitexact",
                "-c:v",
                "libvpx-vp9",
                "-flags:v",
                "+bitexact",
                "-crf",
                "36",
                "-b:v",
                "0",
                "-pix_fmt",
                "yuv420p",
                "-deadline",
                "good",
                "-cpu-used",
                "2",
                "-map_metadata",
                "-1",
                "-write_crc32",
                "0",
                "-an",
                str(webm_path),
            ]
        )
        stabilize_webm_uids(webm_path, name)


def write_static(
    name: str,
    output_dir: Path,
    scene: Callable[[float, tuple[int, int]], Image.Image],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene(1.0, (BASE_W, BASE_H)).save(output_dir / f"{name}.png", optimize=True)


def verify_media(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing or empty media: {path}")
        if path.suffix == ".png":
            with Image.open(path) as image:
                if image.size != (BASE_W, BASE_H):
                    raise RuntimeError(f"Wrong PNG size for {path}: {image.size}")
        elif path.suffix in {".gif", ".webm"}:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=width,height:format=duration",
                    "-of",
                    "default=noprint_wrappers=1",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            if "width=1280" not in probe or "height=720" not in probe:
                raise RuntimeError(f"Wrong animation size for {path}: {probe}")
            duration_line = next(
                line for line in probe.splitlines() if line.startswith("duration=")
            )
            duration = float(duration_line.split("=", 1)[1])
            if duration < 10.0:
                raise RuntimeError(f"Animation is too fast ({duration:.2f}s): {path}")


def main() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required")
    data = load_data()
    jobs = [
        (
            "low-tax-illusion",
            DEMOS / "demo1-low-tax-illusion" / "media",
            110,
            lambda p, size: draw_tax_scene(data, p, size),
        ),
        (
            "housing-assistance",
            DEMOS / "demo2-housing-assistance" / "media",
            120,
            lambda p, size: draw_housing_scene(data, p, size),
        ),
        (
            "public-power",
            DEMOS / "demo3-public-power" / "media",
            130,
            lambda p, size: draw_power_scene(data, p, size),
        ),
        (
            "hormuz-watch",
            DEMOS / "demo4-hormuz-watch" / "media",
            130,
            lambda p, size: draw_energy_scene(data, p, size),
        ),
    ]
    outputs: list[Path] = []
    for name, output_dir, frame_count, scene in jobs:
        write_static(name, output_dir, scene)
        encode_animation(name, output_dir, frame_count, scene)
        outputs.extend(
            [output_dir / f"{name}.png", output_dir / f"{name}.gif", output_dir / f"{name}.webm"]
        )
    verify_media(outputs)
    for path in outputs:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
