"""Generate the memo's Appendix B (full test results) and D (cost of the analysis) from
reports/results.csv and reports/cost_log.csv, and write them into reports/memo.md between
the marker comments, so the appendix tables are never typed by hand.

    python -m delaystats.build_appendix
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
MEMO = REPORTS / "memo.md"


def _num(value: object, places: int = 3) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    number = float(value)  # type: ignore[arg-type]
    if number != 0 and abs(number) < 10**-places:
        return f"{number:.1e}"
    return f"{number:,.{places}f}"


def results_table(results: pd.DataFrame) -> str:
    lines = [
        "| Hypothesis | Test | Statistic | df | p | Adjusted p (Bonferroni / BH) "
        "| Effect size | 95% CI | n |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in results.itertuples():
        adjusted = ""
        if "p_bonferroni" in results.columns and pd.notna(row.p_bonferroni):
            adjusted = f"{_num(row.p_bonferroni, 4)} / {_num(row.p_bh, 4)}"
        effect = f"{row.effect_name} {_num(row.effect_size)}"
        ci = f"[{_num(row.effect_ci_low)}, {_num(row.effect_ci_high)}]"
        lines.append(
            f"| {row.hypothesis} | {row.test} | {_num(row.statistic, 2)} | {_num(row.df, 1)} "
            f"| {_num(row.p, 4)} | {adjusted} | {effect} | {ci} | {row.n} |"
        )
    return "\n".join(lines)


def cost_section(cost_log: Path) -> str:
    if not cost_log.exists():
        return "Athena cost figures come from the deployed run (`make cost-compare`)."
    log = pd.read_csv(cost_log)
    lines = [
        "| Benchmark | Format | Bytes scanned | USD |",
        "|---|---|---|---|",
    ]
    for row in log.to_dict("records"):
        lines.append(
            f"| {row['benchmark']} | {row['format']} | {int(row['bytes_scanned']):,} "
            f"| {row['usd']:.6f} |"
        )
    total = log["usd"].sum()
    lines.append(
        f"\nTotal for the benchmark queries: ${total:.4f} "
        f"at ${log['usd_per_tb'].iloc[0]:.2f} per TB scanned."
    )
    return "\n".join(lines)


def replace_block(text: str, name: str, content: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"memo has no <!-- {name}:start/end --> markers")
    return pattern.sub(lambda m: m.group(1) + content + m.group(2), text)


def main() -> None:
    text = MEMO.read_text(encoding="utf-8")
    text = replace_block(text, "appendix-b", results_table(pd.read_csv(REPORTS / "results.csv")))
    text = replace_block(text, "appendix-d", cost_section(REPORTS / "cost_log.csv"))
    MEMO.write_text(text, encoding="utf-8", newline="\n")
    print(f"updated appendices B and D in {MEMO.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
