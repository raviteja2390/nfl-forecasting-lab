# 2026 Week 10 postgame analysis — descriptive only

Statistics observed: 2026-11-14T05:08:01.426843Z. Results snapshot: 2026-11-14T14:31:06.408393Z.

Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.

These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.

## WAS 24 — NYG 21

| Measure | WAS | NYG |
|---|---:|---:|
| Passing EPA | 2.03 | 6.89 |
| Passing EPA / (attempts + sacks) | 0.060 | 0.186 |
| Rushing EPA | -0.86 | 2.71 |
| Rushing EPA / carry | -0.026 | 0.100 |
| Interceptions thrown | 2 | 1 |
| Sacks suffered | 1 | 1 |
| Field goals made | 1 | 0 |
| Field goals attempted | 1 | 1 |

- NYG had higher passing EPA than WAS (6.89 versus 2.03).
- NYG had higher rushing EPA than WAS (2.71 versus -0.86).
- The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.

## Coverage and next test

1 games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.

Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.

Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.

A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.
