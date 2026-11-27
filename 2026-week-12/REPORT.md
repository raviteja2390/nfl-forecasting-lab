# 2026 Week 12 postgame analysis — descriptive only

Statistics observed: 2026-11-27T04:08:34.721966Z. Results snapshot: 2026-11-27T17:39:17.432566Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## GB 13 — LAR 26

| Measure | GB | LAR |
|---|---:|---:|
| Passing EPA | -2.79 | -1.96 |
| Passing EPA / (attempts + sacks) | -0.093 | -0.082 |
| Rushing EPA | -0.42 | 2.19 |
| Rushing EPA / carry | -0.030 | 0.047 |
| Interceptions thrown | 2 | 1 |
| Sacks suffered | 1 | 1 |
| Field goals made | 2 | 4 |
| Field goals attempted | 2 | 4 |

- GB had lower passing EPA than LAR (-2.79 versus -1.96).
- GB had lower rushing EPA than LAR (-0.42 versus 2.19).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## CHI 39 — DET 35

| Measure | CHI | DET |
|---|---:|---:|
| Passing EPA | 8.65 | 0.48 |
| Passing EPA / (attempts + sacks) | 0.180 | 0.013 |
| Rushing EPA | 8.92 | 8.63 |
| Rushing EPA / carry | 0.372 | 0.278 |
| Interceptions thrown | 0 | 1 |
| Sacks suffered | 4 | 1 |
| Field goals made | 1 | 2 |
| Field goals attempted | 1 | 2 |

- DET had lower passing EPA than CHI (0.48 versus 8.65).
- DET had lower rushing EPA than CHI (8.63 versus 8.92).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## PHI at DAL

Verified final exists, but player-stat coverage is incomplete; analysis withheld.

## KC at BUF

Verified final exists, but player-stat coverage is incomplete; analysis withheld.

## Coverage and next test

2 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
