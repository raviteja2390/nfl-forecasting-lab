# 2026 Week 7 postgame analysis — descriptive only

Statistics observed: 2026-10-25T11:27:30.118489Z. Results snapshot: 2026-10-25T12:46:34.464219Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## NE 24 — CHI 30

| Measure | NE | CHI |
|---|---:|---:|
| Passing EPA | 10.57 | 13.56 |
| Passing EPA / (attempts + sacks) | 0.320 | 0.377 |
| Rushing EPA | -2.81 | -2.22 |
| Rushing EPA / carry | -0.165 | -0.074 |
| Interceptions thrown | 1 | 0 |
| Sacks suffered | 2 | 3 |
| Field goals made | 1 | 3 |
| Field goals attempted | 1 | 4 |

- NE had lower passing EPA than CHI (10.57 versus 13.56).
- NE had lower rushing EPA than CHI (-2.81 versus -2.22).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

1 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
