"""Read-only supplementary uncertainty and tie diagnostics; no model changes."""
import hashlib
import json
from pathlib import Path
import model
from promotion_report import paired_interval
from calibration_report import verify_manifests

ROOT=Path(__file__).resolve().parent


def audit():
    manifests=verify_manifests()
    def rows(name): return [json.loads(s) for s in (ROOT/'runs'/name/'predictions.jsonl').read_text().splitlines()]
    opponent=[r for r in rows('opponent-adjusted-v1') if r['split']=='test']
    metrics={}
    for metric in ('logLoss','brier'):
        paired=[{'week':f"{r['season']}_{r['week']:02d}",'improvement':model.score(r['referenceProbabilities'],r['observedOutcome'])[metric]-model.score(r['probabilities'],r['observedOutcome'])[metric]} for r in opponent]
        metrics[metric]={'improvement':sum(r['improvement'] for r in paired)/len(paired),
                         'interval95':paired_interval(paired,draws=2000,seed=20260926,confidence=.95)}
    ties={};margin=rows('margin-ridge-v1')
    for year in (2023,2024,2025):
        rs=[r for r in margin if r['season']==year]
        ties[str(year)]={'games':len(rs),'predictedTieProbability':sum(r['probabilities']['tie'] for r in rs)/len(rs),
                         'observedTies':sum(r['observedOutcome']=='tie' for r in rs),
                         'observedTieRate':sum(r['observedOutcome']=='tie' for r in rs)/len(rs),
                         'logLossBaseline':sum(model.score(r['referenceProbabilities'],r['observedOutcome'])['logLoss'] for r in rs)/len(rs),
                         'logLossCandidate':sum(model.score(r['probabilities'],r['observedOutcome'])['logLoss'] for r in rs)/len(rs)}
    return {'sourceManifests':manifests,'opponent':{'games':len(opponent),'blocks':len({(r['season'],r['week']) for r in opponent}),
            'bootstrapDraws':2000,'seed':20260926,'method':'paired whole season-week percentile; baseline minus candidate; positive favors candidate',
            'metrics':metrics,'cohortDirection':'Mixed: log loss better in 2023 and 2024, worse in 2025',
            'limitation':'Exploratory exposed cohort; intervals conditional on selected model, not selection-adjusted; direction alone does not establish significance.'},
            'margin':{'status':'shelved; no shadow or live issuance','cohorts':ties,'cohortDirection':'Log loss worse in all three cohorts; consistency alone does not prove statistical significance or a unique cause.'}}


if __name__=='__main__':
    result=audit();out=ROOT/'reports/candidate-audit';out.mkdir(parents=True,exist_ok=True)
    (out/'review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
