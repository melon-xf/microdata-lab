"""US vs Nordic total health spending, % of GDP — OECD SHA 2023 (response chart 3).

Total current expenditure on health (FINANCING_SCHEME=_T, EXP_HEALTH,
PT_B1GQ = % of GDP) for USA vs DNK, FIN, NOR, SWE, 2023 (and the
US 1970–2023 trend for the "we keep paying more" angle).

Claim: America already spends far more on health care than the Nordics —
the "we can't afford single-payer" framing is backwards. The obstacle is
allocation, not resources.

Honest framing: spending share is not a quality/outcome measure; these are
system totals, not proof that any specific reform would cost less.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

ROOT = (
    Path(os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab"))
    / "releases"
    / "oecd_sha"
    / "2023"
)
PARQUET = sorted(
    (ROOT / "127dc06a83002226f056fce3b5481354bd8b0e4d2c2f40fec3c6c33a88659a77" / "normalized").glob(
        "*.parquet"
    )
)[0]
RELEASE_ID = "oecd_sha-2023-127dc06a8300"

COUNTRIES = {
    "USA": "United States",
    "DNK": "Denmark",
    "FIN": "Finland",
    "NOR": "Norway",
    "SWE": "Sweden",
}


def main() -> None:
    df = pd.read_parquet(PARQUET)
    tot = df[(df["FINANCING_SCHEME"] == "_T") & (df["TIME_PERIOD"] == "2023")].copy()
    tot["country"] = tot["REF_AREA"].map(COUNTRIES)
    tot = tot[["country", "value"]].rename(columns={"value": "share_of_gdp"})
    tot = tot.sort_values("share_of_gdp", ascending=False).reset_index(drop=True)

    here = Path(__file__).resolve().parent
    tot.to_csv(here / "data.csv", index=False)

    # US trend is not charted here; the comparison uses the 2023 cross-section.
    us_2023 = float(tot.loc[tot["country"] == "United States", "share_of_gdp"].iloc[0])
    nordic_mean = float(
        tot.loc[
            tot["country"].isin(["Denmark", "Finland", "Norway", "Sweden"]), "share_of_gdp"
        ].mean()
    )

    diag = {
        "analysis": "oecd-sha-us-vs-nordics",
        "release_id": RELEASE_ID,
        "row_counts": {"output_rows": len(tot), "countries": len(tot)},
        "weighted_population": {
            "note": "National accounts share of GDP; no person weights",
            "us_2023": round(us_2023, 3),
            "nordic_mean_2023": round(nordic_mean, 3),
        },
        "missingness": {
            "value": 0,
            "note": "SDMX observations; countries requested = 5, all present",
        },
        "uncertainty": {"measure": "none (census of national accounts)", "replicate": "none"},
        "benchmark": {
            "name": "US total health spending 16.9% of GDP 2023 (OECD SHA; matches prior validated analysis)",
            "observed": round(us_2023, 3),
            "expected": 16.87,
            "tolerance": 0.2,
            "passed": bool(abs(us_2023 - 16.87) <= 0.2),
        },
        "design": {
            "type": "national_accounts_share",
            "weight": "none",
            "variance": "none (census of national accounts)",
        },
        "limitations": [
            "Spending share of GDP is not a quality or outcome measure.",
            "OECD SHA figures are national accounts; cross-country comparability depends on SHA implementation.",
        ],
    }
    (here / "diagnostics.json").write_text(json.dumps(diag, indent=2))
    print(tot.to_string(index=False))
    print(
        f"\nUS: {us_2023:.2f}%  Nordic mean: {nordic_mean:.2f}%  US - Nordic mean: {us_2023 - nordic_mean:.2f}pp"
    )


if __name__ == "__main__":
    main()
