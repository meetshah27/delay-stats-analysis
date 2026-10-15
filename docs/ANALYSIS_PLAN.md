# ANALYSIS PLAN (pre-registered)

Status: FROZEN as of 2026-10-14, before any data was loaded. All decisions below were made without looking at results. Changes after this date go in `docs/DEVIATIONS.md` with a reason; they never overwrite this file.

Global settings
- Alpha: 0.05, two-sided unless stated.
- Unit of analysis: one non-cancelled, non-diverted flight, unless stated.
- Outlier policy: keep all values; delays are naturally heavy-tailed. Report robustness with trimmed or rank-based tests instead of deleting data.
- Independence caveat: flights are clustered (same aircraft, same day, same airport weather). Every test that assumes independence must also report a clustered or aggregated robustness check as specified below.

## H1: Two-group mean difference (t-test)

Question: Did mean arrival delay for flights arriving at SEA (Seattle-Tacoma, Dest = 'SEA') change between summer 2023 (June 1 to August 31, 2023) and summer 2024 (June 1 to August 31, 2024)?

- Why SEA and summer: same season in both years removes seasonality; a single airport keeps weather and infrastructure roughly constant; summer is peak volume, so the operational question matters most then.

- H0: mean ArrDelay equal in both periods. H1: not equal.
- Primary test: Welch's t-test (unequal variances).
- Why Welch: group variances and sizes differ; Welch is safe when they are equal too.
- Assumption checks: Q-Q plot per group, Levene's test (report, do not gate on it), group sizes.
- Robustness:
  - Mann-Whitney U (tests distribution shift, not means; say so).
  - Bootstrapped 95% CI of the mean difference (10,000 resamples, seed fixed).
  - Day-level aggregation: compute daily mean delay, then Welch's t on days (n about 92 per group). This addresses within-day clustering.
- Effect size: Cohen's d (Hedges' g correction) with CI; also the raw difference in minutes, which is what a leader cares about.
- Practical significance threshold: 2 minutes of mean arrival delay. A difference smaller than that is treated as operationally meaningless even if statistically significant. State whether the 95% CI lies entirely beyond 2 minutes, entirely within it, or straddles it.

## H2: Independence of categorical variables (chi-squared)

Question: Is the primary delay cause independent of carrier, among flights delayed 15+ minutes?

- Contingency table: carrier (rows, the top 8 carriers by number of flights delayed 15+ minutes over January 2023 to December 2025, all others grouped as OTHER) x primary_delay_cause (Carrier, Weather, NAS, Security, LateAircraft). Drop TIE and NONE, and report how many rows that removed.
- H0: independent.
- Test: Pearson chi-squared test of independence.
- Assumption: expected count >= 5 in every cell; print the expected table. If Security violates it, merge Security into NAS and log the deviation.
- Effect size: Cramér's V with bias correction (Bergsma). At this n, p will be tiny; V is what matters. Interpret V using the standard small/medium/large thresholds for the table's degrees of freedom.
- Post-hoc: adjusted standardized residuals per cell; flag |r| > 3 as notable. Heat map of residuals.

## H3: Correlation

Question: Is a route's mean arrival delay associated with (a) distance and (b) origin airport congestion?

- Period: January 2023 to December 2025.
- Unit: route-month (Origin, Dest, Year, Month) with >= 30 flights. Congestion = scheduled departures at origin that month.
- Pearson r and Spearman rho for each pair, with 95% CIs (Fisher z for Pearson, bootstrap for Spearman).
- Scatter plots with LOWESS lines; explain any Pearson vs Spearman gap (outliers, nonlinearity).
- Partial correlation of delay with congestion controlling for month-of-year (pingouin `partial_corr`), to show a confounder adjustment.
- Explicitly state: correlation does not establish that congestion causes delay; name two plausible confounders (hub status, weather exposure).

## H4: Multiple comparisons

Question: For each of the top 8 carriers by total flights in calendar year 2025, is its mean arrival delay in 2025 different from the mean of all other carriers combined in 2025?

- Test per carrier: Welch's t-test, carrier vs all other carriers (two independent groups, not a one-sample test against a fixed mean, since the comparison mean is itself estimated).

- Report raw p-values, Bonferroni-adjusted, and Benjamini-Hochberg-adjusted (FDR 5%).
- Table showing which conclusions flip under each correction. The point is to demonstrate how many "findings" are artifacts of testing many things.

## Power analysis

- For H1's day-level analysis: given observed SD and n, what is the minimum detectable difference at 80% power? (statsmodels `TTestIndPower`).
- For the flight-level analysis: show that with n in the tens of thousands, even a 0.5 minute difference is detectable, which is why practical significance thresholds matter.

## Caveats the memo must address

- Observational data; no randomization. Nothing here is causal.
- Clustering inflates flight-level significance; day-level results are the honest ones.
- Cancelled and diverted flights excluded; if cancellations rose, delay averages can improve while service worsens. Report cancellation rate alongside.
- Delay cause attribution is carrier-reported.
- Survivorship: routes with < 30 flights excluded from H3.
