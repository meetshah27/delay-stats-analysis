"""`make cost-compare` (SPEC section 4): run the four benchmark queries on the raw CSV table and
on the partitioned Parquet table, read DataScannedInBytes from Athena, price it, and write
reports/cost_log.csv and reports/cost_comparison.md.

Athena only: the bytes scanned are Athena's own execution statistics. With --check, runs the
Parquet variants on the local backend instead, to prove the SQL before deployment.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from typing import Any

from delaystats.athena import ATHENA_USD_PER_TB, ROOT, execute

BENCHMARKS = {
    "bench_1_month_by_carrier": "Mean delay by carrier, one month",
    "bench_2_sea_causes": "Delay minutes by cause, SEA, all months",
    "bench_3_cancelled_count": "Full-table count of cancelled flights",
    "bench_4_route_month_features": "H3 route-month feature extraction",
}
COST_LOG = ROOT / "reports" / "cost_log.csv"
COST_TABLE = ROOT / "reports" / "cost_comparison.md"


def compare() -> None:
    rows: list[dict[str, Any]] = []
    run_at = datetime.now(UTC).isoformat(timespec="seconds")
    for bench in BENCHMARKS:
        for fmt in ("csv", "parquet"):
            result = execute(f"{bench}_{fmt}", backend="athena")
            scanned = result.bytes_scanned or 0
            rows.append(
                {
                    "run_at": run_at,
                    "benchmark": bench,
                    "format": fmt,
                    "bytes_scanned": scanned,
                    "usd": round(scanned / 1e12 * ATHENA_USD_PER_TB, 6),
                    "usd_per_tb": ATHENA_USD_PER_TB,
                    "execution_id": result.execution_id,
                }
            )
            print(f"{bench} {fmt}: {scanned:,} bytes")
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    by_key = {(r["benchmark"], r["format"]): r for r in rows}
    lines = [
        "| Query | CSV scanned | CSV USD | Parquet scanned | Parquet USD | Bytes saved |",
        "|---|---|---|---|---|---|",
    ]
    for bench, label in BENCHMARKS.items():
        csv_row, pq_row = by_key[(bench, "csv")], by_key[(bench, "parquet")]
        saved = (
            1 - pq_row["bytes_scanned"] / csv_row["bytes_scanned"]
            if csv_row["bytes_scanned"]
            else 0
        )
        lines.append(
            f"| {label} | {csv_row['bytes_scanned'] / 1e9:.3f} GB | ${csv_row['usd']:.4f} "
            f"| {pq_row['bytes_scanned'] / 1e9:.3f} GB | ${pq_row['usd']:.4f} | {saved:.1%} |"
        )
    COST_TABLE.write_text("\n".join(lines) + "\n")
    print(f"wrote {COST_LOG.relative_to(ROOT)} and {COST_TABLE.relative_to(ROOT)}")


def check_locally() -> None:
    for bench in BENCHMARKS:
        df = execute(f"{bench}_parquet", backend="local").df
        print(f"{bench}_parquet: {len(df):,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="run the Parquet SQL locally")
    args = parser.parse_args()
    if args.check:
        check_locally()
    else:
        compare()


if __name__ == "__main__":
    main()
