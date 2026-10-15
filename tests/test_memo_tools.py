"""The memo number check and the appendix builder."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from delaystats import build_appendix, check_memo_numbers


def _reports(tmp_path: Path) -> Path:
    pd.DataFrame(
        [
            {
                "hypothesis": "H1",
                "test": "h1_welch",
                "statistic": -5.123,
                "df": 151.9,
                "p": 0.00004,
                "effect_name": "hedges_g",
                "effect_size": -0.0412,
                "effect_ci_low": -0.06,
                "effect_ci_high": -0.02,
                "estimate": -3.0845,
                "estimate_ci_low": -4.2,
                "estimate_ci_high": -1.9,
                "n": "summer_2024=51234;summer_2023=49876",
                "notes": "",
            },
        ]
    ).to_csv(tmp_path / "results.csv", index=False)
    pd.DataFrame(
        [
            {"name": "alpha", "value": 0.05, "formula": "pre-registered"},
            {"name": "threshold", "value": 2, "formula": "pre-registered"},
        ]
    ).to_csv(tmp_path / "derived_numbers.csv", index=False)
    return tmp_path


def test_traced_numbers_pass_and_untraced_fail(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    memo = tmp_path / "memo.md"
    memo.write_text(
        "# Delay fell\n\nMean delay fell 3.1 minutes in 2024 (Welch's t(152) = -5.12, p < 0.0001, "
        "Hedges' g = -0.04; 51,234 flights). Below the 2-minute threshold at alpha = 0.05. "
        "See Figure 3 and H1.\n\nIt also rose 7.7 minutes somewhere.\n\n"
        "## Appendix\n\n99.9 ignored\n"
    )
    untraced = check_memo_numbers.check(memo, reports)
    assert untraced == ["7.7"]


def test_percentages_match_shares(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    memo = tmp_path / "memo.md"
    memo.write_text("Effect was 4.1% of a standard deviation.\n\n## Appendix\n")
    assert check_memo_numbers.check(memo, reports) == []


def test_appendix_blocks_are_regenerated(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    text = "# Memo\n\n## Appendix\n<!-- appendix-b:start -->\nold\n<!-- appendix-b:end -->\n"
    out = build_appendix.replace_block(
        text, "appendix-b", build_appendix.results_table(pd.read_csv(reports / "results.csv"))
    )
    assert "\nold\n" not in out
    assert "| H1 | h1_welch | -5.12 | 151.9 | 4.0e-05 |" in out
    assert "Athena cost figures come from the deployed run" in build_appendix.cost_section(
        tmp_path / "missing.csv"
    )
