# NFL outcome model v1 — training report

This is a retrospective development experiment, generated 2026-09-26T14:07:06Z. It is not a record of forecasts issued before those games.

## Data and method

- Training: 2,079 regular-season games, 2015–2022. Validation: all 272 regular-season games in 2023.
- Model: three-outcome logistic regression using 11 pregame features, with scaling fitted only on training rows. Constant input columns: homeRecentGames, awayRecentGames.
- Settings were declared in `training-plan.json` before fitting: C = 0.01, 0.1, 1, 10. Selected C = 0.01, using lowest validation log loss.
- Baseline: the empirical home-win, away-win, and tie frequencies from training results only.
- Final test seasons 2024–2025 were not opened by this training run. No random train/test split or final-test tuning was used.

## 2023 validation results

- Model accuracy: **59.9%** (163/272); baseline: **55.5%** (151/272). Both classify every game.
- Log loss, lower is better: model **0.661379**, baseline **0.691514**. Improvement: 0.030134 (4.4% relative).
- Unscaled three-class Brier score (0–2), lower is better: model **0.464293**, baseline **0.494074**.
- Exploratory 95% whole-week bootstrap interval for log-loss improvement: [-0.004260, 0.058621]. It does not adjust for model selection, training uncertainty, or correlation across weeks.
- Training class counts: {"homeWin": 1133, "awayWin": 937, "tie": 9}. Validation class counts: {"homeWin": 151, "awayWin": 121, "tie": 0}.

The validation season selected the model settings, so these are development results, not an unbiased final-test estimate. Accuracy here concerns game outcomes; this experiment has no price-based benchmark or profitability evaluation. Rare ties have limited training support. Calibration-bin counts and rates are in `report.json`; no probability recalibration was fitted.

## Result-delay sensitivity

The reference remains 48 hours. Each alternative is evaluated with the reference model held fixed, then with a model refitted at the same selected C. No alternative delay is selected using these scores.

- **24 hours:** fixed-model log loss 0.661379; same-C refit log loss 0.661379; maximum probability movement versus reference 0.000000 fixed / 0.000000 refitted.
- **48 hours:** fixed-model log loss 0.661379; same-C refit log loss 0.661379; maximum probability movement versus reference 0.000000 fixed / 0.000000 refitted.
- **72 hours:** fixed-model log loss 0.661149; same-C refit log loss 0.661120; maximum probability movement versus reference 0.014004 fixed / 0.014306 refitted.

Similar scores across delays do not establish when historical results were actually published. All inputs still come from a corrected historical snapshot, using assumed availability and a simulated 24-hour pregame cutoff.

## Saved artifacts and next step

`model.json` saves coefficients, scaling, class order, source provenance, actual training time, and selection metadata. `validation.predictions.jsonl` saves every reference prediction with separate actual generation and simulated cutoff timestamps. `timing.predictions.jsonl` saves both comparisons for every delay. `report.json` includes every candidate's scores, week-level results, calibration bins, and runtime versions. `artifacts.json` records checksums of every run output.

The next evaluation should freeze this model and score the reserved 2024–2025 period once, without retuning from those results. The model remains local; it is not connected to the hosted dashboard or to a live forecast service.
