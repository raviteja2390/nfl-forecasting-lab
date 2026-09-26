"""Append-only exploratory evaluation inventory and multiplicity review."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import model
import snapshots
from calibration_report import verify_manifests
from promotion_report import paired_interval
ROOT=Path(__file__).resolve().parent
REGISTER=ROOT/'research/evaluations'


def read(path): return json.loads((ROOT/path).read_text())
def sha(path): return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def historical_entries():
    """Backfill known evaluations, including tuning variants and timing diagnostics."""
    entries=[]
    def add(version,cohort,source,when,improvement,ci=None,variant='selected',reference='outcome-logit-v1'):
        key=f'{version}--{cohort}--{variant}'
        entries.append({'id':key,'model':version,'variant':variant,'cohort':cohort,'testedAt':when,
                        'backfilled':True,'reference':reference,'logLossImprovement':improvement,
                        'interval95':ci,'ciExcludesZero':None if ci is None else ci[0]>0 or ci[1]<0,
                        'ciFavorsCandidate':None if ci is None else ci[0]>0,
                        'ciStatus':'not-computed' if ci is None else 'reported-unadjusted',
                        'source':source,'sourceSha256':sha(source)})
    basepath='runs/outcome-logit-v1/report.json';base=read(basepath);when=base['generatedAt']
    for c in base['candidates']:
        ci=base['uncertainty']['improvementIntervals']['logLoss'] if c['C']==base['selectedC'] else None
        add('outcome-logit-v1','2023',basepath,when,c['validation']['improvement']['logLoss'],ci,'C='+str(c['C']),'training-frequency')
    for lag,data in base['timingSensitivity'].items():
        for mode in ('fixedModel','refitModel'):
            add('outcome-logit-v1','2023',basepath,when,data[mode]['improvement']['logLoss'],variant=f'lag={lag}-{mode}',reference='training-frequency')
    hp='runs/outcome-logit-v1/holdout-2024-2025/report.json';h=read(hp)
    for cohort,stats in [('2024-2025',h['overall'])]+list(h['bySeason'].items()):
        add('outcome-logit-v1',str(cohort),hp,h['evaluatedAt'],stats['improvement']['logLoss'],stats['uncertainty']['improvementIntervals']['logLoss'],reference='training-frequency')
    ppath='runs/player-comparison-v1/report.json';p=read(ppath)
    for family,info in p['families'].items():
        v=info['modelVersion']
        for c in info['candidates']:
            add(v,'2023',ppath,p['createdAt'],p['teamOnly']['validation']['logLoss']-c['validation']['logLoss'],variant='C='+str(c['C']))
        add(v,'2024-2025',ppath,p['createdAt'],info['exploratoryChangeFromTeam']['logLossImprovement'])
        for year,stats in info['bySeason'].items():
            add(v,year,ppath,p['createdAt'],stats['teamOnly']['logLoss']-stats['player']['logLoss'])
    for version,param in [('opponent-adjusted-v1','C'),('margin-ridge-v1','alpha')]:
        path=f'runs/{version}/report.json';r=read(path)
        for c in r['candidates']:
            add(version,'2023',path,r['generatedAt'],base['selectedValidation']['model']['logLoss']-c['validation']['logLoss'],variant=param+'='+str(c[param]))
        for label,stats in r['comparisons'].items():
            if label.startswith('2023'):continue
            cohort='2024-2025' if label.startswith('2024–2025') else label[:4]
            ci=None
            if version=='opponent-adjusted-v1' and cohort=='2024-2025':ci=read('reports/candidate-audit/review.json')['opponent']['metrics']['logLoss']['interval95']
            add(version,cohort,path,r['generatedAt'],stats['logLossImprovement'],ci)
    return entries


def append(entry,folder=REGISTER):
    if not entry.get('id') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-=.' for c in entry['id']):raise ValueError('Unsafe evaluation ID')
    required={'model','variant','cohort','testedAt','backfilled','reference','logLossImprovement','interval95','ciExcludesZero','ciFavorsCandidate','ciStatus','source','sourceSha256'}
    if not required.issubset(entry): raise ValueError('Incomplete evaluation entry')
    snapshots.parse_time(entry['testedAt'])
    if not model.finite(entry['logLossImprovement']): raise ValueError('Invalid improvement')
    source=(ROOT/entry['source']).resolve()
    if not source.is_relative_to(ROOT) or sha(entry['source'])!=entry['sourceSha256']:raise ValueError('Invalid source evidence')
    snapshots.immutable_write(folder/(entry['id']+'.json'),(json.dumps(entry,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())


def review(folder=REGISTER):
    verify_manifests()
    entries=[json.loads(p.read_text()) for p in sorted(folder.glob('*.json'))]
    expected={e['id']:e for e in historical_entries()};actual={e['id']:e for e in entries}
    errors=[]
    if len(actual)!=len(entries):errors.append('Duplicate evaluation ID')
    for key,e in expected.items():
        if actual.get(key)!=e:errors.append('Missing or changed known evaluation: '+key)
    for e in entries:
        if sha(e['source'])!=e['sourceSha256']:errors.append('Changed evaluation source: '+e['id'])
    known={e['model'] for e in entries}
    for path in (ROOT/'runs').rglob('*.json'):
        artifact=json.loads(path.read_text())
        if isinstance(artifact,dict) and artifact.get('kind') in ('multinomial-logistic-regression','ridge-gaussian-margin') and artifact.get('modelVersion') not in known:
            errors.append('Unregistered model: '+str(path.relative_to(ROOT)))
    counts=dict(Counter(e['cohort'] for e in entries))
    # Count all known comparisons on this cohort, including the original reference vs frequency.
    count=counts.get('2024-2025',0);confidence=1-.05/max(1,count)
    ps=[json.loads(s) for s in (ROOT/'runs/opponent-adjusted-v1/predictions.jsonl').read_text().splitlines()]
    paired=[{'week':f"{r['season']}_{r['week']:02d}",'improvement':model.score(r['referenceProbabilities'],r['observedOutcome'])['logLoss']-model.score(r['probabilities'],r['observedOutcome'])['logLoss']} for r in ps if r['split']=='test']
    adjusted=paired_interval(paired,draws=2000,seed=20260926,confidence=confidence)
    return {'entries':entries,'counts':counts,'errors':errors,'historicalPromotionAllowed':False,
            'opponentAdjustedLogLoss':{'familySize':count,'confidenceLevel':confidence,'interval':adjusted,'favorsCandidate':not errors and adjusted[0]>0},
            'rule':'Bonferroni is an exploratory sensitivity check, not a cure for adaptive search or repeated peeking. Promotion requires a separately preregistered future cohort. Expand family counts for subgroup or metric searches; do not pool historical counts into an already fixed prospective protocol.'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--backfill',action='store_true');p.add_argument('--entry',type=Path);a=p.parse_args()
    if a.entry:append(json.loads(a.entry.read_text()))
    if a.backfill:
        for entry in historical_entries():append(entry)
    r=review();out=ROOT/'reports/research-register';out.mkdir(parents=True,exist_ok=True)
    (out/'review.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='entries'},indent=2))
    raise SystemExit(bool(r['errors']))
