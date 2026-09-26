# NFL cloud collection on GitHub Actions

The cloud collector runs on GitHub-hosted Ubuntu runners. Your Mac and Codex do not need to be running. The existing desktop collector is paused after a successful cloud deployment to avoid two independent writers issuing forecasts.

## Schedule and execution

- `.github/workflows/nfl-collector.yml` starts an hourly check at 17 minutes past the hour, in UTC. Because the hourly pattern is timezone-independent, Python can select the correct daily/hourly collection policy using America/New_York and actual NFL schedule dates, including daylight-saving transitions.
- Successful collection runs hourly on regular-season/postseason game dates and once daily otherwise. Off-day hourly invocations check state without installing the model runtime or downloading the public feeds again. Failed or missed runs can be retried on the next hourly invocation. The daily boundary is 00:05 Eastern; the normal next GitHub trigger is 00:17 Eastern.
- Manual dispatch accepts `force=true` for one deployment/recovery collection. It cannot backdate a forecast or overwrite an issued prediction.
- A separate lightweight watchdog runs daily at 12:47 UTC. It reads persisted evidence and fails if the collector is stale. It does not collect, train, promote or modify the persisted research state.
- GitHub schedules are best effort: jobs can be delayed or dropped. This setup removes the Mac dependency, but both jobs depend on GitHub. It does not provide guaranteed exact-time execution or protection against a GitHub-wide outage.
- Eight-minute collector and four-minute watchdog timeouts bound individual runs. Collector concurrency is serialized; active runs are not cancelled by a new scheduled run.

## Persistent state and integrity

Code, frozen models and the original reports live on `main`. Ongoing source payloads, actual observation receipts, issued forecasts, result receipts, operational status and updated reports live on the private `forecast-state` branch. Each persisted file is compressed independently with deterministic gzip and recorded by uncompressed SHA-256 and size in `manifest.json`.

Each runner restores this state before using it. Missing/corrupt archives fail closed; a runner must not silently restart an empty history. Immutable evidence cannot change in place. Reports and current status are explicitly mutable views. New state is committed with a normal fast-forward push after collection, including failure evidence when restoration succeeded. A push failure fails the workflow rather than claiming durable success. A hard-killed runner may lose observations it had not yet committed; GitHub logs and the next health check expose the interruption, and missing receipts are never backdated.

Readable reports are copied to `forecast-state/reports/`, including prospective scores and model-comparison reports. `collector-status.json` shows the last successful data collection. Git history and hashes provide an audit trail, not write-once storage or independent timestamp attestation.

The compressed current state has a 250 MB guard. This is not a limit on accumulated Git history: monitor repository growth and move the archive to dedicated object storage if it becomes large. No archives are automatically pruned. The original pre-change backup also remains attached to the private `backup-before-operations-20260926` release.

## Alerts and visibility

Workflow failures create or update one issue titled **NFL cloud collector needs attention** in this private repository, linking to the failed run. A successful collector workflow closes an existing alert after recovery. The watchdog can open an alert but does not close one merely because its own run succeeds. GitHub email/push delivery depends on your notification settings; this setup does not change your email preferences or send to Slack.

- Runs: https://github.com/raviteja2390/nfl-forecasting-lab/actions
- Current reports: https://github.com/raviteja2390/nfl-forecasting-lab/tree/forecast-state/reports
- Operational alerts: https://github.com/raviteja2390/nfl-forecasting-lab/issues

## Costs and credentials

The jobs use standard hosted Linux runners. GitHub currently documents 2,000 monthly runner minutes on its Free plan for private repositories, shared across the account; your actual plan, remaining allowance and other workflows affect cost. An hourly schedule produces approximately 720–744 checks per month, plus 28–31 watchdog checks. Completed jobs are metered by GitHub; dependency installation, retries and longer game-day runs add runtime. This is not a guarantee that the account will stay within its free allowance.

This workflow uses neither Actions artifact storage nor Actions caches for evidence; persistent state uses the private Git branch. No paid data service, AI inference service, credit purchase or billing-plan change was made. Review the account's Actions usage and spending controls if it already permits paid overages. The workflow does not impose an account-wide spending cap.

GitHub supplies a short-lived `GITHUB_TOKEN` scoped to this repository. Collection needs contents write access to save `forecast-state`; alerts need issues write access. The watchdog only needs contents read and issues write. No personal token or Odds API key is stored in the repository. Third-party action references are pinned to verified full commit hashes.

## Reproduction and recovery

Clone `main` into a fresh directory and clone the `forecast-state` branch into a separate directory. Run `python forecasting/cloud_state.py restore --state /absolute/path/to/state-checkout` from the code checkout; it validates hashes before restoring files. Use Python 3.12 and the pinned training requirements for the full cycle. Do not run local collection concurrently with cloud collection; pause the cloud workflow first if intentionally transferring ownership back to the Mac.

Changing code does not change issued model artifacts. The cloud job never retrains, removes model features, fits calibration, promotes a model or deploys the website. The promotion protocol's fixed prospective review remains in force.

Official references, checked September 26, 2026:

- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.github.com/en/billing/concepts/product-billing/github-actions

## Measured monthly runner budget (September 26, 2026)

Three successful cloud benchmarks measured job start-to-completion time:

- Full collection: **31 seconds**, [run 36252843164](https://github.com/raviteja2390/nfl-forecasting-lab/actions/runs/36252843164).
- Lightweight check with collection and dependency installation skipped: **11 seconds**, [run 36252936887](https://github.com/raviteja2390/nfl-forecasting-lab/actions/runs/36252936887).
- Daily watchdog: **10 seconds**, [run 36252844874](https://github.com/raviteja2390/nfl-forecasting-lab/actions/runs/36252844874).

Budget conservatively in whole minutes per job rather than treating these seconds as the billed invoice. The timing API initially reported zero billable time despite nonzero completed job runtimes; that is not evidence of free private runs. Each workflow has one job.

Using actual game dates from the archived schedule observed at 2026-09-26T15:30:48.493114Z (SHA-256 `c0a65089a0110513fa88ecd48453682b1d847f851e9ad46479c9e943004f445e`), and enumerating UTC hours within Eastern calendar months:

- 2026-10: 13 game dates; 330 collections, 414 lightweight checks, 31 watchdogs. One-minute-per-job budget: 775 minutes; two-minute collections plus 20% headroom: 1,326 minutes.
- 2026-11: 16 game dates; 399 collections, 322 lightweight checks, 30 watchdogs. One-minute-per-job budget: 751 minutes; two-minute collections plus 20% headroom: 1,380 minutes.
- 2026-12: 15 game dates; 376 collections, 368 lightweight checks, 31 watchdogs. One-minute-per-job budget: 775 minutes; two-minute collections plus 20% headroom: 1,382 minutes.

November includes the extra hour on the November 1 daylight-saving transition. January is excluded because the archived postseason dates are incomplete. Future scheduling changes can change the collection/check mix.

For October, the planning calculation is `(330 × 2 + 414 × 1 + 31 × 1) × 1.20 = 1,326 minutes`. A working allocation of **1,500 minutes/month** covers these three modeled months, leaving 500 minutes against GitHub Free's 2,000-minute account allowance if other projects do not consume it. The API did not disclose this account's plan or remaining allowance; those have not been verified. Keeping the repository private is reasonable on this evidence; public visibility is not necessary solely for the current schedule's expected minute usage.

This is a small benchmark, not a monthly guarantee. The full collection ran on an off-day with tomorrow's forecasts already issued; it did not measure first-time forecast issuance or heavy settlement work. Archive growth, dependency downloads, failures, manual runs and other repositories may increase usage. With three-minute collections and the same headroom, October would use 1,722 minutes; with four-minute collections, 2,118 minutes. Review actual billing usage after a representative game week. Routine model retraining is not scheduled and is not included in this estimate. Data subscriptions and other services are separate.

All 42 existing issued forecasts matched their original hashes in the cloud state. The repository remains private. The cloud collector and watchdog succeeded; the desktop collector is paused.
