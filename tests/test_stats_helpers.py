"""Each helper checked against hand-computed formulas or published reference values."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from delaystats import stats_helpers as sh

A = [1.0, 2.0, 3.0, 4.0, 5.0]
B = [2.0, 4.0, 6.0, 8.0, 10.0]


def test_welch_t_matches_hand_formulas() -> None:
    res = sh.welch_t(A, B, groups=("a", "b"))
    # mean 3 vs 6; sample variances 2.5 and 10; n = 5 each
    se = math.sqrt(2.5 / 5 + 10 / 5)
    assert res.statistic == pytest.approx((3 - 6) / se)
    # Welch-Satterthwaite: (0.5 + 2)^2 / (0.5^2/4 + 2^2/4) = 6.25 / 1.0625
    assert res.df == pytest.approx(6.25 / 1.0625)
    assert res.estimate == pytest.approx(-3.0)
    t_crit = stats.t.ppf(0.975, 6.25 / 1.0625)  # about 2.48
    assert res.estimate_ci == pytest.approx((-3 - t_crit * se, -3 + t_crit * se))
    # Hedges' g: d = -3 / pooled sd, pooled var = (4*2.5 + 4*10) / 8 = 6.25 -> sd 2.5
    j = 1 - 3 / (4 * (5 + 5) - 9)
    g = -3 / 2.5 * j
    assert res.effect_size == pytest.approx(g)
    se_g = math.sqrt(10 / 25 + g**2 / (2 * 10))
    assert res.effect_ci == pytest.approx((g - 1.959964 * se_g, g + 1.959964 * se_g), abs=1e-4)
    assert res.n == {"a": 5, "b": 5}
    assert 0 < res.p < 1


def test_mann_whitney_matches_scipy_docs_example() -> None:
    # scipy.stats.mannwhitneyu documentation example: U1 = 17, exact p = 0.1111
    males = [19, 22, 16, 29, 24]
    females = [20, 11, 17, 12]
    res = sh.mann_whitney(males, females, n_boot=200)
    assert res.statistic == 17
    assert res.p == pytest.approx(0.1111, abs=1e-4)
    assert res.effect_size == pytest.approx(2 * 17 / 20 - 1)  # rank-biserial 0.7
    assert res.effect_ci[0] <= res.effect_size <= res.effect_ci[1]


def test_bootstrap_mean_diff_constant_groups_and_seed() -> None:
    res = sh.bootstrap_mean_diff([5.0] * 20, [3.0] * 30, n_boot=500)
    assert res.estimate == 2.0
    assert res.effect_ci == pytest.approx((2.0, 2.0))

    rng = np.random.default_rng(1)
    a, b = rng.normal(10, 2, 400), rng.normal(9, 2, 400)
    first = sh.bootstrap_mean_diff(a, b, n_boot=2000, seed=7)
    again = sh.bootstrap_mean_diff(a, b, n_boot=2000, seed=7)
    assert first.effect_ci == again.effect_ci
    low, high = first.effect_ci
    assert low < a.mean() - b.mean() < high


def test_chi2_independence_matches_scipy_docs_example() -> None:
    # scipy.stats.chi2_contingency documentation example
    observed = pd.DataFrame(
        [[10, 10, 20], [20, 20, 20]], index=["r1", "r2"], columns=["c1", "c2", "c3"]
    )
    out = sh.chi2_independence(observed, n_boot=200)
    assert out.result.statistic == pytest.approx(2.7777777777777777)
    assert out.result.p == pytest.approx(0.24935220877729619)
    assert out.result.df == 2
    assert out.expected.to_numpy() == pytest.approx(np.array([[12, 12, 16], [18, 18, 24]]))
    # adjusted residual, cell (r1, c1): (10 - 12) / sqrt(12 * (1 - 40/100) * (1 - 30/100))
    assert out.adjusted_residuals.loc["r1", "c1"] == pytest.approx(-2 / math.sqrt(5.04))
    assert out.notable_cells == []
    # Bergsma-corrected V by hand: phi2 = 2.7778/100, correction (k-1)(r-1)/(n-1) = 2/99
    phi2_corr = 2.7777777777777777 / 100 - 2 / 99
    r_corr, k_corr = 2 - 1 / 99, 3 - 4 / 99
    assert out.result.effect_size == pytest.approx(
        math.sqrt(phi2_corr / min(k_corr - 1, r_corr - 1))
    )
    assert out.result.n == {"total": 100}


def test_chi2_flags_small_expected_counts_and_notable_cells() -> None:
    observed = pd.DataFrame([[50, 0], [0, 50], [2, 2]], index=["x", "y", "z"], columns=["p", "q"])
    out = sh.chi2_independence(observed, n_boot=100)
    assert "< 5" in out.result.notes
    assert ("x", "p") in out.notable_cells


def test_pearson_with_fisher_ci() -> None:
    x, y = [1, 2, 3, 4, 5], [2, 4, 5, 4, 5]
    res = sh.pearson_with_ci(x, y)
    r = math.sqrt(0.6)  # cov 1.5, var_x 2.5, var_y 1.5 -> r = 1.5 / sqrt(3.75)
    assert res.effect_size == pytest.approx(r)
    z, half = math.atanh(r), 1.959964 / math.sqrt(5 - 3)
    assert res.effect_ci == pytest.approx((math.tanh(z - half), math.tanh(z + half)), abs=1e-5)
    assert res.df == 3


def test_spearman_matches_scipy_docs_example() -> None:
    # scipy.stats.spearmanr documentation example
    res = sh.spearman_with_bootstrap_ci([1, 2, 3, 4, 5], [5, 6, 7, 8, 7], n_boot=300)
    assert res.effect_size == pytest.approx(0.8207826816681233)
    assert res.p == pytest.approx(0.0885870053135438)
    low, high = res.effect_ci
    assert -1 <= low <= high <= 1


def test_partial_corr_matches_first_order_formula() -> None:
    rng = np.random.default_rng(3)
    z = rng.normal(size=500)
    x = z + rng.normal(size=500)
    y = z + 0.5 * x + rng.normal(size=500)
    data = pd.DataFrame({"x": x, "y": y, "z": z})
    res = sh.partial_corr(data, "x", "y", ["z"])
    r = data.corr()
    expected = (r.loc["x", "y"] - r.loc["x", "z"] * r.loc["y", "z"]) / math.sqrt(
        (1 - r.loc["x", "z"] ** 2) * (1 - r.loc["y", "z"] ** 2)
    )
    assert res.effect_size == pytest.approx(expected)
    zr, half = math.atanh(expected), 1.959964 / math.sqrt(500 - 1 - 3)
    assert res.effect_ci == pytest.approx((math.tanh(zr - half), math.tanh(zr + half)), abs=1e-5)


def test_multiple_comparison_table_textbook_case() -> None:
    results = [
        sh.TestResult(f"t{i}", 0.0, 1.0, p, "d", 0.0, (0.0, 0.0), {"n": 10})
        for i, p in enumerate([0.01, 0.02, 0.03, 0.04, 0.05], start=1)
    ]
    table = sh.multiple_comparison_table(results)
    assert table["p_bonferroni"].tolist() == pytest.approx([0.05, 0.10, 0.15, 0.20, 0.25])
    # BH: p_(i) * m / i = 0.05 for every i
    assert table["p_bh"].tolist() == pytest.approx([0.05] * 5)
    # reject when p <= alpha: all 5 raw, all 5 under BH, only the first under Bonferroni
    assert table["significant_raw"].all()
    assert table["significant_bh"].all()
    assert table["significant_bonferroni"].tolist() == [True, False, False, False, False]
    assert table["flips_bonferroni"].tolist() == [False, True, True, True, True]
    assert not table["flips_bh"].any()


def test_power_min_detectable_cohen_table() -> None:
    # Cohen (1988): d = 0.5, alpha .05 two-sided, power .80 needs n = 63.77 per group
    res = sh.power_min_detectable(sd=10.0, n1=63.7656, n2=63.7656)
    assert res.effect_size == pytest.approx(0.5, abs=1e-3)
    assert res.estimate == pytest.approx(5.0, abs=1e-2)  # in the data's units: d * sd


def test_as_row_flattens_for_results_csv() -> None:
    row = sh.welch_t(A, B, groups=("summer_2023", "summer_2024")).as_row()
    assert row["n"] == "summer_2023=5;summer_2024=5"
    assert row["effect_name"] == "hedges_g"
    assert {"effect_ci_low", "effect_ci_high", "estimate_ci_low", "estimate_ci_high"} <= set(row)
