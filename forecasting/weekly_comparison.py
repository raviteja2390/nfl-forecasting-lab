"""Standing NFL-week report from immutable issued forecasts; no new predictions."""
from collections import defaultdict
from datetime import timedelta
import json
from pathlib import Path
import live
import model
import snapshots

VERSIONS=('outcome-logit-v1','player-form-v1','player-availability-v1')
LABELS={'outcome-logit-v1':'Team only (primary)','player-form-v1':'Player form (shadow)','player-availability-v1':'Player availability (shadow)'}


def select_week(games,at):
    day=snapshots.parse_time(at).astimezone(live.features.EASTERN).date()
    weeks=defaultdict(list)
    for g in games:weeks[(g['season'],g['week'])].append(g['localDate'])
    active=[key for key,dates in weeks.items() if min(dates)<=day<=max(dates)]
    if active:return max(active)
    upcoming=[(min(dates),key) for key,dates in weeks.items() if min(dates)>day]
    return min(upcoming)[1] if upcoming else None


def build(games,at,store=live.LIVE):
    week=select_week(games,at)
    rows=[]
    for g in sorted(games,key=lambda g:(g['kickoff'],g['eventId'])):
        if (g['season'],g['week'])!=week:continue
        versions={}
        for v in VERSIONS:
            path=store/'forecasts'/v/(g['eventId']+'.json')
            if not path.exists():versions[v]={'status':'not-issued'};continue
            f=json.loads(path.read_text())
            if snapshots.parse_time(f['generatedAt'])>snapshots.parse_time(at):versions[v]={'status':'not-issued-as-of-report'};continue
            if f['eventId']!=g['eventId'] or f['modelVersion']!=v:raise ValueError('Forecast identity mismatch')
            model.score(f['probabilities'],'homeWin') # Validate distribution without using outcomes.
            deadline=snapshots.parse_time(f['kickoffAt'])-timedelta(hours=24)
            valid=(f['mode']=='prospective' and snapshots.parse_time(f['generatedAt'])<=deadline
                   and snapshots.parse_time(f['featureCutoffAt'])<=snapshots.parse_time(f['generatedAt']))
            versions[v]={'status':'issued' if valid else 'timing-invalid','probabilities':f['probabilities'],
                         'generatedAt':f['generatedAt'],'featureCutoffAt':f['featureCutoffAt'],
                         'kickoffAt':f['kickoffAt'],'modelSha256':f['modelSha256']}
        complete=all(versions[v]['status']=='issued' for v in VERSIONS)
        aligned=complete and len({(versions[v]['featureCutoffAt'],versions[v]['kickoffAt']) for v in VERSIONS})==1
        rows.append({'eventId':g['eventId'],'away':g['awayTeamId'],'home':g['homeTeamId'],
                     'scheduledKickoff':live.features.iso(g['kickoff']),'models':versions,'paired':aligned,
                     'scheduleChanged':any(r.get('kickoffAt')!=live.features.iso(g['kickoff']) for r in versions.values() if 'kickoffAt' in r)})
    return {'generatedAt':at,'season':week[0] if week else None,'week':week[1] if week else None,
            'scheduledGames':len(rows),'fullyPairedGames':sum(r['paired'] for r in rows),'games':rows}


def render(report):
    title=f"{report['season']} NFL Week {report['week']}" if report['week'] else 'No upcoming regular-season week in observed schedule'
    lines=['# This week’s three-model comparison','',title,'',f"Updated {report['generatedAt']}. {report['scheduledGames']} scheduled games; {report['fullyPairedGames']} have all three forecasts with matching cutoffs and kickoff times.",'',
           'All kickoff times Eastern. Probabilities are original issued forecasts, not live updates. Players are included only in the two shadow models; none has established a betting edge. No missing forecast is backfilled. Rounded percentages may not sum to exactly 100%.','',
           'Week selection uses the observed NFL season/week, including its Monday games. Between weeks it shows the next scheduled week. Results and log-loss progress are in [STATUS.md](STATUS.md).','']
    for g in report['games']:
        when=snapshots.parse_time(g['scheduledKickoff']).astimezone(live.features.EASTERN).strftime('%a %b %d, %I:%M %p %Z')
        lines += [f"## {g['away']} at {g['home']} — {when}",'']
        for v,r in g['models'].items():
            if 'probabilities' not in r:lines.append(f"- **{LABELS[v]}:** not issued as of this report.");continue
            p=r['probabilities']
            lines.append(f"- **{LABELS[v]}:** {g['away']} {p['awayWin']:.1%} · {g['home']} {p['homeWin']:.1%} · tie {p['tie']:.1%}. Issued {r['generatedAt']}; cutoff {r['featureCutoffAt']}.")
        if not g['paired']:lines.append('Comparison incomplete or cutoffs differ; do not treat this as a valid three-model paired observation.')
        if g['scheduleChanged']:lines.append('Schedule changed since issuance; original forecast kickoff and probabilities are preserved in the JSON report.')
        lines.append('')
    return '\n'.join(lines)


def write_report(games,at=None,store=live.LIVE):
    report=build(games,at or snapshots.now(),store)
    folder=store/'reports';folder.mkdir(parents=True,exist_ok=True)
    names=['weekly-comparison']
    if report['week']:names.append(f"{report['season']}-week-{report['week']:02d}-comparison")
    for name in names:
        (folder/(name+'.md')).write_text(render(report))
        (folder/(name+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return {'season':report['season'],'week':report['week'],'scheduledGames':report['scheduledGames'],'fullyPairedGames':report['fullyPairedGames']}


if __name__=='__main__':
    at=snapshots.now();_,games=live.current_games(at)
    print(json.dumps(write_report(games,at)))
