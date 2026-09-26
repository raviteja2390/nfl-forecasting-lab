# Game forecast evaluation

A standalone toolkit for preparing sports data, training outcome models, issuing pregame forecasts, and measuring results. The prospective evaluator uses Node's standard library; the data tools and saved-model inference use Python's standard library, with system `curl` for public-feed downloads. Model training and the complete recurring cycle use a separate Python environment with scikit-learn. This folder can be copied into a separate project and does not depend on the website or sportsbook code. Node 22 or newer and Python 3.9 or newer are recommended for the dependency-free tools; the pinned training environment uses Python 3.12. Capture commands access public feeds; historical training works offline after package installation and data capture.

## Run it

From the project directory:

```sh
node forecasting/cli.mjs forecasting/example.json --as-of 2026-09-26T18:00:00Z
node --test forecasting/evaluate.test.mjs
```

The command prints a JSON evaluation. Every event, probability, and score in `example.json` is synthetic. The example demonstrates the interface; its numbers are not NFL predictions or evidence of model quality. No packages or subscriptions are required.

For application integration:

```js
import { evaluate } from './forecasting/evaluate.mjs';
const report = evaluate(dataset, '2026-09-26T18:00:00Z');
```

## Supply your forecasts

Use `example.json` as the input contract. Version 1 evaluates one fixed model on a chronological held-out period. `trainingDataThrough` must precede `evaluationStartsAt`. Train and tune the model using only the training period, then freeze it before evaluating later games. Use separate datasets for subsequent model versions; do not combine their scores as if they came from one fixed model.

The baseline is one constant three-outcome distribution, chosen before evaluation. For example, estimate home wins, away wins, and ties from training-period results only. The example baseline is arbitrary, not such an estimate. Never fit or change the baseline using the games being evaluated.

Each forecast needs a unique event ID, kickoff timestamp, forecast generation timestamp, and probabilities for `homeWin`, `awayWin`, and `tie`. All timestamps must be UTC ISO strings with seconds and optional three-digit milliseconds. Probabilities must be finite, between zero and one, and sum to one. Final scores include overtime. Omit `result` or set it to null until the game has a verified final result; use `finalizedAt` for when that result became available.

Every forecast must precede kickoff. Games before the evaluation period, duplicate event IDs, malformed inputs, and results dated before or at kickoff are rejected. At the selected `--as-of` time, forecasts not yet issued and results not yet available are counted separately and excluded from scores. Missing scores return null metrics rather than an apparent zero error.

## Read the output

- **Brier score:** average sum of squared probability errors across the three outcomes, on the unscaled 0–2 range. Lower is better.
- **Log loss:** average negative natural logarithm of the probability assigned to the observed outcome. Lower is better. A probability floor of `1e-15` prevents infinite output for a zero-probability outcome.
- **Accuracy:** fraction correct among forecasts with a unique most-probable outcome. Tied top probabilities abstain; `coverage` reports the fraction classified. Compare accuracy together with coverage.
- **Improvement:** baseline loss minus model loss, measured on exactly the same finalized games. Positive means lower observed loss; it does not establish statistical significance or future performance.

Definitions follow the [scikit-learn model evaluation documentation](https://scikit-learn.org/stable/modules/model_evaluation.html). This implementation uses an explicitly documented probability floor and an unscaled multiclass Brier score.

## What remains to build

The historical pipeline, frozen-model final test, observed-snapshot live features, pregame forecast store, and verified result importer are implemented below. They run locally and do not update the hosted dashboard. Further work includes prospective validation across many game weeks, more complete roster/starter information, and any future dashboard integration.

Timestamp checks detect contradictions in the supplied data. They cannot prove that timestamps are authentic, that forecasts were saved before kickoff, that features were available at prediction time, or that the evaluation sample was not cherry-picked. Historical forecasts created today must not be presented as prospective predictions. Evaluate all eligible games under a predefined inclusion rule, retain missing-forecast counts, and keep a final test period untouched by model selection.

## Build historical model inputs

The downloaded [nflverse schedules/results snapshot](https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv) is in `data/raw/`, together with its retrieval timestamp and checksum. Its [field dictionary](https://nflreadr.nflverse.com/articles/dictionary_schedules.html) specifies that kickoff times are Eastern time. The builder converts these to UTC using daylight-saving-aware timezone rules.

Run from the project directory with Python 3.9 or newer:

```sh
python3 forecasting/build_features.py
python3 -m unittest discover -s forecasting -p 'test_build_features.py' -v
```

No additional Python packages, API keys, downloads, or network access are needed. The builder verifies the raw file against its download checksum and validates required fields, unique event IDs, dates, teams, venue classification, and scores. Missing outcomes or unknown values in selected historical games cause an error instead of being filled or silently dropped. Existing generated files are replaced on a successful rebuild. The raw file is preserved.

Outputs are in `data/processed/v1/`:

- `train.features.jsonl` and `train.labels.jsonl`: 2,079 games, seasons 2015–2022.
- `validation.features.jsonl` and `validation.labels.jsonl`: 272 games, season 2023.
- `test.features.jsonl` and `test.labels.jsonl`: 544 games, seasons 2024–2025.
- `manifest.json`: feature order, source and builder checksums, output checksums, split counts, settings, and limitations.

These are newline-delimited JSON files: one game per line. Join features to labels by `eventId`, not by line number. The 2014 regular season supplies 256 warm-up games but contributes no training targets. Every selected 2015–2025 regular-season game in this snapshot is included, and none has missing features. The snapshot has 271 regular-season games in 2022; the builder does not create a record for a game absent from the source. It does not independently establish schedule completeness against official gamebooks.

Each feature row contains a numeric `features` object, game metadata, and `evidence` with the prior game IDs used. **Only the named `features` object is the model input.** Final scores and the home-win/away-win/tie outcome are in the separate labels file.

The 11 input columns are:

- `homeField`: 1 at the designated home team's home venue, 0 at a neutral site.
- For each of `home` and `away`: `RecentGames` (up to eight eligible prior games), `PointsForMean`, `PointsAgainstMean`, `ResultRate` (win = 1, tie = 0.5, loss = 0), and `DaysSincePriorGameCapped30` (calendar days since the previous regular-season kickoff, capped at 30).

Feature history carries across season boundaries and excludes playoffs. Rest therefore means regular-season-only schedule spacing, particularly at season openers. Older Rams, Chargers, and Raiders codes map to their continuous franchise identities; original source abbreviations and game IDs are preserved. Points and result rates are simple historical summaries, not opponent-adjusted ratings.

### Historical timing and evaluation rules

Features use a simulated cutoff 24 hours before kickoff. An earlier result is eligible only when its kickoff plus 48 hours falls at or before the cutoff, and it belongs to an earlier NFL week or season. Same-week outcomes are excluded. Team history updates after the current game's features are constructed. Dates use the NFL season field, so January games stay with the preceding season.

The 48-hour lag is an explicit availability assumption because this source lacks historical publication and finalization timestamps. The dataset is marked `retrospective-reconstruction`; it uses the latest corrected source schedule and results. It cannot establish exactly what a forecaster could have downloaded at a past instant. `featureCutoffAt` is a simulated boundary, not a claim that a prediction was generated then. Do not rename it to `generatedAt` to bypass the prospective evaluator.

No current-game outcome, quarterback identity, observed game weather, or sportsbook fields are used as features. The code tests verify that changing a current or future game's scores cannot change that game's or an earlier game's inputs.

Train on the training split and choose settings with validation only. Fit scaling and imputation on training data only; this builder fits neither. Keep test labels out of training and selection. During chronological testing, earlier test-period results may enter features once their assumed availability time passes, as earlier results would during a season. They must not refit the model unless a separately defined rolling-training experiment allows it. No model or prediction-quality claim is produced by this preprocessing step.

## Capture and replay observed source versions

```sh
python3 forecasting/snapshots.py capture
python3 forecasting/snapshots.py verify
python3 forecasting/snapshots.py schedule
python3 forecasting/snapshots.py as-of 2026-09-26T14:00:00Z --max-age-hours 24
```

`capture` makes one HTTPS request to the fixed free nflverse feed. It validates the CSV and appends an observation under `data/snapshots/observations/`. Exact response bytes live under `data/snapshots/blobs/`, named by SHA-256. Repeated identical downloads reuse the same blob and retain separate observation records. Changed responses create new blobs; the collector never overwrites old observations or versions. Source corrections therefore remain inspectable. The archive is local, not cloud storage.

Each observation records request start, full-response receipt (`observedAt`), storage timestamp, byte count, checksum, and CSV validation counts. HTTP Date, Last-Modified, and ETag are preserved separately when present. These are response/file metadata, not proof of when individual game records were first published. `providerPublishedAt` remains null when unknown. A score appearing in this feed does not itself establish that a live game has finished.

The `as-of` command selects the latest successfully archived observation received at or before the requested cutoff and verifies its payload before returning its path. It refuses to substitute future data. If nothing was observed by then, or the most recent eligible observation exceeds the requested maximum age, it prints `found: false` and exits with code 2. Invalid/corrupt archives exit with code 1. A successful selection exits with code 0. Explicit timezone offsets are required.

This starts our own observation history on September 26, 2026. The earlier one-off download retains its separate provenance and is not backdated into this observed archive. No archive of 2015–2025 publication times has been reconstructed. Receipt timestamps depend on the computer's clock, and the append-only application behavior plus checksums provide integrity checks, not protection against a local administrator rewriting both data and metadata. Live forecasting below selects snapshots observed before its feature cutoff.

A task named **NFL snapshots on game days** (ID `daily-nfl-data-snapshot`) is configured in this chat. It runs **hourly at :05 on dates with scheduled NFL regular-season or postseason games**, and **once at 00:05 on other dates**, all in **America/New_York**. The midnight run captures a fresh feed and uses `snapshots.py schedule` to switch that same task to the appropriate cadence for the new date. This handles Saturday and holiday games when they appear in the feed; it does not assume only Sunday, Monday, and Thursday are game days. The source does not cover preseason here. The first midnight transition has been configured but has not yet run unattended.

Each run captures once and verifies the archive. Routine captures and cadence changes stay quiet; failures require attention. Keep this computer on and the desktop app running; offline periods do not create observations retroactively. Schedule changes announced after an off-day's single check may only be detected at the next check. The collector itself has no paid API or model calls, while running it through a scheduled Codex task uses the normal plan allowance. No data subscriptions or credits were purchased.

At the initial 2,180,912-byte payload size, 30 changed daily captures add approximately 65.4 MB; 720 changed hourly captures add approximately 1.57 GB, plus small observation metadata. Deduplication lowers disk use when responses are identical. These are size estimates for this feed, not a fixed storage limit or pricing quote. There is no automatic deletion/retention policy.

## Test the historical timing assumption

```sh
python3 forecasting/timing_sensitivity.py
python3 -m unittest discover -s forecasting -p 'test_timing_sensitivity.py' -v
```

This rebuilds the training and validation features at 24-, 48-, and 72-hour assumed result delays. It uses the same checked raw snapshot, retains the 24-hour pregame cutoff and exclusion of same-week results, and compares games by ID. The 2024–2025 final test period is excluded from the study before score parsing. It does not fit a model, inspect final-test performance, or select a delay based on outcomes.

The output directory `data/experiments/timing-v1/` contains six scenario feature files, two shared label files, and `timing-sensitivity.json`. The report includes checksums, counts and exact feature changes, supporting a later model comparison without redownloading data.

For the downloaded snapshot:

- 24 hours versus 48 hours: no changed inputs across 2,079 training and 272 validation games.
- 72 hours versus 48 hours: 10 training games changed (44 feature cells), and one validation game changed (five feature cells).
- The changed validation game is `2023_12_GB_DET`. Longer assumed availability removes more recent results from that game's rolling history.

This feature report establishes sensitivity of the selected inputs only. It does not measure prediction accuracy or prove the timing assumption correct. The training command below adds both a model held fixed while inputs change and separately trained models under each timing scenario, using the same validation games and fitting preprocessing on each training split only. The 48-hour setting remains the reference assumption.

The general feature builder also accepts `--result-lag-hours` (1–168). Use a distinct `--output` directory when experimenting so the main 48-hour dataset stays unchanged.

## Train and validate the first model

The first model predicts `homeWin`, `awayWin`, and `tie` probabilities from the 11 prepared features. It uses [multinomial logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) with L2 regularization. Scaling is fitted only on training data using a pipeline, following the library's [data-leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).

Set up a local environment with Python 3.12, once:

```sh
python3.12 -m venv forecasting/.venv
forecasting/.venv/bin/python -m pip install -r forecasting/requirements-training.txt
```

The environment is already installed in this workspace and is excluded from Git. Package installation requires internet access; training itself needs no network, API key, paid data, or subscription.

```sh
forecasting/.venv/bin/python forecasting/train_model.py
forecasting/.venv/bin/python -m unittest discover -s forecasting -p 'test_*.py' -v
node --test forecasting/evaluate.test.mjs
```

The saved first run is `runs/outcome-logit-v1/`. The command refuses to overwrite an existing run. For a reproduction, specify a fresh directory with `--output forecasting/runs/outcome-logit-v1-repeat`. A reproduction is not a new independent validation sample.

The experiment is specified in `training-plan.json`: train on 2015–2022, select among four C values (0.01, 0.1, 1, 10) by 2023 log loss, break exact ties toward smaller C, and keep 2024–2025 unopened. The baseline is the three training-period outcome frequencies. No class balancing or probability recalibration is fitted. Missing numeric features, label mismatches, corrupt inputs, invalid availability boundaries, and optimizer nonconvergence stop the run.

The trainer reads only the timing study's explicit training and validation files, verifies their checksums and feature-builder version, and joins labels by event ID. Its tests guard against opening any final-test file. The saved model remains fitted on 2015–2022; validation chooses C but does not refit coefficients on 2023. Predictions on later games can use earlier results that pass the feature cutoff while coefficients remain fixed.

Run outputs:

- `REPORT.md`: readable results and limitations.
- `model.json`: portable coefficients, scaling, explicit class order, actual training time, parameters, and data/code/plan checksums. This is plain JSON, not a pickle.
- `report.json`: every candidate's validation scores, class counts, per-week metrics, calibration bins, runtime versions, paired week-bootstrap intervals, and fixed/refitted timing comparisons.
- `validation.predictions.jsonl`: all 272 reference predictions, marked `historical-simulation`. Actual `generatedAt` is distinct from `simulatedFeatureCutoffAt`.
- `timing.predictions.jsonl`: both comparison predictions for every 24/48/72-hour scenario, using the selected C throughout.
- `training-plan.json` and `artifacts.json`: the plan copy and checksums for every output.

Probability scoring matches the prospective evaluator's definitions, including the unscaled three-class Brier score, log-loss floor, and abstention on tied top probabilities. These retrospective records cannot be passed off as pregame forecasts by backdating them. The validation scores were used for selection; they are not an unbiased final-test estimate. Bootstrap intervals are exploratory and do not account for selection, training uncertainty, or dependence between weeks. Similar results under different delays do not resolve the unknown historical publication times.

For application code, `model.py` provides `predict_many(model_dict, list_of_feature_objects)` using only the standard library. It requires exactly the saved feature names and returns probabilities keyed by outcome. A CLI accepts one JSON features object:

```sh
python3 forecasting/model.py forecasting/runs/outcome-logit-v1/model.json /absolute/path/to/features.json
```

The saved coefficients were frozen for the final test described below and are now the primary model for local prospective forecasts. These runs do not enable live predictions on the hosted site.

## Frozen final test — completed

The one-time 2024–2025 evaluation is saved in `runs/outcome-logit-v1/holdout-2024-2025/`. Read its `REPORT.md` for results and `report.json` for complete metrics. Across all 544 games, the frozen model correctly classified 340 (62.5%) versus 291 (53.5%) for the original training-frequency baseline. Log loss was 0.651701 versus 0.703894, a 7.4% relative reduction. Accuracy was 63.2% in 2024 and 61.8% in 2025; probability losses also improved in both seasons.

The exploratory 95% paired week-bootstrap interval for aggregate log-loss improvement was [0.022453, 0.080909]. It favors the model over this frequency baseline, conditional on the fitted model and reconstructed data. It does not include all dependence between games, training uncertainty, or errors in the historical availability assumptions. This is an outcome forecast comparison, not a comparison against sportsbook prices or a profitability result.

The following command performed the evaluation using the standard library only:

```sh
python3 forecasting/evaluate_holdout.py
python3 -m unittest discover -s forecasting -p 'test_evaluate_holdout.py' -v
```

Running the evaluator again refuses to replace the existing results or re-open test outcomes. Tests use synthetic holdout rows only. There is no fitting or parameter-search dependency in this command. `holdout-plan.json` was declared before opening the actual test outcomes and pins the exact model, processed manifest, test-file hashes, sample, baseline, metrics, and bootstrap settings.

The command verifies the saved model against its training artifact checksum and verifies that inference/scoring code is unchanged. The processed manifest predates the configurable-lag builder used for training, so its builder hash differs; its 48-hour training and validation feature and label hashes match the model's provenance exactly. Both builder hashes and that compatibility check are recorded in the final-test report. The original test dataset was retained without rebuilding it or changing its settings.

The evaluator writes `plan.json`, an exact `frozen-model.json` copy, and all `predictions.jsonl` probabilities before loading the outcome file. An `exposure.json` marker records the first scoring attempt and remains if scoring fails. The final artifacts add `scored-predictions.jsonl`, `report.json`, `REPORT.md`, and `artifacts.json` checksums. The original training outputs are preserved. Local files and timestamps provide an audit trail, not tamper-proof external attestation.

**The 2024–2025 test period is now exposed.** Subsequent experiments that use these results to change the model must treat those seasons as development data, not claim a fresh independent test. The next evaluation source should be forecasts recorded prospectively before future games, with observed snapshots and verified final results.

## Player-data challengers — completed, not promoted

`feeds.py` archives free nflverse weekly player stats and injury files under `data/feeds/`, with receipt times and content hashes. The initial collection covers 2014–2026. Historical files are corrected snapshots, not reconstructed publication archives. Sources and field definitions are documented by [nflreadr player statistics](https://nflreadr.nflverse.com/reference/load_player_stats) and its [injury dictionary](https://nflreadr.nflverse.com/articles/dictionary_injuries.html). The player statistics include attribution to nflverse; injury reports come through its public release feed. ESPN public scoreboards provide the independent schedule/final-status check for live forecasts.

The predeclared `player-plan.json` compares two challengers on the same games as the frozen team model. Both fit 2015–2022 and select C using 2023 log loss. Results, all candidates, source audit, frozen models, feature files, and predictions are saved in `runs/player-comparison-v1/`.

- **Player form:** adds prior primary-passer efficiency, passer changes, leading receiver/rusher usage and efficiency, and EPA coverage indicators. It uses four prior eligible team games and never uses current-game player performance. The passing role is inferred from earlier attempts, so a TE/WR season position label does not incorrectly remove a player who previously played quarterback.
- **Player availability:** adds eligible injury reports, separate Out/Doubtful/Questionable offensive usage shares, and counts of offensive-line and defensive players listed Out. These are predictive associations, not causal individual-player impact estimates. A previous primary passer is not a confirmed upcoming starter.
- **Missing information:** unknown EPA is excluded from its numerator/denominator and tracked with coverage. Historical injury rows without update timestamps, or updated after the cutoff, cannot contribute a status. No eligible report is explicitly flagged as unavailable; it never establishes a healthy roster. Current undated reports can be used prospectively after an actual archive receipt.

The 2025 injury file has no update timestamps; 2024 has them. Across the already exposed 2024–2025 games, team-only accuracy was **62.5%**, player form **61.9%**, and player availability **61.4%**. Form slightly improved log loss (0.649752 vs 0.651701), while availability was worse (0.660591). The 2025 availability comparison lacks usable historical injury timing. In 2024 alone, availability accuracy was 64.0% versus the team's 63.2%. These mixed development results do not establish that player data improves predictions, so team-only remains primary and both challengers run in shadow mode.

Do not refit these models to tomorrow's results. Compare a growing set of genuinely prospective predictions on identical games and information cutoffs before considering promotion.

## Live forecasts and automatic scoring

**Ready date:** September 27, 2026, America/New_York. The local store contains 14 primary forecasts and 14 forecasts for each of the two player challengers. All were issued more than 24 hours before kickoff, with the same feature cutoff for each game across models.

- Primary matchups: `live/reports/2026-09-27.md`.
- Three-model comparison: `live/reports/2026-09-27-comparison.md`.
- Historical player comparison: `runs/player-comparison-v1/REPORT.md`.
- Prospective results: `live/reports/prospective-scores.md` and `.json`. There are no scored games until verified finals arrive.

Canonical forecasts are append-only under `live/forecasts/<modelVersion>/<eventId>.json`. They include actual generation time, feature cutoff, model hash, team features, source observations, and player evidence where applicable. Subsequent collection does not rewrite these predictions. This first experiment issues at least 24 hours before kickoff; hourly collection does not mean hourly revision of its locked predictions. Missed deadlines fail rather than backdate forecasts.

Live inputs retain the regular-season history, earlier-week exclusion and conservative 48-hour result lag. Every prior score used is also checked against an observed ESPN completed status with identical scores. The upcoming matchup, kickoff, and venue designation must agree across the two sources. A fresh source read is required, and no snapshot received after the cutoff can be substituted.

The complete operation is:

```sh
forecasting/.venv/bin/python forecasting/cycle.py
```

It captures/validates the schedule, refreshes relevant player feeds, prepares tomorrow's first forecasts, adds same-cutoff player shadows, imports verified finals for issued games, and writes prospective scores. It never trains or promotes models. `--no-capture` verifies the workflow offline using existing fresh archives. The individual commands remain available:

```sh
python3 forecasting/live.py prepare 2026-09-27
python3 forecasting/live.py publish 2026-09-27
forecasting/.venv/bin/python forecasting/compare_players.py publish --date 2026-09-27
python3 forecasting/live.py settle 2026-09-27
python3 forecasting/score_live.py --date 2026-09-27
```

`prepare` downloads the scoreboards needed to validate prior results. `settle` uses already captured fresh schedule/scoreboard observations, requires completed status plus agreement on both scores, and appends a result receipt. Pending games and source disagreements remain unscored. `score_live.py` reports pending counts, accuracy, Brier score and log loss, and compares challengers only on shared finalized events with identical feature cutoffs. It never gives a pending game a zero error. Local result receipts can retain corrections when explicitly rechecked; the recurring cycle ordinarily revisits unscored games only.

The existing **NFL snapshots on game days** task is extended to run this full cycle: hourly at :05 on actual NFL game dates and daily at 00:05 on other dates, in Eastern time. The midnight run changes its cadence for the day. The local computer and app must remain running. Routine unchanged runs stay quiet; failures, missing deadlines, source disagreements, and meaningful completed result sets can notify you. No paid data or software subscription was purchased. The hosted website remains unchanged.

## Operational safeguards and supplemental evaluation

The issued models and their pinned inference/feature code remain unchanged. The September 26 operational changes add:

- A nonblocking collection lock, atomic `live/operations/status.json` recording, and failure receipts even when a cycle raises before completing. Only successful network-enabled cycles refresh `lastSuccessAt`; offline checks cannot conceal a missed collection.
- `python3 forecasting/operations.py check`: compares the last successful collection with actual game-day hourly runs at :05 or off-day daily runs at 00:05 Eastern, allowing 20 minutes of grace. It handles DST in UTC, writes health and transition alerts locally, and exits nonzero on failure. `notify` is true only for a new problem, changed problem or recovery. A separate desktop heartbeat invokes this check; it cannot run while the computer or Codex is off.
- Pending outcomes are revisited regardless of age. Settled games are also checked on their game date and the following six Eastern dates. Both feeds must agree on a final. A changed score appends a receipt and a correction audit under `live/rechecks/`; old receipts remain. Source disagreements or loss of finality quarantine that event from current scores until a later recheck resolves it. Corrections older than this window require an explicit manual settlement recheck.
- `python3 forecasting/calibration_report.py`: verifies existing run manifests and writes supplemental historical JSON plus an HTML report to `reports/calibration/`. It covers all three models, both development and evaluation periods, per-class bin counts, and descriptive Wilson intervals. It does not alter original reports or fit calibration.
- `python3 forecasting/promotion_report.py`: evaluates the preregistered rules in `promotion_criteria.md` and `promotion-plan.json`; its report is also refreshed by `cycle.py`. No automatic promotion occurs. Prospective calibration appears only when verified scored games exist. At and after the formal review, evidence is capped at the fixed review timestamp, so later receipts cannot silently alter that review's dataset.

The two registered challengers are evaluated once on February 8, 2027 at 12:00 UTC. The thresholds require at least 200 shared games, 12 NFL weeks, 95% reference-cohort coverage, mean log-loss improvement of 0.010, a positive lower bound on a paired-week 97.5% bootstrap interval, and a Brier/integrity guard. The interval adjusts for the two comparisons but remains approximate; sample floors are not a power guarantee. Interim metrics are descriptive. Read the protocol for the full conditions and limitations.

A pre-change, restore-verified backup of all forecasting files and the guide—including local raw archives—was uploaded to the private GitHub release `backup-before-operations-20260926`. See `docs/OPERATIONS_CHANGELOG.md` for hashes and boundaries. GitHub releases can be edited or deleted by authorized users; this is an off-device backup, not immutable storage. Future raw data still needs future backups.
