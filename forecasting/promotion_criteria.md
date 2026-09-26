# Prospective model promotion protocol — version 1

Declared 26 September 2026, before any of the 14 issued games per model was scored. These are decision rules, not evidence that a model will improve. The team-only `outcome-logit-v1` remains primary. No automatic promotion is authorized by this protocol.

## Registered comparison and review

- Challengers: `player-form-v1` and `player-availability-v1`, exactly as frozen in `runs/player-comparison-v1/artifacts.json`.
- Reference: `outcome-logit-v1`, pinned by its existing artifact manifest.
- Cohort: prospective NFL regular-season games with Eastern game dates from 2026-09-27 through 2027-02-01 inclusive, issued at least 24 hours before kickoff. A challenger and reference must have the same event ID, feature cutoff, kickoff and model hashes matching their registered artifacts.
- One formal review: 2027-02-08 at 12:00 UTC, using only result receipts observed by that time. Pending or disputed games remain unscored. Later corrected results require a separately recorded amendment, never a silent change to the decision.
- Interim reports are descriptive. Do not promote early, stop on a favorable result, change thresholds or select a favorable subgroup after inspecting results.

## Required evidence at the fixed review

1. At least 200 shared finalized games across at least 12 distinct NFL season-week blocks per challenger; at least 95% coverage of the reference's eligible finalized cohort. Report omitted games and reasons. These are practical minimums, not a power calculation or a guarantee of adequate precision.
2. Mean paired log-loss improvement, reference minus challenger, of at least 0.010 natural-log units per game. This is a preselected practical threshold, not a proven economic edge.
3. A paired whole-NFL-week percentile bootstrap, 20,000 draws, seed 20260926, with a 97.5% two-sided interval whose lower bound is strictly above zero. The interval uses percentiles 1.25 and 98.75: a Bonferroni adjustment for the two registered comparisons at a nominal family error rate of 5%. Bootstrap approximation and cross-week dependence remain limitations; this is not an exact error guarantee.
4. Challenger multiclass Brier score no more than 0.005 worse than the reference. Report accuracy, abstention coverage, per-class calibration with bin counts, seasonal coverage, missing player inputs and all operational failures alongside the decision.
5. No unresolved integrity, timing, pairing or settlement discrepancy. Manual review is required even when numeric criteria pass. Passing establishes eligibility for a forecasting-model change, not a betting-profit claim.

If evidence is insufficient at the review, keep the reference and record an inconclusive result. A later experiment must be registered prospectively with a new future cohort and review date; do not repeatedly retest this same cohort until significance appears. New model families or parameter searches are not added to these two registered comparisons.

## Permanent preservation

Never edit or retrain an issued model version in place, whether its games are pending or settled. Preserve model bytes, feature/inference code hashes, original forecasts, plans and source receipts. Changes to features, scaling, coefficients or recalibration require a distinct version and a new prospective protocol. Result corrections append receipts and retain earlier evidence.

Dropping the two constant, zero-weight team features is optional schema maintenance. An exactly equivalent implementation cannot beat the reference's log loss and is not an improvement challenger under this protocol. Verify numerical equivalence separately if that maintenance is undertaken.

2023 selected model settings. The 2024–2025 outcomes have been exposed; further experiments on those seasons are exploratory. Preserve their original reports and publish supplemental analyses elsewhere.
