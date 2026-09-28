"""Read verified public forecast-state evidence and write isolated descriptive reports."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import cloud_state
from postgame_report import build


def load(path):
    return json.loads(path.read_text())


def disputed_events(live, at):
    latest = {}
    for path in (live / 'rechecks').glob('*.json'):
        row = load(path)
        if row['checkedAt'] <= at and (row['date'] not in latest or row['checkedAt'] > latest[row['date']]['checkedAt']):
            latest[row['date']] = row
    return {event for r in latest.values() for key in ('sourceDisagreements', 'previouslyFinalNowPending') for event in r.get(key, [])}


def assemble(root, weekly, provenance, at, commit):
    live = root / 'forecasting/live'
    disputed = disputed_events(live, at)
    games, excluded = [], []
    for game in weekly['games']:
        event = game['eventId']
        if event in disputed:
            excluded.append({'eventId': event, 'reason': 'disputed-result'})
            continue
        results = [load(p) for p in (live / 'results' / event).glob('*.json')]
        results = [r for r in results if r['finalizedAt'] <= at]
        if not results:
            excluded.append({'eventId': event, 'reason': 'no-verified-final'})
            continue
        result = max(results, key=lambda r: (r['finalizedAt'], r['espnObservationId']))
        if result['eventId'] != event or result['timingBasis'] != 'observed-final-in-two-sources':
            raise ValueError('Invalid final provenance')
        if any(type(result[k]) is not int or result[k] < 0 for k in ('homeScore', 'awayScore')):
            raise ValueError('Invalid scores')
        if provenance['observedAt'] <= game['scheduledKickoff']:
            excluded.append({'eventId': event, 'reason': 'stats-snapshot-predates-kickoff'})
            continue
        games.append({**game, 'result': result})
    return {**weekly, 'games': games, 'excluded': excluded, 'asOf': at, 'sourceStateCommit': commit}


def run(state, output, commit):
    at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        cloud_state.restore(state, root)
        feeds = root / 'forecasting/data/feeds'
        observations = [load(p) for p in (feeds / 'observations').glob('*.json')]
        reports = sorted((root / 'forecasting/live/reports').glob('????-week-??-comparison.json'))
        if not reports:
            raise ValueError('No weekly forecast reports in state')
        index = ['# NFL postgame research reports', '', f'Generated {at}. Source forecast-state commit: `{commit}`.', '',
                 'Descriptive statistics only; no model training, causal claims or changes to frozen forecasts. Raw inputs remain in their existing stores; this branch contains derived reports only.', '',
                 'Report generation uses the latest available archived statistics, which can still be incomplete or revised. A successful run does not certify every statistic. Excluded games and source receipt timestamps are in each JSON report.', '',
                 '[Research protocol](https://github.com/raviteja2390/nfl-forecasting-lab/blob/main/docs/protocols/POSTGAME_RESEARCH_V1.md)', '']
        output.mkdir(parents=True, exist_ok=True)
        for path in reports:
            weekly = load(path)
            season = str(weekly['season'])
            url = f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
            eligible = [r for r in observations if r.get('kind') == 'stats' and r.get('key') == season and r.get('sourceUrl') == url and r['observedAt'] <= at]
            name = f"{season}-week-{weekly['week']:02d}"
            if not eligible:
                index.append(f'- {name}: no eligible archived player-stat snapshot; no analysis generated.')
                continue
            provenance = max(eligible, key=lambda r: (r['observedAt'], r['id']))
            comparison = assemble(root, weekly, provenance, at, commit)
            body = (feeds / 'blobs' / provenance['sha256']).read_bytes()
            count = build(body, provenance, comparison, output / name)
            index.append(f'- [{name}]({name}/REPORT.md): {count} games analyzed; {len(comparison["excluded"])} withheld before statistical coverage checks.')
        (output / 'README.md').write_text('\n'.join(index) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--state-commit', required=True)
    args = parser.parse_args()
    run(args.state, args.output, args.state_commit)
