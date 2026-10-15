"""Run a query file from queries/ and return a DataFrame.

    df = run_query("h1_sea_summer_flights", {"year_a": 2023, "year_b": 2024})

Queries are Athena SQL against the Glue table `ontime`; `$name` placeholders are filled from
params (values are validated: numbers, ISO dates or codes only). Two backends, chosen by
DELAYSTATS_BACKEND:

- athena (the deployed system): runs in the delaystats-wg workgroup and appends bytes scanned
  and cost to reports/query_log.csv
- local (default): DuckDB over data/curated/parquet with the SQL transpiled by sqlglot, so the
  analysis runs on the same data before or after the AWS deployment
"""

from __future__ import annotations

import csv
import io
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import duckdb
import pandas as pd
import sqlglot

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "queries"
QUERY_LOG = ROOT / "reports" / "query_log.csv"
CURATED_GLOB = (ROOT / "data" / "curated" / "parquet" / "*" / "*" / "*.parquet").as_posix()
SAFE_PARAM = re.compile(r"^[A-Za-z0-9_\-:. ]+$")
ATHENA_USD_PER_TB = float(os.environ.get("ATHENA_USD_PER_TB", "5.0"))

Param = str | int | float


@dataclass(frozen=True)
class QueryResult:
    df: pd.DataFrame
    bytes_scanned: int | None  # Athena only
    execution_id: str | None


def render(name: str, params: dict[str, Param] | None = None) -> str:
    for key, value in (params or {}).items():
        if not SAFE_PARAM.match(str(value)):
            raise ValueError(f"unsafe value for ${key}: {value!r}")
    return Template((QUERIES / f"{name}.sql").read_text()).substitute(params or {})


def _local(sql: str) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute(
        "create view ontime as select * exclude (month), cast(month as integer) as month "
        f"from read_parquet('{CURATED_GLOB}', hive_partitioning = true)"
    )
    duck_sql = sqlglot.transpile(sql, read="athena", write="duckdb")[0]
    df = con.sql(duck_sql).df()
    df.columns = [str(c).lower() for c in df.columns]  # Athena returns lowercase names
    return df


def _athena(sql: str, name: str) -> QueryResult:
    import boto3

    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE") or None,
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )
    athena = session.client("athena")
    execution_id = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": os.environ.get("GLUE_DATABASE", "delaystats")},
        WorkGroup=os.environ.get("ATHENA_WORKGROUP", "delaystats-wg"),
    )["QueryExecutionId"]
    while True:
        execution = athena.get_query_execution(QueryExecutionId=execution_id)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if state != "SUCCEEDED":
        raise RuntimeError(f"{name}: {state}: {execution['Status'].get('StateChangeReason')}")

    scanned = int(execution["Statistics"]["DataScannedInBytes"])
    log_query(name, execution_id, scanned)
    bucket, key = (
        execution["ResultConfiguration"]["OutputLocation"].removeprefix("s3://").split("/", 1)
    )
    body = session.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    return QueryResult(pd.read_csv(io.BytesIO(body)), scanned, execution_id)


def log_query(name: str, execution_id: str, scanned_bytes: int) -> None:
    QUERY_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not QUERY_LOG.exists()
    with QUERY_LOG.open("a", newline="") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["run_at", "query", "execution_id", "bytes_scanned", "usd"])
        writer.writerow(
            [
                datetime.now(UTC).isoformat(timespec="seconds"),
                name,
                execution_id,
                scanned_bytes,
                round(scanned_bytes / 1e12 * ATHENA_USD_PER_TB, 6),
            ]
        )


def execute(
    name: str, params: dict[str, Param] | None = None, backend: str | None = None
) -> QueryResult:
    sql = render(name, params)
    chosen = backend or os.environ.get("DELAYSTATS_BACKEND", "local")
    if chosen == "athena":
        return _athena(sql, name)
    if chosen == "local":
        return QueryResult(_local(sql), None, None)
    raise ValueError(f"unknown backend {chosen!r}")


def run_query(
    name: str, params: dict[str, Param] | None = None, backend: str | None = None
) -> pd.DataFrame:
    return execute(name, params, backend).df
