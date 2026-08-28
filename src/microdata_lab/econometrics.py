"""Econometric estimators with survey-weight correctness and proper inference.

Conventions follow AGENTS.md "Statistical correctness":

* Survey weights are mandatory — every descriptive statistic here takes
  explicit weights and validates them.
* Replicate weights drive standard errors when the design supports them; the
  jackknife helpers implement the JK1/JKn delete-1 and Fay balanced repeated
  replication (BRR) variance estimators used by survey replicate designs.
* SCF publishable inference requires all five implicates plus the supplied
  replicate design; the replicate SE helpers are the per-implicate building
  blocks for that workflow.
* Standard errors and confidence intervals are reported whenever the design
  supports them; the OLS wrapper emits coef/se/CI/t/p per regressor in
  JSON-serializable form for diagnostics.json benchmark fields.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
import statsmodels.api as sm  # type: ignore[import-untyped]
from scipy import stats  # type: ignore[import-untyped]

WeightType = Literal["reliability", "frequency"]


@dataclass
class ReplicateSE:
    """Standard error of a point estimate from replicate estimates."""

    estimate: float
    se: float
    variance: float
    replicates: int
    method: str
    fay_rho: float = 0.0

    def as_dict(self) -> dict[str, float | int | str]:
        """Return a JSON-serializable mapping for diagnostics.json."""
        return asdict(self)


def _as_arrays(
    values: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
    weights: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    x = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if x.shape != w.shape:
        raise ValueError(
            f"values and weights must have the same shape, got {x.shape} and {w.shape}"
        )
    if x.size == 0:
        raise ValueError("values must be non-empty")
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(w))):
        raise ValueError("values and weights must be finite")
    if np.any(w < 0):
        raise ValueError("weights must be non-negative")
    if float(w.sum()) <= 0:
        raise ValueError("weights must have a positive total")
    return x, w


def weighted_mean(
    values: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
    weights: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
) -> float:
    """Weighted arithmetic mean: sum(w_i * x_i) / sum(w_i).

    Weights are mandatory and must be non-negative with a positive total.
    """
    x, w = _as_arrays(values, weights)
    return float(np.dot(x, w) / w.sum())


def weighted_quantile(
    values: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
    weights: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
    q: float,
) -> float:
    """Weighted quantile under the sorted cumulative-weight midpoint convention.

    Sort observations by value (zero-weight records are excluded), then place
    each observation at the midpoint of its own cumulative-weight interval:

        p_i = (cumsum(w)_i - w_i / 2) / sum(w)

    and linearly interpolate x_(i) against p_i, clamping to the observed
    extremes for q outside [p_1, p_n].

    Tie handling: tied values occupy adjacent, distinct p_i positions, but
    interpolation across a tied block returns the shared value exactly, so
    ties never average adjacent distinct values unless the interpolated point
    itself lies between two distinct values. With equal weights this reduces
    to the standard "inverted CDF with midpoint averaging" sample quantile.
    """
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q must lie in [0, 1], got {q}")
    x, w = _as_arrays(values, weights)
    keep = w > 0
    x = x[keep]
    w = w[keep]
    order = np.argsort(x, kind="stable")
    x = x[order]
    w = w[order]
    p = (np.cumsum(w) - 0.5 * w) / float(w.sum())
    return float(np.interp(q, p, x))


def weighted_variance(
    values: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
    weights: list[float] | tuple[float, ...] | npt.NDArray[np.float64] | pd.Series,
    *,
    weight_type: WeightType = "reliability",
) -> float:
    """Weighted sample variance, with the weight semantics made explicit.

    weight_type="reliability" (default): analytic/precision weights, the
    usual case for survey sampling weights. Uses the reliability-weight
    unbiased estimator

        V = sum(w_i (x_i - xbar_w)^2) / (V1 - V2 / V1),
        V1 = sum(w_i), V2 = sum(w_i^2)

    which reduces to the ddof=1 sample variance when all weights are 1.

    weight_type="frequency": each weight is an integer repeat count and

        V = sum(w_i (x_i - xbar_w)^2) / (V1 - 1)

    the Bessel-corrected variance of the expanded sample.

    The two disagree whenever weights are non-uniform; pick the one matching
    the survey documentation.
    """
    x, w = _as_arrays(values, weights)
    xbar = float(np.dot(x, w) / w.sum())
    numerator = float(np.dot(w, (x - xbar) ** 2))
    v1 = float(w.sum())
    if weight_type == "reliability":
        v2 = float(np.dot(w, w))
        denominator = v1 - v2 / v1
    elif weight_type == "frequency":
        denominator = v1 - 1.0
    else:
        raise ValueError(f"unknown weight_type: {weight_type!r}")
    if denominator <= 0:
        raise ValueError(
            f"non-positive variance denominator ({denominator}); "
            "the sample must carry weight on at least two distinct observations"
        )
    return numerator / denominator


def jackknife_se(
    full_estimate: float,
    replicate_estimates: list[float] | tuple[float, ...] | npt.NDArray[np.float64],
) -> ReplicateSE:
    """JK1/JKn delete-1 jackknife standard error from replicate estimates.

    Given the full-sample point estimate theta and m replicate estimates
    theta_(i) computed from delete-1 (or delete-group) replicate weights:

        Var(theta) = sum_i (theta_(i) - theta)^2 / (m * (m - 1))
        SE(theta)  = sqrt(Var(theta))

    This is the delete-1 jackknife variance estimator family (Wolter,
    "Introduction to Variance Estimation", 2nd ed., ch. 4); pass the
    estimates exactly as produced by the survey's replicate weights.
    """
    reps = np.asarray(replicate_estimates, dtype=np.float64)
    m = int(reps.size)
    if m < 2:
        raise ValueError(f"need at least 2 replicate estimates, got {m}")
    if not np.all(np.isfinite(reps)):
        raise ValueError("replicate estimates must be finite")
    theta = float(full_estimate)
    variance = float(np.sum((reps - theta) ** 2) / (m * (m - 1)))
    return ReplicateSE(
        estimate=theta,
        se=float(np.sqrt(variance)),
        variance=variance,
        replicates=m,
        method="jk1",
    )


def replicate_ci(result: ReplicateSE, *, level: float = 0.95) -> dict[str, float]:
    """t-based confidence interval around a replicate-weight point estimate.

    Uses the Student t quantile with m - 1 degrees of freedom (m = number of
    replicates), the usual finite-replicate reference distribution:

        CI = estimate +/- t_{level, m-1} * se

    Report alongside the SE whenever the replicate design supports it
    (AGENTS.md "Statistical correctness").
    """
    if not 0.0 < level < 1.0:
        raise ValueError(f"level must lie in (0, 1), got {level}")
    critical = float(stats.t.ppf(0.5 + level / 2.0, df=result.replicates - 1))
    half_width = critical * result.se
    return {
        "estimate": result.estimate,
        "se": result.se,
        "ci_lower": result.estimate - half_width,
        "ci_upper": result.estimate + half_width,
        "level": float(level),
    }


def fay_se(
    full_estimate: float,
    replicate_estimates: list[float] | tuple[float, ...] | npt.NDArray[np.float64],
    rho: float,
) -> ReplicateSE:
    """Fay balanced repeated replication (BRR) standard error.

    Fay's variant of BRR forms replicate weights by perturbing the full-sample
    weight toward/away from each half-sample by the perturbation factor rho in
    (0, 1). The variance estimator is

        Var(theta) = sum_i (theta_(i) - theta)^2 / (m * (1 - rho)^2)
        SE(theta)  = sqrt(Var(theta))

    Classical BRR is the special case rho = 0.5 (factor 4 / m); Fay's choice
    rho in (0, 0.5) improves stability for quantile statistics. Estimator
    family: Fay BRR (Judkins 1990; Wolter 2007, ch. 2/4).
    """
    if not 0.0 < rho < 1.0:
        raise ValueError(f"fay perturbation factor rho must lie in (0, 1), got {rho}")
    reps = np.asarray(replicate_estimates, dtype=np.float64)
    m = int(reps.size)
    if m < 2:
        raise ValueError(f"need at least 2 replicate estimates, got {m}")
    if not np.all(np.isfinite(reps)):
        raise ValueError("replicate estimates must be finite")
    theta = float(full_estimate)
    variance = float(np.sum((reps - theta) ** 2) / (m * (1.0 - rho) ** 2))
    return ReplicateSE(
        estimate=theta,
        se=float(np.sqrt(variance)),
        variance=variance,
        replicates=m,
        method="fay-brr",
        fay_rho=float(rho),
    )


def did_2x2(
    df: pd.DataFrame,
    *,
    unit: str = "unit",
    time: str = "time",
    treated: str = "treated",
    post: str = "post",
    outcome: str = "outcome",
) -> dict[str, float | int]:
    """Two-group/two-period difference-in-differences from group means.

    The panel must be tidy: one row per (unit, time) with boolean/0-1
    `treated` and `post` indicators. The estimand is

        DID = (ybar_T,post - ybar_T,pre) - (ybar_C,post - ybar_C,pre)

    computed as simple group means of `outcome`. This is the descriptive 2x2
    contrast; it is not a causal estimate without the parallel-trends
    assumption, which this function does not test.
    """
    required = {unit, time, treated, post, outcome}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"panel is missing required columns: {sorted(missing)}")
    grouped = df.groupby([treated, post], observed=True)[outcome].mean()
    counts = df.groupby([treated, post], observed=True)[outcome].size()
    expected = [(1, 1), (1, 0), (0, 1), (0, 0)]
    for key in expected:
        if key not in grouped.index:
            raise ValueError(f"panel lacks observations for treated={key[0]}, post={key[1]}")
    treated_post = float(grouped.loc[(1, 1)])
    treated_pre = float(grouped.loc[(1, 0)])
    control_post = float(grouped.loc[(0, 1)])
    control_pre = float(grouped.loc[(0, 0)])
    return {
        "did": (treated_post - treated_pre) - (control_post - control_pre),
        "treated_pre": treated_pre,
        "treated_post": treated_post,
        "control_pre": control_pre,
        "control_post": control_post,
        "n_treated": int(df.loc[df[treated] == 1, unit].nunique()),
        "n_control": int(df.loc[df[treated] == 0, unit].nunique()),
        "n_cells": int(counts.size),
    }


def ols_diagnostics(
    df: pd.DataFrame,
    outcome: str,
    regressors: list[str] | tuple[str, ...],
    *,
    ci_level: float = 0.95,
) -> dict[str, object]:
    """Thin statsmodels OLS wrapper emitting per-regressor benchmark fields.

    Fits y = const + X beta by ordinary least squares (no weights, no
    covariate engineering — this is deliberately thin, not a TWFE
    reimplementation) and returns a JSON-serializable dict with, per
    regressor: coef, se, ci_lower, ci_upper (classical OLS CI at `ci_level`),
    t, and p. Intended for diagnostics.json benchmark fields; for
    survey-weighted inference use the replicate-weight helpers instead.
    """
    if not 0.0 < ci_level < 1.0:
        raise ValueError(f"ci_level must lie in (0, 1), got {ci_level}")
    columns = [outcome, *regressors]
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"data is missing columns: {sorted(missing)}")
    y = df[outcome].to_numpy(dtype=np.float64)
    x = df[list(regressors)].to_numpy(dtype=np.float64)
    design = sm.add_constant(x)
    fit = sm.OLS(y, design).fit()
    params = np.asarray(fit.params, dtype=np.float64)
    bse = np.asarray(fit.bse, dtype=np.float64)
    tvalues = np.asarray(fit.tvalues, dtype=np.float64)
    pvalues = np.asarray(fit.pvalues, dtype=np.float64)
    conf_int = np.asarray(fit.conf_int(alpha=1.0 - ci_level), dtype=np.float64)
    terms = ["const", *regressors]
    rows: list[dict[str, float | str]] = []
    for index, term in enumerate(terms):
        rows.append(
            {
                "term": term,
                "coef": float(params[index]),
                "se": float(bse[index]),
                "ci_lower": float(conf_int[index, 0]),
                "ci_upper": float(conf_int[index, 1]),
                "t": float(tvalues[index]),
                "p": float(pvalues[index]),
            }
        )
    return {
        "outcome": outcome,
        "nobs": int(fit.nobs),
        "r_squared": float(fit.rsquared),
        "ci_level": float(ci_level),
        "terms": rows,
    }


def event_study_summary(
    coefficients: dict[int, float],
    *,
    reference_period: int = -1,
) -> dict[str, float | int]:
    """Summarize event-study relative-time coefficients into pre/post averages.

    `coefficients` maps event time (integer periods relative to treatment) to
    the estimated coefficient; the omitted/reference period (default -1) is
    ignored. Returns the unweighted mean of pre-period coefficients
    (event time < 0, excluding the reference) and of post-period coefficients
    (event time >= 0), plus the cell counts. Pre-average near zero is the
    usual parallel-trends plausibility check; the post-average summarizes the
    average effect over the observed post window.
    """
    pre = [
        coef for period, coef in coefficients.items() if period < 0 and period != reference_period
    ]
    post = [coef for period, coef in coefficients.items() if period >= 0]
    if not pre or not post:
        raise ValueError(
            "need at least one non-reference pre-period and one post-period coefficient"
        )
    return {
        "pre_average": float(np.mean(pre)),
        "post_average": float(np.mean(post)),
        "n_pre": len(pre),
        "n_post": len(post),
        "reference_period": reference_period,
    }


def full_pt_benchmark(labor_share: float, wage_increase_pct: float) -> float:
    """Full pass-through benchmark price increase, in percent.

    Under full pass-through of a labor-cost shock with labor cost share
    lambda and economy-wide wage increase of `wage_increase_pct` percent,
    unit costs — and hence prices — rise by

        full_pt = lambda * wage_increase_pct

    This is the benchmark convention used in minimum-wage price pass-through
    work (NBER w34990 conventions): a pass-through rate of 1 means prices
    rose exactly by the mechanical labor-cost share of the wage shock. All
    inputs/outputs are in percent (10.0 means 10%).
    """
    if not 0.0 <= labor_share <= 1.0:
        raise ValueError(f"labor_share must lie in [0, 1], got {labor_share}")
    return labor_share * wage_increase_pct


def pass_through_rate(
    price_change_pct: float,
    labor_share: float,
    wage_increase_pct: float,
) -> float:
    """Observed pass-through rate relative to the full pass-through benchmark.

        rate = price_change_pct / (labor_share * wage_increase_pct)

    rate = 1 is full pass-through; rate < 1 indicates partial pass-through
    (absorption in margins or non-labor substitution); rate > 1 indicates
    over-shifting. All inputs are in percent.
    """
    benchmark = full_pt_benchmark(labor_share, wage_increase_pct)
    if benchmark == 0.0:
        raise ValueError("full pass-through benchmark is zero; the rate is undefined")
    return price_change_pct / benchmark


def pass_through_decomposition(
    price_change_pct: float,
    labor_share: float,
    wage_increase_pct: float,
) -> dict[str, float]:
    """Decompose an observed price change into mechanical and residual parts.

    Splits the observed percent price change into the mechanical labor-cost
    pass-through component and the residual (composition, demand, margin, and
    other non-mechanical) component:

        mechanical = labor_share * wage_increase_pct
        residual   = price_change_pct - mechanical

    Returns both components in percent plus `mechanical_share`
    (mechanical / price_change_pct) and the implied `pass_through_rate`.
    A nonzero residual is the signature of composition effects: the observed
    price move is not fully explained by the mechanical cost channel. All
    inputs/outputs are in percent.
    """
    mechanical = full_pt_benchmark(labor_share, wage_increase_pct)
    if price_change_pct == 0.0:
        raise ValueError("price_change_pct is zero; the decomposition shares are undefined")
    residual = price_change_pct - mechanical
    return {
        "mechanical_component": mechanical,
        "composition_residual": residual,
        "mechanical_share": mechanical / price_change_pct,
        "pass_through_rate": price_change_pct / mechanical if mechanical != 0.0 else float("nan"),
    }
