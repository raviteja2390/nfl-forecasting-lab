# 2026 Week 5 postgame analysis — descriptive only

Statistics observed: 2026-11-18T05:08:09.081199Z. Results snapshot: 2026-11-18T16:43:25.062175Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## TB 24 — DAL 16

| Measure | TB | DAL |
|---|---:|---:|
| Passing EPA | 4.84 | -1.96 |
| Passing EPA / (attempts + sacks) | 0.186 | -0.047 |
| Rushing EPA | 3.63 | 0.52 |
| Rushing EPA / carry | 0.093 | 0.040 |
| Interceptions thrown | 0 | 2 |
| Sacks suffered | 1 | 0 |
| Field goals made | 1 | 1 |
| Field goals attempted | 1 | 1 |

- DAL had lower passing EPA than TB (-1.96 versus 4.84).
- DAL had lower rushing EPA than TB (0.52 versus 3.63).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## BUF 37 — LAR 34

| Measure | BUF | LAR |
|---|---:|---:|
| Passing EPA | 6.36 | 15.97 |
| Passing EPA / (attempts + sacks) | 0.318 | 0.290 |
| Rushing EPA | 8.14 | 0.13 |
| Rushing EPA / carry | 0.220 | 0.006 |
| Interceptions thrown | 1 | 0 |
| Sacks suffered | 1 | 1 |
| Field goals made | 3 | 0 |
| Field goals attempted | 3 | 2 |

- LAR had higher passing EPA than BUF (15.97 versus 6.36).
- LAR had lower rushing EPA than BUF (0.13 versus 8.14).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

2 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
