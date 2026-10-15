# MEMO TEMPLATE (Claude Code writes the prose from results.csv)

Format: narrative prose, no bullet-point slides. 2 to 3 pages. Figures and tables in an appendix, referenced by number. Written for an operations director who will not read the notebook.

## Title
One line stating the main finding, not the topic. Write it only after all results exist; it must reflect the strongest practically meaningful result, or say plainly that no practically meaningful change was found.

## 1. Summary (one paragraph, 4 to 6 sentences)
The question, the answer, how confident we are, and the one action or decision it supports.

## 2. Background
Why this question matters to the reader. Data used (source, period, row count), in two sentences.

## 3. Findings
One subsection per hypothesis. Each one:
- What we asked, in plain language.
- What we found, with the number a leader cares about first (minutes, percentage points), then the statistic in parentheses: e.g. "Mean delay fell 3.1 minutes (Welch's t(…)=…, p=…, Hedges' g=…, 95% CI […, …])."
- How much it matters practically.

## 4. What this does not tell us
The caveats from ANALYSIS_PLAN.md, written as consequences for decisions, not as a disclaimer list. For each: what someone might wrongly conclude, and why they should not.

## 5. Recommendation and next step
One concrete recommendation. One follow-up analysis that would turn an association into a stronger claim (for example, a natural experiment or a difference-in-differences design).

## Appendix
- A. Figures
- B. Full test results table (test, statistic, df, p, adjusted p, effect size, CI, n)
- C. Data and method notes, including deviations
- D. Cost of the analysis (Athena bytes scanned and USD)
