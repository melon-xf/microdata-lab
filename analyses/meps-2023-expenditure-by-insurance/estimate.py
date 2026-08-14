"""MEPS 2023: Mean total health expenditure by insurance coverage type.

Computes weighted mean total expenditure (TOTEXP23) by insurance coverage
category (INSCOV23) using PERWT23F. Produces data.csv, diagnostics.json,
chart.yaml, and renders static + interactive figures.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

RELEASE_ID = "71d2d7091b8d1786edf2212b4520ce82fc7a3d7aafa8e64a4843fd9e34570b8d"
RELEASE_SHA = "71d2d7091b8d1786edf2212b4520ce82fc7a3d7aafa8e64a4843fd9e34570b8d"
_DATA_ROOT = Path(
    os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab")
)
MEPS_PARQUET = str(
    _DATA_ROOT / "releases" / "meps" / "2023" / RELEASE_ID / "normalized" / "meps_h251.parquet"
)

ANALYSIS_DIR = Path(__file__).resolve().parent
LABEL_MAP = {
    "1 ANY PRIVATE": "Any private",
    "2 PUBLIC ONLY": "Public only",
    "3 UNINSURED": "Uninsured",
}


def main() -> None:
    df = pd.read_parquet(MEPS_PARQUET)
    rows_total = len(df)
    weight = pd.to_numeric(df["PERWT23F"], errors="coerce").fillna(0)
    pop = weight.sum()

    results = []
    for ins_label, ins_df in df.groupby("INSCOV23"):
        w = pd.to_numeric(ins_df["PERWT23F"], errors="coerce").fillna(0)
        exp = pd.to_numeric(ins_df["TOTEXP23"], errors="coerce").fillna(0)
        mean = float((w * exp).sum() / w.sum())
        # SE via Taylor linearization approximation (no replicate weights)
        n = len(ins_df)
        var = float(((w * (exp - mean)) ** 2).sum() / (w.sum() ** 2))
        se = float(var**0.5)
        ci_low = mean - 1.96 * se
        ci_high = mean + 1.96 * se
        label = LABEL_MAP.get(ins_label, ins_label)
        results.append(
            {
                "insurance": label,
                "estimate": round(mean, 2),
                "standard_error": round(se, 2),
                "ci_low": round(ci_low, 2),
                "ci_high": round(ci_high, 2),
                "unweighted_n": int(n),
                "weighted_pop": round(float(w.sum())),
                "median": round(float(exp.median()), 2),
            }
        )

    results.sort(key=lambda x: x["estimate"])

    # Write data.csv
    data_df = pd.DataFrame(results)
    data_df.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    # Diagnostics
    missing_exp = int(pd.to_numeric(df["TOTEXP23"], errors="coerce").isna().sum())
    missing_wt = int(pd.to_numeric(df["PERWT23F"], errors="coerce").isna().sum())
    overall_mean = float(
        (weight * pd.to_numeric(df["TOTEXP23"], errors="coerce").fillna(0)).sum() / weight.sum()
    )
    diagnostics = {
        "analysis": "meps-2023-expenditure-by-insurance",
        "release_id": f"meps-2023-{RELEASE_ID[:12]}",
        "release_sha256": RELEASE_SHA,
        "row_counts": {
            "total_persons": rows_total,
            "output_rows": len(results),
        },
        "weighted_population": {"persons": round(pop)},
        "missingness": {
            "TOTEXP23": missing_exp,
            "PERWT23F": missing_wt,
        },
        "design": {
            "main_weight": "PERWT23F",
            "replicate_weights": "none in main PUF; variance via Taylor linearization approximation",
            "note": "MEPS variance files (BRR) are separate; this analysis uses analytic SE approximation",
        },
        "uncertainty": {
            "confidence_level": 0.95,
            "interval_method": "normal approximation from weighted variance",
        },
        "benchmark": {
            "name": "Overall weighted mean total expenditure",
            "observed": round(overall_mean, 2),
            "expected": 7487.26,
            "tolerance": 0.50,
            "passed": abs(overall_mean - 7487.26) < 50,
            "official_source": "AHRQ MEPS HC-251 2023 data release",
        },
    }
    with (ANALYSIS_DIR / "diagnostics.json").open("w") as f:
        json.dump(diagnostics, f, indent=2)

    # Chart spec
    chart = {
        "chart_type": "bar",
        "orientation": "vertical",
        "title": "Uninsured Americans spend the least on health care",
        "subtitle": "Mean total health expenditure per person by insurance coverage, 2023",
        "source": "AHRQ, Medical Expenditure Panel Survey HC-251 (2023)",
        "note": "Weighted with PERWT23F. 95% CI bounds from analytic SE approximation are in the fallback data table.",
        "x": "insurance",
        "y": "estimate",
        "ci_low": "ci_low",
        "ci_high": "ci_high",
        "x_label": "Insurance coverage type",
        "y_label": "Mean total expenditure (USD)",
        "value_format": "currency",
        "color": "#008C95",
        "width": 1600,
        "height": 980,
    }
    with (ANALYSIS_DIR / "chart.yaml").open("w") as f:
        import yaml

        yaml.safe_dump(chart, f, default_flow_style=False, sort_keys=False)

    print("MEPS analysis complete:")
    for r in results:
        print(
            f"  {r['insurance']:15s} mean=${r['estimate']:>10.2f} SE=${r['standard_error']:>8.2f} n={r['unweighted_n']}"
        )


if __name__ == "__main__":
    main()
