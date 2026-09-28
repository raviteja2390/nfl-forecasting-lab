"""Local descriptive postgame report; no network, training or production writes."""
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def number(value):
    if value in (None, '', 'NA', 'NaN'):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite statistic')
    return result


def total(rows, field):
    values = [number(r.get(field)) for r in rows]
    return None if not values or any(v is None for v in values) else sum(values)


def aggregate(rows):
    passing = [r for r in rows if (number(r.get('attempts')) or 0) > 0 or (number(r.get('sacks_suffered')) or 0) > 0]
    rushing = [r for r in rows if (number(r.get('carries')) or 0) > 0]
    kicking = [r for r in rows if (number(r.get('fg_att')) or 0) > 0]
    result = {'rows': len(rows)}
    for field in ('attempts', 'passing_epa', 'passing_interceptions', 'sacks_suffered'):
        result[field] = total(passing, field)
    for field in ('carries', 'rushing_epa'):
        result[field] = total(rushing, field)
    for field in ('fg_att', 'fg_made'):
        result[field] = total(kicking, field)
    result['passing_epa_per_attempt_plus_sack'] = None
    a, s, e = (result[k] for k in ('attempts', 'sacks_suffered', 'passing_epa'))
    if a is not None and s is not None and e is not None and a + s > 0:
        result['passing_epa_per_attempt_plus_sack'] = e / (a + s)
    c, e = result['carries'], result['rushing_epa']
    result['rushing_epa_per_carry'] = e / c if c and e is not None else None
    return result


def fmt(v, digits=1):
    return 'unknown' if v is None else f'{v:.{digits}f}'


def build(body, provenance, comparison, output_dir):
    if hashlib.sha256(body).hexdigest() != provenance['sha256'] or len(body) != provenance['bytes']:
        raise ValueError('Stats integrity mismatch')
    season, week = comparison['season'], comparison['week']
    grouped, seen = defaultdict(list), set()
    for row in csv.DictReader(body.decode('utf-8-sig').splitlines()):
        if row['season'] != str(season) or row['week'] != str(week) or row['season_type'] != 'REG':
            continue
        identity = (row['game_id'], row['team'], row['player_id'])
        if identity in seen:
            raise ValueError('Duplicate player/game/team')
        seen.add(identity)
        grouped[(row['game_id'], row['team'])].append(row)
    output = []
    lines = [f'# {season} Week {week} postgame analysis — descriptive only', '',
             f"Statistics observed: {provenance['observedAt']}. Results snapshot: {comparison['asOf']}.", '',
             'Source: nflverse contributors; existing archived player-stat feed. No new source, training or live model change.', '',
             'These are statistical differences associated with the final result, not proven causes. Both teams are shown. EPA means expected points added; it is not actual points scored. Missing values stay unknown. No model log-loss improvement has been tested.', '']
    for game in comparison['games']:
        result = game['result']
        if not result:
            continue
        if result['timingBasis'] != 'observed-final-in-two-sources':
            raise ValueError('Unverified final')
        home, away = game['home'], game['away']
        teams = {team: aggregate(grouped[(game['eventId'], team)]) for team in (away, home)}
        for team, stats in teams.items():
            # Missing team rows are reported below, never interpreted as zero.
            if any(r['opponent_team'] != (home if team == away else away) for r in grouped[(game['eventId'], team)]):
                raise ValueError('Opponent mismatch')
        if not all(stats['rows'] for stats in teams.values()):
            lines += [f'## {away} at {home}', '', 'Verified final exists, but player-stat coverage is incomplete; analysis withheld.', '']
            continue
        loser = away if result['awayScore'] < result['homeScore'] else home if result['homeScore'] < result['awayScore'] else None
        winner = home if loser == away else away if loser else None
        lines += [f"## {away} {result['awayScore']} — {home} {result['homeScore']}", '',
                  '| Measure | ' + away + ' | ' + home + ' |', '|---|---:|---:|']
        for label, field, digits in [('Passing EPA', 'passing_epa', 2), ('Passing EPA / (attempts + sacks)', 'passing_epa_per_attempt_plus_sack', 3), ('Rushing EPA', 'rushing_epa', 2), ('Rushing EPA / carry', 'rushing_epa_per_carry', 3), ('Interceptions thrown', 'passing_interceptions', 0), ('Sacks suffered', 'sacks_suffered', 0), ('Field goals made', 'fg_made', 0), ('Field goals attempted', 'fg_att', 0)]:
            lines.append(f'| {label} | {fmt(teams[away][field], digits)} | {fmt(teams[home][field], digits)} |')
        notes = []
        if loser:
            for label, field in [('passing EPA', 'passing_epa'), ('rushing EPA', 'rushing_epa')]:
                l, w = teams[loser][field], teams[winner][field]
                if l is not None and w is not None:
                    direction = 'lower' if l < w else 'higher' if l > w else 'equal'
                    notes.append(f'{loser} had {direction} {label} than {winner} ({l:.2f} versus {w:.2f}).')
            notes.append('The score and these components do not establish the cause of defeat; efficiency, game state and unmeasured phases can disagree.')
        lines += ['', *['- ' + n for n in notes], '']
        output.append({'eventId': game['eventId'], 'result': result, 'teams': teams, 'loser': loser, 'notes': notes,
                       'availableNoEarlierThan': max(provenance['observedAt'], result['finalizedAt'])})
    lines += ['## Coverage and next test', '',
              f'{len(output)} games have both a verified result and team player-stat rows. Other scheduled games are excluded, not treated as zero-stat games.', '',
              'Passing EPA is aggregated only from passing records; receiving EPA is excluded to avoid counting the same passing plays twice. The passing denominator is attempts plus sacks, not all dropbacks (scrambles excluded from that denominator). Rushing totals can include kneels and scrambles. A missing kicker row is unknown, not proof of zero attempts. Player sums are not an exhaustive team play-by-play accounting.', '',
              'Third downs, red zone, pressure, field position, injuries and weather are not assessed. Raw yards and outcome do not identify coaching or player availability effects.', '',
              'A future offline candidate must use prior-game records observed before its 24-hour cutoff, chronological splits, and the existing evaluation register. Previously inspected weeks are exploratory. See docs/protocols/POSTGAME_RESEARCH_V1.md on the main branch. No predictive benefit or cohort consistency has been established.']
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    report = {'study': 'postgame-research-v1', 'generatedAt': datetime.now(timezone.utc).isoformat(),
              'statsProvenance': {k: provenance[k] for k in ('sourceUrl', 'observedAt', 'sha256', 'bytes')}, 'season': season, 'week': week, 'sourceStateCommit': comparison['sourceStateCommit'], 'excluded': comparison['excluded'], 'resultsAsOf': comparison['asOf'], 'games': output,
              'status': 'descriptive-only; no model evaluated'}
    (output_dir / 'REPORT.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return len(output)
