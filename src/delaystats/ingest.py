"""Download BTS on-time performance files, validate them, and convert them to typed Parquet.

    python -m delaystats.ingest --years 2023,2024,2025,2026
    python -m delaystats.ingest --years 2023 --local-dir ~/Downloads/bts   # manually downloaded

Each month: data/zips/YYYY_MM.zip (download cache) -> header check against SPEC section 2 ->
data/curated/parquet/year=YYYY/month=MM/part-0000.parquet (snappy, typed, with
primary_delay_cause). The CSV inside the zip is what lands in S3 landing/csv/ at upload time.
Rows per month (source lines vs Parquet rows) go to data/ingest_log.csv.

year and month are partition keys only (they come back from the path): Athena column names
are case-insensitive, so Year/Month columns would collide with the partition keys.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pcsv
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ZIPS = DATA / "zips"
CURATED = DATA / "curated" / "parquet"
INGEST_LOG = DATA / "ingest_log.csv"
URL = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)

# SPEC section 2, in file order, with the typed schema of SPEC section 3.
COLUMNS: dict[str, pa.DataType] = {
    "Year": pa.int32(),
    "Month": pa.int32(),
    "DayofMonth": pa.int32(),
    "DayOfWeek": pa.int32(),
    "FlightDate": pa.date32(),
    "Reporting_Airline": pa.string(),
    "Tail_Number": pa.string(),
    "Flight_Number_Reporting_Airline": pa.int32(),
    "Origin": pa.string(),
    "OriginState": pa.string(),
    "Dest": pa.string(),
    "DestState": pa.string(),
    "CRSDepTime": pa.int32(),
    "DepDelay": pa.int32(),
    "CRSArrTime": pa.int32(),
    "ArrDelay": pa.int32(),
    "ArrDelayMinutes": pa.int32(),
    "ArrDel15": pa.int32(),
    "Cancelled": pa.int32(),
    "CancellationCode": pa.string(),
    "Diverted": pa.int32(),
    "Distance": pa.int32(),
    "CarrierDelay": pa.int32(),
    "WeatherDelay": pa.int32(),
    "NASDelay": pa.int32(),
    "SecurityDelay": pa.int32(),
    "LateAircraftDelay": pa.int32(),
}
PARTITION_COLUMNS = ("Year", "Month")
CAUSES = {
    "CarrierDelay": "Carrier",
    "WeatherDelay": "Weather",
    "NASDelay": "NAS",
    "SecurityDelay": "Security",
    "LateAircraftDelay": "LateAircraft",
}


class HeaderError(ValueError):
    pass


class DownloadBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class MonthResult:
    year: int
    month: int
    source_rows: int
    parquet_rows: int


def _csv_member(archive: zipfile.ZipFile) -> str:
    names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
    if len(names) != 1:
        raise HeaderError(f"expected one CSV in the zip, found {names}")
    return names[0]


def validate_header(header: list[str]) -> None:
    missing = [column for column in COLUMNS if column not in header]
    if missing:
        raise HeaderError(f"BTS file is missing columns: {', '.join(missing)}")


def primary_delay_cause(table: pa.Table) -> pa.Array:
    """The cause with the most minutes; NONE when not delayed 15+ or no minutes; TIE on a tie."""
    minutes = np.column_stack(
        [pc.fill_null(table[c], 0).to_numpy(zero_copy_only=False) for c in CAUSES]
    )
    largest = minutes.max(axis=1)
    ties = (minutes == largest[:, None]).sum(axis=1) > 1
    names = np.array(list(CAUSES.values()), dtype=object)[minutes.argmax(axis=1)]
    delayed = pc.fill_null(table["ArrDel15"], 0).to_numpy(zero_copy_only=False) == 1
    cause = np.where(~delayed | (largest == 0), "NONE", np.where(ties, "TIE", names))
    return pa.array(cause, pa.string())


def read_month(zip_path: Path) -> tuple[pa.Table, int]:
    """Typed table for one month plus the number of data lines in the source CSV."""
    with zipfile.ZipFile(zip_path) as archive:
        data = archive.read(_csv_member(archive))
    header = next(csv.reader(io.StringIO(data[: data.index(b"\n")].decode("utf-8-sig"))))
    validate_header(header)
    source_rows = data.count(b"\n") - 1 + (0 if data.endswith(b"\n") else 1)

    raw = pcsv.read_csv(
        io.BytesIO(data),
        convert_options=pcsv.ConvertOptions(
            include_columns=list(COLUMNS),
            column_types={
                # decimals such as "-12.00" and "1.00": parse as float, then cast exactly
                name: (pa.float64() if pa.types.is_integer(kind) else kind)
                for name, kind in COLUMNS.items()
            },
            strings_can_be_null=True,
        ),
    )
    typed = pa.table(
        {
            name: raw[name].cast(kind, safe=True)
            for name, kind in COLUMNS.items()
            if name not in PARTITION_COLUMNS
        }
    )
    typed = typed.append_column("primary_delay_cause", primary_delay_cause(typed))
    return typed, source_rows


def partition_path(year: int, month: int) -> Path:
    return CURATED / f"year={year}" / f"month={month:02d}" / "part-0000.parquet"


RETRIES = 5
CHUNK = 1 << 20


def download(year: int, month: int) -> Path | None:
    """Cached download; None if BTS has not published the month yet.

    Streams to a .part file and, when the connection drops (BTS does this on large files),
    resumes from where it stopped with an HTTP Range request.
    """
    target = ZIPS / f"{year}_{month:02d}.zip"
    if target.exists():
        return target
    ZIPS.mkdir(parents=True, exist_ok=True)
    url = URL.format(year=year, month=month)
    partial = target.with_suffix(".part")
    partial.unlink(missing_ok=True)
    total: int | None = None
    for attempt in range(1, RETRIES + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(
            url, headers={"Range": f"bytes={offset}-"} if offset else {}
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                if "zip" not in response.headers.get("Content-Type", ""):
                    raise DownloadBlocked(url)
                if offset and response.status != 206:
                    offset = 0  # server ignored the range: start over
                if total is None:
                    total = offset + int(response.headers["Content-Length"])
                with partial.open("ab" if offset else "wb") as out:
                    while chunk := response.read(CHUNK):
                        out.write(chunk)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise DownloadBlocked(url) from error
        except (http.client.IncompleteRead, ConnectionError, TimeoutError, urllib.error.URLError):
            if attempt == RETRIES:
                raise
            time.sleep(5 * attempt)
            continue
        if total is not None and partial.stat().st_size == total:
            partial.replace(target)
            return target
    raise DownloadBlocked(f"{url} (incomplete after {RETRIES} attempts)")


def from_local_dir(directory: Path, year: int, month: int) -> Path | None:
    """A manually downloaded month: BTS names it ..._{year}_{month}.zip."""
    matches = sorted(directory.glob(f"*_{year}_{month}.zip"))
    return matches[0] if matches else None


def ingest_month(zip_path: Path, year: int, month: int) -> MonthResult:
    table, source_rows = read_month(zip_path)
    target = partition_path(year, month)
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="snappy")
    return MonthResult(year, month, source_rows, table.num_rows)


MANUAL_INSTRUCTIONS = """
BTS blocked the scripted download of {url}.
Download the monthly files in a browser instead:
  1. Open https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
  2. Tick "Prezipped File", pick each year and month, and download.
  3. Put the zips in one folder and run:
       python -m delaystats.ingest --years {years} --local-dir <that folder>
"""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--years", required=True, help="comma-separated, e.g. 2023,2024,2025")
    parser.add_argument("--local-dir", type=Path, help="folder of manually downloaded zips")
    args = parser.parse_args(argv)
    years = [int(y) for y in args.years.split(",")]

    results: list[MonthResult] = []
    for year in years:
        for month in range(1, 13):
            try:
                zip_path = (
                    from_local_dir(args.local_dir, year, month)
                    if args.local_dir
                    else download(year, month)
                )
            except DownloadBlocked as blocked:
                sys.exit(MANUAL_INSTRUCTIONS.format(url=blocked, years=args.years))
            if zip_path is None:
                print(f"{year}-{month:02d}: not published yet, skipped")
                continue
            result = ingest_month(zip_path, year, month)
            results.append(result)
            status = "ok" if result.source_rows == result.parquet_rows else "MISMATCH"
            print(
                f"{year}-{month:02d}: {result.source_rows:>9,} source rows, "
                f"{result.parquet_rows:>9,} parquet rows  {status}"
            )

    previous = {}
    if INGEST_LOG.exists():
        previous = {(int(r["year"]), int(r["month"])): r for r in csv.DictReader(INGEST_LOG.open())}
    for r in results:
        previous[(r.year, r.month)] = {
            "year": r.year,
            "month": r.month,
            "source_rows": r.source_rows,
            "parquet_rows": r.parquet_rows,
        }
    with INGEST_LOG.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "month", "source_rows", "parquet_rows"])
        writer.writeheader()
        writer.writerows(previous[key] for key in sorted(previous))
    if any(r.source_rows != r.parquet_rows for r in results):
        sys.exit("row counts differ between source and Parquet")


if __name__ == "__main__":
    main()
