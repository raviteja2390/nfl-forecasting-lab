# Requested safeguards and candidate review — September 26, 2026

## 1. Backup protection and restore

Previous dated local archives and private release attachments could be removed or replaced by their filesystem owner or a GitHub administrator/token with contents-write permission. Git history and checksums detect some changes but do not prevent an authorized actor rewriting both data and hashes. No S3 bucket or Object Lock is configured.

Chosen approach: option (b), dated write-once snapshots. `forecasting/checkpoint.py create` requires a new `YYYY-MM-DDTHHMMSSZ-checkpoint` directory outside the source repository, creates files exclusively, refuses existing directories, hashes every file and the complete ZIP, and makes the finished local snapshot read-only. The utility has no overwrite/delete command. Each off-device copy uses a distinct private release tag; never use `--clobber` or reuse the tag. This is application-enforced write-once behavior, not WORM retention: an owner/admin can still chmod/delete a directory or delete a release. That distinction remains explicit.

Back up a quiescent, isolated checkout. Restore the latest `forecast-state` branch into that isolated checkout first so cloud observations are included. Never copy concurrently changing live state. The checkpoint includes tracked code/models/reports plus runtime feed/snapshot/live archives, excludes Git credentials and environments, and validates all restore content before writing to a NEW destination.

Restore: download `checkpoint.zip` and `manifest.json` from the dated private release into a local folder, then run `python3 forecasting/checkpoint.py restore --source /absolute/path/to/checkpoint-folder --destination /absolute/path/to/new-restored-project`. Existing restore destinations are refused. A corrupt archive, mismatched member, unsafe path or changed file hash aborts restoration. The restored project contains code, models and evidence; recreate its Python environment from `forecasting/requirements-training.txt`. It does not contain Git authentication. Pause the cloud collector before intentionally transferring collection ownership to a restored local instance. Preserve the original archive and use the recorded archive SHA to verify the download independently.

## 2. Cloud scope, cost, time and secrets

Service: GitHub Actions standard hosted Ubuntu runners, private repository; state persists on `forecast-state`. No AWS service or paid data API is used by these workflows. Estimated monthly collector/watchdog usage remains approximately 1,326–1,382 minutes, allowing two-minute collections plus 20% headroom, with a planning allocation of 1,500 minutes. The one-time verification workflow added here is manual only and adds its actual runtime when dispatched.

GitHub Free includes 2,000 account-wide private-runner minutes. Expected additional runner charge is $0 if sufficient included allowance remains. This is NOT an actual invoice or a spending cap. The account billing endpoint returned 404 and explicitly reported that the authenticated credential lacks the `user` scope; no actual monthly bill, remaining allowance, or other-project usage was accessible. No billing scope or paid plan was changed. The user can verify actual charges in GitHub Settings → Billing and licensing → Usage. All spending must remain within the user's combined $1,000 budget; this work does not authorize spending that amount or reserve it for infrastructure. Private release/Git storage must also be monitored; it is not unlimited immutable storage.

Timing: `cloud_runner.run` invokes the same `cycle.run_cycle` and `live.publish` as local execution, and imports the identical `scheduled_run.collection_due` gate. `live.publish` checks the actual issue time before feature generation AND again before writing: generatedAt must be <= kickoff minus 24 elapsed hours in UTC. The policy is AT LEAST 24 hours, not issuance exactly at T-24. GitHub can delay a trigger; a delay crossing the deadline causes refusal, never backdating. The hourly UTC :17 trigger differs from the earlier local :05 trigger but does not change eligibility. `America/New_York` is used for game-day selection and the next local calendar date; comparisons use aware UTC times, including DST. Added tests exercise both repeated fall-back hours, the spring gap, shared cloud/local function identity, and crossing the issue deadline during generation. Existing tests cover stale/post-cutoff/corrupt observations. Run these tests locally and on GitHub's Linux runner.

Credentials: collector receives GitHub's short-lived `github.token` as runner-only `GH_TOKEN`, with contents/issue-write permissions; watchdog uses contents-read/issue-write. Checkout v7 can persist job authentication in temporary runner storage for the state push; it is not committed. The verification job disables credential persistence and has contents-read only. Repository secret listing returned no configured repository secrets. Local GitHub CLI authentication is separate from the cloud token. No credentials are intentionally embedded in reports, model artifacts or browser-side code. This audit includes a heuristic reachable-history scan; it is not proof against every secret format or a full hosted-website audit. The Odds API key previously pasted into chat was browser-visible there already, so we cannot claim it has never been exposed; it is not needed by these cloud jobs. Rotate it before any future integration and store a replacement server-side, never in chat or frontend code.

References: https://docs.github.com/en/billing/concepts/product-billing/github-actions and `.github/workflows/`.

## 3. Opponent-adjusted bootstrap

544 games, 36 season-week blocks, 2,000 paired whole-block resamples, seed 20260926, two-sided 95% percentile intervals with interpolated quantiles. Same draw count and seed convention as the original team evaluation. Improvements are reference minus candidate, so positive favors the candidate.

- Log loss improvement 0.000495407; 95% interval [-0.002601078, 0.003319544].
- Brier improvement 0.000464318; 95% interval [-0.002337411, 0.003180681].

Both include zero: no distinguishable improvement at this sample size under this exploratory method. Log-loss direction is mixed (better in 2023 and 2024, worse in 2025). The exposed cohort and model-selection uncertainty prevent interpreting these intervals as a pristine confirmatory test. Source hashes and full output: `forecasting/reports/candidate-audit/review.json`; reproducible with `python forecasting/candidate_audit.py`.

## 4. Prospective preparation, issuance blocked

Review `protocols/OPPONENT_PROSPECTIVE_DRAFT.md`. The draft was written before any shadow issuer, and `opponent_live_features.py` only prepares features; it does not write forecasts or probabilities and is not connected to either scheduler. It selects hash-verified observations by the actual target cutoff, uses the existing team feature row, reconstructs nested opponent histories under the frozen feature rules, and independently confirms every baseline and nested historical score using observed ESPN final scores. Missing evidence blocks preparation. Historical nested-match publication timing still retains the 48-hour assumption; a receipt collected now cannot establish what was published before a matchup years ago.

Before issuance: user protocol review and explicit authorization, committed activation record with future start/model/code/protocol hashes, then separate issuer implementation and testing. None of those issuance steps has been activated here.

## 5. Margin candidate shelved

Log loss is worse than the reference in ALL three cohorts. Consistent direction alone does not establish statistical significance or prove the entire loss is caused by ties, but the tie calibration defect is clear:

- 2023: mean predicted ties 2.74784%; actual 0/272 = 0%.
- 2024: mean predicted ties 2.74975%; actual 0/272 = 0%.
- 2025: mean predicted ties 2.73722%; actual 1/272 = 0.36765%.

`margin-ridge-v1` is shelved with no shadow/live use, promotion, or further fitting. No isotonic/recalibrated successor was built. A future replacement mapping requires a separate registered candidate and authorization. Frozen artifacts remain intact.

## 6. Reporting convention

Lead with log loss. Explicitly describe direction across 2023/2024/2025 as consistent or mixed. Accuracy is secondary. Do not equate consistency with significance or forecasting scores with profit. Persisted in `MODEL_REVIEW_POLICY.md`.

Verification notes: the initial Linux run passed the timing/DST tests but exposed exact floating-point equality assertions in the two offline experiment replay tests (differences around 1e-16 from platform math libraries). Those assertions now allow an absolute probability tolerance of 1e-14. No model, inference code, forecast or fitted artifact changed. This is numerical rounding, not timestamp or eligibility drift. The initial checkpoint attempt also correctly rejected a tracked `.env.example` template; the safe-path rule now permits that credential-free template while continuing to reject real `.env` files. Its incomplete dated directory is retained and never reused.
