"""Fail if any number in the memo body cannot be traced to the results.

    python -m delaystats.check_memo_numbers

Every number written in reports/memo.md before the Appendix must match a value in
reports/results.csv, reports/cost_log.csv or reports/derived_numbers.csv, at the precision
the memo writes it: "3.1" matches -3.0845 (sign is free, because prose says "fell 3.1
minutes"), "12.3%" matches 0.1234 or 12.34. Years 2000-2099 are exempt. Anything else (the
alpha, the practical threshold, a difference of two results) belongs in derived_numbers.csv
with the formula that produced it.
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
MEMO = REPORTS / "memo.md"
SOURCES = ("results.csv", "cost_log.csv", "derived_numbers.csv")
NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?")


def memo_body(text: str) -> str:
    """Prose before the appendix, without comments, links or figure/table references."""
    body = text.split("\n## Appendix", 1)[0]
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"\]\([^)]*\)", "]", body)  # link targets
    body = re.sub(r"\b(Figure|Table|Appendix|H)\s?\d+\b", "", body)  # references and H1..H4
    body = re.sub(r"^#+ .*$", "", body, flags=re.M)  # headings
    body = re.sub(r"\bp\s*[<>]\s*0?\.\d+", "p", body)  # "p < 0.0001" is a bound, not a result
    return body


def tokens(body: str) -> list[str]:
    return NUMBER.findall(body)


def source_values(reports: Path = REPORTS) -> list[float]:
    values: list[float] = []
    for name in SOURCES:
        path = reports / name
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        for column in frame.columns:
            numeric = pd.to_numeric(frame[column], errors="coerce").dropna()
            values += numeric.astype(float).tolist()
            if not pd.api.types.is_numeric_dtype(frame[column]):  # n: "group=123;group=456"
                for text in frame[column].dropna().astype(str):
                    values += [float(x) for x in re.findall(r"(?<==)-?\d+(?:\.\d+)?", text)]
    return values


def traced(token: str, values: list[float]) -> bool:
    is_percent = token.endswith("%")
    text = token.rstrip("%").replace(",", "")
    target = abs(Decimal(text))
    places = len(text.split(".")[1]) if "." in text else 0
    if not is_percent and places == 0 and 2000 <= target <= 2099:
        return True  # a year
    quantum = Decimal(1).scaleb(-places)
    for value in values:
        candidates = [value * 100, value] if is_percent else [value]
        for candidate in candidates:
            if abs(Decimal(str(candidate))).quantize(quantum) == target:
                return True
    return False


def check(memo: Path = MEMO, reports: Path = REPORTS) -> list[str]:
    values = source_values(reports)
    return [t for t in tokens(memo_body(memo.read_text(encoding="utf-8"))) if not traced(t, values)]


def main() -> None:
    untraced = check()
    if untraced:
        print("numbers in the memo not found in results.csv, cost_log.csv or derived_numbers.csv:")
        for token in sorted(set(untraced), key=untraced.index):
            print(f"  {token}")
        sys.exit(1)
    print(f"every number in {MEMO.relative_to(ROOT)} traces to the results files")


if __name__ == "__main__":
    main()
