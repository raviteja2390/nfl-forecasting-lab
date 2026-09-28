# Postgame research v1

Status: registered descriptive study; no fitted candidate, evaluation claim, or live integration.

Purpose: describe statistical differences in completed games, then investigate whether lagged information improves future home/tie/away probabilities. This is not a spread-cover model or a causal explanation engine. Week 3, 2026 has already been inspected and is exploratory, never a fresh holdout.

## First report

Reuse already archived nflverse player statistics and independently confirmed results. Preserve original receipt timestamps, source URL and SHA-256; do not fetch articles, injury narratives, or new restricted sources. Cloud reports contain only derived team aggregates and source receipts in the separate postgame-reports branch; no new raw-data publishing. Attribution: nflverse contributors. Existing source licensing review applies; this study grants no additional redistribution rights. A separate daily reporting workflow reads verified public forecast-state snapshots. No collector scheduler, frozen model, or active player/opponent protocol is changed.

Show both teams, including wins and losses, to avoid selecting only evidence about losers. Aggregate passing EPA from passing rows and rushing EPA from rushing rows; never add receiving EPA to passing EPA because the same passing plays would be counted twice. Report attempts, carries, interceptions thrown, sacks suffered, and field goals made/attempted. Missing active-player metrics remain unknown; absent data never imply zero. EPA means expected points added, a descriptive estimate rather than points literally scored. Do not interpret summed player EPA as a complete team scoring decomposition.

Use deterministic descriptions of differences, not invented causal stories or a language model's assessment of coaching. Report contrary evidence too. No arbitrary composite score, significance tests, or model selection on this week.

## Timing and future eligibility

A record becomes usable no earlier than its actual full-response receipt. Source publication time is unknown unless independently supplied. For a future game, require observedAt <= feature cutoff <= issuance <= kickoff minus 24 hours. The earlier game's result must also have been observed final by the feature cutoff. Later corrections must remain separate versions; never replace the historical as-of view with the newest data. A file received today cannot become evidence that its contents were known last week. No same-game postgame statistic may predict that game's outcome.

## Offline experiment plan (not executed)

First perform an as-of coverage audit across prior games and future prediction cutoffs. Current Week 3 receipts cannot support a new prospective performance estimate yet. Historical current-version files may support a separately labeled retrospective sensitivity analysis with explicit publication-delay assumptions, not a true observation-time backtest.

Before fitting, create a distinct candidate and freeze a machine-readable manifest containing source checksums, target, dates, splits, features, lookback/minimum-history rules, missingness handling, hyperparameters and seed. Use lagged rolling passing/rushing efficiency, interception and sack rates as a small predeclared feature family; retain kicking as descriptive initially. Do not expand the list after reviewing holdout outcomes. Estimate scalers, shrinkage, opponent adjustment, and calibration only on earlier training data. Use chronological training/validation and a later untouched evaluation cohort, with identical games and cutoffs for baseline and challenger.

Log every fitted/evaluated variant in the existing evaluation register before judging it, including abandoned and diagnostic variants. Reference outcome-logit-v1 as frozen at registration; quantify overlap with player-form and opponent-adjusted features. An ablation against existing player information is necessary before claiming new information from postgame statistics.

Primary metric: mean three-outcome log loss. Secondary: multiclass Brier score and calibration; accuracy is descriptive. Paired whole season-week block bootstrap, 95% percentile interval using the existing seed convention, plus exploratory multiplicity correction for all variants tested on each cohort. State direction separately for 2023, 2024, 2025 if tested; do not infer consistency from pooled results. A new future cohort and separate approval are required before shadow/live issuance; existing frozen protocols remain unchanged.

## Known gaps

This initial player-stat report does not establish third-down/red-zone efficiency, drives, field position, pressure rate, weather effects, penalties, special-teams coverage, full participation, or injury causality. Those require separate data/coverage/rights checks. Final-result agreement does not verify every player statistic. Game state and opponent strength confound box-score differences. No performance benefit has yet been measured.

## Cloud operation

The NFL postgame research report workflow runs daily at 07:43 UTC (03:43 EDT / 02:43 EST), plus manual dispatch. GitHub scheduling is best effort. No laptop is required. The job has a five-minute timeout, uses standard-library Python, and makes no provider requests. At most 31 scheduled runs per month: a 155 runner-minute timeout ceiling, excluding manual runs. Actual usage depends on runtime and account billing. It uses only the built-in GitHub token, no odds/news/private-archive secrets. Derived reports are published to postgame-reports, separate from main and forecast-state. Each report records its input commit and receipt hashes; branch history retains revisions, but administrators can delete history. No new immutable-storage claim is made.

Only existing public nflverse player statistics and confirmed results are read; no access to nfl-collection-archive is configured. Full raw responses, player-level rows, headlines, injury records and odds are not copied into postgame-reports. Code/protocol live on main. Failure of this workflow cannot prevent the separate collector from running. Disputed results are withheld. Missing statistics are reported, never fabricated.
