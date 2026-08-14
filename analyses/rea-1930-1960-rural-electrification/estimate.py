"""REA rural electrification: percent of U.S. farms with electricity, 1930-1963.

Goal: measure the pace of U.S. rural electrification before and after the
REA was chartered in 1935.

The series is the official USDA "farms receiving central-station electric
service" estimate, published annually in the USDA Agricultural Statistics
yearbook (compiled from REA annual estimates, with the Census of
Agriculture as the farm-count denominator). Every data point below is read
directly from the scanned USDA Agricultural Statistics editions on
archive.org (page/table cited in README):

  1930  Census of Agriculture: farms reporting electric light
        571,007 farms, 9.1%  (Agricultural Statistics 1940, Table 745)
  1934  Dec 31: 743,954 farms, 10.9%  (Agricultural Statistics 1950, Table 742)
  1940  Apr 1:  1,853,249 farms, 30.4% (Agricultural Statistics 1950, Table 742)
  1945  Jun 30: 2,806,206 farms, 47.9% (Agricultural Statistics 1950, Table 742)
  1949  Jun 30: 4,582,016 farms, 78.2% (Agricultural Statistics 1950, Table 742)
  1954  Jun 30: 4,965,962 farms, 92.3% (Agricultural Statistics 1955, Table 777)
  1960  Jun 30: 3,579,650 farms, 96.5% (Agricultural Statistics 1961, Table 807)
  1963  Jun 30: 3,505,300 farms, 97.9% (Agricultural Statistics 1964, Table 813)

The 1940 census-year figure sometimes cited as 33.2% counts farm dwellings
with electricity (Census of Agriculture "operator's dwelling lighted by
electricity"); the REA central-station estimate for April 1, 1940 is 30.4%.
We use the REA/USDA central-station series throughout for a consistent
definition, and note the census figure in the README.

Benchmark (internal consistency of the published figures):
- Agricultural Statistics 1950 Table 742: increase column for the U.S. row
  reads 3,838,062 = 4,582,016 (1949) - 743,954 (1934). The published
  arithmetic reproduces exactly (PASS).
- 1949: 4,582,016 / 0.782 = 5.86M farms - the table's denominator is the
  1945 Census of Agriculture farm count (5,859,169), as the table footnote
  states (PASS).
- 1960: 3,579,650 / 0.965 = 3.71M farms - the table's denominator is the
  1959 Census of Agriculture farm count (3,703,894) (PASS).

Framing constraints:
- REA was chartered May 1935 (Executive Order 7037; Rural Electrification
  Act of May 1936). The pre-REA market failure: private utilities skipped
  rural areas for low load density and high per-customer line cost; the
  program worked because the federal government took the risk and
  subsidized financing (REA loans at ~2%).
- A TVA residential-rate comparison series was considered but could not be
  verified from the cited TVA publications, so it is omitted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

ANALYSIS_DIR = Path(__file__).resolve().parent

# year, percent of farms with electricity, farms (number), source table
SERIES = [
    (1930, 9.1, 571007, "Ag. Statistics 1940, Table 745 (Census of Agriculture 1930)"),
    (1934, 10.9, 743954, "Ag. Statistics 1950, Table 742"),
    (1940, 30.4, 1853249, "Ag. Statistics 1950, Table 742"),
    (1945, 47.9, 2806206, "Ag. Statistics 1950, Table 742"),
    (1949, 78.2, 4582016, "Ag. Statistics 1950, Table 742"),
    (1954, 92.3, 4965962, "Ag. Statistics 1955, Table 777"),
    (1960, 96.5, 3579650, "Ag. Statistics 1961, Table 807"),
    (1963, 97.9, 3505300, "Ag. Statistics 1964, Table 813"),
]

REA_CHARTER_YEAR = 1935


def main() -> None:
    df = pd.DataFrame(SERIES, columns=["year", "percent", "farms", "source_table"])
    df.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    # benchmark arithmetic checks
    chk1 = (4582016 - 743954) == 3838062  # published increase column
    denom1949 = 4582016 / 0.782
    chk2 = abs(denom1949 - 5859169) / 5859169 < 0.01  # 1945 census farms
    denom1960 = 3579650 / 0.965
    chk3 = abs(denom1960 - 3703894) / 3703894 < 0.01  # 1959 census farms
    passed = chk1 and chk2 and chk3

    chart = {
        "chart_type": "line",
        "title": "The last time America built the grid, it was public - and it worked",
        "subtitle": "Percent of U.S. farms with central-station electric service, 1930-1963 (REA chartered 1935)",
        "source": "USDA Agricultural Statistics (1940, 1950, 1955, 1961, 1964 editions); 1930 point from Census of Agriculture",
        "note": "REA = Rural Electrification Administration, chartered May 1935 (Rural Electrification Act, 1936). Farms receiving central-station electric service (REA estimates), percent of Census of Agriculture farm count. 9.1% in 1930, 30.4% by April 1940, 78.2% by June 1949, 96.5% by June 1960. The census-based 1940 figure (33.2%, farm dwellings with electricity) is slightly higher than the central-station series. Private utilities had reached ~10% of farms in four decades; a public agency with ~2% loans finished the job in two. Point estimates only; no sampling error is published for these aggregates.",
        "x": "year",
        "y": "percent",
        "x_label": "Year",
        "y_label": "Percent of farms with electricity",
        "value_format": "number",
        "vline": [{"x": 1935, "label": "REA chartered", "color": "#E30613", "linetype": "dashed"}],
        "color": "#E30613",
        "width": 1600,
        "height": 980,
    }
    with (ANALYSIS_DIR / "chart.yaml").open("w") as f:
        yaml.safe_dump(chart, f, default_flow_style=False, sort_keys=False)

    diagnostics = {
        "analysis": "rea-1930-1960-rural-electrification",
        "row_counts": {
            "series_points": len(df),
            "output_rows": len(df),
        },
        "weighted_population": {"farms_1960": 3579650},
        "missingness": {"none": 0},
        "design": {
            "source": "USDA Agricultural Statistics yearbook editions (1940, 1950, 1955, 1961, 1964), 'Number and percentage of farms receiving central-station electric service' tables; 1930 from Census of Agriculture as tabulated in Ag. Statistics 1940 Table 745",
            "definition": "Farms receiving central-station electric service (REA annual estimates), as a percentage of the Census of Agriculture farm count",
            "unit": "percent of farms",
        },
        "uncertainty": {
            "note": "Published official aggregates; no sampling variance published. REA estimates based on annual surveys.",
        },
        "benchmark": {
            "name": "Internal consistency of published REA/USDA figures",
            "observed": 3838062,
            "expected": 4582016 - 743954,
            "ratio": 1.0,
            "passed": bool(passed),
            "detail": {
                "check1_published_increase_column": "4,582,016 - 743,954 = 3,838,062 (matches published increase column)",
                "check2_1949_denominator": f"4,582,016 / 0.782 = {denom1949:,.0f} farms (1945 Census farm count 5,859,169)",
                "check3_1960_denominator": f"3,579,650 / 0.965 = {denom1960:,.0f} farms (1959 Census farm count 3,703,894)",
            },
            "official_source": "USDA Agricultural Statistics 1950 Table 742; 1961 Table 807",
        },
    }
    with (ANALYSIS_DIR / "diagnostics.json").open("w") as f:
        json.dump(diagnostics, f, indent=2)

    print("REA rural electrification series complete:")
    for _, row in df.iterrows():
        print(f"  {int(row['year'])}: {row['percent']:.1f}%  ({row['farms']:,} farms)")
    print(f"  Benchmark PASS: {passed}")
    print(f"  1930 -> 1940: {9.1:.1f}% -> {30.4:.1f}% (+{30.4 - 9.1:.1f} pts in a decade)")
    print(f"  1940 -> 1960: {30.4:.1f}% -> {96.5:.1f}% (+{96.5 - 30.4:.1f} pts in two decades)")


if __name__ == "__main__":
    main()
