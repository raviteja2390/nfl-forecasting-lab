# Model reporting and status

Lead chat summaries and future reports with log loss as the primary metric. Always state whether the direction across 2023, 2024 and 2025 is consistent or mixed. Report accuracy secondarily. Consistent direction does not by itself establish statistical significance; exploratory intervals do not remove selection bias or prove profitability.

- outcome-logit-v1: unchanged primary.
- player-form-v1 / player-availability-v1: existing registered prospective comparisons unchanged.
- opponent-adjusted-v1: mixed historical log-loss direction; bootstrap includes zero. Read-only prospective feature pipeline prepared. Protocol approved September 26, 2026: `protocols/OPPONENT_PROSPECTIVE_V1.md`. Approval and fixed identities recorded in `forecasting/opponent-activation-v1.json`; shadow issuance remains disabled pending tested issuer/evaluator integration.
- margin-ridge-v1: SHELVED. No live or shadow issuance, promotion, recalibration, or further modeling work on this version. Worse log loss in every tested cohort. Any future alternative probability mapping requires a newly registered, separately evaluated version and a new task authorization.

## Required interpretation note for the February 2027 player-family review

Include [player-availability-v1: missing-injury-data effect](models/PLAYER_AVAILABILITY_V1.md) in the February 8, 2027 manual review. When all availability inputs are zero, the frozen model has a learned, approximately constant away-directed log-odds shift relative to the form model, primarily associated with standardized missing-report effects. The probability shift is game-dependent, not a fixed percentage-point adjustment. Review its relationship to injury-data coverage and calibration without changing the registered full-cohort criteria or treating descriptive subgroups as new promotion tests.
