# Operational safeguards — September 26, 2026

## Preserved state

Before code changes, 256 files under `forecasting/` and `docs/` (excluding the Python environment and caches) were copied into a compressed archive, restored into a temporary directory, and checked against individual SHA-256 hashes. This includes the raw feed archives omitted from normal Git commits.

- Local backup: `../.nfl-backups/20260926T152435Z/`
- Private off-device copy: https://github.com/raviteja2390/nfl-forecasting-lab/releases/tag/backup-before-operations-20260926
- Archive: `nfl-pre-operations.tar.gz`, 20,067,755 bytes.
- SHA-256: `77dd7fb36dd34894164a57c18f2dc1d71bcbf0ee372163544f4893d15671bbb8`.
- GitHub's uploaded asset digest matched this local checksum.
- Original project commit: `dd0c8f20ba1cf1577fdd10cfc2b60e3b1db7c771`.
- Original training artifacts and issued forecasts remain unchanged.

The local copy is read-only to reduce accidental edits. Neither filesystem permissions nor a private GitHub release provide immutable storage or external timestamp attestation. Restore requires checking the manifest, rejecting unexpected or unsafe archive paths, and restoring to a separate location before replacing a working archive. This is one point-in-time backup, not recurring backup coverage.

## Implemented scope

- Fixed, versioned promotion criteria for the two existing player challengers, committed before prospective results.
- Cycle locking, success/failure status, and missed-run health checks with cadence-aware deadlines.
- Seven-calendar-date rechecks of settled games, unlimited-age rechecks of pending games, correction audit receipts and quarantine of source-disputed scores.
- Supplemental calibration JSON and HTML for all three historical model comparisons, including bin counts and uncertainty bars.
- Prospective paired reporting, fixed-review promotion gates and prospective calibration once outcomes are observed.

The team model remains primary. No fitting, feature removal, recalibration, parameter search, model promotion, stake sizing, paid service purchase or website deployment is part of this change. The unused-feature cleanup remains optional maintenance; an identical-output model cannot meet an improvement threshold.

## Remaining scope

Opponent-adjusted features and margin models are separate future experiments. They must preserve as-of feature timing and use new versioned artifacts. Odds capture and same-time market benchmarks remain a separate integration task; this operational update does not establish closing-line value or profitability.

A local health checker cannot notify while the host or Codex is off. The app permits one heartbeat per conversation, so the existing heartbeat combines due collection with follow-up health checks at :05 and :35 (hourly on game days, midnight only on off-days). A successful :05 collection is not repeated at :35. Missing/failed collections can be retried. This is not an independent scheduler: a hung agent may delay monitoring too. Independent off-device monitoring is still needed for that guarantee. Scheduled desktop runs consume normal Codex plan allowance. No external email or Slack destination is configured.

## Cloud execution added following the user's Mac-availability requirement

The desktop-only monitoring limitation led to a GitHub Actions deployment, with persisted private-branch archives and an independent daily watchdog workflow. The earlier combined desktop schedule is retained only as a fallback; it is paused once the cloud run is verified. See `CLOUD_OPERATIONS.md` for the current operating design. The same-host limitations above describe the local fallback, while the cloud jobs depend on GitHub availability and account Actions allowance instead.

## Opponent-adjusted experiment — September 26, 2026

The separately committed `forecasting/opponent-plan.json` defined the experiment before fitting. `opponent-adjusted-v1` adds six inputs: each team's mean scoring and conceding residual relative to its previous opponents' pre-match scoring averages, plus usable-history counts. Both levels of history enforce the original 24-hour pregame cutoff, 48-hour assumed score-availability delay, no same-week outcomes, and an eight-game regular-season window.

Training uses 2015–2022, with C selected on 2023 log loss. Saved feature rows include nested opponent-history evidence. Frozen model bytes, input manifests, code hashes, predictions, calibration plots and comparison results are in `forecasting/runs/opponent-adjusted-v1/`. The existing models and live scheduler are unchanged.

On the already-exposed 544 games in 2024–2025, log loss is 0.651206 versus the reference's 0.651701, but accuracy falls from 340/544 to 339/544. The candidate's 2025 log loss is worse than the reference. These exploratory differences do not establish improvement or profitability. Keep the existing primary model. This candidate is saved for offline research; it is not yet issuing live shadow forecasts. A new prospective protocol and an observation-time-aware live adapter are required before that step. The retrospective feature builder must not be used directly for live forecasts.

Margin regression, timestamped odds/closing-line evaluation, optional zero-weight feature cleanup, and prospective validation remain outstanding.
