"""AHS 2023 severe housing-cost burden by poverty band and rental assistance."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ANALYSIS_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(
    os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab")
)
EXPECTED_RELEASE = "ahs-2023-cd440e383936"
EXPECTED_SHA256 = "cd440e383936eaaa0435fc63be15caae2e95b6f29aadf0a88d6e147dd3ebfee6"
REPLICATE_COUNT = 160
VARIANCE_FACTOR = 4 / REPLICATE_COUNT

GROUP_MAP = {
    "1": "Public housing",
    "2": "Voucher",
    "3": "Voucher",
    "4": "Other government assistance",
    "5": "Other government assistance",
    "8": "No assistance",
}
ALL_DISPLAY_GROUPS = ["Public housing", "Voucher", "No assistance"]
PUBLICATION_GROUPS = ["Public housing", "No assistance"]
BAND_LABELS = ["≤50%", "51–100%", "101–150%", "151–200%"]


def normalize_code(series: pd.Series) -> pd.Series:
    """Remove literal quote marks preserved from the official AHS CSV."""
    return series.astype("string").str.strip("'")


def replicate_share(part: pd.DataFrame, outcome: str) -> tuple[float, float, float, float]:
    weights = part["WEIGHT"].to_numpy(dtype=float)
    values = part[outcome].to_numpy(dtype=float)
    estimate = float(np.average(values, weights=weights))
    replicates = []
    for index in range(1, REPLICATE_COUNT + 1):
        replicate_weights = part[f"REPWEIGHT{index}"].to_numpy(dtype=float)
        replicates.append(float(np.average(values, weights=replicate_weights)))
    standard_error = math.sqrt(
        VARIANCE_FACTOR * float(np.square(np.asarray(replicates) - estimate).sum())
    )
    return (
        estimate,
        standard_error,
        max(0.0, estimate - 1.96 * standard_error),
        min(1.0, estimate + 1.96 * standard_error),
    )


def main() -> None:
    pointer = json.loads((DATA_ROOT / "current" / "ahs.json").read_text())
    if pointer["release_id"] != EXPECTED_RELEASE or pointer["release_sha256"] != EXPECTED_SHA256:
        raise RuntimeError(
            "Current AHS release does not match the contracted 2023 release: "
            f"{pointer['release_id']} ({pointer['release_sha256']})"
        )

    release_path = Path(pointer["release_path"])
    household_path = release_path / "normalized" / "household.parquet"
    replicate_columns = [f"REPWEIGHT{index}" for index in range(1, REPLICATE_COUNT + 1)]
    columns = [
        "INTSTATUS",
        "TENURE",
        "RENTSUB",
        "HINCP",
        "PERPOVLVL",
        "TOTHCAMT",
        "WEIGHT",
        *replicate_columns,
    ]
    frame = pd.read_parquet(household_path, columns=columns)
    raw_rows = len(frame)

    for column in ("INTSTATUS", "TENURE", "RENTSUB"):
        frame[column] = normalize_code(frame[column])
    for column in ("HINCP", "PERPOVLVL", "TOTHCAMT", "WEIGHT", *replicate_columns):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # Official occupied-unit benchmark, reproduced before filtering the analysis universe.
    occupied = frame["INTSTATUS"] == "1"
    benchmark_estimate_thousands = float(frame.loc[occupied, "WEIGHT"].sum() / 1000)
    benchmark_replicates = np.asarray(
        [float(frame.loc[occupied, column].sum() / 1000) for column in replicate_columns]
    )
    benchmark_se_thousands = math.sqrt(
        VARIANCE_FACTOR
        * float(np.square(benchmark_replicates - benchmark_estimate_thousands).sum())
    )
    benchmark_moe90_thousands = 1.6448536269514722 * benchmark_se_thousands
    benchmark_passed = (
        abs(benchmark_estimate_thousands - 133231.0) <= 0.5
        and abs(benchmark_moe90_thousands - 381.0) <= 0.5
    )
    if not benchmark_passed:
        raise RuntimeError("AHS occupied-unit benchmark failed")

    renter_rows = (frame["INTSTATUS"] == "1") & (frame["TENURE"] == "2")
    invalid_income = int((renter_rows & (frame["HINCP"] <= 0)).sum())
    invalid_assistance = int((renter_rows & ~frame["RENTSUB"].isin(GROUP_MAP)).sum())

    analysis = frame[
        renter_rows
        & (frame["HINCP"] > 0)
        & frame["PERPOVLVL"].between(2, 200, inclusive="both")
        & (frame["TOTHCAMT"] >= 0)
        & (frame["WEIGHT"] > 0)
        & frame["RENTSUB"].isin(GROUP_MAP)
    ].copy()
    if analysis.empty:
        raise RuntimeError("AHS analysis universe is empty")
    if not np.isfinite(analysis[["WEIGHT", *replicate_columns]].to_numpy(dtype=float)).all():
        raise RuntimeError("AHS analysis weights contain missing or non-finite values")
    if (analysis[["WEIGHT", *replicate_columns]] <= 0).any().any():
        raise RuntimeError("AHS analysis weights must be positive")

    analysis["group"] = analysis["RENTSUB"].map(GROUP_MAP)
    analysis["housing_burden"] = 12 * analysis["TOTHCAMT"] / analysis["HINCP"]
    analysis["severe_burden"] = analysis["housing_burden"] > 0.5
    analysis["poverty_band"] = pd.cut(
        analysis["PERPOVLVL"],
        bins=[1, 50, 100, 150, 200],
        labels=BAND_LABELS,
        include_lowest=True,
    )

    rows: list[dict[str, object]] = []
    all_group_rows: list[dict[str, object]] = []
    for (band, group), part in analysis.groupby(["poverty_band", "group"], observed=True):
        estimate, standard_error, ci_low, ci_high = replicate_share(part, "severe_burden")
        row = {
            "poverty_band": str(band),
            "group": str(group),
            "estimate": estimate,
            "standard_error": standard_error,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "unweighted_households": len(part),
            "weighted_households": float(part["WEIGHT"].sum()),
        }
        all_group_rows.append(row)
        if group in ALL_DISPLAY_GROUPS:
            rows.append(row)

    all_groups_output = pd.DataFrame(rows)
    all_groups_output["poverty_band"] = pd.Categorical(
        all_groups_output["poverty_band"], categories=BAND_LABELS, ordered=True
    )
    all_groups_output["group"] = pd.Categorical(
        all_groups_output["group"], categories=ALL_DISPLAY_GROUPS, ordered=True
    )
    all_groups_output = all_groups_output.sort_values(["poverty_band", "group"])
    all_groups_output.to_csv(ANALYSIS_DIR / "all-groups.csv", index=False)
    output = all_groups_output[all_groups_output["group"].isin(PUBLICATION_GROUPS)].copy()
    output["group"] = output["group"].cat.remove_unused_categories()
    output.to_csv(ANALYSIS_DIR / "data.csv", index=False)

    diagnostics = {
        "analysis": ANALYSIS_DIR.name,
        "release_id": pointer["release_id"],
        "release_sha256": pointer["release_sha256"],
        "row_counts": {
            "raw_household_rows": raw_rows,
            "occupied_renter_rows": int(renter_rows.sum()),
            "analysis_rows_all_classified_groups": len(analysis),
            "all_display_group_rows": len(all_groups_output),
            "publication_rows": len(output),
            "nonpositive_income_renter_rows": invalid_income,
            "unclassified_assistance_renter_rows": invalid_assistance,
        },
        "weighted_population": {
            "analysis_households_all_classified_groups": float(analysis["WEIGHT"].sum()),
            "publication_groups": {
                group: float(analysis.loc[analysis["group"] == group, "WEIGHT"].sum())
                for group in ALL_DISPLAY_GROUPS
            },
        },
        "missingness": {
            column: int(frame[column].isna().sum())
            for column in ("HINCP", "PERPOVLVL", "TOTHCAMT", "WEIGHT")
        },
        "design": {
            "record_unit": "occupied AHS housing unit / household",
            "weight": "WEIGHT",
            "replicate_weights": "REPWEIGHT1-REPWEIGHT160",
            "variance_factor": VARIANCE_FACTOR,
            "replicate_method": "4/160 times sum of squared replicate deviations",
        },
        "uncertainty": {
            "method": "AHS replicate-weight variance; normal 95% confidence intervals",
            "chart_policy": "point estimates only; intervals retained in data.csv",
        },
        "benchmark": {
            "name": "2023 AHS occupied housing units",
            "observed": benchmark_estimate_thousands,
            "expected": 133231.0,
            "observed_estimate_thousands": benchmark_estimate_thousands,
            "expected_estimate_thousands": 133231.0,
            "observed_moe90_thousands": benchmark_moe90_thousands,
            "expected_moe90_thousands": 381.0,
            "passed": benchmark_passed,
            "official_source": "2023 AHS National PUF verification benchmark",
        },
        "classification": {
            "source_variable": "RENTSUB",
            "public_housing": ["1"],
            "voucher": ["2", "3"],
            "other_government_assistance": ["4", "5"],
            "no_assistance": ["8"],
            "all_group_estimates": all_group_rows,
        },
        "limitations": [
            "Cross-sectional descriptive associations; not causal treatment effects.",
            "RENTSUB is respondent-reported and derived from multiple interview items.",
            "TOTHCAMT includes rent, utilities, and other housing costs.",
            "Nonpositive-income households are excluded from burden ratios.",
            "PERPOVLVL is rounded in the released file.",
        ],
    }
    (ANALYSIS_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2))

    chart = {
        "chart_type": "dumbbell",
        "theme": "editorial",
        "eyebrow": "housing · AHS 2023",
        "title": "Public housing is associated with far less severe housing burden",
        "subtitle": "Share spending more than half of income on total housing costs, renters with positive income at or below 200% of poverty",
        "source": "U.S. Census Bureau and HUD, 2023 American Housing Survey National PUF",
        "note": "Public housing status uses respondent-reported AHS RENTSUB; voucher estimates are retained in all-groups.csv. Weighted with WEIGHT; 160 replicate weights used for uncertainty. Descriptive, not causal. Point estimates shown; confidence intervals are in the fallback table.",
        "x": "poverty_band",
        "y": "estimate",
        "series": "group",
        "series_order": PUBLICATION_GROUPS,
        "color_map": {"Public housing": "#0B7A75", "No assistance": "#D1495B"},
        "x_label": "Households spending more than half of income on housing",
        "value_format": "percent",
        "y_min": 0,
        "y_max": 1,
        "width": 1800,
        "height": 1200,
    }
    (ANALYSIS_DIR / "chart.yaml").write_text(yaml.safe_dump(chart, sort_keys=False))

    print(
        "AHS severe burden: "
        f"rows={len(analysis)}; benchmark={benchmark_estimate_thousands:.3f}k; "
        f"MOE90={benchmark_moe90_thousands:.3f}k"
    )


if __name__ == "__main__":
    main()
