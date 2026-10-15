"""Statistical tests for the pre-registered plan (docs/ANALYSIS_PLAN.md).

Every helper returns a TestResult (or a ChiSquareResult wrapping one), so each reported test
carries the same fields: test name, statistic, degrees of freedom, p-value, effect size with
a 95% CI, and n per group. `estimate` holds the quantity in its natural units where one
exists (for example the difference in mean delay in minutes), because the practical
significance threshold is stated in those units.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pingouin as pg
from numpy.typing import ArrayLike, NDArray
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import TTestIndPower

CONFIDENCE = 0.95
_Z = float(stats.norm.ppf(0.5 + CONFIDENCE / 2))

Interval = tuple[float, float]


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class

    name: str
    statistic: float | None
    df: float | None
    p: float | None
    effect_name: str
    effect_size: float
    effect_ci: Interval
    n: Mapping[str, int]
    estimate: float | None = None
    estimate_ci: Interval | None = None
    notes: str = ""

    def as_row(self) -> dict[str, object]:
        """Flat record for reports/results.csv."""
        return {
            "test": self.name,
            "statistic": self.statistic,
            "df": self.df,
            "p": self.p,
            "effect_name": self.effect_name,
            "effect_size": self.effect_size,
            "effect_ci_low": self.effect_ci[0],
            "effect_ci_high": self.effect_ci[1],
            "estimate": self.estimate,
            "estimate_ci_low": self.estimate_ci[0] if self.estimate_ci else None,
            "estimate_ci_high": self.estimate_ci[1] if self.estimate_ci else None,
            "n": ";".join(f"{group}={count}" for group, count in self.n.items()),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ChiSquareResult:
    result: TestResult
    expected: pd.DataFrame
    adjusted_residuals: pd.DataFrame
    notable_cells: list[tuple[str, str]] = field(default_factory=list)


def _array(values: ArrayLike) -> NDArray[np.float64]:
    arr = np.asarray(values, dtype=np.float64)
    return arr[~np.isnan(arr)]


def _interval(low: float, high: float) -> Interval:
    return float(low), float(high)


def _fisher_ci(r: float, n_effective: float) -> Interval:
    """95% CI of a correlation via Fisher's z; n_effective is n minus partialled covariates."""
    z = math.atanh(r)
    half = _Z / math.sqrt(n_effective - 3)
    return _interval(math.tanh(z - half), math.tanh(z + half))


# ------------------------------------------------------------------ two groups


def welch_t(
    a: ArrayLike, b: ArrayLike, name: str = "welch_t", groups: tuple[str, str] = ("a", "b")
) -> TestResult:
    """Welch's t-test (unequal variances). Effect: Hedges' g; estimate: mean(a) - mean(b)."""
    x, y = _array(a), _array(b)
    res = stats.ttest_ind(x, y, equal_var=False)
    diff_ci = res.confidence_interval(CONFIDENCE)
    g = float(pg.compute_effsize(x, y, eftype="hedges"))
    n_x, n_y = len(x), len(y)
    # Hedges & Olkin (1985) large-sample standard error of g
    se_g = math.sqrt((n_x + n_y) / (n_x * n_y) + g**2 / (2 * (n_x + n_y)))
    return TestResult(
        name=name,
        statistic=float(res.statistic),
        df=float(res.df),
        p=float(res.pvalue),
        effect_name="hedges_g",
        effect_size=g,
        effect_ci=_interval(g - _Z * se_g, g + _Z * se_g),
        n={groups[0]: n_x, groups[1]: n_y},
        estimate=float(x.mean() - y.mean()),
        estimate_ci=_interval(diff_ci.low, diff_ci.high),
        notes="estimate = difference in means (a - b), Welch CI",
    )


def mann_whitney(
    a: ArrayLike,
    b: ArrayLike,
    name: str = "mann_whitney_u",
    groups: tuple[str, str] = ("a", "b"),
    n_boot: int = 2000,
    seed: int = 0,
) -> TestResult:
    """Mann-Whitney U (two-sided). Tests a shift in distribution, not in means.

    Effect: rank-biserial correlation 2*U/(n_a*n_b) - 1 (positive when a tends to be larger),
    with a percentile bootstrap CI.
    """
    x, y = _array(a), _array(b)
    res = stats.mannwhitneyu(x, y, alternative="two-sided")
    n_x, n_y = len(x), len(y)

    def rank_biserial(u: float, nx: int, ny: int) -> float:
        return 2 * u / (nx * ny) - 1

    rng = np.random.default_rng(seed)
    boot = np.empty(n_boot)
    for i in range(n_boot):
        bx = rng.choice(x, n_x, replace=True)
        by = rng.choice(y, n_y, replace=True)
        boot[i] = rank_biserial(float(stats.mannwhitneyu(bx, by).statistic), n_x, n_y)
    low, high = np.percentile(boot, [2.5, 97.5])
    return TestResult(
        name=name,
        statistic=float(res.statistic),
        df=None,
        p=float(res.pvalue),
        effect_name="rank_biserial",
        effect_size=rank_biserial(float(res.statistic), n_x, n_y),
        effect_ci=_interval(low, high),
        n={groups[0]: n_x, groups[1]: n_y},
        notes=f"tests distribution shift, not means; effect CI: {n_boot} bootstrap resamples, "
        f"seed {seed}",
    )


def bootstrap_mean_diff(
    a: ArrayLike,
    b: ArrayLike,
    name: str = "bootstrap_mean_diff",
    groups: tuple[str, str] = ("a", "b"),
    n_boot: int = 10_000,
    seed: int = 0,
) -> TestResult:
    """Percentile bootstrap CI of mean(a) - mean(b), resampling each group independently."""
    x, y = _array(a), _array(b)
    res = stats.bootstrap(
        (x, y),
        lambda s1, s2, axis: np.mean(s1, axis=axis) - np.mean(s2, axis=axis),
        n_resamples=n_boot,
        confidence_level=CONFIDENCE,
        method="percentile",
        vectorized=True,
        rng=np.random.default_rng(seed),
    )
    diff = float(x.mean() - y.mean())
    ci = _interval(res.confidence_interval.low, res.confidence_interval.high)
    return TestResult(
        name=name,
        statistic=None,
        df=None,
        p=None,
        effect_name="mean_difference",
        effect_size=diff,
        effect_ci=ci,
        n={groups[0]: len(x), groups[1]: len(y)},
        estimate=diff,
        estimate_ci=ci,
        notes=f"{n_boot} resamples, seed {seed}",
    )


# ------------------------------------------------------------------ categorical


def cramers_v_corrected(table: NDArray[np.float64]) -> float:
    """Cramér's V with Bergsma's (2013) bias correction. Empty rows and columns are dropped
    (a bootstrap table can lose a rare category entirely)."""
    table = table[table.sum(axis=1) > 0][:, table.sum(axis=0) > 0]
    if min(table.shape) < 2:
        return 0.0
    chi2 = float(stats.chi2_contingency(table, correction=False).statistic)
    n = table.sum()
    r, k = table.shape
    phi2 = chi2 / n
    phi2_corr = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    r_corr = r - (r - 1) ** 2 / (n - 1)
    k_corr = k - (k - 1) ** 2 / (n - 1)
    return math.sqrt(phi2_corr / min(k_corr - 1, r_corr - 1))


def chi2_independence(
    observed: pd.DataFrame,
    name: str = "chi2_independence",
    n_boot: int = 2000,
    seed: int = 0,
    notable_residual: float = 3.0,
) -> ChiSquareResult:
    """Pearson chi-squared test of independence on a contingency table (rows x columns).

    Effect: bias-corrected Cramér's V; its CI comes from a parametric bootstrap (tables
    redrawn from the observed cell proportions). Returns the expected counts and the adjusted
    standardized residuals; cells with |residual| > notable_residual are listed.
    """
    counts = observed.to_numpy(dtype=np.float64)
    res = stats.chi2_contingency(counts, correction=False)
    expected = pd.DataFrame(res.expected_freq, index=observed.index, columns=observed.columns)

    n = counts.sum()
    row_share = counts.sum(axis=1, keepdims=True) / n
    col_share = counts.sum(axis=0, keepdims=True) / n
    adjusted = (counts - res.expected_freq) / np.sqrt(
        res.expected_freq * (1 - row_share) * (1 - col_share)
    )
    residuals = pd.DataFrame(adjusted, index=observed.index, columns=observed.columns)
    notable = [
        (str(row), str(col))
        for row in observed.index
        for col in observed.columns
        if abs(residuals.loc[row, col]) > notable_residual
    ]

    rng = np.random.default_rng(seed)
    probabilities = (counts / n).ravel()
    boot = [
        cramers_v_corrected(
            rng.multinomial(int(n), probabilities).reshape(counts.shape).astype(np.float64)
        )
        for _ in range(n_boot)
    ]
    low, high = np.percentile(boot, [2.5, 97.5])

    min_expected = float(res.expected_freq.min())
    notes = f"min expected count {min_expected:.2f}"
    if min_expected < 5:
        notes += " (< 5: assumption violated, apply the pre-registered merge)"
    result = TestResult(
        name=name,
        statistic=float(res.statistic),
        df=float(res.dof),
        p=float(res.pvalue),
        effect_name="cramers_v_bias_corrected",
        effect_size=cramers_v_corrected(counts),
        effect_ci=_interval(low, high),
        n={"total": int(n)},
        notes=notes + f"; V CI: {n_boot} parametric bootstrap tables, seed {seed}",
    )
    return ChiSquareResult(result, expected, residuals, notable)


# ------------------------------------------------------------------ correlation


def pearson_with_ci(x: ArrayLike, y: ArrayLike, name: str = "pearson_r") -> TestResult:
    """Pearson r with a Fisher z 95% CI."""
    xs, ys = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    res = stats.pearsonr(xs, ys)
    r = float(res.statistic)
    return TestResult(
        name=name,
        statistic=r,
        df=float(len(xs) - 2),
        p=float(res.pvalue),
        effect_name="pearson_r",
        effect_size=r,
        effect_ci=_fisher_ci(r, len(xs)),
        n={"pairs": len(xs)},
        notes="CI: Fisher z",
    )


def spearman_with_bootstrap_ci(
    x: ArrayLike, y: ArrayLike, name: str = "spearman_rho", n_boot: int = 2000, seed: int = 0
) -> TestResult:
    """Spearman rho with a percentile bootstrap CI (pairs resampled together)."""
    xs, ys = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    res = stats.spearmanr(xs, ys)
    rng = np.random.default_rng(seed)
    n = len(xs)
    boot = np.empty(n_boot)
    with warnings.catch_warnings():
        # a resample with a constant column has no rho; it is dropped (nan) below
        warnings.simplefilter("ignore", stats.ConstantInputWarning)
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            boot[i] = stats.spearmanr(xs[idx], ys[idx]).statistic
    low, high = np.nanpercentile(boot, [2.5, 97.5])
    dropped = int(np.isnan(boot).sum())
    rho = float(res.statistic)
    return TestResult(
        name=name,
        statistic=rho,
        df=float(n - 2),
        p=float(res.pvalue),
        effect_name="spearman_rho",
        effect_size=rho,
        effect_ci=_interval(low, high),
        n={"pairs": n},
        notes=f"CI: {n_boot} bootstrap resamples of pairs, seed {seed}"
        + (f", {dropped} constant resamples dropped" if dropped else ""),
    )


def partial_corr(
    data: pd.DataFrame, x: str, y: str, covar: Sequence[str], name: str = "partial_corr"
) -> TestResult:
    """Pearson partial correlation of x and y controlling for covar (pingouin).

    The CI is Fisher z with n reduced by the number of covariates, at full precision
    (pingouin's own CI column is rounded to two decimals).
    """
    res = pg.partial_corr(data=data, x=x, y=y, covar=list(covar), method="pearson")
    n = int(res["n"].iloc[0])
    r = float(res["r"].iloc[0])
    k = len(covar)
    return TestResult(
        name=name,
        statistic=r,
        df=float(n - 2 - k),
        p=float(res["p_val"].iloc[0]),
        effect_name="partial_r",
        effect_size=r,
        effect_ci=_fisher_ci(r, n - k),
        n={"pairs": n},
        notes=f"controlling for {', '.join(covar)}; CI: Fisher z",
    )


# ------------------------------------------------------------------ many tests


def multiple_comparison_table(results: Sequence[TestResult], alpha: float = 0.05) -> pd.DataFrame:
    """Raw, Bonferroni- and Benjamini-Hochberg-adjusted p-values, and which verdicts flip.

    `flips_bonferroni` / `flips_bh` mark tests significant at raw alpha that are not
    significant after that correction.
    """
    p = np.array([r.p for r in results], dtype=np.float64)
    # reject when p <= alpha; statsmodels' own decisions avoid float error at the boundary
    reject_bonf, p_bonf, _, _ = multipletests(p, alpha=alpha, method="bonferroni")
    reject_bh, p_bh, _, _ = multipletests(p, alpha=alpha, method="fdr_bh")
    table = pd.DataFrame(
        {
            "test": [r.name for r in results],
            "p_raw": p,
            "p_bonferroni": p_bonf,
            "p_bh": p_bh,
            "significant_raw": p <= alpha,
            "significant_bonferroni": reject_bonf,
            "significant_bh": reject_bh,
        }
    )
    table["flips_bonferroni"] = table["significant_raw"] & ~table["significant_bonferroni"]
    table["flips_bh"] = table["significant_raw"] & ~table["significant_bh"]
    return table


# ------------------------------------------------------------------ power


def power_min_detectable(
    sd: float,
    n1: float,
    n2: float,
    alpha: float = 0.05,
    power: float = 0.8,
    name: str = "power_min_detectable",
) -> TestResult:
    """Smallest true difference in means a two-sided two-sample t-test detects with the given
    power. Effect: that difference as Cohen's d; estimate: the same in the data's units
    (d * sd). There is no sampling interval here, so the CI is the point value.
    """
    d = float(
        TTestIndPower().solve_power(
            effect_size=None,
            nobs1=n1,
            ratio=n2 / n1,
            alpha=alpha,
            power=power,
            alternative="two-sided",
        )
    )
    return TestResult(
        name=name,
        statistic=None,
        df=None,
        p=None,
        effect_name="min_detectable_cohens_d",
        effect_size=d,
        effect_ci=(d, d),
        n={"group1": round(n1), "group2": round(n2)},
        estimate=d * sd,
        estimate_ci=None,
        notes=f"alpha {alpha}, power {power}, sd {sd}",
    )
