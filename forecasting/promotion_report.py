"""Read-only prospective gate evaluation. Never promote or fit a model."""
from collections import defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import random

from calibration_report import summarize
import model
import snapshots

ROOT = Path(__file__).resolve().parent


def paired_interval(rows, draws=20000, seed=20260926, confidence=.975):
    blocks=defaultdict(list)
    for row in rows:
        blocks[row['week']].append(row['improvement'])
    if len(blocks)<2:
        return None
    summaries=[(len(values),sum(values)) for _,values in sorted(blocks.items())]
    rng=random.Random(seed)
    samples=[]
    for _ in range(draws):
        chosen=rng.choices(summaries,k=len(summaries))
        samples.append(sum(s for n,s in chosen)/sum(n for n,s in chosen))
    samples.sort()
    def quantile(p):
        i=(len(samples)-1)*p; lo=math.floor(i); hi=math.ceil(i)
        return samples[lo]+(samples[hi]-samples[lo])*(i-lo)
    tail=(1-confidence)/2
    return [quantile(tail),quantile(1-tail)]


def evaluate(store=ROOT/'live', at=None, plan=None):
    at=at or snapshots.now()
    plan=plan or json.loads((ROOT/'promotion-plan.json').read_text())
    if hashlib.sha256((ROOT/'promotion_criteria.md').read_bytes()).hexdigest()!=plan['protocolSha256']:
        raise ValueError('Promotion protocol changed after registration')
    review=snapshots.parse_time(plan['reviewAt'])
    cutoff=min(snapshots.parse_time(at),review)
    errors=[]; groups=defaultdict(dict); issued=defaultdict(int)
    # Latest audit per game-date determines unresolved finality disputes.
    audits={}
    for path in (store/'rechecks').glob('*.json'):
        row=json.loads(path.read_text())
        if snapshots.parse_time(row['checkedAt'])<=cutoff:
            old=audits.get(row['date'])
            if old is None or row['checkedAt']>old['checkedAt']: audits[row['date']]=row
    disputed={event for row in audits.values() for field in ('sourceDisagreements','previouslyFinalNowPending') for event in row.get(field,[])}
    for path in sorted((store/'forecasts').glob('*/*.json')):
        f=json.loads(path.read_text()); version=f['modelVersion']
        if version not in plan['modelHashes']: continue
        if not plan['cohortStart']<=f['dateEastern']<=plan['cohortEnd']: continue
        if snapshots.parse_time(f['generatedAt'])>cutoff: continue
        event=f['eventId']; issued[version]+=1
        if (f.get('mode')!='prospective' or f.get('modelSha256')!=plan['modelHashes'][version]
            or (snapshots.parse_time(f['kickoffAt'])-snapshots.parse_time(f['generatedAt'])).total_seconds()<86400
            or snapshots.parse_time(f['featureCutoffAt'])>snapshots.parse_time(f['generatedAt'])):
            errors.append(event+': invalid forecast identity/timing for '+version); continue
        receipts=[json.loads(p.read_text()) for p in (store/'results'/event).glob('*.json')]
        eligible=[r for r in receipts if snapshots.parse_time(r['finalizedAt'])<=cutoff]
        if not eligible: continue
        if event in disputed:
            errors.append(event+': unresolved settlement discrepancy'); continue
        result=max(eligible,key=lambda r:(snapshots.parse_time(r['finalizedAt']),r['espnObservationId']))
        if (result.get('eventId')!=event or result.get('timingBasis')!='observed-final-in-two-sources'
            or snapshots.parse_time(result['finalizedAt'])<=snapshots.parse_time(f['kickoffAt'])
            or any(type(result.get(k)) is not int or result[k]<0 for k in ('homeScore','awayScore'))):
            errors.append(event+': invalid result receipt'); continue
        h,a=result['homeScore'],result['awayScore']
        outcome='homeWin' if h>a else 'awayWin' if a>h else 'tie'
        groups[version][event]={'eventId':event,'probabilities':f['probabilities'],'observedOutcome':outcome,
                                'forecast':f,'score':model.score(f['probabilities'],outcome)}
    reference=groups[plan['reference']]
    comparisons={}
    for version in plan['challengers']:
        candidate=groups[version]
        common=sorted(set(reference)&set(candidate))
        aligned=[]
        for event in common:
            if any(reference[event]['forecast'][k]!=candidate[event]['forecast'][k] for k in ('featureCutoffAt','kickoffAt')):
                errors.append(event+': mismatched paired cutoffs/kickoff'); continue
            aligned.append(event)
        base=model.aggregate([reference[e]['score'] for e in aligned])
        challenger=model.aggregate([candidate[e]['score'] for e in aligned])
        paired=[{'week':'_'.join(e.split('_')[:2]),'improvement':reference[e]['score']['logLoss']-candidate[e]['score']['logLoss']} for e in aligned]
        interval=paired_interval(paired,plan['bootstrapDraws'],plan['bootstrapSeed'],plan['confidenceLevel'])
        improvement=base['logLoss']-challenger['logLoss'] if aligned else None
        coverage=len(aligned)/len(reference) if reference else 0
        weeks=len({r['week'] for r in paired})
        gates={'minimumGames':len(aligned)>=plan['minimumGames'],'minimumWeeks':weeks>=plan['minimumWeeks'],
               'minimumCoverage':coverage>=plan['minimumCoverage'],
               'minimumImprovement':improvement is not None and improvement>=plan['minimumLogLossImprovement'],
               'confidenceInterval':interval is not None and interval[0]>0,
               'brierGuard':bool(aligned) and challenger['brier']-base['brier']<=plan['maximumBrierDeterioration']}
        comparisons[version]={'sameGames':len(aligned),'weeks':weeks,'referenceFinalized':len(reference),'coverage':coverage,
                              'excludedReferenceEvents':sorted(set(reference)-set(aligned)),
                              'reference':base,'challenger':challenger,'logLossImprovement':improvement,
                              'interval':interval,'confidenceLevel':plan['confidenceLevel'],'gates':gates}
    for c in comparisons.values():
        c['gates']['integrity']=not errors
        c['status']=('awaiting-fixed-review' if snapshots.parse_time(at)<review else
                     'eligible-for-manual-review' if all(c['gates'].values()) else 'not-eligible-or-inconclusive')
    return {'generatedAt':at,'evidenceCutoffAt':cutoff.isoformat(),'reviewAt':plan['reviewAt'],
            'protocolSha256':plan['protocolSha256'],'errors':sorted(set(errors)), 'issued':dict(issued),
            'comparisons':comparisons,'calibration':{v:summarize(list(rows.values())) for v,rows in groups.items() if rows},
            'automaticPromotion':False,'interpretation':'Interim comparisons are descriptive; no profitability conclusion. Formal decisions use the fixed review cutoff.'}


def write_report(store=ROOT/'live', at=None):
    report=evaluate(store,at)
    output=store/'reports'; output.mkdir(parents=True,exist_ok=True)
    (output/'promotion-status.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    lines=['# Prospective promotion status','',report['interpretation'],'',f"Fixed review: {report['reviewAt']}.",'']
    for version,c in report['comparisons'].items():
        lines.append(f"- {version}: {c['status']}; {c['sameGames']} paired scored games across {c['weeks']} weeks.")
    if report['errors']: lines+=['','Integrity issues:']+['- '+e for e in report['errors']]
    (output/'promotion-status.md').write_text('\n'.join(lines)+'\n')
    return report


if __name__=='__main__':
    report=write_report()
    print(json.dumps({'reviewAt':report['reviewAt'],'errors':report['errors'],'comparisons':{k:v['status'] for k,v in report['comparisons'].items()}},indent=2))
    raise SystemExit(1 if report['errors'] else 0)
