"""One deduplicated private GitHub issue for cloud operational failures."""
import argparse
import json
import os
import subprocess

TITLE='NFL cloud collector needs attention'


def gh(*args):
    result=subprocess.run(['gh',*args],capture_output=True,text=True,timeout=45,check=True)
    return result.stdout


def notify(failed):
    repository=os.environ['REPOSITORY']
    if repository!='raviteja2390/nfl-forecasting-lab': raise ValueError('Unexpected alert repository')
    run=os.environ['GITHUB_RUN_ID']
    if not run.isdigit(): raise ValueError('Invalid workflow run ID')
    url=f'https://github.com/{repository}/actions/runs/{run}'
    existing=json.loads(gh('issue','list','--repo',repository,'--state','open','--search',TITLE+' in:title','--json','number,title'))
    matching=[i for i in existing if i['title']==TITLE]
    body=('The cloud collector or its health check failed. Review the workflow logs and persisted collector status. Original forecasts must not be rewritten.\n\n' if failed else 'The cloud collection workflow has recovered.\n\n')+'Workflow: '+url
    if failed and not matching:
        gh('issue','create','--repo',repository,'--title',TITLE,'--body',body)
    for item in matching:
        gh('issue','edit',str(item['number']),'--repo',repository,'--body',body)
        if not failed: gh('issue','close',str(item['number']),'--repo',repository)
    print(json.dumps({'failure':failed,'existingAlerts':len(matching),'runUrl':url}))


def coverage_alert():
    from pathlib import Path
    repository = os.environ['REPOSITORY']
    if repository != 'raviteja2390/nfl-forecasting-lab':
        raise ValueError('Unexpected alert repository')
    value = json.loads((Path(__file__).parent/'live/reports/forecast-coverage.json').read_text())
    if not value['missed']:
        return
    title = 'NFL forecast coverage gaps require review'
    body = ('Missed prospective forecasts remain missing even when collection succeeds. '
            'Do not backfill or relax the 24-hour cutoff.\n\n'
            'Details: https://github.com/'+repository+'/blob/forecast-state/reports/forecast-coverage.md\n\n')
    body += '\n'.join('- '+r['eventId']+': '+', '.join(r['missingModels']) for r in value['missed'])
    issues = json.loads(gh('issue','list','--repo',repository,'--state','all','--search',title+' in:title','--json','number,title,body,state'))
    matches = [r for r in issues if r['title'] == title]
    if not matches:
        gh('issue','create','--repo',repository,'--title',title,'--body',body)
    else:
        item = max(matches, key=lambda r: r['number'])
        if item['body'] != body:
            gh('issue','edit',str(item['number']),'--repo',repository,'--body',body)
            if item['state'] == 'CLOSED':
                gh('issue','reopen',str(item['number']),'--repo',repository)
    # Unchanged acknowledged gaps do not reopen an issue on every hourly run.


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('state',choices=('failure','recovery','coverage')); a=p.parse_args()
    if a.state == 'coverage': coverage_alert()
    else: notify(a.state=='failure')
