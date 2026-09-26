# This week’s three-model comparison

[Open the automatically refreshed weekly report](https://github.com/raviteja2390/nfl-forecasting-lab/blob/forecast-state/reports/weekly-comparison.md).

The existing cloud collector updates this report after each collection: hourly on scheduled NFL game days, daily otherwise. It compares original issued forecasts from outcome-logit-v1, player-form-v1 and player-availability-v1. It does not retrain, update probabilities, issue missing forecasts or activate other candidates.

The week is the observed NFL regular-season week, including Monday games. Between weeks, the report switches to the next scheduled week. Missing predictions, cutoff mismatches and schedule changes are identified. A stable week-specific report such as `2026-week-03-comparison.md` is also saved in `forecast-state/reports/`; these are derived views, while original forecast receipts remain canonical and immutable. Kickoff times are America/New_York with DST handling. For scored results and evaluation status, see [STATUS.md](https://github.com/raviteja2390/nfl-forecasting-lab/blob/forecast-state/reports/STATUS.md).
