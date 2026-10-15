# Delay Stats Analysis

**Where do delivery delays come from, did anything we changed help, and what should we stop believing?**

A formal hypothesis-testing study of US airline arrival delays, written up as a short memo an operations director can act on. Flights stand in for shipments: scheduled vs actual arrival, carrier-reported delay causes, carriers as vendors, airports as sites. The data is the Bureau of Transportation Statistics' on-time performance record, queried on Amazon Athena over partitioned Parquet in S3.

The deliverable is the memo, not the notebook: plain language first, statistics in parentheses, and every caveat written as a consequence for decisions. A build step fails if any number in the memo cannot be traced to the results files.

## The questions

All four hypotheses, the tests, alpha (0.05, two-sided) and the practical-significance thresholds were pre-registered in [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md) and frozen before any data was loaded. Departures are logged in `docs/DEVIATIONS.md`, never edited into the plan.

| | Question | Primary test | Robustness | Effect size |
|---|---|---|---|---|
| H1 | Did mean arrival delay at Seattle-Tacoma change between summer 2023 and summer 2024? | Welch's t-test | Mann-Whitney U, bootstrapped CI (10,000 resamples), day-level Welch's t | Hedges' g with CI, and the raw difference in minutes against a 2-minute practical threshold |
| H2 | Is the primary delay cause independent of carrier, among flights delayed 15+ minutes? | Pearson chi-squared | Expected-count check with a pre-registered merge of rare causes | Bias-corrected Cramér's V with CI; adjusted standardized residuals per cell |
| H3 | Is a route's mean delay associated with distance and with origin congestion? | Pearson r and Spearman rho | Partial correlation controlling for month of year | r and rho with CIs (Fisher z, bootstrap) |
| H4 | For each of the top 8 carriers in 2025, is its mean delay different from everyone else's? | Welch's t-test per carrier | Bonferroni and Benjamini-Hochberg corrections | A table of which conclusions flip under correction |

A power analysis states the minimum detectable difference for H1's day-level test, and shows why, with tens of thousands of flights, even half a minute is "significant": the reason practical thresholds are part of the plan.

## Method

**Every result carries the same fields.** Each test in `src/delaystats/stats_helpers.py` returns a `TestResult`: test name, statistic, degrees of freedom, p-value, effect size with a 95% CI, and n per group, plus the estimate in natural units (minutes) where one exists. No p-value is reported without an effect size, and "significant" is never written without the alpha and the correction method.

**Statistically significant is not the same as meaningful.** H1's verdict is read from the confidence interval of the raw difference: entirely beyond 2 minutes, entirely within it, or straddling it.

**Clustering is taken seriously.** Flights share aircraft, days and airport weather, so flight-level tests overstate certainty. Every test that assumes independence has a clustered or aggregated check alongside it, and the day-level results are the ones the memo leans on.

**The test helpers are verified against known answers**, each against at least one case that can be checked by hand or a published reference:

| Helper | Checked against |
|---|---|
| `welch_t` | Welch t, Welch-Satterthwaite df, CI of the difference, Hedges' g and its CI, worked by hand |
| `mann_whitney` | scipy documentation example (U = 17, p = 0.1111); rank-biserial 0.7 |
| `bootstrap_mean_diff` | Constant groups give an exact CI; fixed seed reproduces |
| `chi2_independence` | scipy documentation example (chi-squared 2.778, p = 0.2494); adjusted residual and corrected Cramér's V by hand |
| `pearson_with_ci`, `spearman_with_bootstrap_ci` | r = sqrt(0.6) by hand with its Fisher z CI; scipy example (rho = 0.8208) |
| `partial_corr` | First-order partial correlation formula |
| `multiple_comparison_table` | Benjamini-Hochberg textbook case: BH keeps all 5 of p = 0.01 to 0.05, Bonferroni keeps 1 |
| `power_min_detectable` | Cohen's table: 64 per group detects d = 0.5 at 80% power |

## Data and pipeline

```mermaid
flowchart LR
    bts[BTS monthly zips<br/>Jan 2023 onward] -->|ingest.py: header check| landing[(S3 landing/csv<br/>year=/month=)]
    landing -->|typed, snappy Parquet<br/>+ primary_delay_cause| curated[(S3 curated/parquet<br/>year=/month=)]
    curated --> glue[Glue Data Catalog<br/>explicit schema,<br/>partition projection]
    glue --> athena[Athena workgroup<br/>bytes-scanned cap]
    athena -->|queries/*.sql| nb[Notebooks:<br/>profile, H1 to H4, power]
    nb --> results[reports/results.csv<br/>figures/]
    results --> memo[memo.md + PDF]
```

- **Source:** BTS Reporting Carrier On-Time Performance, monthly files from January 2023, 27 columns kept. Downloads are validated against the expected header; if scripted downloads are blocked, ingestion takes a folder of manually downloaded zips instead of scraping around the block.
- **Derived column:** `primary_delay_cause`, the cause with the most delay minutes, or `NONE` / `TIE`.
- **Explicit schema:** Glue tables are defined in Terraform, not by a crawler, with partition projection on year and month.
- **Every query is a file:** Athena SQL lives in `queries/`, and each execution logs its bytes scanned.

**Cost is measured, not estimated.** `make cost-compare` runs four benchmark queries (single-month partition pruning, a cause distribution for one airport, a full-table count, and the H3 feature extraction) against both the raw CSV table and the partitioned Parquet table. It records bytes scanned and dollars from Athena's own execution statistics in `reports/cost_log.csv`; then the CSV copy is deleted.

## What this does not tell us

The memo addresses each of these as a consequence for decisions, not as a disclaimer:

- **Observational data, no randomization:** nothing here is causal.
- **Clustering inflates flight-level significance;** the day-level results are the honest ones.
- **Cancelled and diverted flights are excluded,** so average delay can improve while service gets worse. The cancellation rate is reported alongside.
- **Delay causes are carrier-reported.**
- **Survivorship:** routes with fewer than 30 flights a month are excluded from H3.

## Repository layout

```
src/delaystats/   ingest, athena runner, stats helpers, plotting, memo appendix and number check
queries/          every Athena query as a .sql file
notebooks/        data profile, one notebook per hypothesis, power analysis
reports/          memo, results.csv, cost_log.csv, figures/
infra/            Terraform: S3, Glue, Athena workgroup
docs/             spec, pre-registered analysis plan, memo template
```

## How to run

Prerequisites: [uv](https://docs.astral.sh/uv/) and GNU Make; Python 3.12 is installed by uv. AWS steps need a profile in `.env` (see `.env.example`).

```sh
make setup
make test                       # stats helpers against reference values
make tf-apply                   # S3 bucket, Glue database, Athena workgroup
make ingest YEARS=2023,2024,2025
make cost-compare               # CSV vs Parquet bytes scanned and cost
make notebooks                  # every notebook headless, top to bottom
make memo-pdf                   # memo with figures; fails if any number is untraceable
make teardown
```

## Implementation status

| Part | Status |
|---|---|
| Pre-registered analysis plan | Frozen 2026-10-14, before any data was loaded |
| Statistical test helpers | Built and verified (above) |
| Ingestion, Athena tables, cost comparison, notebooks, memo | Specified in `docs/`, not yet run; runs on an AWS free-plan account and is torn down afterwards |
