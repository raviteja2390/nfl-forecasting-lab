# Small kickoff discrepancy policy — November 7, 2026

User-authorized operational schedule tolerance for future issuance; models and statistical evaluation protocols stay frozen. This replaces the one-game LV-SF exception. Already saved forecasts and their original correction metadata remain immutable.

Accept an ESPN kickoff strictly later than nflverse by at most 30 minutes only when the existing matchup key matches (same Eastern date, home and away teams), nflverse's ESPN event ID is nonempty numeric and exactly matches ESPN, ESPN is pregame, and both sources explicitly agree on venue classification. Compare elapsed time in UTC and dates in America/New_York. Reject earlier ESPN times, larger differences, missing IDs, unknown venue, changed dates or live games. Exact-time agreement keeps its existing validation path.

Keep the earlier nflverse kickoff in features and forecasts. All existing at-least-24-hour checks, including the post-inference deadline check, remain enforced against that earlier time. Never add a 30-minute grace period to issuance. The stored kickoff is a conservative deadline basis, not a claim of exact source agreement. Save both source times, difference, policy version and matched event ID in scoreboardObservations.scheduleDiscrepancies. The discrepancy is visible in canonical provenance; raw source responses are not edited. Historical results must still agree exactly and be independently final. No new data provider or paid service.

Tests cover inclusive 30 minutes, rejection beyond the bound, earlier starts, missing/wrong IDs, unknown/conflicting venue, live status and Eastern date rollover, together with existing deadline, feature parity and DST safeguards.
