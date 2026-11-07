# Reviewed Week 9 kickoff source lag — November 7, 2026

The existing nflverse feed retains 2026_09_LV_SF at November 8 21:05 UTC. ESPN event 401873047 and the official 49ers schedule show 21:25 UTC (4:25 p.m. EST). Official confirmation: https://www.49ers.com/schedule/ and https://www.49ers.com/news/5-things-to-know-49ers-week-9-matchup-vs-raiders-salute-to-service . These were manually reviewed November 7; no new automated source is added.

The validator accepts only this exact event, team pair, ESPN ID and pair of times. All other kickoff disagreements, live-game states and venue mismatches remain rejected. The original earlier kickoff remains in the forecast and feature row, so the at-least-24-hour deadline stays November 7 21:05 UTC. This is deliberately conservative, not a claim that the two feeds agree. A reviewedScheduleCorrections entry in the saved scoreboard provenance records the confirmed actual time and review source. No raw snapshot is edited, and no model weights, features, inference implementation or existing forecast is changed. Once both sources agree, ordinary validation applies. This exception cannot authorize late issuance or backdating.

Validation: exact-match acceptance and provenance, rejection of wrong event ID, changed times, live status and venue mismatch; existing deadline and feature-parity tests.

Superseded for future issuance by KICKOFF_TOLERANCE.md. The original LV-SF forecasts retain their original reviewed provenance.
