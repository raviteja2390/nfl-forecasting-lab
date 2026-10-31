# 2026 Week 8 postgame analysis — descriptive only

Statistics observed: 2026-10-31T04:07:51.708807Z. Results snapshot: 2026-10-31T13:53:56.056248Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## CAR 19 — GB 27

| Measure | CAR | GB |
|---|---:|---:|
| Passing EPA | -7.60 | 11.74 |
| Passing EPA / (attempts + sacks) | -0.162 | 0.286 |
| Rushing EPA | -2.83 | -3.40 |
| Rushing EPA / carry | -0.123 | -0.131 |
| Interceptions thrown | 1 | 1 |
| Sacks suffered | 6 | 0 |
| Field goals made | 2 | unknown |
| Field goals attempted | 2 | unknown |

- CAR had lower passing EPA than GB (-7.60 versus 11.74).
- CAR had higher rushing EPA than GB (-2.83 versus -3.40).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

1 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
