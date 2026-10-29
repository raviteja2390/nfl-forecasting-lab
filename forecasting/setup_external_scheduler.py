"""Configure cron-job.org using hidden prompts. Never persist or print credentials."""
import argparse
import getpass
import json
import urllib.request
import warnings

REPO='raviteja2390/nfl-forecasting-lab'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def hidden(prompt):
    # Never fall back to visible input when no terminal is attached.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        return getpass.getpass(prompt).strip()

BASE='https://api.cron-job.org'
DISPATCH=f'https://api.github.com/repos/{REPO}/actions/workflows/nfl-collector.yml/dispatches'
TITLE='NFL public collector hourly dispatch'

def request(url,key,method='GET',body=None):
    req=urllib.request.Request(url,method=method,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json','User-Agent':'NFLArchiveScheduler/1.0'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:
        raw=response.read(2_000_000)
        return json.loads(raw) if raw else {}

def job(token):
    return {'title':TITLE,'url':DISPATCH,'enabled':True,'saveResponses':False,'requestMethod':1,'requestTimeout':30,'redirectSuccess':False,
            'schedule':{'timezone':'UTC','expiresAt':0,'hours':[-1],'minutes':[7],'mdays':[-1],'months':[-1],'wdays':[-1]},
            'notification':{'onFailure':True,'onFailureCount':1,'onSuccess':True,'onDisable':True},
            'extendedData':{'headers':{'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'},
                            'body':json.dumps({'ref':'main','inputs':{'force':False,'trigger_source':'cron-job.org'}})}}

def find_job(api):
    value=request(BASE+'/jobs',api)
    if value.get('someFailed'):raise ValueError('Incomplete job list; stop to avoid duplicates')
    matches=[j for j in value['jobs'] if j.get('title')==TITLE and j.get('url')==DISPATCH]
    if len(matches)>1:raise ValueError('Multiple matching jobs; review in console')
    return matches[0]['jobId'] if matches else None

def main(check=False):
    api=hidden('cron-job.org API key (hidden): ')
    identifier=find_job(api)
    if check:
        if identifier is None:print('External scheduler not configured');return
        value=request(f'{BASE}/jobs/{identifier}',api)['jobDetails']
        history=request(f'{BASE}/jobs/{identifier}/history',api)
        print(json.dumps({'jobId':identifier,'enabled':value['enabled'],'nextExecution':value.get('nextExecution'),'recentExecutions':[{k:r.get(k) for k in ('date','httpStatus','status')} for r in history['history'][:3]]},indent=2))
        return
    print('Use a NEW fine-grained GitHub token: raviteja2390; ONLY nfl-forecasting-lab; Actions read/write; automatic Metadata read. No other permissions.')
    token=hidden('Fine-grained GitHub token (hidden): ')
    if not token.startswith('github_pat_'):raise ValueError('Fine-grained token required')
    # Confirm this exact repository and exercise the dispatch permission before saving anything.
    repo=request(f'https://api.github.com/repos/{REPO}',token)
    if repo.get('private') is not False or repo.get('full_name')!=REPO:raise ValueError('Wrong/public repository access')
    request(DISPATCH,token,'POST',{'ref':'main','inputs':{'force':False,'trigger_source':'setup-test'}})
    if identifier is None:identifier=request(BASE+'/jobs',api,'PUT',{'job':job(token)})['jobId']
    else:request(f'{BASE}/jobs/{identifier}',api,'PATCH',{'job':job(token)})
    result=request(f'{BASE}/jobs/{identifier}',api)['jobDetails']
    if (result.get('enabled') is not True or result.get('url') != DISPATCH
        or result.get('requestMethod') != 1 or result.get('saveResponses') is not False
        or result.get('schedule') != job(token)['schedule']
        or result.get('extendedData',{}).get('body') != job(token)['extendedData']['body']):raise ValueError('Scheduler verification failed')
    print('External scheduler configured. Job ID:',identifier)
    print('GitHub dispatch accepted; the collector due gate remains active. Scheduled execution still needs verification.')
    print('Hourly at :07 UTC. One permission-test workflow dispatched; this is not proof of an unattended cron run.')
    print('GitHub token is stored as a request header at cron-job.org. No token is saved locally. Set a reminder before its expiration.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    try:main(args.check)
    except Exception as exc:
        print('Scheduler setup/check failed:',type(exc).__name__,'HTTP',getattr(exc,'code','n/a'))
        print('No secret values logged. Check account permissions and retry; existing matching jobs are reused.')
        raise SystemExit(1)
