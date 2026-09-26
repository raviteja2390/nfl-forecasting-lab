"""Train a registered offline margin candidate; preserve existing artifacts."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import calibration_report
from compare_players import checked_rows
import live
import margin_model
import model
import snapshots

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs/margin-ridge-v1'


def fit(rows,targets,alpha,names):
    x=np.array([model.feature_vector(r['features'],names) for r in rows])
    scaler=StandardScaler().fit(x)
    with threadpool_limits(limits=1):
        reg=Ridge(alpha=alpha,solver='svd').fit(scaler.transform(x),targets)
    return {'schemaVersion':1,'kind':'ridge-gaussian-margin','featureNames':names,
            'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),
            'coefficients':reg.coef_.tolist(),'intercept':float(reg.intercept_),
            'alpha':alpha,'sigma':1.0}


def fit_candidate(rows,targets,alpha,names):
    errors=[];folds=[]
    for year in range(2017,2023):
        train=[i for i,r in enumerate(rows) if r['season']<year]
        test=[i for i,r in enumerate(rows) if r['season']==year]
        if not train or not test: raise ValueError('Missing expanding-season fold')
        fitted=fit([rows[i] for i in train],[targets[i] for i in train],alpha,names)
        for i in test:
            errors.append({'eventId':rows[i]['eventId'],'season':year,
                           'error':targets[i]-margin_model.predict_margin(fitted,rows[i]['features'])})
        folds.append({'evaluationSeason':year,'trainingSeasons':sorted({rows[i]['season'] for i in train}),
                      'trainingGames':len(train),'evaluationGames':len(test)})
    artifact=fit(rows,targets,alpha,names)
    artifact['sigma']=max(1.0,math.sqrt(sum(r['error']**2 for r in errors)/len(errors)))
    artifact['errorEstimation']={'method':'expanding-season out-of-fold RMSE, zero-mean Gaussian', 'folds':folds,'games':len(errors)}
    return artifact,errors


def compare(output=RUN):
    if output.exists(): raise ValueError('Preserve the existing experiment; register a new version before refitting')
    calibration_report.verify_manifests()
    plan_body=(ROOT/'margin-plan.json').read_bytes();plan=json.loads(plan_body)
    data=ROOT/'data/processed/v1';manifest=json.loads((data/'manifest.json').read_text())
    rows={};targets={};outcomes={}
    for split in ('train','validation','test'):
        rows[split]=checked_rows(data/f'{split}.features.jsonl',manifest['files'][f'{split}.features.jsonl'])
        labels=checked_rows(data/f'{split}.labels.jsonl',manifest['files'][f'{split}.labels.jsonl'])
        by_id={r['eventId']:r for r in labels}
        if len(by_id)!=len(labels) or len({r['eventId'] for r in rows[split]})!=len(rows[split]) or set(by_id)!={r['eventId'] for r in rows[split]}:
            raise ValueError('Nonunique or mismatched label join')
        targets[split]=[by_id[r['eventId']]['homeScore']-by_id[r['eventId']]['awayScore'] for r in rows[split]]
        outcomes[split]=[by_id[r['eventId']]['outcome'] for r in rows[split]]
    if sorted({r['season'] for r in rows['train']})!=plan['trainingSeasons'] or {r['season'] for r in rows['validation']}!={plan['selectionSeason']} or sorted({r['season'] for r in rows['test']})!=plan['exploratorySeasons']:
        raise ValueError('Season splits differ from registered plan')
    baseline=json.loads(live.MODEL_PATH.read_text());names=baseline['featureNames']
    candidates=[];fitted={};residuals={}
    for alpha in plan['candidateAlpha']:
        artifact,errors=fit_candidate(rows['train'],targets['train'],alpha,names)
        probs=margin_model.predict_many(artifact,[r['features'] for r in rows['validation']])
        metrics=model.aggregate([model.score(p,y) for p,y in zip(probs,outcomes['validation'])])
        candidates.append({'alpha':alpha,'sigma':artifact['sigma'],'validation':metrics})
        fitted[alpha]=artifact;residuals[alpha]=errors
    selected=min(candidates,key=lambda r:(r['validation']['logLoss'],-r['alpha']))
    artifact=fitted[selected['alpha']]
    artifact.update(modelVersion=plan['modelVersion'],trainedAt=snapshots.now(),role='offline-research-candidate',
                    trainingSeasons=plan['trainingSeasons'],selectionSeasons=[plan['selectionSeason']],
                    provenance={'planSha256':hashlib.sha256(plan_body).hexdigest(),'inputFiles':manifest['files'],
                                'baselineSha256':hashlib.sha256(live.MODEL_PATH.read_bytes()).hexdigest(),
                                'codeSha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('margin_model.py','compare_margins.py','model.py','compare_players.py','calibration_report.py')},
                                'requirementsSha256':hashlib.sha256((ROOT/'requirements-training.txt').read_bytes()).hexdigest()})
    report={'generatedAt':snapshots.now(),'kind':'margin-regression-exploratory-comparison','finalTestUntouched':False,
            'selectedAlpha':selected['alpha'],'sigma':artifact['sigma'],'candidates':candidates,
            'productionModel':'outcome-logit-v1','liveIssuanceEnabled':False,'groups':{},'comparisons':{},
            'limitations':plan['limitations']+['Continuous predicted margin is the latent Gaussian center; probabilities discretize it to integer outcomes.', 'Spread probabilities are unvalidated distribution outputs, not market-edge estimates. No automatic promotion.']}
    predictions=[]
    for split,title in [('validation','2023 development'),('test','2024–2025 exploratory')]:
        features=[r['features'] for r in rows[split]]
        probs=margin_model.predict_many(artifact,features);ref=model.predict_many(baseline,features)
        margins=[margin_model.predict_margin(artifact,f) for f in features]
        cohorts=[(title,list(range(len(features))))]
        if split=='test': cohorts += [(str(y)+' exploratory',[i for i,r in enumerate(rows[split]) if r['season']==y]) for y in (2024,2025)]
        for label,indices in cohorts:
            stats={}
            for version,ps in [('outcome-logit-v1',ref),(plan['modelVersion'],probs)]:
                records=[{'eventId':rows[split][i]['eventId'],'probabilities':ps[i],'observedOutcome':outcomes[split][i]} for i in indices]
                summary=calibration_report.summarize(records)
                report['groups'][version+' / '+label]=summary;stats[version]=summary['metrics']
            a,b=stats['outcome-logit-v1'],stats[plan['modelVersion']]
            report['comparisons'][label]={'games':len(indices),'baseline':a,'candidate':b,
                'logLossImprovement':a['logLoss']-b['logLoss'],'accuracyChange':b['accuracy']-a['accuracy'],
                'marginMAE':sum(abs(margins[i]-targets[split][i]) for i in indices)/len(indices),
                'marginRMSE':math.sqrt(sum((margins[i]-targets[split][i])**2 for i in indices)/len(indices))}
        predictions += [{'eventId':r['eventId'],'season':r['season'],'week':r['week'],'split':split,
                         'predictedMargin':m,'observedMargin':t,'probabilities':p,'referenceProbabilities':b,'observedOutcome':y}
                        for r,m,t,p,b,y in zip(rows[split],margins,targets[split],probs,ref,outcomes[split])]
    lines=['# Margin-regression experiment','', 'Offline research candidate; current primary model and issued forecasts unchanged.','',
           'Ridge predicts home-minus-away points using the original team features. Train: 2015–2022; select alpha: 2023 log loss. 2024–2025 results are exploratory.','',
           f"Selected alpha: {selected['alpha']}; Gaussian error sigma: {artifact['sigma']:.4f} points, estimated only from expanding-season training folds.",'']
    for label,r in report['comparisons'].items():
        a,b=r['baseline'],r['candidate']
        lines += [f'## {label}','', f"{r['games']} identical games. Accuracy: baseline {a['accuracy']:.2%}, candidate {b['accuracy']:.2%}. Log loss: baseline {a['logLoss']:.6f}, candidate {b['logLoss']:.6f}. Brier: baseline {a['brier']:.6f}, candidate {b['brier']:.6f}.",f"Margin MAE {r['marginMAE']:.3f}; RMSE {r['marginRMSE']:.3f} points.",'']
    lines += ['## Limitations','',*['- '+s for s in report['limitations']], '', 'A home handicap of -3.5 means the home team covers at a margin of 4 or more; -3 has a push at margin 3. No closing spread data were used or evaluated. Register a separate prospective protocol and live adapter before shadow issuance.','']
    encode_rows=lambda rs: ''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rs).encode()
    blobs={'model.json':live.encode(artifact),'plan.json':plan_body,'report.json':live.encode(report),
           'REPORT.md':'\n'.join(lines).encode(),'calibration.html':calibration_report.render(report).encode(),
           'predictions.jsonl':encode_rows(predictions),'training-oof-errors.jsonl':encode_rows(residuals[selected['alpha']])}
    output.mkdir(parents=True,exist_ok=False)
    for name,body in blobs.items(): snapshots.immutable_write(output/name,body)
    snapshots.immutable_write(output/'artifacts.json',live.encode({'files':{n:{'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)} for n,b in blobs.items()}}))
    return report


if __name__=='__main__':
    r=compare();print(json.dumps({'selectedAlpha':r['selectedAlpha'],'sigma':r['sigma'],'comparisons':r['comparisons']},indent=2))
