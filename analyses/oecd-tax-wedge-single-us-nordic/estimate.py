"""US vs Nordic average tax wedge, single adults, 2025 (published figure 1).

Replicates a published figure (``nordic_single_average_wedge-1.png``) from
OECD Tax Wages decomposition (DSD_TAX_WAGES_DECOMP), measure AV_TW,
household type S_C0 (single, no children), wage grid AW50-AW250, 2025.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import yaml

ANALYSIS_DIR = Path(__file__).resolve().parent
LAKE = Path(
    os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab")
)


def load_tax_wages() -> pd.DataFrame:
    import glob

    hits = sorted(
        glob.glob(
            str(
                LAKE
                / "releases"
                / "oecd_tax_wages"
                / "2025"
                / "*"
                / "normalized"
                / "tax_wages.parquet"
            )
        )
    )
    if not hits:
        raise FileNotFoundError("No oecd_tax_wages 2025 release found; sync first")
    return pd.read_parquet(hits[-1])


def wage_level_num(code: str) -> int:
    """AW50 -> 50, AW250 -> 250."""
    return int(code.removeprefix("AW"))


def main() -> None:
    df = load_tax_wages()

    # Series: AV_TW by country, wage grid, single no children, 2025
    countries = ["USA", "DNK", "FIN", "NOR", "SWE"]
    wedge = df[
        (df["MEASURE"] == "AV_TW")
        & (df["HOUSEHOLD_TYPE"] == "S_C0")
        & (df["TIME_PERIOD"] == "2025")
        & (df["REF_AREA"].isin(countries))
        & (df["INCOME_PRINCIPAL"].str.startswith("AW"))
    ].copy()
    wedge["wage_pct"] = wedge["INCOME_PRINCIPAL"].map(wage_level_num)
    wedge = wedge[(wedge["wage_pct"] >= 50) & (wedge["wage_pct"] <= 250)]

    country_names = {
        "USA": "United States",
        "DNK": "Denmark",
        "FIN": "Finland",
        "NOR": "Norway",
        "SWE": "Sweden",
    }
    wedge["country"] = wedge["REF_AREA"].map(country_names)
    wedge["avg_tax_wedge"] = wedge["value"]  # already percent

    out = wedge[["wage_pct", "country", "avg_tax_wedge"]].sort_values(["wage_pct", "country"])
    out.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    benchmark_row = wedge[(wedge["REF_AREA"] == "USA") & (wedge["wage_pct"] == 100)]
    observed = float(benchmark_row["avg_tax_wedge"].iloc[0])
    diagnostics = {
        "analysis": ANALYSIS_DIR.name,
        "release_id": "oecd_tax_wages-2025-511005655c1e",
        "row_counts": {
            "output_rows": len(out),
            "wage_levels": out["wage_pct"].nunique(),
            "countries": out["country"].nunique(),
        },
        "weighted_population": {"note": "macrodata; no survey weight"},
        "missingness": {"value": int(out["avg_tax_wedge"].isna().sum())},
        "design": {"type": "macrodata", "weight": "none", "replicate_weights": "none"},
        "uncertainty": {"note": "no sampling variance; official macrodata"},
        "benchmark": {
            "name": "USA single AW100 average tax wedge 2025",
            "observed": observed,
            "expected": 29.98,
            "tolerance": 0.1,
            "passed": bool(abs(observed - 29.98) <= 0.1),
            "official_source": "OECD Tax Wages decomposition, DSD_TAX_WAGES_DECOMP",
        },
    }
    (ANALYSIS_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2))

    chart = {
        "chart_type": "line",
        "title": "The U.S. labor tax wedge is the lowest of the five at every wage level (2025)",
        "subtitle": "Average tax wedge by percent of average wage, single adults with no children",
        "source": "OECD, Labor Tax Decomposition, 2025",
        "note": "Average tax wedge: share of total labor cost absorbed by taxes and social security contributions.",
        "x": "wage_pct",
        "y": "avg_tax_wedge",
        "series": "country",
        "series_order": [
            "United States",
            "Sweden",
            "Finland",
            "Denmark",
            "Norway",
        ],
        "x_label": "Wage as a Percent of Average Wage",
        "y_label": "Average tax wedge",
        "x_ticks": [50, 100, 150, 200, 250],
        "y_ticks": [20, 30, 40, 50, 60],
        "y_min": 20,
        "y_max": 60,
        "tick_suffix": "%",
        "value_format": "number",
        "theme": "swiss",
        "eyebrow": "labor taxes · 2025",
        "width": 2200,
        "height": 1400,
    }
    (ANALYSIS_DIR / "chart.yaml").write_text(yaml.safe_dump(chart, sort_keys=False))

    print(f"Wedge single: {len(out)} rows, USA@100% = {observed:.2f}%")


if __name__ == "__main__":
    main()
