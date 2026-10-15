# CLAUDE.md: delay-stats-analysis

## What this repo is

A statistical analysis of US airline arrival delays using the Bureau of Transportation Statistics (BTS) Reporting Carrier On-Time Performance data. Raw monthly files land in Amazon S3, are converted to partitioned Parquet, registered in the AWS Glue Data Catalog, and queried with Amazon Athena. Analysis runs in Jupyter notebooks with scipy, statsmodels and pingouin. The headline deliverable is a written memo, not the notebook.

Read `docs/SPEC.md`, `docs/ANALYSIS_PLAN.md`, `docs/MEMO_TEMPLATE.md` and `docs/BUILD_PLAN.md` before writing code.

## Division of labor

Claude Code builds everything, including interpretation and the memo. The pre-registered plan in `docs/ANALYSIS_PLAN.md` is already filled in and frozen.

Rules for interpretation and the memo:
- Every number in an interpretation cell or in `reports/memo.md` must come from `reports/results.csv` or `reports/cost_log.csv`. The memo build script checks this: it fails if any number in the memo is not found in those files or is not a simple derivation of them, which are listed in `reports/derived_numbers.csv` with the formula used.
- Interpretation follows the evidence even if it is boring or negative. A null result is reported as a null result, with the minimum detectable effect from the power analysis.
- Separate "statistically significant" from "practically meaningful" in every finding, using the practical threshold from ANALYSIS_PLAN.md.
- Write the memo for an operations director: plain language first, statistics in parentheses.
- After the memo, write `docs/INTERVIEW_PREP.md`. For each hypothesis it contains:
  - why this test and not the obvious alternative
  - what each assumption check showed
  - what would change the conclusion
  - three likely interviewer questions with answers
  The owner studies this file. They have to be able to defend every choice without notes.

## Hard rules

- Hypotheses in `docs/ANALYSIS_PLAN.md` are pre-registered. Do not add, drop or reword hypotheses, and do not change alpha, after looking at results. If a planned test turns out to be invalid (assumptions fail), apply the pre-registered fallback and log it in `docs/DEVIATIONS.md`.
- Every reported test result includes: test name, statistic, degrees of freedom where applicable, p-value, effect size with 95% CI, n per group.
- Never report a p-value without an effect size.
- Never print "significant" without stating the alpha and the correction method.
- All figures saved to `reports/figures/` as PNG at 150 dpi with descriptive filenames, plus the code that made them in a script (not only in a notebook).
- Notebooks must run top to bottom with `jupyter nbconvert --execute`. No hidden state.
- Athena queries live as `.sql` files in `queries/`, never as inline strings longer than one line.
- Never hardcode credentials or account IDs. Tag AWS resources `project=delay-stats-analysis`.

## Stack

- Python 3.12 with uv. pandas, pyarrow, awswrangler (AWS SDK for pandas), scipy, statsmodels, pingouin, matplotlib, seaborn, jupyter, papermill.
- Terraform for S3 bucket, Glue database, Athena workgroup with query result location and per-query bytes-scanned limit.
- ruff, mypy on `src/`, pytest.

## Layout

```
src/delaystats/
  ingest.py         download/unzip/convert/upload
  athena.py         run .sql with params, return DataFrame, log bytes scanned
  stats_helpers.py  wrappers that return a standard TestResult dataclass
  plotting.py
queries/
notebooks/
  01_data_profile.ipynb
  02_h1_ttest.ipynb
  03_h2_chisq.ipynb
  04_h3_correlation.ipynb
  05_h4_multiple_comparisons.ipynb
  06_power.ipynb
reports/
  figures/
  memo.md           narrative memo (see MEMO_TEMPLATE.md)
  derived_numbers.csv
  cost_log.csv
infra/
docs/
```

## Commands

```
make setup
make ingest YEARS=2023,2024,2025
make tf-apply / teardown
make crawl          # create/update Glue table
make cost-compare   # run benchmark queries on CSV vs Parquet tables, write cost_log.csv
make notebooks      # execute all notebooks headless
make test
```
