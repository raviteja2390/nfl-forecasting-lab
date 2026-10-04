# Week 4 operational repair — October 4, 2026

The postgame report failed when archived Rams statistics arrived with team code LA while issued forecast reports used LAR. The report now uses the existing validated team-code mapping on statistics team/opponent fields and comparison teams. Source event IDs and archived bytes are preserved. Unknown teams, genuine opponent mismatches, checksum failures and duplicate player/game/team rows still fail; normalization happens before duplicate detection.

The public collector had successful but delayed GitHub scheduled starts. Its external cron-job.org trigger currently covers the private archive only. The public watchdog now runs hourly at minute 47 UTC, alongside the normal collector schedule at minute 17. Both use the same serialized collector and Eastern/DST-aware due gate, preserving daily non-game-day collection and hourly game-day collection. Repeated checks in an already-covered slot do not recollect. The 24-hour issuance cutoff and frozen forecasts are unchanged.

This is scheduling redundancy, not an independent scheduler or an exact hourly guarantee. GitHub can delay both schedules. Independent public dispatch requires a separately scoped credential/external trigger; the existing private-only token must not be silently broadened. Missing historical observations cannot be reconstructed by a recovery run.

Validation: nine postgame tests (including alias match, real opponent mismatch, normalized duplicate detection and checksum failure); eleven operations tests including repeated-slot suppression and DST handling; actual forecast-state replay at 6e281b3 generates 15 Week 3 games and one Week 4 game, retaining exclusions for unverified finals.
