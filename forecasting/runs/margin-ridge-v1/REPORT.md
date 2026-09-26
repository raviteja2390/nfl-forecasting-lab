# Margin-regression experiment

Offline research candidate; current primary model and issued forecasts unchanged.

Ridge predicts home-minus-away points using the original team features. Train: 2015–2022; select alpha: 2023 log loss. 2024–2025 results are exploratory.

Selected alpha: 0.1; Gaussian error sigma: 13.4423 points, estimated only from expanding-season training folds.

## 2023 development

272 identical games. Accuracy: baseline 59.93%, candidate 60.29%. Log loss: baseline 0.661379, candidate 0.681520. Brier: baseline 0.464293, candidate 0.462435.
Margin MAE 10.365; RMSE 13.562 points.

## 2024–2025 exploratory

544 identical games. Accuracy: baseline 62.50%, candidate 62.87%. Log loss: baseline 0.651701, candidate 0.672289. Brier: baseline 0.450083, candidate 0.451642.
Margin MAE 10.378; RMSE 13.303 points.

## 2024 exploratory

272 identical games. Accuracy: baseline 63.24%, candidate 62.87%. Log loss: baseline 0.649219, candidate 0.672847. Brier: baseline 0.452676, candidate 0.454086.
Margin MAE 10.397; RMSE 13.444 points.

## 2025 exploratory

272 identical games. Accuracy: baseline 61.76%, candidate 62.87%. Log loss: baseline 0.654184, candidate 0.671731. Brier: baseline 0.447490, candidate 0.449199.
Margin MAE 10.359; RMSE 13.161 points.

## Limitations

- Gaussian errors ignore football key-number spikes, skew and changing variance
- Tie and push probabilities may be poorly calibrated
- Historical source availability still assumes a 48-hour lag
- 2024-2025 results are exposed and exploratory
- No sportsbook odds, CLV, or profitability evaluation
- Continuous predicted margin is the latent Gaussian center; probabilities discretize it to integer outcomes.
- Spread probabilities are unvalidated distribution outputs, not market-edge estimates. No automatic promotion.

A home handicap of -3.5 means the home team covers at a margin of 4 or more; -3 has a push at margin 3. No closing spread data were used or evaluated. Register a separate prospective protocol and live adapter before shadow issuance.
