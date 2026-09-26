"""Collection and follow-up health checks on one desktop heartbeat."""
import csv
import io
import json

import cycle
import live
import operations
import snapshots


def collection_due(store, archive, at):
    try:
        state=json.loads((store/'operations/status.json').read_text())
        if state.get('state')=='failed' or not state.get('lastSuccessAt'):
            return True
        selected=snapshots.select_as_of(archive,at,max_age_hours=25)
        if not selected['found']: return True
        body=snapshots.verified_body(archive,selected['observation'])
        dates={r['gameday'] for r in csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
               if r['game_type'] in ('REG','WC','DIV','CON','SB')}
        if not dates: return True
        due=operations.latest_due(at,dates,grace_minutes=0)
        return snapshots.parse_time(state['lastSuccessAt'])<due
    except (OSError,ValueError,KeyError,TypeError):
        return True


def run():
    before=operations.check_health()
    result={'healthBefore':before,'collectionRun':False,'error':None}
    if collection_due(live.LIVE,snapshots.DEFAULT_STORE,snapshots.now()):
        result['collectionRun']=True
        try:
            report=cycle.run_cycle()
            result['cycle']={key:report[key] for key in ('errors','forecastRuns','resultRuns','scores')}
        except Exception as exc:
            result['error']=str(exc)
    result['healthAfter']=operations.check_health()
    result['cadence']=result['healthAfter']['cadence']
    return result


if __name__=='__main__':
    result=run()
    print(json.dumps(result,indent=2,allow_nan=False))
    raise SystemExit(1 if result['error'] or not result['healthAfter']['healthy'] else 0)
