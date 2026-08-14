"""US health expenditure by financing scheme, 1970-2023 (article figure 5).

Replicates "sha_financing-1.png" from OECD System of Health Accounts
(DSD_SHA@DF_SHA): current health expenditure as percent of GDP by financing
scheme. The article's bands:
  - Government programs        = HF11 (government schemes) + HF121/HF122?
  - Compulsory private         = HF121/HF122 (compulsory private insurance)
  - Voluntary private          = HF2 (voluntary health care payment schemes)
  - Out-of-pocket              = HF3 (household out-of-pocket)

NOTE: The OECD SHA codelist has HF1 (government + compulsory), HF11
(government), HF121/HF122 (compulsory private), HF2 (voluntary), HF3
(out-of-pocket). The article plots four bands. We follow the OECD taxonomy:
HF11 = government, HF121+HF122 = compulsory private, HF2 = voluntary
private, HF3 = out-of-pocket.
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


def load_sha() -> pd.DataFrame:
    import glob

    hits = sorted(
        glob.glob(
            str(
                LAKE
                / "releases"
                / "oecd_sha"
                / "2023"
                / "*"
                / "normalized"
                / "sha_financing.parquet"
            )
        )
    )
    if not hits:
        raise FileNotFoundError("No oecd_sha release found; sync first")
    return pd.read_parquet(hits[-1])


SCHEME_LABELS = {
    "HF11": "Government programs",
    "HF121": "Government programs",
    "HF122": "Compulsory private",
    "HF2": "Voluntary private",
    "HF3": "Out-of-pocket",
}


def main() -> None:
    df = load_sha()

    # Filter to USA, EXP_HEALTH, % of GDP, financing schemes of interest.
    # Band mapping per OECD SHA taxonomy:
    #   government programs = HF11 (government) + HF121 (social insurance)
    #   compulsory private  = HF122 (compulsory private insurance, i.e. ESI
    #                         treated as compulsory after the ACA)
    #   voluntary private   = HF2
    #   out-of-pocket       = HF3
    schemes = ["HF11", "HF121", "HF122", "HF2", "HF3"]
    sub = df[
        (df["REF_AREA"] == "USA")
        & (df["MEASURE"] == "EXP_HEALTH")
        & (df["UNIT_MEASURE"] == "PT_B1GQ")
        & (df["FINANCING_SCHEME"].isin(schemes))
        & (df["TIME_PERIOD"].astype(int) <= 2023)
    ].copy()

    sub["year"] = pd.to_numeric(sub["TIME_PERIOD"], errors="coerce")
    sub["label"] = sub["FINANCING_SCHEME"].map(SCHEME_LABELS)

    # Combine HF121+HF122 into the "Compulsory private" band
    grouped = sub.groupby(["year", "label"], as_index=False)["value"].sum()
    # Encode the article's band order (bottom to top) so both renderers
    # stack deterministically: Out-of-pocket, Voluntary, Compulsory, Government.
    grouped["label"] = pd.Categorical(
        grouped["label"],
        categories=[
            "Out-of-pocket",
            "Voluntary private",
            "Compulsory private",
            "Government programs",
        ],
        ordered=True,
    )
    grouped = grouped.sort_values(["year", "label"])  # type: ignore[assignment]
    grouped.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    # Benchmark: total health expenditure % of GDP 2023 (sum of all bands)
    total_2023 = grouped[grouped["year"] == 2023]["value"].sum()
    diagnostics = {
        "analysis": ANALYSIS_DIR.name,
        "release_id": "oecd_sha-2023-60b53ef2dd00",
        "row_counts": {
            "output_rows": len(grouped),
            "years": grouped["year"].nunique(),
            "bands": grouped["label"].nunique(),
        },
        "weighted_population": {"note": "macrodata; no survey weight"},
        "missingness": {"value": int(grouped["value"].isna().sum())},
        "design": {"type": "macrodata", "weight": "none", "replicate_weights": "none"},
        "uncertainty": {"note": "no sampling variance; official national accounts"},
        "benchmark": {
            "name": "USA total health expenditure % of GDP 2023 (sum of scheme bands)",
            "observed": total_2023,
            "expected": 17.2,
            "tolerance": 1.0,
            "passed": bool(abs(total_2023 - 17.2) <= 1.0),
            "official_source": "OECD System of Health Accounts (DSD_SHA@DF_SHA)",
        },
    }
    (ANALYSIS_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2))

    chart = {
        "chart_type": "area",
        "title": "Government and compulsory sources finance most U.S. health spending (1970–2023)",
        "subtitle": "Share of current health expenditure by financing scheme, United States, 1970–2023",
        "source": "OECD, System of Health Accounts",
        "note": "Bands: government programs (HF11 + HF121 social insurance), compulsory private (HF122, ESI reclassified as compulsory after the ACA), voluntary private (HF2), out-of-pocket (HF3).",
        "x": "year",
        "y": "value",
        "series": "label",
        "x_label": "Year",
        "y_label": "Percent of GDP",
        "x_ticks": [1970, 1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020],
        "y_ticks": [0, 5, 10, 15, 20],
        "y_min": 0,
        "y_max": 20,
        "tick_suffix": "%",
        "x_tick_suffix": "",
        "vline": [
            {
                "x": 2014,
                "label": "ACA employer mandate (2014)",
                "label_y": 18,
                "hjust": 1,
            }
        ],
        "value_format": "number",
        "theme": "swiss",
        "eyebrow": "health financing · 1970–2023",
        "width": 2200,
        "height": 1400,
    }
    (ANALYSIS_DIR / "chart.yaml").write_text(yaml.safe_dump(chart, sort_keys=False))

    print(f"SHA: {len(grouped)} rows, total 2023 = {total_2023:.2f}% of GDP")


if __name__ == "__main__":
    main()
