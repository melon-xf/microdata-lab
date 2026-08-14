"""SHED 2025: Financial well-being by race/ethnicity.

Computes weighted share "at least okay financially" by race/ethnicity
using SHED weight. Produces data.csv, diagnostics.json, chart.yaml,
and renders static + interactive figures.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import yaml

SHED_GLOB = str(
    Path(os.environ.get("MICRODATA_ROOT", Path.home() / ".local" / "share" / "microdata-lab"))
    / "releases"
    / "shed"
    / "2025"
    / "*"
    / "normalized"
    / "respondents.parquet"
)
ANALYSIS_DIR = Path(__file__).resolve().parent

RACE_ORDER = ["White", "Hispanic", "Black", "Asian", "Other"]


def main() -> None:
    import glob as _glob

    shed_path = Path(sorted(_glob.glob(SHED_GLOB))[0])
    df = pd.read_parquet(shed_path)
    rows_total = len(df)
    weight = pd.to_numeric(df["weight"], errors="coerce").fillna(0)
    pop = weight.sum()

    results = []
    for race_val, race_df in df.groupby("race_5cat"):
        w = pd.to_numeric(race_df["weight"], errors="coerce").fillna(0)
        okay = race_df["atleast_okay"]
        okay_mask = (okay == "Yes").fillna(False)
        total_w = w.sum()
        share_okay = float(w[okay_mask].sum() / total_w) if total_w > 0 else 0.0

        n = len(race_df)
        se = float((share_okay * (1 - share_okay) / n) ** 0.5) if n > 0 else 0.0
        ci_low = max(0.0, share_okay - 1.96 * se)
        ci_high = min(1.0, share_okay + 1.96 * se)

        results.append(
            {
                "race": str(race_val),
                "estimate": round(share_okay, 4),
                "standard_error": round(se, 4),
                "ci_low": round(ci_low, 4),
                "ci_high": round(ci_high, 4),
                "unweighted_n": int(n),
                "weighted_pop": round(float(total_w)),
            }
        )

    # Sort by RACE_ORDER
    results.sort(key=lambda x: RACE_ORDER.index(x["race"]) if x["race"] in RACE_ORDER else 99)

    # Write data.csv
    data_df = pd.DataFrame(results)
    data_df.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    # Diagnostics
    overall_okay = float(weight[(df["atleast_okay"] == "Yes").fillna(False)].sum() / weight.sum())
    diagnostics = {
        "analysis": "shed-2025-wellbeing-by-race",
        "release_id": "shed-2025-9a5cea7a2f8e",
        "row_counts": {"total_respondents": rows_total, "output_rows": len(results)},
        "weighted_population": {"respondents": round(pop)},
        "missingness": {
            "race_5cat": int(df["race_5cat"].isna().sum()),
            "atleast_okay": int(df["atleast_okay"].isna().sum()),
        },
        "design": {
            "main_weight": "weight",
            "replicate_weights": "none in public release",
            "note": "SHED provides analysis weights but no replicate weights; SE is simple proportion",
        },
        "uncertainty": {
            "confidence_level": 0.95,
            "interval_method": "normal approximation for proportions",
        },
        "benchmark": {
            "name": "Overall share at least okay financially",
            "observed": round(overall_okay, 4),
            "expected": 0.73,
            "tolerance": 0.01,
            "passed": abs(overall_okay - 0.73) < 0.01,
            "official_source": "https://www.federalreserve.gov/publications/2026-economic-well-being-of-us-households-in-2025-overall-financial-well-being.htm",
        },
    }
    with (ANALYSIS_DIR / "diagnostics.json").open("w") as f:
        json.dump(diagnostics, f, indent=2)

    # Chart spec
    chart = {
        "chart_type": "bar",
        "orientation": "vertical",
        "title": "White households report the highest financial well-being",
        "subtitle": "Share 'at least okay financially' by race/ethnicity, 2025",
        "source": "Federal Reserve, Survey of Household Economics and Decisionmaking (SHED) 2025",
        "note": "Weighted with SHED analysis weight. 95% CI bounds are in the fallback data table.",
        "x": "race",
        "y": "estimate",
        "ci_low": "ci_low",
        "ci_high": "ci_high",
        "x_label": "Race/ethnicity",
        "y_label": "Share 'at least okay'",
        "value_format": "percent",
        "color": "#008C95",
        "width": 1600,
        "height": 980,
    }
    with (ANALYSIS_DIR / "chart.yaml").open("w") as f:
        yaml.safe_dump(chart, f, default_flow_style=False, sort_keys=False)

    print("SHED analysis complete:")
    for r in results:
        print(
            f"  {r['race']:15s} okay={r['estimate']:.1%} SE={r['standard_error']:.4f} n={r['unweighted_n']}"
        )


if __name__ == "__main__":
    main()
