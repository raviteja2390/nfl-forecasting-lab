# NFL research status

Generated 2026-11-21T06:08:14.916940Z. Log loss is the primary metric. No demonstrated profitability.

**Primary:** outcome-logit-v1. Repository is public. Cloud collection runs on GitHub Actions.

**Live status:** [latest cloud-generated page](https://github.com/raviteja2390/nfl-forecasting-lab/blob/forecast-state/reports/STATUS.md). The main-branch page is a dated snapshot.

[This week’s three-model comparison](https://github.com/raviteja2390/nfl-forecasting-lab/blob/forecast-state/reports/weekly-comparison.md)

## Prospective evidence

**Forecast coverage: GAPS — 13 games with missed issuance.** [Gap details](forecast-coverage.md). Successful collection does not repair historical gaps.

- outcome-logit-v1: log loss 0.621872407334066; 105 scored, 9 pending, 114 issued.
- player-form-v1: log loss 0.6374496521403471; 105 scored, 9 pending, 114 issued.
- player-availability-v1: log loss 0.6266004383889124; 105 scored, 9 pending, 114 issued.

Unique games are shared across models; do not count each model forecast as an independent game. The two player challengers remain in their fixed prospective protocol (review February 8, 2027; >=200 paired games and >=12 weeks). No new candidate is being added while evidence accumulates.

## Candidate and confidence status

- player-form-v1: awaiting-fixed-review; paired log-loss improvement -0.015577244806281088; prospective interval [-0.04157446087969887, 0.00406728709106453] at 97.5%. Evidence as of 2026-11-21T06:08:14.253164Z.
- player-availability-v1: awaiting-fixed-review; paired log-loss improvement -0.004728031054846427; prospective interval [-0.024981111566147744, 0.012511771791767616] at 97.5%. Evidence as of 2026-11-21T06:08:14.253164Z.
- Opponent-adjusted-v1: offline; protocol approved; shadow issuance disabled pending tested integration. Log loss mixed across 2023/2024/2025. Exploratory unadjusted 95% interval [-0.002601, 0.003320] includes zero.
- Its Bonferroni sensitivity interval (99.0%, family size 5): [-0.003394, 0.004356]; includes zero.
- Margin-ridge-v1: SHELVED; log loss worse in all three cohorts; bootstrap not computed. Tie overprediction quantified. No shadow/live use.

## Evaluation register and promotion safeguards

Logged comparisons by cohort: {'2023': 26, '2024': 5, '2024-2025': 5, '2025': 5}. Counts include the original model versus training frequency, hyperparameter trials on 2023 and timing diagnostics. Year subgroups overlap the combined cohort and are not independent replications.
Register audit: PASS
Historical promotion is prohibited even if a corrected interval excludes zero. Fresh prospective evidence and manual review are required. The existing two-player Bonferroni protocol is unchanged.

## Open actions

- Accumulate prospective games; wait for the registered review rather than optimizing against interim outcomes.
- Implement and verify the approved opponent protocol (docs/protocols/OPPONENT_PROSPECTIVE_V1.md); registered cohort starts October 1, 2026. Issuance remains technically disabled.
- User to rotate the previously exposed Odds API key and check actual GitHub billing. No new key should be posted in chat.
- Odds/closing-line tracking remains a separate integration task.
- Ensembling team-only and player-form probabilities: deferred until enough prospective evidence exists; future blend weights and evaluation must be preregistered as a new candidate.
- Backup: dated write-once checkpoint is restore-tested; administrator deletion remains possible. See docs/REVIEW_CLOSURE.md.
