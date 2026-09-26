# GitHub repository and archive boundaries

The private repository is `raviteja2390/nfl-forecasting-lab`. It contains the existing website project plus the local NFL forecasting toolkit.

## Included in version control

- Website and forecasting source code, tests, dependency manifests and setup instructions.
- Frozen model artifacts, training plans, checksums, historical evaluation reports and processed feature datasets.
- Saved prospective forecasts, result receipts when present, cycle reports and source-observation metadata.
- The fixed initial `forecasting/data/raw/nflverse-games.csv` training input and its provenance. This small frozen input is distinct from the growing feed archives below.
- The editable project guide and repository documentation.

An initial push is a snapshot of these files. Later local observations and forecasts require subsequent commits and pushes; the collection automation does not automatically synchronize GitHub.

## Retained locally, excluded from Git

- Installed dependencies, including `node_modules/` and `forecasting/.venv/`.
- Environment files and credential files. `.env.example` contains setup placeholders only.
- Raw-response blobs in `forecasting/data/feeds/blobs/` and `forecasting/data/snapshots/blobs/`.
- Exploratory CSV payloads and the scoreboard payload in `forecasting/data/player-probe/`; their provenance JSON files remain included.
- Build output, caches and local tool state.

Excluding a file from Git does not delete or alter it on this computer. Existing model and forecast files are preserved without retraining or rewriting them.

## Restoring a working copy

A Git clone is not a complete backup of the raw observation archives. The tracked receipt metadata refers to content-addressed blobs that must be restored separately, to the same relative paths, before replaying archived observations or running workflows that verify those archives. Downloading the current upstream feed cannot reconstruct an older receipt or replace missing historical bytes.

Keep a separate verified backup of the complete `forecasting/data/`, `forecasting/runs/` and `forecasting/live/` directories. Restore the blob directories before validating the schedule archive with `python3 forecasting/snapshots.py verify`. Player-feed readers also check the hashes of the blobs they load. This repository setup does not create an off-device backup.

Follow `forecasting/README.md` to recreate the Python environment and run the existing checks. Install website dependencies from the committed lockfile using the root README. Credentials must be supplied through the documented environment configuration, never committed.

## Deployment and access

Creating and pushing this repository does not deploy the hosted website, change the collection schedule or promote a model. Keep repository visibility private unless you explicitly decide to publish its contents. Git history and local checksums provide an audit trail, not independently attested timestamps or immutable storage.
