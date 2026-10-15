# Deviations

Every departure from the pre-registered plan (docs/ANALYSIS_PLAN.md) or from the project's design, with the reason. Entries are added, never edited away.

## 2026-10-15: data and ingestion

**Header check against the real BTS file.** All 27 columns the analysis uses are present with exactly those names in the January 2023 file. Two format details worth recording:

- The header ends with a trailing comma, so the file has a 110th, unnamed column. Ingestion reads only the 27 named columns; the raw CSV table declares the 109 named columns and ignores the empty one.
- Numeric fields are written as decimals (`-12.00`, flags as `1.00`). Ingestion parses them as floats and casts to integers with a check that no fractional part is lost, as the typed schema requires.

**Period.** The design is January 2023 through the latest available month. On 2026-10-15 BTS had published through July 2026 (August 2026 returned 404), so the data covers 43 months. The hypotheses use only the windows the plan names (H1: summers 2023 and 2024; H2 and H3: January 2023 to December 2025; H4: 2025); later months appear only in the data profile.

**Year and month as partition keys only.** The Parquet files do not contain the Year and Month columns: they are the `year=`/`month=` partition keys, which Athena (case-insensitive column names) would otherwise see twice. Queries read `year` and `month` from the partition.

**primary_delay_cause edge case.** The design defines the cause as the largest of the five cause columns, NONE when ArrDel15 = 0 and TIE on a tie. Flights with ArrDel15 = 1 but zero minutes in every cause column (no cause reported) are also labelled NONE. H2 drops NONE and TIE and reports how many rows that removed.

**Local backend before deployment.** The same `queries/*.sql` run on two backends: Athena (the deployed system) and DuckDB over the same Parquet (SQL transpiled with sqlglot). The analysis was first run locally on the real BTS data; the Athena run repeats it and must reproduce `reports/results.csv`. Cost figures (Athena bytes scanned) exist only from the Athena run.
