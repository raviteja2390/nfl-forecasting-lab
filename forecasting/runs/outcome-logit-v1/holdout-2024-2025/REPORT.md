# NFL outcome model v1 — final test

Evaluated 2026-09-26T14:11:36Z. All 544 reserved regular-season games from 2024–2025 are included.

## Overall results

- Outcome accuracy: **62.5%** (340/544), versus **53.5%** (291/544) for the unchanged training-frequency baseline.
- Log loss (primary metric; lower is better): **0.651701**, baseline **0.703894**. Baseline minus model: 0.052193 (7.4% relative).
- Unscaled three-class Brier score (0–2; lower is better): **0.450083**, baseline **0.499528**.
- Forecast coverage: 100.0%. No games were excluded based on confidence or result.
- Exploratory 95% paired week-bootstrap interval for log-loss improvement: **[0.022453, 0.080909]**.
- Outcome counts: {"homeWin": 291, "awayWin": 252, "tie": 1}.

The entire interval favors the frozen model over the frequency baseline on this sample.

## Results by season

- **2024:** 172/272 correct (63.2%), baseline 53.3%; log loss 0.649219 versus 0.695704; Brier 0.452676 versus 0.498233.
- **2025:** 168/272 correct (61.8%), baseline 53.7%; log loss 0.654184 versus 0.712084; Brier 0.447490 versus 0.500822.

## What was frozen

- Model: `outcome-logit-v1`, SHA-256 `c67dd15b7f6c45db1f62d386783f9158b3994675240bb63b83aa10a0a50c34f0`.
- Coefficients, scaling, class order, C = 0.01, baseline probabilities, and the 48-hour result-availability assumption were unchanged.
- The evaluation plan was saved before opening test outcomes. Every prediction was saved before the outcome file was read.
- This evaluation has no training, parameter search, or recalibration step. Coefficients remain fitted to 2015–2022; 2023 selected C.
- The original training artifacts were preserved. The 2024–2025 outcomes are now exposed and cannot be reused as an untouched test for future tuning.

## Interpretation and limits

These are retrospective game-outcome forecasts created today, using a corrected source snapshot. The simulated feature cutoff is 24 hours before kickoff; unknown publication times remain modeled with a 48-hour delay. Earlier test-period results can enter later games’ features after that cutoff, while model coefficients remain fixed.

The uncertainty interval resamples whole season-week blocks. It does not capture all dependence between games, uncertainty from training, or source-timing errors. Per-class calibration and counts are in `report.json`; rare ties limit what can be concluded about tie probabilities.

This comparison measures improvement over historical outcome frequencies. It does not compare against sportsbook prices or establish betting profitability.

The next engineering step is prospective evaluation: build features from timestamped snapshots and save forecasts before kickoff, then score them after verified final results. These predictions are local artifacts, not live predictions on the hosted website.

## Artifacts

`plan.json` fixes the test design. `frozen-model.json` is an exact model copy. `predictions.jsonl` contains all probabilities without outcomes. `exposure.json` marks the first scoring attempt. `scored-predictions.jsonl` joins outcomes by ID. `report.json` includes aggregate, seasonal, weekly, calibration, and uncertainty results. `artifacts.json` records output checksums.
