"""Tests for microdata_lab.econometrics: synthetic, deterministic data only.

Every expected value below is hand-computed from the documented formulas and
asserted against the implementation; the OLS wrapper is additionally
cross-checked against statsmodels' own fit on identical data.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm  # type: ignore[import-untyped]

from microdata_lab.econometrics import (
    did_2x2,
    event_study_summary,
    fay_se,
    full_pt_benchmark,
    jackknife_se,
    ols_diagnostics,
    pass_through_decomposition,
    pass_through_rate,
    replicate_ci,
    weighted_mean,
    weighted_quantile,
    weighted_variance,
)

# ---------------------------------------------------------------------------
# Weighted statistics
# ---------------------------------------------------------------------------


def test_weighted_mean_hand_computed() -> None:
    # (1*1 + 2*1 + 3*2) / 4 = 9/4
    assert weighted_mean([1.0, 2.0, 3.0], [1.0, 1.0, 2.0]) == pytest.approx(2.25)


def test_weighted_mean_rejects_invalid_weights() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        weighted_mean([1.0, 2.0], [1.0, -1.0])
    with pytest.raises(ValueError, match="positive total"):
        weighted_mean([1.0, 2.0], [0.0, 0.0])
    with pytest.raises(ValueError, match="same shape"):
        weighted_mean([1.0, 2.0], [1.0])


def test_weighted_quantile_midpoint_convention() -> None:
    # values [10, 20, 30], equal weights -> p = [1/6, 1/2, 5/6]
    # q = 0.5 hits the middle midpoint exactly -> 20
    assert weighted_quantile([10.0, 20.0, 30.0], [1.0, 1.0, 1.0], 0.5) == pytest.approx(20.0)
    # q = 0.25 interpolates between (1/6, 10) and (1/2, 20):
    # 10 + (0.25 - 1/6) / (1/2 - 1/6) * 10 = 10 + 2.5 = 12.5
    assert weighted_quantile([10.0, 20.0, 30.0], [1.0, 1.0, 1.0], 0.25) == pytest.approx(12.5)


def test_weighted_quantile_ties_return_shared_value() -> None:
    # Tied values occupy adjacent midpoint positions, so any quantile landing
    # inside the tied block returns the shared value exactly.
    # values [1, 2, 2, 3], equal weights -> p = [1/8, 3/8, 5/8, 7/8];
    # q = 0.5 lies between (3/8, 2) and (5/8, 2) -> 2.0 exactly.
    assert weighted_quantile([1.0, 2.0, 2.0, 3.0], [1.0, 1.0, 1.0, 1.0], 0.5) == pytest.approx(2.0)


def test_weighted_quantile_weighted_ties_and_clamping() -> None:
    # values [1, 2, 2, 4], weights [1, 2, 1, 1]
    # cumw = [1, 3, 4, 5], midpoints p = [0.1, 0.4, 0.7, 0.9]
    values = [1.0, 2.0, 2.0, 4.0]
    weights = [1.0, 2.0, 1.0, 1.0]
    # q = 0.5 lies inside the tied block between (0.4, 2) and (0.7, 2) -> 2.0
    assert weighted_quantile(values, weights, 0.5) == pytest.approx(2.0)
    # q = 0.8 between (0.7, 2) and (0.9, 4): 2 + (0.1 / 0.2) * 2 = 3.0
    assert weighted_quantile(values, weights, 0.8) == pytest.approx(3.0)
    # q outside the midpoint range clamps to the observed extremes
    assert weighted_quantile(values, weights, 0.0) == pytest.approx(1.0)
    assert weighted_quantile(values, weights, 1.0) == pytest.approx(4.0)


def test_weighted_quantile_rejects_bad_q() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        weighted_quantile([1.0, 2.0], [1.0, 1.0], 1.5)


def test_weighted_variance_frequency_weights() -> None:
    # values [1, 2, 3], weights [1, 2, 1]; xbar = (1 + 4 + 3) / 4 = 2
    # numerator = 1*1 + 2*0 + 1*1 = 2; frequency: 2 / (4 - 1) = 2/3
    var = weighted_variance([1.0, 2.0, 3.0], [1.0, 2.0, 1.0], weight_type="frequency")
    assert var == pytest.approx(2.0 / 3.0)


def test_weighted_variance_reliability_weights() -> None:
    # Same data; reliability: V1 = 4, V2 = 1 + 4 + 1 = 6, denom = 4 - 6/4 = 2.5
    # variance = 2 / 2.5 = 0.8 -- distinct from the frequency value 2/3
    var = weighted_variance([1.0, 2.0, 3.0], [1.0, 2.0, 1.0], weight_type="reliability")
    assert var == pytest.approx(0.8)


def test_weighted_variance_reduces_to_sample_variance_for_unit_weights() -> None:
    # values [1, 2, 3], unit weights: both conventions give 2 / 2 = 1.0
    assert weighted_variance([1.0, 2.0, 3.0], [1.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert (
        weighted_variance([1.0, 2.0, 3.0], [1.0, 1.0, 1.0], weight_type="frequency")
        == pytest.approx(1.0)
    )


def test_weighted_variance_rejects_degenerate_weighting() -> None:
    with pytest.raises(ValueError, match="denominator"):
        weighted_variance([5.0, 5.0], [1.0, 0.0])


# ---------------------------------------------------------------------------
# Replicate-weight standard errors
# ---------------------------------------------------------------------------


def test_jackknife_se_hand_computed() -> None:
    # full = 10, reps = [9, 10, 11]: sum of squared deviations = 2, m = 3
    # variance = 2 / (3 * 2) = 1/3; se = sqrt(1/3)
    result = jackknife_se(10.0, [9.0, 10.0, 11.0])
    assert result.variance == pytest.approx(1.0 / 3.0)
    assert result.se == pytest.approx(math.sqrt(1.0 / 3.0))
    assert result.estimate == 10.0
    assert result.replicates == 3
    assert result.method == "jk1"


def test_fay_se_hand_computed() -> None:
    # Same estimates, rho = 0.5: variance = 2 / (3 * (1 - 0.5)^2) = 2 / 0.75 = 8/3
    result = fay_se(10.0, [9.0, 10.0, 11.0], 0.5)
    assert result.variance == pytest.approx(8.0 / 3.0)
    assert result.se == pytest.approx(math.sqrt(8.0 / 3.0))
    assert result.method == "fay-brr"
    assert result.fay_rho == 0.5


def test_replicate_se_requires_two_replicates() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        jackknife_se(10.0, [9.5])
    with pytest.raises(ValueError, match="at least 2"):
        fay_se(10.0, [9.5], 0.5)


def test_fay_se_rejects_bad_rho() -> None:
    with pytest.raises(ValueError, match=r"\(0, 1\)"):
        fay_se(10.0, [9.0, 11.0], 1.0)


def test_replicate_ci_hand_computed() -> None:
    # se = sqrt(1/3) with m = 3 replicates -> t_{0.975, df=2} ~ 4.3026527
    result = jackknife_se(10.0, [9.0, 10.0, 11.0])
    ci = replicate_ci(result)
    half_width = 4.302652729749461 * math.sqrt(1.0 / 3.0)
    assert ci["ci_lower"] == pytest.approx(10.0 - half_width)
    assert ci["ci_upper"] == pytest.approx(10.0 + half_width)
    assert ci["estimate"] == 10.0
    assert ci["level"] == 0.95


def test_replicate_se_as_dict_is_json_serializable() -> None:
    result = jackknife_se(10.0, [9.0, 10.0, 11.0]).as_dict()
    assert result["method"] == "jk1"
    assert result["replicates"] == 3
    assert set(result) == {"estimate", "se", "variance", "replicates", "method", "fay_rho"}


# ---------------------------------------------------------------------------
# DiD toolkit
# ---------------------------------------------------------------------------


def _panel() -> pd.DataFrame:
    # Treated units 1-2: pre [10, 12] post [14, 16] -> means 11 -> 15
    # Control units 3-4: pre [8, 6]  post [10, 8]  -> means 7 -> 9
    rows = [
        (1, 0, 1, 0, 10.0),
        (1, 1, 1, 1, 14.0),
        (2, 0, 1, 0, 12.0),
        (2, 1, 1, 1, 16.0),
        (3, 0, 0, 0, 8.0),
        (3, 1, 0, 1, 10.0),
        (4, 0, 0, 0, 6.0),
        (4, 1, 0, 1, 8.0),
    ]
    return pd.DataFrame(rows, columns=["unit", "time", "treated", "post", "outcome"])


def test_did_2x2_matches_manual_group_means() -> None:
    result = did_2x2(_panel())
    assert result["treated_pre"] == pytest.approx(11.0)
    assert result["treated_post"] == pytest.approx(15.0)
    assert result["control_pre"] == pytest.approx(7.0)
    assert result["control_post"] == pytest.approx(9.0)
    # (15 - 11) - (9 - 7) = 4 - 2 = 2
    assert result["did"] == pytest.approx(2.0)
    assert result["n_treated"] == 2
    assert result["n_control"] == 2


def test_did_2x2_missing_cell_raises() -> None:
    panel = _panel()
    panel = panel[~((panel["treated"] == 1) & (panel["post"] == 1))]
    with pytest.raises(ValueError, match="lacks observations"):
        did_2x2(panel)


def test_ols_diagnostics_cross_checked_against_statsmodels() -> None:
    # Fixed synthetic sample with noise; no randomness anywhere.
    x1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    x2 = [2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0]
    y = [3.1, 4.9, 7.2, 8.8, 11.3, 12.7, 15.2, 16.9]
    df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})

    result = ols_diagnostics(df, "y", ["x1", "x2"])
    reference = sm.OLS(
        np.asarray(y, dtype=np.float64),
        sm.add_constant(np.column_stack([x1, x2])),
    ).fit()

    assert result["nobs"] == 8
    assert result["r_squared"] == pytest.approx(float(reference.rsquared))
    terms = result["terms"]
    assert isinstance(terms, list)
    assert [row["term"] for row in terms] == ["const", "x1", "x2"]
    for index, row in enumerate(terms):
        assert row["coef"] == pytest.approx(float(reference.params[index]))
        assert row["se"] == pytest.approx(float(reference.bse[index]))
        assert row["t"] == pytest.approx(float(reference.tvalues[index]))
        assert row["p"] == pytest.approx(float(reference.pvalues[index]))
        ref_ci = reference.conf_int(alpha=0.05)[index]
        assert row["ci_lower"] == pytest.approx(float(ref_ci[0]))
        assert row["ci_upper"] == pytest.approx(float(ref_ci[1]))


def test_ols_diagnostics_missing_column_raises() -> None:
    df = pd.DataFrame({"y": [1.0, 2.0], "x": [1.0, 2.0]})
    with pytest.raises(ValueError, match="missing columns"):
        ols_diagnostics(df, "y", ["nope"])


def test_event_study_summary_hand_computed() -> None:
    coefs = {-3: 0.1, -2: 0.2, -1: 0.0, 0: 1.0, 1: 1.4, 2: 1.8}
    summary = event_study_summary(coefs)
    # pre = mean(0.1, 0.2) = 0.15 (reference period -1 excluded)
    # post = mean(1.0, 1.4, 1.8) = 1.4
    assert summary["pre_average"] == pytest.approx(0.15)
    assert summary["post_average"] == pytest.approx(1.4)
    assert summary["n_pre"] == 2
    assert summary["n_post"] == 3
    assert summary["reference_period"] == -1


def test_event_study_summary_requires_both_sides() -> None:
    with pytest.raises(ValueError, match="pre-period"):
        event_study_summary({0: 1.0, 1: 2.0})


# ---------------------------------------------------------------------------
# Pass-through arithmetic (NBER w34990 conventions)
# ---------------------------------------------------------------------------


def test_full_pt_benchmark_hand_computed() -> None:
    # full_pt = 0.3 * 10.0 = 3.0 percent
    assert full_pt_benchmark(0.3, 10.0) == pytest.approx(3.0)


def test_full_pt_benchmark_rejects_bad_labor_share() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        full_pt_benchmark(1.5, 10.0)


def test_pass_through_rate_hand_computed() -> None:
    # rate = 1.5 / (0.3 * 10.0) = 0.5 -> half of full pass-through
    assert pass_through_rate(1.5, 0.3, 10.0) == pytest.approx(0.5)
    # rate = 3.0 / 3.0 = 1.0 -> exactly full pass-through
    assert pass_through_rate(3.0, 0.3, 10.0) == pytest.approx(1.0)


def test_pass_through_rate_undefined_for_zero_benchmark() -> None:
    with pytest.raises(ValueError, match="undefined"):
        pass_through_rate(1.0, 0.0, 10.0)


def test_pass_through_decomposition_hand_computed() -> None:
    # mechanical = 0.25 * 8.0 = 2.0; observed = 3.0 -> residual = 1.0
    result = pass_through_decomposition(3.0, 0.25, 8.0)
    assert result["mechanical_component"] == pytest.approx(2.0)
    assert result["composition_residual"] == pytest.approx(1.0)
    assert result["mechanical_share"] == pytest.approx(2.0 / 3.0)
    assert result["pass_through_rate"] == pytest.approx(1.5)


def test_pass_through_decomposition_pure_mechanical() -> None:
    # observed exactly equals the mechanical component -> no composition effect
    result = pass_through_decomposition(2.0, 0.25, 8.0)
    assert result["composition_residual"] == pytest.approx(0.0)
    assert result["mechanical_share"] == pytest.approx(1.0)
    assert result["pass_through_rate"] == pytest.approx(1.0)


def test_pass_through_decomposition_rejects_zero_price_change() -> None:
    with pytest.raises(ValueError, match="zero"):
        pass_through_decomposition(0.0, 0.25, 8.0)
