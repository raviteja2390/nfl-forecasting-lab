"""Fit the predeclared opponent-adjusted candidate without changing frozen models."""
import csv
import hashlib
import io
import json
from pathlib import Path

import build_features
import calibration_report
from compare_players import checked_rows, fit
import live
import model
from opponent_features import OpponentHistory
import snapshots

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'runs/opponent-adjusted-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(output=OUTPUT):
    if output.exists():
        raise ValueError('Experiment already exists; use a newly registered version for further work')
    calibration_report.verify_manifests()
    plan_body = (ROOT/'opponent-plan.json').read_bytes()
    plan = json.loads(plan_body)
    data = ROOT/'data/processed/v1'
    manifest = json.loads((data/'manifest.json').read_text())
    raw_path = ROOT/'data/raw/nflverse-games.csv'
    provenance = json.loads((ROOT/'data/raw/nflverse-games.provenance.json').read_text())
    source_hash = digest(raw_path)
    if source_hash != provenance['sha256'] or source_hash != manifest['source']['sha256']:
        raise ValueError('Raw snapshot does not match baseline source')
    games = build_features.normalize(csv.DictReader(io.StringIO(raw_path.read_text(encoding='utf-8-sig'))))
    source = OpponentHistory(games)
    rows, augmented, outcomes, blobs = {}, {}, {}, {}
    for split in ('train','validation','test'):
        rows[split] = checked_rows(data/f'{split}.features.jsonl', manifest['files'][f'{split}.features.jsonl'])
        labels = checked_rows(data/f'{split}.labels.jsonl', manifest['files'][f'{split}.labels.jsonl'])
        by_id = {r['eventId']:r['outcome'] for r in labels}
        if len(by_id) != len(labels) or len({r['eventId'] for r in rows[split]}) != len(rows[split]) or set(by_id) != {r['eventId'] for r in rows[split]}:
            raise ValueError('Expected exact one-to-one label join')
        outcomes[split] = [by_id[r['eventId']] for r in rows[split]]
        augmented[split] = []
        saved = []
        for row in rows[split]:
            values, evidence = source.augment(row)
            augmented[split].append(values)
            saved.append({**row, 'features':values, 'opponentEvidence':evidence})
        blobs[f'{split}.features.jsonl'] = ''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in saved).encode()
    baseline = json.loads(live.MODEL_PATH.read_text())
    names = list(augmented['train'][0])
    candidates, fitted = [], {}
    for c in plan['candidateC']:
        artifact = fit(augmented['train'], outcomes['train'], names, c)
        p = model.predict_many(artifact, augmented['validation'])
        metrics = model.aggregate([model.score(a,b) for a,b in zip(p,outcomes['validation'])])
        candidates.append({'C':c,'validation':metrics})
        fitted[c] = artifact
    selected = min(candidates,key=lambda r:(r['validation']['logLoss'],r['C']))
    artifact = fitted[selected['C']]
    artifact.update(modelVersion=plan['modelVersion'], trainedAt=snapshots.now(),
                    role='offline-research-candidate', trainingSeasons=plan['trainingSeasons'],
                    selectionSeasons=[plan['selectionSeason']], baselineProbabilities=baseline['baselineProbabilities'],
                    provenance={'planSha256':hashlib.sha256(plan_body).hexdigest(), 'sourceSha256':source_hash,
                                'baselineModelSha256':digest(live.MODEL_PATH), 'inputFiles':manifest['files'],
                                'codeSha256':{n:digest(ROOT/n) for n in ('opponent_features.py','compare_opponents.py','build_features.py','compare_players.py','model.py','calibration_report.py')},
                                'requirementsSha256':digest(ROOT/'requirements-training.txt')})
    report = {'generatedAt':snapshots.now(),'kind':'opponent-adjusted-exploratory-comparison',
              'finalTestUntouched':False,'selectedC':selected['C'],'candidates':candidates,
              'productionModel':'outcome-logit-v1','liveIssuanceEnabled':False,
              'limitations':plan['limitations']+['No prospective results exist for this candidate. No automatic promotion.', 'Coverage count distinguishes unavailable opponent history from a zero residual.'],
              'groups':{},'comparisons':{}}
    predictions = []
    for split, title in [('validation','2023 development'),('test','2024–2025 exploratory')]:
        p = model.predict_many(artifact,augmented[split])
        ref = model.predict_many(baseline,[r['features'] for r in rows[split]])
        for label,indices in [(title,list(range(len(p))))]+([(str(y)+' exploratory',[i for i,r in enumerate(rows[split]) if r['season']==y]) for y in (2024,2025)] if split=='test' else []):
            stats = {}
            for version,probs in [('outcome-logit-v1',ref),(plan['modelVersion'],p)]:
                records = [{'eventId':rows[split][i]['eventId'],'probabilities':probs[i],'observedOutcome':outcomes[split][i]} for i in indices]
                summary = calibration_report.summarize(records)
                report['groups'][version+' / '+label] = summary
                stats[version] = summary['metrics']
            a,b=stats['outcome-logit-v1'],stats[plan['modelVersion']]
            report['comparisons'][label]={'games':len(indices),'baseline':a,'candidate':b,
                                         'logLossImprovement':a['logLoss']-b['logLoss'],
                                         'accuracyChange':b['accuracy']-a['accuracy'],'brierImprovement':a['brier']-b['brier']}
        predictions += [{'eventId':r['eventId'],'season':r['season'],'week':r['week'],'split':split,
                         'probabilities':a,'referenceProbabilities':b,'observedOutcome':y}
                        for r,a,b,y in zip(rows[split],p,ref,outcomes[split])]
    lines=['# Opponent-adjusted model experiment','', 'Offline candidate only. Existing models and forecasts are unchanged.','',
           'Training: 2015–2022. Regularization selected on 2023 log loss. Previously exposed 2024–2025 results are exploratory.','',
           f"Selected C: {selected['C']}. Six opponent-adjusted inputs supplement the existing team features.",'']
    for label,s in report['comparisons'].items():
        a,b=s['baseline'],s['candidate']
        lines += [f'## {label}', '', f"{s['games']} identical games. Baseline accuracy {a['accuracy']:.2%}, candidate {b['accuracy']:.2%}. Baseline log loss {a['logLoss']:.6f}, candidate {b['logLoss']:.6f}. Baseline Brier {a['brier']:.6f}, candidate {b['brier']:.6f}.",'']
    lines += ['## Limits and next step','',*['- '+s for s in report['limitations']], '', 'Register a separate future-cohort evaluation protocol and implement observation-time-aware live features before issuing prospective shadow forecasts. Do not reuse this retrospective builder for live issuance.','']
    blobs.update({'model.json':live.encode(artifact),'plan.json':plan_body,'report.json':live.encode(report),
                  'REPORT.md':'\n'.join(lines).encode(),'calibration.html':calibration_report.render(report).encode(),
                  'predictions.jsonl':''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in predictions).encode()})
    output.mkdir(parents=True,exist_ok=False)
    for name,body in blobs.items():
        snapshots.immutable_write(output/name,body)
    snapshots.immutable_write(output/'artifacts.json',live.encode({'files':{name:{'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)} for name,body in blobs.items()}}))
    return report


if __name__ == '__main__':
    report=compare()
    print(json.dumps({'selectedC':report['selectedC'],'comparisons':report['comparisons']},indent=2))
