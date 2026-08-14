from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyreadstat


def validate_scf_files(
    summary_csv: Path,
    replicate_weights_dta: Path,
    full_data_dta: Path,
    *,
    year: int | None = None,
) -> tuple[dict[str, bool], list[str]]:
    """Validate structural properties required for valid SCF inference."""
    checks: dict[str, bool] = {}
    notes: list[str] = []

    summary = pd.read_csv(
        summary_csv,
        usecols=lambda name: name in {"YY1", "Y1", "WGT", "NETWORTH", "CCBAL"},
    )
    required = {"YY1", "Y1", "WGT", "NETWORTH", "CCBAL"}
    checks["scf_summary_required_columns"] = required.issubset(summary.columns)
    if not checks["scf_summary_required_columns"]:
        notes.append("SCF summary extract is missing identifiers, weights, or core test variables")
        return checks, notes

    implicates = summary["Y1"].astype("int64") % 10
    family_counts = summary.groupby("YY1", sort=False).size()
    checks["scf_exactly_five_implicates"] = set(implicates.unique()) == {
        1,
        2,
        3,
        4,
        5,
    } and bool((family_counts == 5).all())
    checks["scf_positive_main_weights"] = bool((summary["WGT"] > 0).all())
    checks["scf_summary_row_count_consistent"] = len(summary) == len(family_counts) * 5

    if year == 2022:
        medians: list[float] = []
        for implicate in range(1, 6):
            group = summary.loc[implicates == implicate].sort_values(
                ["NETWORTH", "YY1"], kind="mergesort"
            )
            cutoff = group["WGT"].sum() / 2
            medians.append(float(group.loc[group["WGT"].cumsum() >= cutoff, "NETWORTH"].iloc[0]))
        reproduced = sum(medians) / len(medians)
        official = 192_900.0
        relative_error = abs(reproduced - official) / official
        checks["scf_official_median_net_worth_within_one_percent"] = relative_error <= 0.01
        notes.append(
            f"2022 median net worth benchmark: ${reproduced:,.0f} reproduced "
            f"versus ${official:,.0f} official ({relative_error:.2%} relative error)"
        )

    _, replicate_meta = pyreadstat.read_dta(replicate_weights_dta, metadataonly=True)
    replicate_names = set(replicate_meta.column_names)
    expected_weights = {f"wt1b{index}" for index in range(1, 1000)}
    expected_multiplicities = {f"mm{index}" for index in range(1, 1000)}
    checks["scf_999_replicate_weights"] = expected_weights.issubset(replicate_names)
    checks["scf_999_multiplicity_factors"] = expected_multiplicities.issubset(replicate_names)
    checks["scf_replicate_family_count_matches"] = replicate_meta.number_rows == len(family_counts)

    _, full_meta = pyreadstat.read_dta(full_data_dta, metadataonly=True)
    checks["scf_full_data_row_count_matches"] = full_meta.number_rows == len(summary)

    for name, passed in checks.items():
        if not passed:
            notes.append(f"SCF validation failed: {name}")
    return checks, notes
