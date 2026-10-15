"""reports/results.csv: every TestResult the notebooks produce, one row per test.

Each notebook saves its hypothesis's rows with `save`, replacing that hypothesis's previous
rows, so re-running a notebook never duplicates results. The memo's numbers must trace back to
this file (or cost_log.csv / derived_numbers.csv).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from delaystats.stats_helpers import TestResult

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "reports" / "results.csv"


def frame(hypothesis: str, results: Sequence[TestResult]) -> pd.DataFrame:
    return pd.DataFrame([{"hypothesis": hypothesis, **r.as_row()} for r in results])


def save_frame(hypothesis: str, rows: pd.DataFrame) -> Path:
    """Replace this hypothesis's rows with `rows` (columns beyond TestResult's are kept)."""
    rows = rows.assign(hypothesis=hypothesis)
    if RESULTS.exists():
        existing = pd.read_csv(RESULTS)
        rows = pd.concat([existing[existing["hypothesis"] != hypothesis], rows], ignore_index=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    rows.sort_values(["hypothesis", "test"], kind="stable").to_csv(RESULTS, index=False)
    return RESULTS


def save(hypothesis: str, results: Sequence[TestResult]) -> Path:
    return save_frame(hypothesis, frame(hypothesis, results))


def load(hypothesis: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(RESULTS)
    return df if hypothesis is None else df[df["hypothesis"] == hypothesis]
