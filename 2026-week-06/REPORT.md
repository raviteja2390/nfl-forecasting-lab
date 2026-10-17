# 2026 Week 6 postgame analysis — descriptive only

Statistics observed: 2026-10-17T06:15:59.869234Z. Results snapshot: 2026-10-17T11:45:44.795811Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## SEA 14 — DEN 17

| Measure | SEA | DEN |
|---|---:|---:|
| Passing EPA | -6.74 | -6.08 |
| Passing EPA / (attempts + sacks) | -0.120 | -0.210 |
| Rushing EPA | -0.39 | -1.97 |
| Rushing EPA / carry | -0.015 | -0.070 |
| Interceptions thrown | 2 | 0 |
| Sacks suffered | 5 | 2 |
| Field goals made | 2 | 1 |
| Field goals attempted | 3 | 1 |

- SEA had lower passing EPA than DEN (-6.74 versus -6.08).
- SEA had higher rushing EPA than DEN (-0.39 versus -1.97).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

1 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
