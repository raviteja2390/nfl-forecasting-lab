# player-availability-v1 — interpretation and review notes

Status: frozen prospective shadow model. These notes supplement the original immutable training artifacts; they do not modify model parameters, inference, forecasts, the registered cohort, or promotion thresholds.

## Missing-injury-data effect

Diagnostic recorded September 26, 2026: when BOTH teams have unavailable injury evidence and all 24 additional availability inputs are zero, this frozen model exhibits a learned shift toward away teams relative to `player-form-v1`. This is a conditional model property, not a claim that every forecast or every missing-data pattern has the same shift.

The two models use the same player-form feature construction and selected L2 regularization strength (`C = 0.01`), but were fitted separately. It is not an extra smoothing/shrinkage step. Standardization maps a raw zero to `(0 - training mean) / training scale`, so zero availability inputs do not eliminate their contributions to the fitted logits. Shared-feature coefficients and intercepts also differ between the models.

For the frozen availability model, the contribution of the 24 standardized all-zero availability features to **home-versus-away log odds** is **-0.4338943032**. This component is constant whenever those inputs are all zero. The two missing-report indicator contributions are `homeInjuryReportObserved: +0.7042843948` and `awayInjuryReportObserved: -1.0781527895`; other availability features supply the remaining net contribution. These are algebraic contributions in the saved standardized parameterization, not causal player effects or proof of the reason the training data produced those weights.

Relative to the form model, the home-versus-away intercept difference is **+0.0017165928**. Differences in shared-feature coefficients add a game-dependent component. In the inspected 14-game all-missing-input diagnostic, the total relative home-versus-away log-odds shift ranged from **-0.49754 to -0.38546**, and home-win probability fell by **7.87–11.24 percentage points**. These ranges describe that diagnostic only; probability shifts are nonlinear and are NOT a universal fixed subtraction to apply to future predictions.

Therefore a better score when injury evidence is absent must not be described as an advantage from knowing injuries. A general away-team shift can help on an away-heavy result slate and hurt on another. Missing reports remain unavailable evidence, never a declaration that the roster is healthy. The observation does not establish persistent benefit, statistical significance, or profitability. No replay results have been added to the prospective evaluation cohort.

## February 8, 2027 manual-review checklist

As part of the existing manual review, explicitly consider this note alongside the registered full-cohort log-loss, Brier, confidence-interval, coverage and integrity gates:

- Report how often neither, one, or both teams have eligible injury evidence, preserving unknown versus genuinely reported status.
- Inspect descriptive calibration and home/away probability shifts by those coverage patterns, including whether improvements concentrate in missing-data cases.
- Distinguish use of actual injury information from a missingness-associated team-side shift; do not attribute the latter to causal injury impact.
- Keep the original full-cohort promotion decision rules fixed. These diagnostics are not new hypothesis tests, selectable favorable subgroups, an alternative promotion route, or authorization to tune after seeing results.
- If the effect motivates a correction, use a separately registered new version and future evaluation. Never rewrite `player-availability-v1` or its issued forecasts.

## Reproducing the coefficient diagnostic

Use `forecasting/runs/player-comparison-v1/player-availability-v1.json`. For every feature absent from the form model's feature-name list, sum `(coefficient_homeWin - coefficient_awayWin) * (-mean / scale)`. Resolve class indices by their names in each artifact, not by assuming class order. Compare intercepts separately. The feature inputs and coefficients of the shared form terms determine the remaining game-dependent difference.

The original manifests and the registered model hashes remain the integrity authority. This interpretation note is supplemental and does not replace them.
