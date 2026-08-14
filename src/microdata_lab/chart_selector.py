"""Claim-shape → chart-type selector.

Standardized decision system so chart-form choices are repeatable across
projects. Each claim shape maps to the encoding that communicates it
most directly — a form that requires the reader to do arithmetic is a
failed encoding for a less familiar audience.
"""

from __future__ import annotations

from enum import StrEnum


class ClaimShape(StrEnum):
    """The rhetorical shape of the data's claim."""

    GAP = "gap"  # Two series diverge across categories
    TREND = "trend"  # Monotone change across ordered categories
    RATIO = "ratio"  # One group's rate relative to another
    PROPORTION = "proportion"  # Parts of a whole
    PLACE = "place"  # Geographic variation
    SCALE = "scale"  # Absolute magnitude / count
    LEVEL = "level"  # Categorical comparison at one point in time


# Decision matrix: claim shape → recommended chart types (best first)
SELECTOR: dict[ClaimShape, list[dict[str, str]]] = {
    ClaimShape.GAP: [
        {"type": "ribbon", "why": "Shaded area between two lines IS the gap — no arithmetic"},
        {"type": "dumbbell", "why": "Connector length encodes the gap per category"},
        {
            "type": "bar",
            "why": "Side-by-side bars require the reader to subtract (weakest for gaps)",
        },
    ],
    ClaimShape.TREND: [
        {
            "type": "step",
            "why": "Step area shows cumulative decline/increase with the shape being the claim",
        },
        {"type": "line", "why": "Connected points show direction of change"},
        {"type": "bar", "why": "Disconnected bars hide the trajectory (weakest for trends)"},
    ],
    ClaimShape.RATIO: [
        {
            "type": "ratio_ladder",
            "why": "Dots on a ratio scale vs parity line — the multiplier IS the mark",
        },
        {"type": "bar", "why": "Paired bars with ratio stamps (2.5×) make the ratio explicit"},
    ],
    ClaimShape.PROPORTION: [
        {"type": "pictogram", "why": "Each glyph = one unit; count the red ones (no scale needed)"},
        {
            "type": "donut",
            "why": "Arc length shows share of whole (familiar but harder to compare)",
        },
    ],
    ClaimShape.PLACE: [
        {"type": "choropleth", "why": "Color intensity shows geographic variation directly"},
        {"type": "pictogram", "why": "One grid per region shows the scale difference"},
    ],
    ClaimShape.SCALE: [
        {"type": "pictogram", "why": "Glyph count makes magnitude tangible (1 glyph = 1%)"},
        {"type": "bar", "why": "Bar length shows relative magnitude"},
    ],
    ClaimShape.LEVEL: [
        {"type": "bar", "why": "Horizontal bars compare categorical values at a glance"},
        {"type": "dot", "why": "Dots on a common axis for sparse categories"},
    ],
}


def recommend_charts(shape: ClaimShape, n_alternatives: int = 3) -> list[dict[str, str]]:
    """Return the top N recommended chart types for a claim shape.

    Each entry: {"type": "ribbon", "why": "Shaded area..."}
    """
    return SELECTOR.get(shape, SELECTOR[ClaimShape.LEVEL])[:n_alternatives]


def detect_shape(
    n_series: int = 1,
    is_ordered: bool = False,
    is_geographic: bool = False,
    is_ratio: bool = False,
    n_categories: int = 2,
) -> ClaimShape:
    """Auto-detect claim shape from data characteristics.

    This is a heuristic first pass — the human override (via chart.yaml)
    always wins.
    """
    if is_geographic:
        return ClaimShape.PLACE
    if is_ratio:
        return ClaimShape.RATIO
    if n_series >= 2:
        return ClaimShape.GAP
    if is_ordered and n_categories > 2:
        return ClaimShape.TREND
    return ClaimShape.LEVEL
