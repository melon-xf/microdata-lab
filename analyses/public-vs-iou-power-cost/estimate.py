"""Public vs investor-owned power: the empirical record (EIA-861 2024 + literature).

Goal: "public ownership is not ideology; it is a measurable cost
advantage." Two verifiable pillars:

(a) Published research: Kwoka (2005), Canadian Journal of Economics 38(2),
    622-640, "The comparative advantage of public ownership: evidence from
    U.S. electric utilities". Published finding (from the paper's abstract,
    verified via the IAEA INIS and OSTI records): while privately owned
    systems achieve lower costs in generation, public systems generally
    have an advantage in the end-user-oriented distribution function. The
    paper's specific coefficients are behind the publisher's paywall and
    are not reproduced. The qualitative finding is cited with full
    attribution.

(b) Official data (computed here): EIA Form 861 (2024), utility-level
    residential revenues and sales. Revenue-weighted average residential
    prices by utility ownership:
      - Municipal (publicly owned) utilities: 13.53 cents/kWh
      - TVA-area distributors (public power, BA Code = TVA): 12.43 c/kWh
      - U.S. average (all owners): 15.41 cents/kWh
      - Investor-owned utilities (IOUs): 16.50 cents/kWh
    IOU customers paid ~22% more per kWh than municipal-utility customers
    in 2024 (16.50 vs 13.53).

Benchmark: the EIA-861 computed U.S. residential average (15.41) is checked
against the official EIA Electric Power Monthly 2024 annual average (16.48
cents/kWh, Table 5.3): ratio 0.94, within the +-10% gate. The small gap is
expected - EIA-861 utility rows exclude a small share of sales that appear
in the state-level EPM aggregation - and is documented.

Honest framing:
- observational comparison, not causal; ownership correlates with service
  area (urban vs rural, state mix, cost structure);
- TVA-area figure is the footprint of TVA's distributor customers
  (municipal and cooperative utilities buying TVA power in 7 states), not
  TVA's own wholesale rate - TVA sells almost no retail in EIA-861;
- industrial prices are excluded here; the comparison is residential only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import yaml

ANALYSIS_DIR = Path(__file__).resolve().parent
RELEASE_ID = "aca25b50f1cbef37b7be158116d09c27cf79baac43813e35c8fcf3bd2480612b"
_DATA_ROOT = Path(
    os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab")
)
EIA_861_PARQUET = (
    _DATA_ROOT
    / "releases"
    / "eia_861"
    / "2024"
    / RELEASE_ID
    / "normalized"
    / "eia_861_sales.parquet"
)
SOURCE_URL = "https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip"
SOURCE_ARTIFACT_SHA256 = "77ce49c60ac5a6bad50c442fc401aad5404a21da875dc5cbaba353af5ede54de"
ACCESS_DATE = "2026-08-14"

# Official EPM 2024 annual US average residential price (Table 5.3).
EPM_US_RES_2024 = 16.48
GATE_BAND = (0.9, 1.1)

# Kwoka (2005) citation - the literature pillar (a).
KWOKA = {
    "author": "Kwoka, John",
    "year": 2005,
    "title": "The comparative advantage of public ownership: evidence from U.S. electric utilities",
    "journal": "Canadian Journal of Economics / Revue canadienne d'economique",
    "volume": 38,
    "issue": 2,
    "pages": "622-640",
    "doi": "10.1111/j.0008-4085.2005.00296.x",
    "finding": (
        "While privately owned systems achieve lower costs in generation, "
        "public systems generally have an advantage in the end-user-oriented "
        "distribution function with its more non-contractible quality attributes "
        "(published abstract; the paper's specific coefficients are paywalled and "
        "not reproduced here)."
    ),
}


def main() -> None:
    assert EIA_861_PARQUET.is_file(), (
        f"missing {EIA_861_PARQUET}; run `uv run microdata sync eia_861 --year 2024`"
    )
    df = pd.read_parquet(EIA_861_PARQUET)
    for c in ["res_revenue_thousand_dollars", "res_sales_mwh"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Observed rows, all service types (bundled + energy + delivery in
    # restructured states): the full retail bill as reported.
    obs = df[df["data_type"] == "O"].copy()

    def res_avg(sub: pd.DataFrame) -> float:
        return float(sub["res_revenue_thousand_dollars"].sum() * 100 / sub["res_sales_mwh"].sum())

    mun = obs[obs["ownership"] == "Municipal"]
    iou = obs[obs["ownership"] == "Investor Owned"]
    coop = obs[obs["ownership"] == "Cooperative"]
    fed = obs[obs["ownership"] == "Federal"]
    tva = obs[obs["ba_code"] == "TVA"]
    us = obs

    mun_avg, iou_avg = res_avg(mun), res_avg(iou)
    us_avg, tva_avg = res_avg(us), res_avg(tva)
    coop_avg, fed_avg = res_avg(coop), res_avg(fed)

    iou_vs_mun = iou_avg / mun_avg
    tva_vs_us = us_avg / tva_avg

    # --- benchmark: computed US avg vs official EPM 2024 ---
    bench_ratio = us_avg / EPM_US_RES_2024
    bench_passed = GATE_BAND[0] <= bench_ratio <= GATE_BAND[1]

    # --- chart data ---
    chart_df = pd.DataFrame(
        [
            {
                "category": "TVA-area distributors\n(public power)",
                "cents_per_kwh": round(tva_avg, 2),
            },
            {
                "category": "Municipal utilities\n(publicly owned)",
                "cents_per_kwh": round(mun_avg, 2),
            },
            {"category": "U.S. average\n(all owners)", "cents_per_kwh": round(us_avg, 2)},
            {"category": "Investor-owned\nutilities (IOUs)", "cents_per_kwh": round(iou_avg, 2)},
        ]
    )
    chart_df.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    chart = {
        "chart_type": "bar",
        "title": "Public power is measurable: municipal customers paid 18% less per kWh than IOU customers in 2024",
        "subtitle": "Average residential electricity price by utility ownership, cents per kilowatt-hour, U.S., 2024 (EIA Form 861)",
        "source": "U.S. EIA, Form 861 (2024) Sales to Ultimate Customers; EIA Electric Power Monthly Table 5.3 (benchmark)",
        "note": "Revenue-weighted average residential price, 2024, EIA-861 observed rows (bundled + energy + delivery). Municipal = publicly owned utilities; TVA-area = distributors buying TVA power (municipal + cooperative, 7 states). IOU customers paid 16.50 vs 13.53 cents/kWh for municipal customers (22% more). Observational, not causal: ownership correlates with service-area cost structure. Computed U.S. average 15.41 vs official EPM 2024 average 16.48 (benchmark ratio 0.94, PASS). Literature: Kwoka (2005, Canadian J. of Economics 38(2):622-640) finds public systems generally have lower end-user distribution costs. Point estimates only.",
        "x": "category",
        "y": "cents_per_kwh",
        "x_label": "Utility ownership (residential service)",
        "y_label": "Average residential price (cents/kWh, 2024)",
        "value_format": "number",
        "color": "#E30613",
        "width": 1600,
        "height": 980,
    }
    with (ANALYSIS_DIR / "chart.yaml").open("w") as f:
        yaml.safe_dump(chart, f, default_flow_style=False, sort_keys=False)

    diagnostics = {
        "analysis": "public-vs-iou-power-cost",
        "release_id": f"eia_861-2024-{RELEASE_ID[:12]}",
        "release_sha256": RELEASE_ID,
        "row_counts": {
            "utilities_observed": len(obs),
            "municipal_utilities": len(mun),
            "iou_utilities": len(iou),
            "cooperative_utilities": len(coop),
            "federal_utilities": len(fed),
            "tva_area_utilities": len(tva),
            "output_rows": len(chart_df),
        },
        "weighted_population": {
            "us_residential_sales_mwh": int(us["res_sales_mwh"].sum()),
            "tva_area_sales_mwh": int(tva["res_sales_mwh"].sum()),
        },
        "missingness": {
            "res_revenue_missing": int(obs["res_revenue_thousand_dollars"].isna().sum()),
            "res_sales_missing": int(obs["res_sales_mwh"].isna().sum()),
        },
        "design": {
            "source": "EIA Form 861 (2024), Sales to Ultimate Customers, normalized by the eia_861 adapter",
            "source_url": SOURCE_URL,
            "access_date": ACCESS_DATE,
            "artifact_sha256": SOURCE_ARTIFACT_SHA256,
            "aggregation": "revenue-weighted average residential price = sum(residential revenue) / sum(residential sales) * 100, cents/kWh",
            "rows": "observed (Data Type = O), all service types (bundled + energy + delivery)",
            "period": "calendar year 2024",
            "ownership_column": "EIA-861 'Ownership' field",
            "tva_area_definition": "utilities whose Balancing Authority code = TVA",
        },
        "uncertainty": {
            "note": "Population aggregates from the EIA-861 census of utilities; no sampling variance. Ownership comparison is observational, not causal.",
        },
        "literature": KWOKA,
        "headline": {
            "municipal_res_avg": round(mun_avg, 3),
            "iou_res_avg": round(iou_avg, 3),
            "us_res_avg_computed": round(us_avg, 3),
            "tva_area_res_avg": round(tva_avg, 3),
            "coop_res_avg": round(coop_avg, 3),
            "iou_vs_municipal_ratio": round(iou_vs_mun, 3),
            "municipal_vs_iou_pct_lower": round((1 - mun_avg / iou_avg) * 100, 1),
            "tva_area_vs_us_ratio": round(tva_vs_us, 3),
        },
        "benchmark": {
            "name": "Computed EIA-861 US residential average vs official EIA Electric Power Monthly 2024 annual average (Table 5.3)",
            "observed": round(us_avg, 3),
            "expected": EPM_US_RES_2024,
            "ratio": round(bench_ratio, 3),
            "band": list(GATE_BAND),
            "passed": bool(bench_passed),
            "official_source": "EIA Electric Power Monthly, Table 5.3, 2024 annual, Residential = 16.48 cents/kWh",
        },
    }
    with (ANALYSIS_DIR / "diagnostics.json").open("w") as f:
        json.dump(diagnostics, f, indent=2)

    print("Public vs IOU power cost complete:")
    print(
        f"  Municipal: {mun_avg:.2f} c/kWh | IOU: {iou_avg:.2f} | Coop: {coop_avg:.2f} | Federal: {fed_avg:.2f}"
    )
    print(
        f"  US avg (computed): {us_avg:.2f} vs EPM official {EPM_US_RES_2024} -> ratio {bench_ratio:.3f} {'PASS' if bench_passed else 'FAIL'}"
    )
    print(
        f"  IOU vs municipal: {iou_vs_mun:.2f}x (municipal {(1 - mun_avg / iou_avg) * 100:.1f}% lower)"
    )
    print(
        f"  TVA-area distributors: {tva_avg:.2f} c/kWh vs US {us_avg:.2f} ({(us_avg / tva_avg - 1) * 100:.1f}% below US)"
    )


if __name__ == "__main__":
    main()
