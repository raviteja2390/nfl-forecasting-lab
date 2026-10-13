"""Audit missed issuance independently of successful collection; never backfill."""
from datetime import timedelta
import json
import operations
import snapshots

VERSIONS = ('outcome-logit-v1', 'player-form-v1', 'player-availability-v1')


def write_coverage(games, store, at):
    records = {v: {p.stem: json.loads(p.read_text()) for p in (store/'forecasts'/v).glob('*.json')} for v in VERSIONS}
    primary = list(records[VERSIONS[0]].values())
    # Start at the first prospectively covered kickoff, excluding pre-launch games.
    start = min((r['kickoffAt'] for r in primary), default=None)
    missed = []
    for game in games:
        if start is None or game['kickoff'] < snapshots.parse_time(start):
            continue
        deadline = game['kickoff'] - timedelta(hours=24)
        if snapshots.parse_time(at) <= deadline:
            continue
        missing = [v for v in VERSIONS if game['eventId'] not in records[v]]
        if missing:
            missed.append({'eventId': game['eventId'], 'deadline': deadline.isoformat(), 'missingModels': missing})
    # Historical gaps remain visible even if a future schedule snapshot omits them.
    path = store/'reports/forecast-coverage.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    by_event = {r['eventId']: r for r in previous.get('missed', [])}
    by_event.update({r['eventId']: r for r in missed})
    missed = sorted(by_event.values(), key=lambda r: r['eventId'])
    result = {'checkedAt': at, 'trackingStartKickoff': start, 'missed': missed,
              'missedGames': len(missed), 'status': 'GAPS' if missed else ('complete-through-cutoff' if start else 'not-initialized')}
    operations.atomic_json(path, result)
    lines = ['# Forecast issuance coverage', '', f'Checked {at}.', '',
             f'{len(missed)} games have missed model issuance. Collection success does not resolve these gaps.', '',
             'Pre-launch games are excluded. No retrospective forecast may fill a prospective gap.', '']
    lines += [f"- {r['eventId']}: missing {', '.join(r['missingModels'])}; deadline {r['deadline']}" for r in missed]
    (store/'reports/forecast-coverage.md').write_text('\n'.join(lines)+'\n')
    return result
