# Opponent-adjusted model experiment

Offline candidate only. Existing models and forecasts are unchanged.

Training: 2015–2022. Regularization selected on 2023 log loss. Previously exposed 2024–2025 results are exploratory.

Selected C: 0.01. Six opponent-adjusted inputs supplement the existing team features.

## 2023 development

272 identical games. Baseline accuracy 59.93%, candidate 59.56%. Baseline log loss 0.661379, candidate 0.660352. Baseline Brier 0.464293, candidate 0.463108.

## 2024–2025 exploratory

544 identical games. Baseline accuracy 62.50%, candidate 62.32%. Baseline log loss 0.651701, candidate 0.651206. Baseline Brier 0.450083, candidate 0.449619.

## 2024 exploratory

272 identical games. Baseline accuracy 63.24%, candidate 63.24%. Baseline log loss 0.649219, candidate 0.647191. Baseline Brier 0.452676, candidate 0.450643.

## 2025 exploratory

272 identical games. Baseline accuracy 61.76%, candidate 61.40%. Baseline log loss 0.654184, candidate 0.655221. Baseline Brier 0.447490, candidate 0.448595.

## Limits and next step

- Corrected historical snapshot with assumed publication timing
- Opponent averages are a one-pass adjustment, not causal or recursively schedule-adjusted ratings
- No odds or betting-return evaluation
- Exposed 2024-2025 outcomes provide exploratory evidence only
- No prospective results exist for this candidate. No automatic promotion.
- Coverage count distinguishes unavailable opponent history from a zero residual.

Register a separate future-cohort evaluation protocol and implement observation-time-aware live features before issuing prospective shadow forecasts. Do not reuse this retrospective builder for live issuance.
