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


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('state',choices=('failure','recovery')); a=p.parse_args(); notify(a.state=='failure')
