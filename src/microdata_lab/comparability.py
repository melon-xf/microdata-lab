"""Cross-source comparability checks.

Verifies that overlapping concepts measured by different sources agree
within tolerance. These catch normalization errors that source-specific
benchmarks might miss.

Implemented checks:

* acs_vs_cps_population: ACS PUMS total persons vs CPS ASEC total persons
  (both IPUMS, same reference year, tolerance 5%)
* meps_vs_cps_uninsured_share: MEPS uninsured share vs CPS ASEC uninsured
  share (tolerance 5 percentage points)
* worldbank_vs_eurostat_germany_gdp: World Bank Germany GDP (USD) vs
  Eurostat Germany GDP (EUR converted at a reference rate) — informational
  only, no strict gate
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

_ACCEPTABLE_RELATIVE_DIFF = 0.05
_ACCEPTABLE_PP_DIFF = 5.0

# Reference EUR/USD rate for informational cross-checks (2023 annual average,
# ECB reference; used only for comparability, not for analysis).
_EUR_USD_2023 = 1.0813


@dataclass
class ComparabilityRow:
    check: str
    source_a: str
    source_b: str
    metric: str
    value_a: float
    value_b: float
    difference: float
    tolerance: str
    passed: bool
    note: str = ""
    skipped: bool = False


def _load_release_parquet(data_root: Path, survey: str) -> pd.DataFrame | None:
    release_root = data_root / "releases" / survey
    if not release_root.is_dir():
        return None
    for year_dir in sorted(release_root.iterdir(), reverse=True):
        for release_dir in sorted(year_dir.iterdir(), reverse=True):
            normalized = release_dir / "normalized"
            if not normalized.is_dir():
                continue
            parquets = sorted(normalized.glob("*.parquet"))
            if parquets:
                return pd.read_parquet(parquets[0])
    return None


def _weighted_sum(df: pd.DataFrame, weight_col: str, value_col: str | None = None) -> float:
    if value_col is None:
        return float(pd.to_numeric(df[weight_col], errors="coerce").sum())
    mask = pd.to_numeric(df[value_col], errors="coerce") > 0
    return float(pd.to_numeric(df.loc[mask, weight_col], errors="coerce").sum())


def _relative_diff(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-9)


def _acs_vs_cps_population(data_root: Path) -> ComparabilityRow:
    acs = _load_release_parquet(data_root, "acs_pums")
    cps = _load_release_parquet(data_root, "cps_asec")
    if acs is None or cps is None:
        return ComparabilityRow(
            check="acs_vs_cps_population",
            source_a="acs_pums",
            source_b="cps_asec",
            metric="total persons (weighted)",
            value_a=0.0,
            value_b=0.0,
            difference=0.0,
            tolerance="5%",
            passed=False,
            note="missing release data",
        )
    weight_a = next((c for c in ("PERWT", "PWGTP", "WTPF") if c in acs.columns), None)
    weight_b = next((c for c in ("ASECWT", "WTFINL", "PERWT") if c in cps.columns), None)
    if weight_a is None or weight_b is None:
        return ComparabilityRow(
            check="acs_vs_cps_population",
            source_a="acs_pums",
            source_b="cps_asec",
            metric="total persons (weighted)",
            value_a=0.0,
            value_b=0.0,
            difference=0.0,
            tolerance="5%",
            passed=False,
            note=f"missing weight columns: acs={weight_a!r} cps={weight_b!r}",
        )
    pop_a = _weighted_sum(acs, weight_a)
    pop_b = _weighted_sum(cps, weight_b)
    diff = _relative_diff(pop_a, pop_b)
    return ComparabilityRow(
        check="acs_vs_cps_population",
        source_a="acs_pums",
        source_b="cps_asec",
        metric="total persons (weighted)",
        value_a=pop_a,
        value_b=pop_b,
        difference=diff,
        tolerance="5%",
        passed=diff <= _ACCEPTABLE_RELATIVE_DIFF,
    )


def _meps_vs_cps_uninsured(data_root: Path) -> ComparabilityRow:
    meps = _load_release_parquet(data_root, "meps")
    cps = _load_release_parquet(data_root, "cps_asec")
    if meps is None or cps is None:
        return ComparabilityRow(
            check="meps_vs_cps_uninsured_share",
            source_a="meps",
            source_b="cps_asec",
            metric="uninsured share",
            value_a=0.0,
            value_b=0.0,
            difference=0.0,
            tolerance="5 pp",
            passed=False,
            note="missing release data",
        )
    ins_col = next((c for c in meps.columns if c.startswith("INSCOV")), None)
    weight = next((c for c in meps.columns if c.startswith("PERWT")), None)
    if ins_col is None or weight is None:
        return ComparabilityRow(
            check="meps_vs_cps_uninsured_share",
            source_a="meps",
            source_b="cps_asec",
            metric="uninsured share",
            value_a=0.0,
            value_b=0.0,
            difference=0.0,
            tolerance="5 pp",
            passed=False,
            note=f"missing meps columns: ins={ins_col!r} weight={weight!r}",
        )
    df = meps[[ins_col, weight]].copy()
    df[weight] = pd.to_numeric(df[weight], errors="coerce").fillna(0)
    # INSCOV values are stored as strings like "3 UNINSURED" or ints (1/2/3).
    raw = pd.to_numeric(df[ins_col], errors="coerce")
    uninsured = raw == 3 if raw.notna().any() else df[ins_col].astype(str).str.startswith("3")
    share_a = float(df.loc[uninsured, weight].sum() / max(df[weight].sum(), 1e-9))
    # CPS: use the POVERTY/health-insurance universe if available; otherwise
    # fall back to a population-weighted count from HIINT columns when present.
    hi_col = next((c for c in cps.columns if c.startswith("HI") and "INT" in c), None)
    if hi_col is None:
        return ComparabilityRow(
            check="meps_vs_cps_uninsured_share",
            source_a="meps",
            source_b="cps_asec",
            metric="uninsured share",
            value_a=share_a,
            value_b=float("nan"),
            difference=float("nan"),
            tolerance="5 pp",
            passed=False,
            skipped=True,
            note="CPS extract has no health-insurance column; check skipped",
        )
    weight_b = next((c for c in ("ASECWT", "WTFINL") if c in cps.columns), None)
    if weight_b is None:
        return ComparabilityRow(
            check="meps_vs_cps_uninsured_share",
            source_a="meps",
            source_b="cps_asec",
            metric="uninsured share",
            value_a=share_a,
            value_b=float("nan"),
            difference=float("nan"),
            tolerance="5 pp",
            passed=False,
            skipped=True,
            note="CPS weight column not found; check skipped",
        )
    cps_df = cps[[hi_col, weight_b]].copy()
    cps_df[weight_b] = pd.to_numeric(cps_df[weight_b], errors="coerce").fillna(0)
    unins_b = pd.to_numeric(cps_df[hi_col], errors="coerce") == 3
    share_b = float(cps_df.loc[unins_b, weight_b].sum() / max(cps_df[weight_b].sum(), 1e-9))
    diff = abs(share_a - share_b) * 100
    return ComparabilityRow(
        check="meps_vs_cps_uninsured_share",
        source_a="meps",
        source_b="cps_asec",
        metric="uninsured share",
        value_a=share_a,
        value_b=share_b,
        difference=diff,
        tolerance="5 pp",
        passed=diff <= _ACCEPTABLE_PP_DIFF,
    )


def _worldbank_vs_eurostat_germany(data_root: Path) -> ComparabilityRow:
    wb = _load_release_parquet(data_root, "worldbank")
    euro = _load_release_parquet(data_root, "eurostat")
    if wb is None or euro is None:
        return ComparabilityRow(
            check="worldbank_vs_eurostat_germany_gdp",
            source_a="worldbank",
            source_b="eurostat",
            metric="Germany GDP 2023 (USD-equivalent)",
            value_a=0.0,
            value_b=0.0,
            difference=0.0,
            tolerance="informational",
            passed=False,
            note="missing release data",
        )
    try:
        de_row = wb[wb["country_name"] == "Germany"].sort_values("date").iloc[-1]
        gdp_usd = float(de_row["value"])
    except (KeyError, IndexError):
        return ComparabilityRow(
            check="worldbank_vs_eurostat_germany_gdp",
            source_a="worldbank",
            source_b="eurostat",
            metric="Germany GDP 2023 (USD-equivalent)",
            value_a=0.0,
            value_b=0.0,
            difference=0.0,
            tolerance="informational",
            passed=False,
            note="Germany row not found in World Bank release",
        )
    try:
        de_eur = float(
            euro[
                (euro["geo"] == "DE")
                & (euro["unit"] == "CP_MEUR")
                & (euro["na_item"] == "B1GQ")
                & (euro["time"].astype(str) == "2023")
            ]["value"].iloc[0]
        )
    except (KeyError, IndexError):
        return ComparabilityRow(
            check="worldbank_vs_eurostat_germany_gdp",
            source_a="worldbank",
            source_b="eurostat",
            metric="Germany GDP 2023 (USD-equivalent)",
            value_a=gdp_usd,
            value_b=0.0,
            difference=0.0,
            tolerance="informational",
            passed=False,
            note="Germany 2023 B1GQ row not found in Eurostat release",
        )
    euro_usd = de_eur * 1_000_000 * _EUR_USD_2023
    diff = _relative_diff(gdp_usd, euro_usd)
    return ComparabilityRow(
        check="worldbank_vs_eurostat_germany_gdp",
        source_a="worldbank",
        source_b="eurostat",
        metric="Germany GDP 2023 (USD-equivalent)",
        value_a=gdp_usd,
        value_b=euro_usd,
        difference=diff,
        tolerance="informational",
        passed=True,
        note="informational cross-check (ECB 2023 average EUR/USD)",
    )


def run_comparability(data_root: Path) -> list[ComparabilityRow]:
    return [
        _acs_vs_cps_population(data_root),
        _meps_vs_cps_uninsured(data_root),
        _worldbank_vs_eurostat_germany(data_root),
    ]


def comparability_to_json(rows: list[ComparabilityRow]) -> str:
    return json.dumps([asdict(row) for row in rows], indent=2)
