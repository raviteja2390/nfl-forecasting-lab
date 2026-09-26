# Gridiron Lab

Private NFL market-research pilot for Maryland. It compares six Maryland-licensed sportsbooks, saves immutable paper-trade snapshots, and tracks manually verified results. It never submits a real wager.

## Implemented

- The Odds API server adapter for NFL moneylines, spreads, totals, and per-event receptions/passing/rushing/receiving yards.
- Six-book allowlist: DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers. Verify continued Maryland licensing before expanding or using it for real decisions.
- Matching on event, market, player, side, and exact point threshold; stale quotes excluded after 120 seconds.
- Paired proportional margin removal, median of at least three other books excluding the target book, reference dispersion guard. All estimates are unvalidated market baselines.
- Moneylines and integer lines are displayed but held from the shortlist until push/tie probabilities are modeled. No trained sports model is shipped.
- Authenticated, owner-scoped D1 snapshots, paper trades, and immutable manual settlements. Demo data and live data are separate. Export includes full reference quotes and notes.
- Refresh on request only, with a one-minute cooldown. No scheduled collector or daily delivery is enabled. No paid subscriptions were purchased.

## Live setup

Use a key from https://the-odds-api.com/ (note the hyphens).
Set `ODDS_API_KEY` as a secret in the private Site runtime; do not put it in source, URLs you share, browser storage, or a public client variable. Locally, set it in the ignored `.env` file and restart. A populated key is not proof of a working connection: confirm a successful refresh.

Begin by checking API quotes against the Maryland sportsbook bet slip. Feeds can differ by jurisdiction, user, market, time, and settlement rules. Only identical contracts are comparable. Provider integration requires a real key to validate actual coverage and quota consumption.

## Development

Node >=22.13 is required. Run `npm run dev -- --hostname 127.0.0.1` and use the printed URL. Local preview sign-in is simulated by the starter; hosted sign-in is platform-owned. The private Site access policy must be preserved.

Generate schema migrations with `npm run db:generate`. Build using the Sites skill helper, then apply pending SQL locally with the starter README workflow (command below). Production applies schema-only migrations at deployment. Never overwrite a migration already deployed.

```
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_clever_alex_power.sql
```

## Verification

```
node --experimental-strip-types --test tests/odds.test.ts
node node_modules/typescript/bin/tsc --noEmit
node --experimental-strip-types tests/integration.mjs
```

Integration tests require the local preview and migrated local DB. They create clearly labeled synthetic practice trades, never production entries. Repeated tests need the refresh cooldown to expire.

## Measurement limits

Displayed return estimates are market-implied, not calibrated predictions. Book prices are correlated. A 2% candidate filter and an 8-percentage-point dispersion cutoff are provisional research settings. Gross ledger returns exclude provider costs, infrastructure, taxes and real execution differences. Settled turnover excludes voids; pushes are included. Only the most recent 1,000 records are shown/exported in this pilot. Exports expose the cap in the UI.

The next research stages are live quote-quality checks, prospective paper results, chronological held-out backtests and sport-specific features. Injuries, weather, news, automatic settlement, closing-line-value capture, trained probabilities, and historical backtesting are not implemented. Injury/stat sources in the UI are research links, not automatically ingested evidence. Do not label this pilot profitable without data.

A read-only `read_nfl_research_board` WebMCP tool exposes the displayed board in browsers supporting document.modelContext. It makes no external calls or bets.
