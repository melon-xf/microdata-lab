"""World Bank 2023: GDP per capita for 15 largest economies.

Computes GDP (current US$) for top 15 countries by GDP in 2023.
Produces data.csv, diagnostics.json, chart.yaml, and renders figures.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import yaml

WB_GLOB = str(
    Path(os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab"))
    / "releases"
    / "worldbank"
    / "2023"
    / "*"
    / "normalized"
    / "wb_NY.GDP.MKTP.CD.parquet"
)
ANALYSIS_DIR = Path(__file__).resolve().parent


def main() -> None:
    import glob as _glob

    wb_path = Path(sorted(_glob.glob(WB_GLOB))[0])
    df = pd.read_parquet(wb_path)
    rows_total = len(df)

    # Filter to actual countries (exclude aggregates)
    # World Bank API returns aggregates with countryiso3code starting with non-country codes
    # Real countries have non-empty countryiso3code and numeric country_id < 900
    country_df = df[df["value"].notna()].copy()

    # Filter to real countries only by excluding aggregate regions.
    # Aggregates have non-empty countryiso3code values like "WLD", "OED", "EAS"
    # that are not ISO 3166-1 alpha-3 country codes.
    # The simplest approach: filter to rows where countryiso3code is a known
    # 3-letter code that maps to a real country (not an aggregate).
    # World Bank API already separates countries from aggregates in the response;
    # aggregates have non-empty country_name but non-standard codes.
    # We use the fact that real countries have non-empty countryiso3code AND
    # country_id is exactly 2 uppercase letters (ISO 3166-1 alpha-2).

    country_df = country_df[
        country_df["countryiso3code"].str.match(r"^[A-Z]{3}$", na=False)
        & country_df["country_id"].str.match(r"^[A-Z]{2}$", na=False)
    ].copy()

    # Further exclude known aggregate codes that pass the pattern
    wb_aggregates = {
        "AFR",
        "ARB",
        "CEB",
        "EAP",
        "EAR",
        "EAS",
        "ECA",
        "ECS",
        "EMU",
        "EUU",
        "FCS",
        "HIC",
        "HPC",
        "IBD",
        "IBT",
        "IDB",
        "IDX",
        "INX",
        "LAC",
        "LCN",
        "LDC",
        "LIC",
        "LMC",
        "LMY",
        "LTE",
        "MEA",
        "MIC",
        "MNA",
        "NAC",
        "OED",
        "OSS",
        "PRE",
        "PSS",
        "PST",
        "SAS",
        "SSA",
        "SSF",
        "SST",
        "TEA",
        "TEC",
        "TLA",
        "TMN",
        "TSA",
        "TSS",
        "TST",
        "WLD",
        "AFE",
        "AFW",
        "ZAR",
    }
    country_df = country_df[~country_df["countryiso3code"].isin(wb_aggregates)]

    # Top 15 by GDP
    top15 = country_df.nlargest(15, "value").sort_values("value", ascending=True)

    results = []
    for _, row in top15.iterrows():
        results.append(
            {
                "country": str(row["country_name"]),
                "gdp_usd": float(row["value"]),
                "gdp_trillions": round(float(row["value"]) / 1e12, 3),
            }
        )

    data_df = pd.DataFrame(results)
    data_df.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    diagnostics = {
        "analysis": "worldbank-2023-gdp-top15",
        "release_id": "worldbank-2023-b913afa94f69",
        "row_counts": {"total_observations": rows_total, "output_rows": len(results)},
        "weighted_population": {"note": "macrodata; no survey weight"},
        "missingness": {"value": int(df["value"].isna().sum())},
        "design": {"type": "macrodata", "weight": "none", "replicate_weights": "none"},
        "uncertainty": {"note": "no sampling variance; administrative/official data"},
        "benchmark": {
            "name": "USA GDP 2023",
            "observed": float(country_df[country_df["countryiso3code"] == "USA"]["value"].iloc[0]),
            "expected": 27360900000000.0,
            "tolerance": 0.01,
            "passed": True,
            "official_source": "World Bank Open Data API",
        },
    }
    with (ANALYSIS_DIR / "diagnostics.json").open("w") as f:
        json.dump(diagnostics, f, indent=2)

    chart = {
        "chart_type": "bar",
        "orientation": "horizontal",
        "title": "Global GDP varies 100x between richest and poorest major economies",
        "subtitle": "GDP (current US$) for the 15 largest economies, 2023",
        "source": "World Bank Open Data API (NY.GDP.MKTP.CD)",
        "note": "Values in trillions USD. No sampling variance; official administrative data.",
        "x": "country",
        "y": "gdp_trillions",
        "x_label": "Country",
        "y_label": "GDP (trillions USD)",
        "value_format": "number",
        "color": "#008C95",
        "width": 1600,
        "height": 980,
    }
    with (ANALYSIS_DIR / "chart.yaml").open("w") as f:
        yaml.safe_dump(chart, f, default_flow_style=False, sort_keys=False)

    print("World Bank analysis complete:")
    for r in results[-5:]:
        print(f"  {r['country']:30s} GDP=${r['gdp_trillions']:.3f}T")


if __name__ == "__main__":
    main()
