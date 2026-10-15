"""Every figure in the analysis, as a function. Notebooks call these; nothing is drawn only in
a notebook. Figures go to reports/figures/<name>.png at 150 dpi.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "reports" / "figures"
DPI = 150


def save(fig: Figure, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def _month_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.to_datetime({"year": df["year"], "month": df["month"], "day": 1})  # type: ignore[return-value]


# ---------------------------------------------------------------- data profile


def flights_and_cancellations_by_month(df: pd.DataFrame) -> Path:
    months = _month_index(df)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(months, df["flights"] / 1e3, width=20, color="#4C72B0")
    ax.set_ylabel("Flights (thousands)")
    rate = ax.twinx()
    rate.plot(months, df["cancellation_rate"] * 100, color="#C44E52", marker="o", markersize=3)
    rate.set_ylabel("Cancelled (%)", color="#C44E52")
    ax.set_title("Flights per month and the share cancelled")
    return save(fig, "profile_flights_and_cancellations_by_month")


def arrdelay_distribution(df: pd.DataFrame, clip: tuple[int, int] = (-60, 300)) -> Path:
    shown = df[(df["arrdelay"] >= clip[0]) & (df["arrdelay"] <= clip[1])]
    beyond = int(df.loc[df["arrdelay"] > clip[1], "flights"].sum())
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(shown["arrdelay"], shown["flights"], width=1.0, color="#4C72B0")
    ax.set_yscale("log")
    ax.set_xlabel("Arrival delay (minutes; negative = early)")
    ax.set_ylabel("Flights (log scale)")
    ax.set_title(
        f"Arrival delays are heavily right-skewed "
        f"({beyond:,} flights beyond {clip[1]} min not shown)"
    )
    return save(fig, "profile_arrdelay_distribution")


def null_rates(df: pd.DataFrame) -> Path:
    rates = df.iloc[0].sort_values(ascending=True) * 100
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(rates.index, rates.to_numpy(), color="#4C72B0")
    ax.set_xlabel("Null values (%)")
    ax.set_title("Share of null values per column")
    return save(fig, "profile_null_rates")


def carriers_by_volume(df: pd.DataFrame) -> Path:
    ordered = df.sort_values("flights")
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(ordered["reporting_airline"], ordered["flights"] / 1e6, color="#4C72B0")
    ax.set_xlabel("Completed flights (millions)")
    ax.set_title("Carriers by volume")
    return save(fig, "profile_carriers_by_volume")


# ---------------------------------------------------------------- hypothesis tests


def qq_plots(groups: dict[str, np.ndarray], name: str, title: str) -> Path:
    from scipy import stats

    fig, axes = plt.subplots(1, len(groups), figsize=(5 * len(groups), 4))
    for ax, (label, values) in zip(np.atleast_1d(axes), groups.items(), strict=True):
        stats.probplot(values, dist="norm", plot=ax)
        ax.set_title(f"{label} (n = {len(values):,})")
    fig.suptitle(title)
    return save(fig, name)


def group_distributions(
    groups: dict[str, np.ndarray],
    name: str,
    title: str,
    xlabel: str,
    clip: tuple[float, float] = (-60, 180),
) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4))
    bins = np.linspace(clip[0], clip[1], 80).tolist()
    for label, values in groups.items():
        ax.hist(np.clip(values, *clip), bins=bins, alpha=0.5, density=True, label=label)
        ax.axvline(np.mean(values), linestyle="--", linewidth=1)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Density")
    ax.set_title(title)
    ax.legend()
    return save(fig, name)


def bootstrap_distribution(
    diffs: np.ndarray, ci: tuple[float, float], threshold: float, name: str, title: str
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(diffs, bins=60, color="#4C72B0", alpha=0.8)
    for x in ci:
        ax.axvline(x, color="black", linestyle="--", linewidth=1)
    for x in (-threshold, threshold):
        ax.axvline(x, color="#C44E52", linewidth=1.5)
    ax.set_xlabel("Difference in mean arrival delay (minutes)")
    ax.set_title(title)
    return save(fig, name)


def residual_heatmap(residuals: pd.DataFrame, name: str, title: str, notable: float = 3.0) -> Path:
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(9, 6))
    limit = float(np.nanmax(np.abs(residuals.to_numpy())))
    sns.heatmap(
        residuals,
        annot=True,
        fmt=".1f",
        cmap="RdBu_r",
        center=0,
        vmin=-limit,
        vmax=limit,
        ax=ax,
        cbar_kws={"label": "Adjusted standardized residual"},
    )
    ax.set_title(f"{title}\n|residual| > {notable:g} is notable")
    return save(fig, name)


def scatter_with_lowess(
    x: np.ndarray,
    y: np.ndarray,
    name: str,
    title: str,
    xlabel: str,
    ylabel: str,
    log_x: bool = False,
) -> Path:
    from statsmodels.nonparametric.smoothers_lowess import lowess

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(x, y, s=4, alpha=0.15, color="#4C72B0")
    smooth = lowess(y, np.log10(x) if log_x else x, frac=0.3)
    ax.plot(
        10 ** smooth[:, 0] if log_x else smooth[:, 0], smooth[:, 1], color="#C44E52", linewidth=2
    )
    if log_x:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    return save(fig, name)


def correction_table_plot(table: pd.DataFrame, alpha: float, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(table))
    width = 0.27
    for offset, column, label in (
        (-width, "p_raw", "raw"),
        (0, "p_bonferroni", "Bonferroni"),
        (width, "p_bh", "Benjamini-Hochberg"),
    ):
        ax.bar(x + offset, -np.log10(table[column].clip(lower=1e-300)), width, label=label)
    ax.axhline(
        -np.log10(alpha), color="black", linestyle="--", linewidth=1, label=f"alpha = {alpha}"
    )
    ax.set_xticks(x, table["test"], rotation=30, ha="right")
    ax.set_ylabel("-log10(p)")
    ax.set_title(title)
    ax.legend()
    return save(fig, name)


def power_curve(
    differences: np.ndarray, power: np.ndarray, detectable: float, name: str, title: str
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(differences, power, color="#4C72B0")
    ax.axhline(0.8, color="black", linestyle="--", linewidth=1)
    ax.axvline(detectable, color="#C44E52", linewidth=1.5)
    ax.set_xlabel("True difference in mean arrival delay (minutes)")
    ax.set_ylabel("Power")
    ax.set_title(title)
    return save(fig, name)
