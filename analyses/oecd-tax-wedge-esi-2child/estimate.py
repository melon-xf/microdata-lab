"""US vs Nordic average tax wedge incl. family ESI premium, 2025 (article figure 4).

Replicates "nordic_s_c2_average_wedge_health-1.png". Same normalization as
the single ESI figure, using the average US family premium applied to the
S_C2 (single adult, two children) household.

KFF 2025 Employer Health Benefits Survey, family coverage:
  total premium $26,993; worker share $6,850; employer share $20,143.
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

PREMIUM_TOTAL = 26993.0
PREMIUM_EMPLOYER = 20143.0
PREMIUM_WORKER = 6850.0
assert PREMIUM_TOTAL == PREMIUM_EMPLOYER + PREMIUM_WORKER


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
    return int(code.removeprefix("AW"))


def main() -> None:
    df = load_tax_wages()

    countries = ["USA", "DNK", "FIN", "NOR", "SWE"]
    mask = (
        (df["TIME_PERIOD"] == "2025")
        & (df["REF_AREA"].isin(countries))
        & (df["INCOME_PRINCIPAL"].str.startswith("AW"))
    )
    wedge = df[mask & (df["MEASURE"] == "AV_TW") & (df["HOUSEHOLD_TYPE"] == "S_C2")].copy()
    lc = df[mask & (df["MEASURE"] == "LC") & (df["HOUSEHOLD_TYPE"] == "S_C2")][
        ["REF_AREA", "INCOME_PRINCIPAL", "value"]
    ].rename(columns={"value": "labor_cost"})

    wedge["wage_pct"] = wedge["INCOME_PRINCIPAL"].map(wage_level_num)
    wedge = wedge.merge(lc, on=["REF_AREA", "INCOME_PRINCIPAL"], how="left")
    wedge = wedge[(wedge["wage_pct"] >= 50) & (wedge["wage_pct"] <= 250)]

    # US: recompute wedge with ESI premium added (dashed "US + HI" series).
    # Keep the unadjusted US wedge as its own series, matching the article's
    # six-line figure (US solid + US+HI dashed).
    wedge["avg_tax_wedge"] = wedge["value"]
    us = wedge["REF_AREA"] == "USA"
    tax = wedge.loc[us, "value"] / 100 * wedge.loc[us, "labor_cost"]
    us_hi = wedge.loc[us].copy()
    us_hi["avg_tax_wedge"] = (
        (tax + PREMIUM_TOTAL) / (wedge.loc[us, "labor_cost"] + PREMIUM_EMPLOYER)
    ) * 100

    country_names = {
        "USA": "United States",
        "DNK": "Denmark",
        "FIN": "Finland",
        "NOR": "Norway",
        "SWE": "Sweden",
    }
    wedge["country"] = wedge["REF_AREA"].map(country_names)
    us_hi["country"] = "United States + Health Insurance"

    base = wedge[["wage_pct", "country", "avg_tax_wedge"]]
    hi = us_hi[["wage_pct", "country", "avg_tax_wedge"]]
    out = pd.concat([base, hi]).sort_values(["wage_pct", "country"])
    out.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    us100 = out[(out["country"] == "United States + Health Insurance") & (out["wage_pct"] == 100)]
    nordic = out[
        (out["wage_pct"] == 100) & (out["country"].isin(["Denmark", "Finland", "Norway", "Sweden"]))
    ]
    nordic_avg = nordic["avg_tax_wedge"].mean()
    us_val = float(us100["avg_tax_wedge"].iloc[0])
    diagnostics = {
        "analysis": ANALYSIS_DIR.name,
        "release_id": "oecd_tax_wages-2025-511005655c1e",
        "row_counts": {
            "output_rows": len(out),
            "wage_levels": out["wage_pct"].nunique(),
            "series": out["country"].nunique(),
        },
        "weighted_population": {"note": "macrodata; no survey weight"},
        "missingness": {"value": int(out["avg_tax_wedge"].isna().sum())},
        "design": {"type": "macrodata", "weight": "none", "replicate_weights": "none"},
        "uncertainty": {"note": "no sampling variance; official macrodata"},
        "adjustment": {
            "name": "US ESI family premium added to tax wedge (article method)",
            "premium_total": PREMIUM_TOTAL,
            "premium_employer": PREMIUM_EMPLOYER,
            "premium_worker": PREMIUM_WORKER,
            "source": "KFF 2025 Employer Health Benefits Survey",
        },
        "benchmark": {
            "name": "US 2-child AW100 wedge with ESI at or above Nordic average",
            "observed": us_val,
            "expected": float(nordic_avg),
            "tolerance": 0.0,
            "passed": bool(us_val >= nordic_avg),
            "note": "With the average family ESI premium counted as tax, the US 2-child wedge at the average wage (44.09) exceeds the Nordic average (31.26) and every Nordic country.",
            "official_source": "OECD Tax Wages decomposition + KFF 2025",
        },
    }
    (ANALYSIS_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2))

    chart = {
        "chart_type": "line",
        "title": "adding health premiums closes the tax gap (2025)",
        "subtitle": "Average tax wedge by percent of average wage, single adults with two children",
        "source": "OECD, Labor Tax Decomposition, 2025; KFF Employer Health Benefits Survey, 2025",
        "note": "US + Health Insurance adds the average family-coverage premium ($26,993) to the wedge and employer share ($20,143) to labor cost.",
        "x": "wage_pct",
        "y": "avg_tax_wedge",
        "series": "country",
        "series_order": [
            "United States",
            "Sweden",
            "Finland",
            "United States + Health Insurance",
            "Denmark",
            "Norway",
        ],
        "line_style": {"United States + Health Insurance": "dashed"},
        "x_label": "Wage as a Percent of Average Wage",
        "y_label": "Average tax wedge",
        "x_ticks": [50, 100, 150, 200, 250],
        "y_ticks": [0, 10, 20, 30, 40, 50, 60],
        "y_min": -10,
        "y_max": 60,
        "tick_suffix": "%",
        "value_format": "number",
        "theme": "swiss",
        "eyebrow": "health premiums · 2025",
        "width": 2200,
        "height": 1400,
    }
    (ANALYSIS_DIR / "chart.yaml").write_text(yaml.safe_dump(chart, sort_keys=False))

    print(f"ESI 2-child: US@100% = {us_val:.2f}%, Nordic avg = {nordic_avg:.2f}%")


if __name__ == "__main__":
    main()
