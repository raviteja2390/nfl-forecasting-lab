# External public collector trigger

Run `python3 forecasting/setup_external_scheduler.py` in a normal local terminal. The hidden prompts request a cron-job.org API key and a separate fine-grained GitHub token. On GitHub choose owner raviteja2390, only nfl-forecasting-lab, Actions read/write and automatic Metadata read. Do not use the private archive token or paste secrets in chat. Choose an expiration and renew before expiry.

The helper validates repository identity and exercises workflow dispatch, then creates or updates only the exact public job title and endpoint. It rejects ambiguous listings and HTTP redirects. Keys are not persisted locally or printed. The GitHub token is stored in the cron-job.org job's Authorization header; that service must hold it to dispatch unattended. Response saving is disabled.

The job dispatches main's nfl-collector.yml hourly at :07 UTC with force=false and trigger_source=cron-job.org. The collector's Eastern/DST-aware due gate retains daily non-game-day and hourly game-day collection. Existing GitHub schedules remain fallbacks and share the collector concurrency lock. The private scheduler is unchanged.

Setup success is not proof of unattended execution. Use `python3 forecasting/setup_external_scheduler.py --check` to inspect safe execution status (requires the cron API key only). Confirm an HTTP 204 dispatch in scheduler history, a completed GitHub run labeled cron-job.org, and fresh collector-status.json. GitHub runner availability remains a dependency. No model, forecast cutoff, source permission, or protocol changes.

Settings: https://github.com/settings/personal-access-tokens/new and https://console.cron-job.org/settings . Scheduler API reference: https://docs.cron-job.org/rest-api.html .
