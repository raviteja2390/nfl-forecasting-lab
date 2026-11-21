# 2026 Week 11 postgame analysis — descriptive only

Statistics observed: 2026-11-21T15:08:11.127032Z. Results snapshot: 2026-11-21T15:37:46.040975Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## IND 3 — HOU 26

| Measure | IND | HOU |
|---|---:|---:|
| Passing EPA | -9.87 | 7.46 |
| Passing EPA / (attempts + sacks) | -0.318 | 0.266 |
| Rushing EPA | -5.09 | -6.36 |
| Rushing EPA / carry | -0.299 | -0.172 |
| Interceptions thrown | 1 | 1 |
| Sacks suffered | 2 | 1 |
| Field goals made | 1 | 1 |
| Field goals attempted | 3 | 1 |

- IND had lower passing EPA than HOU (-9.87 versus 7.46).
- IND had higher rushing EPA than HOU (-5.09 versus -6.36).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

1 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
