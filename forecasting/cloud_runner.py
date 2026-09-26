"""Cloud schedule gate and bounded collection; frozen models are never trained."""
import argparse
import json
import os
from pathlib import Path

import cycle
import live
import operations
import snapshots
from scheduled_run import collection_due


def plan(force=False):
    at=snapshots.now()
    due=force or collection_due(live.LIVE,snapshots.DEFAULT_STORE,at)
    # An explicit override is for deployment/manual recovery, never a backdated run.
    return {'checkedAt':at,'collect':due,'forced':force}


def run():
    before=operations.check_health()
    report=cycle.run_cycle()
    health=operations.check_health()
    output={'errors':report['errors'],'healthBefore':before,'health':health,'schedule':report['schedule'],
            'forecastRuns':report['forecastRuns'],'resultRuns':report['resultRuns'],'scores':report['scores']}
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as handle:
            handle.write('## NFL collection\n\n'+f"Cadence: {report['schedule']['cadence']}. Errors: {len(report['errors'])}.\n\n")
            if not before['healthy']:
                handle.write('Collection needed attention before this run: '+ '; '.join(before['reasons'])+'\n\n')
            for version,metrics in report['scores']['models'].items():
                handle.write(f"- {version}: {metrics['issued']} issued, {metrics['games']} scored, {metrics['pending']} pending.\n")
            handle.write('\nOriginal model versions and issued forecasts are preserved. No training or model promotion runs in this workflow.\n')
    print(json.dumps(output,indent=2))
    return 1 if report['errors'] or not health['healthy'] else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','run','health')); parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    if args.command=='plan':
        value=plan(args.force)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as handle: handle.write('collect='+str(value['collect']).lower()+'\n')
        print(json.dumps(value))
    elif args.command=='health':
        result=operations.check_health(); print(json.dumps(result,indent=2)); raise SystemExit(0 if result['healthy'] else 1)
    else: raise SystemExit(run())
