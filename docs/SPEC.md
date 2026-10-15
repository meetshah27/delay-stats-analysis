# SPEC: Delay Stats Analysis

## 1. Purpose

Demonstrate formal hypothesis testing on a large, real, messy dataset, and communicate results with explicit caveats in a short narrative memo that a non-technical leader could act on.

Business framing: an operations leader asks, "Where do delivery delays come from, did anything we changed help, and what should we stop believing?" Flights are the stand-in for shipments: scheduled vs actual arrival, delay cause codes, carriers as vendors, airports as sites.

## 2. Data source

BTS TranStats, "Reporting Carrier On-Time Performance (1987 to present)", monthly files. Use January 2023 through the latest available month.

Download: the TranStats download page is form-based. Implement `ingest.py` to fetch the prezipped monthly files if a stable URL pattern is available; if downloads are blocked or the pattern fails, the script must print exact manual download instructions and accept a local folder of zips via `--local-dir`. Do not scrape around blocks.

Columns to keep (names as in BTS file): `Year`, `Month`, `DayofMonth`, `DayOfWeek`, `FlightDate`, `Reporting_Airline`, `Tail_Number`, `Flight_Number_Reporting_Airline`, `Origin`, `OriginState`, `Dest`, `DestState`, `CRSDepTime`, `DepDelay`, `CRSArrTime`, `ArrDelay`, `ArrDelayMinutes`, `ArrDel15`, `Cancelled`, `CancellationCode`, `Diverted`, `Distance`, `CarrierDelay`, `WeatherDelay`, `NASDelay`, `SecurityDelay`, `LateAircraftDelay`.

Verify column names against the actual file header in Phase 1; record any differences in `docs/DEVIATIONS.md`.

## 3. Pipeline

```
monthly zip (CSV) -> S3 landing/csv/year=YYYY/month=MM/
                  -> convert -> S3 curated/parquet/year=YYYY/month=MM/ (snappy, typed)
Glue Data Catalog: db delaystats, tables ontime_csv (for comparison only) and ontime
Athena workgroup delaystats-wg: result location in S3, BytesScannedCutoffPerQuery set
```

Typed schema: integers for delays and flags, `DATE` for FlightDate, strings for codes. Add derived column `primary_delay_cause` (the cause with the largest minutes among the five cause columns, `NONE` if ArrDel15 = 0, `TIE` if tied).

## 4. Cost measurement (Frugality)

`make cost-compare` runs the same 4 benchmark queries against `ontime_csv` and `ontime` (partitioned Parquet), pulls `DataScannedInBytes` from `GetQueryExecution`, converts to USD using the Athena per-TB price stored in config (set manually from the pricing page), and writes `reports/cost_log.csv`. Then delete the CSV table and prefix to stop paying for storage.

Benchmark queries:
1. Mean ArrDelay by carrier for one month (partition pruning).
2. Delay cause distribution across all months for SEA.
3. Full-table count of cancelled flights.
4. The H3 correlation feature extraction query.

## 5. Analysis

Defined in `ANALYSIS_PLAN.md`.

## 6. Deliverables

- `reports/memo.md` and PDF export: 2 to 3 pages, structure in MEMO_TEMPLATE.md.
- Notebooks that reproduce every number in the memo.
- README: question, data, pipeline diagram, cost table, link to memo, limitations.
- `docs/DEVIATIONS.md`: every departure from the pre-registered plan and why.
