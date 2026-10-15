"""Move ingested data to S3 and check row counts.

    python -m delaystats.storage upload         # landing/csv (from the zips) + curated/parquet
    python -m delaystats.storage verify-counts  # count(*) per month vs source lines

The bucket comes from Terraform (`terraform -chdir=infra output -raw bucket`) or BUCKET.
verify-counts runs on the backend DELAYSTATS_BACKEND selects, so it checks the local Parquet
before deployment and the Glue/Athena table after.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import zipfile

from delaystats.athena import run_query
from delaystats.ingest import CURATED, INGEST_LOG, ROOT, ZIPS


def _bucket() -> str:
    if os.environ.get("BUCKET"):
        return os.environ["BUCKET"]
    return subprocess.run(
        ["terraform", f"-chdir={ROOT / 'infra'}", "output", "-raw", "bucket"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def upload() -> None:
    import boto3

    s3 = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE") or None,
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    ).client("s3")
    bucket = _bucket()
    for zip_path in sorted(ZIPS.glob("*.zip")):
        year, month = zip_path.stem.split("_")
        with zipfile.ZipFile(zip_path) as archive:
            member = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
            with archive.open(member) as body:
                key = f"landing/csv/year={year}/month={month}/data.csv"
                s3.upload_fileobj(body, bucket, key)
        print(f"s3://{bucket}/landing/csv/year={year}/month={month}/")
    for path in sorted(CURATED.rglob("*.parquet")):
        key = f"curated/parquet/{path.relative_to(CURATED).as_posix()}"
        s3.upload_file(str(path), bucket, key)
    print(f"s3://{bucket}/curated/parquet/ ({len(list(CURATED.rglob('*.parquet')))} files)")


def verify_counts() -> None:
    source = {
        (int(r["year"]), int(r["month"])): int(r["source_rows"])
        for r in csv.DictReader(INGEST_LOG.open())
    }
    table = {
        (int(r["year"]), int(r["month"])): int(r["row_count"])
        for r in run_query("count_by_month").to_dict("records")
    }
    print(f"{'month':<8} {'source rows':>12} {'table rows':>12}")
    for key in sorted(source.keys() | table.keys()):
        status = "" if source.get(key) == table.get(key) else "  MISMATCH"
        print(f"{key[0]}-{key[1]:02d} {source.get(key, 0):>12,} {table.get(key, 0):>12,}{status}")
    total_source, total_table = sum(source.values()), sum(table.values())
    print(f"{'total':<8} {total_source:>12,} {total_table:>12,}")
    if source != table:
        sys.exit("row counts differ")
    print(f"all {len(source)} months match")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("command", choices=["upload", "verify-counts"])
    args = parser.parse_args()
    if args.command == "upload":
        upload()
    else:
        verify_counts()


if __name__ == "__main__":
    main()
