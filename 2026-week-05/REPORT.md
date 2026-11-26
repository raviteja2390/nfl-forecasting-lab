# 2026 Week 5 postgame analysis — descriptive only

Statistics observed: 2026-11-26T17:08:02.960666Z. Results snapshot: 2026-11-26T17:54:15.316243Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## TB 24 — DAL 16

| Measure | TB | DAL |
|---|---:|---:|
| Passing EPA | 4.07 | -3.18 |
| Passing EPA / (attempts + sacks) | 0.157 | -0.076 |
| Rushing EPA | 4.06 | 1.21 |
| Rushing EPA / carry | 0.104 | 0.093 |
| Interceptions thrown | 0 | 2 |
| Sacks suffered | 1 | 0 |
| Field goals made | 1 | 1 |
| Field goals attempted | 1 | 1 |

- DAL had lower passing EPA than TB (-3.18 versus 4.07).
- DAL had lower rushing EPA than TB (1.21 versus 4.06).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## BUF 37 — LAR 34

| Measure | BUF | LAR |
|---|---:|---:|
| Passing EPA | 6.95 | 15.66 |
| Passing EPA / (attempts + sacks) | 0.347 | 0.285 |
| Rushing EPA | 9.18 | 0.73 |
| Rushing EPA / carry | 0.248 | 0.032 |
| Interceptions thrown | 1 | 0 |
| Sacks suffered | 1 | 1 |
| Field goals made | 3 | 0 |
| Field goals attempted | 3 | 2 |

- LAR had higher passing EPA than BUF (15.66 versus 6.95).
- LAR had lower rushing EPA than BUF (0.73 versus 9.18).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

2 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
