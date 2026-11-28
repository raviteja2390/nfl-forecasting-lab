# 2026 Week 12 postgame analysis — descriptive only

Statistics observed: 2026-11-28T05:08:21.351437Z. Results snapshot: 2026-11-28T16:24:42.259175Z.

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

## PHI 39 — DAL 38

| Measure | PHI | DAL |
|---|---:|---:|
| Passing EPA | 8.10 | 11.00 |
| Passing EPA / (attempts + sacks) | 0.225 | 0.355 |
| Rushing EPA | -2.91 | 0.46 |
| Rushing EPA / carry | -0.162 | 0.012 |
| Interceptions thrown | 1 | 1 |
| Sacks suffered | 5 | 3 |
| Field goals made | 2 | 1 |
| Field goals attempted | 2 | 2 |

- DAL had higher passing EPA than PHI (11.00 versus 8.10).
- DAL had higher rushing EPA than PHI (0.46 versus -2.91).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## KC 10 — BUF 13

| Measure | KC | BUF |
|---|---:|---:|
| Passing EPA | 0.03 | -12.82 |
| Passing EPA / (attempts + sacks) | 0.001 | -0.557 |
| Rushing EPA | -1.23 | 5.05 |
| Rushing EPA / carry | -0.061 | 0.117 |
| Interceptions thrown | 0 | 2 |
| Sacks suffered | 1 | 2 |
| Field goals made | 1 | 2 |
| Field goals attempted | 2 | 2 |

- KC had higher passing EPA than BUF (0.03 versus -12.82).
- KC had lower rushing EPA than BUF (-1.23 versus 5.05).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## DEN at PIT

Verified final exists, but player-stat coverage is incomplete; analysis withheld.

## Coverage and next test

4 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
