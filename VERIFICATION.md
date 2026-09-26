# Pilot verification — September 26, 2026

- Seven calculation tests passed: odds conversion and settlement, target-book exclusion, stale/started markets, exact-line/player isolation, push/tie holds, book allowlist/deduplication, and required opposing quotes.
- Local API integration passed: missing authentication rejected, cross-origin mutation rejected, missing provider key reported, demo snapshot generated, negative stake rejected, trade persisted, duplicate rejected, losing result saved, settlement overwrite rejected, live/demo board separation preserved.
- TypeScript check passed after adding typed API response handling.
- Browser: local sign-in, live setup state, demo mode, odds board, six-book quote inspection, and simulated loss totals verified. Screenshot reviewed in the in-app viewport.
- WebMCP: read-only board tool registered; valid empty-object input returned the displayed demo board; invalid input rejected.
- Real-provider calls, Maryland bet-slip equivalence, live props coverage, live quote latency, and paid-plan quotas are unverified pending a provider key.
- No trained model, historical backtest, automatic daily run, or proven profitability is included in this pilot.
