# BUILD PLAN: Delay Stats Analysis

$0 plan: Phases 0 and 3 run locally with no AWS account. Phases 1, 2, 4, 5 run on an AWS free plan account (S3, Glue, Athena are covered by Free Tier credits). Phase 7 tears everything down. See docs/DEPLOY_WINDOW.md.

## Phase 0: Scaffold
- Layout from CLAUDE.md, pyproject with uv, Makefile, CI (ruff, mypy, pytest), `.env.example`.
- Acceptance: `make setup` and `make test` pass; CI green.

## Phase 1: Infrastructure and ingestion
- Terraform: S3 bucket (landing/curated/athena-results prefixes, lifecycle rule expiring athena-results after 7 days), Glue database, Athena workgroup with enforced result location and BytesScannedCutoffPerQuery.
- `ingest.py`: download or `--local-dir`, unzip, validate header against SPEC column list, upload CSV to landing, convert to typed Parquet partitioned by year/month, upload to curated.
- Glue table definitions created by Terraform or awswrangler (not a crawler, so schema is explicit). Partition projection on year/month.
- Acceptance:
  - Athena `select count(*)` per month matches the source file line counts minus headers (print the comparison).
  - Header validation failure produces a clear error naming the missing columns.
  - Header differences, if any, recorded in DEVIATIONS.md.

## Phase 2: Cost comparison and data profile
- `make cost-compare` per SPEC section 4; output `reports/cost_log.csv` and a markdown table.
- `01_data_profile.ipynb`: row counts by month, null rates per column, ArrDelay distribution (log-scaled histogram), cancellation rate by month, carriers by volume, verification that cause minutes sum approximately to ArrDelay for delayed flights.
- Acceptance: notebook executes headless; cost table shows bytes and USD for both formats on all 4 queries.
- Then drop `ontime_csv` and its S3 prefix.

## Phase 3: Helpers (ANALYSIS_PLAN.md is already frozen)
- `stats_helpers.py`: functions returning a `TestResult` dataclass (name, statistic, df, p, effect_size, effect_ci, n, notes) for: welch_t, mann_whitney, bootstrap_mean_diff, chi2_independence (with expected table, Cramér's V bias-corrected, adjusted residuals), pearson_with_ci, spearman_with_bootstrap_ci, partial_corr, multiple_comparison_table, power_min_detectable.
- Unit tests against known textbook values (e.g. scipy docs examples) for every helper.
- Acceptance: pytest passes with each helper tested against at least one hand-verifiable case.

## Phase 4: Hypothesis notebooks
- One notebook per H1 to H4 plus power. Each: load via `queries/*.sql`, assumption checks, primary test, robustness checks, figures saved via `plotting.py`, a results table cell, and an interpretation cell written under the rules in CLAUDE.md.
- Acceptance: `make notebooks` executes all; `reports/results.csv` contains every TestResult; every figure exists in `reports/figures/`.

## Phase 5: Memo
- Script `src/delaystats/build_appendix.py` generates Appendix B table and D cost section as markdown from `results.csv` and `cost_log.csv`.
- Write `reports/memo.md` following MEMO_TEMPLATE.md, 2 to 3 pages before the appendix.
- `src/delaystats/check_memo_numbers.py`: extracts every number from the memo body and fails if any is not in `results.csv`, `cost_log.csv` or `derived_numbers.csv`.
- Pandoc export of `reports/memo.md` to PDF with figures.
- Write `docs/INTERVIEW_PREP.md` per CLAUDE.md.
- Acceptance: number check passes; `make memo-pdf` produces the PDF; Claude Code reads the PDF pages and confirms figures render and the body is within 3 pages.

## Phase 6: README
- Question, data, pipeline diagram, cost table, key findings in 3 sentences linking the memo, limitations, how to reproduce.
- `docs/RESUME_BULLETS.md`: 2 bullets with numbers (rows analyzed, cost reduction from Parquet, tests applied).

## Phase 7: Evidence capture and teardown
- Commit `reports/memo.pdf`, all figures, `results.csv`, `cost_log.csv` (memo and figures stay valid after teardown).
- Publish a one-page GitHub Pages site (`site/index.html`): question, three headline findings with their caveats, key figures, link to memo PDF and repo.
- README states the analysis ran on Amazon Athena over <N> rows between <dates> and that the S3 data was deleted afterwards; `make ingest` + `make tf-apply` reproduce it.
- `make teardown`: drop Glue database and tables, Athena workgroup, empty and delete the S3 bucket, then the state bucket. Verify with the tag-based resource search returning nothing for `project=delay-stats-analysis`.
