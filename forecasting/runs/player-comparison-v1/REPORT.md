# Team-only versus player-aware models

Both challengers train on 2015–2022 and select regularization on 2023. The team-only model is unchanged.

2024–2025 results below are exploratory because those seasons were already exposed during the original model test.

Team-only: 2023 accuracy 59.9%, log loss 0.661379; 2024–2025 accuracy 62.5%, log loss 0.651701.

## player-form

2023: accuracy **60.3%** (164/272), log loss **0.674312**.
2024–2025: accuracy **61.9%** (337/544), log loss **0.649752**.

- 2024: accuracy 63.2%, log loss 0.640904.
- 2025: accuracy 60.7%, log loss 0.658599.

## player-form-and-available-injuries

2023: accuracy **60.3%** (164/272), log loss **0.664502**.
2024–2025: accuracy **61.4%** (334/544), log loss **0.660591**.

- 2024: accuracy 64.0%, log loss 0.643661.
- 2025: accuracy 58.8%, log loss 0.677521.

## Interpretation

Accuracy is compared on exactly the same games. Lower log loss and Brier scores indicate better probability forecasts. A higher win-pick accuracy alone does not establish better calibrated probabilities or profitability.

The form model adds past quarterback efficiency, quarterback changes, and leading receiver/rusher usage and efficiency. The availability model also adds known Out/Doubtful/Questionable players' prior offensive usage shares and counts of offensive-line and defensive players listed Out. These are learned predictive associations, not causal individual player valuations.

The 2025 injury file has no update timestamps, so its historical injury inputs are marked unavailable, rather than assuming healthy players or using after-the-fact statuses. Current reports captured now can be used prospectively with real receipt timestamps.

The preferred shadow model by 2023 log loss is **player-form-and-available-injuries**. The team-only model stays primary. Both challengers can be tracked on future games without changing the original predictions.
