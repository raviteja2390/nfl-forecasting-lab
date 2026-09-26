"""Supplemental calibration reports from saved predictions; no training or rewrites."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path

import model
import snapshots

ROOT = Path(__file__).resolve().parent


def summarize(rows):
    if len({r['eventId'] for r in rows}) != len(rows):
        raise ValueError('Duplicate prediction event in calibration cohort')
    scores = [model.score(r['probabilities'], r['observedOutcome']) for r in rows]
    bins = model.calibration([r['probabilities'] for r in rows], [r['observedOutcome'] for r in rows])
    for values in bins.values():
        for b in values:
            n, p = b['count'], b['observedRate']
            if not n:
                b['observedRateInterval95'] = None
                continue
            z = 1.959963984540054
            denom = 1 + z*z/n
            center = (p + z*z/(2*n))/denom
            half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denom
            b['observedRateInterval95'] = [max(0, center-half), min(1, center+half)]
    return {'metrics': model.aggregate(scores), 'classes': bins}


def verify_manifests():
    receipts = []
    for manifest in sorted((ROOT/'runs').rglob('artifacts.json')):
        for name, expected in json.loads(manifest.read_text())['files'].items():
            path = manifest.parent/name
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']:
                raise ValueError('Frozen artifact checksum mismatch: '+str(path))
        receipts.append({'path':str(manifest.relative_to(ROOT)), 'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
    return receipts


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def historical():
    receipts = verify_manifests()
    groups = {}
    base = ROOT/'runs/outcome-logit-v1'
    groups['outcome-logit-v1 / 2023 development'] = summarize(read_rows(base/'validation.predictions.jsonl'))
    groups['outcome-logit-v1 / 2024–2025 original held-out evaluation'] = summarize(read_rows(base/'holdout-2024-2025/scored-predictions.jsonl'))
    for version in ('player-form-v1','player-availability-v1'):
        rows = read_rows(ROOT/'runs/player-comparison-v1'/f'{version}.predictions.jsonl')
        for split, label in [('validation','2023 development'),('test','2024–2025 exploratory')]:
            groups[f'{version} / {label}'] = summarize([r for r in rows if r['split']==split])
    return {'generatedAt':snapshots.now(),'kind':'supplemental-historical-calibration','sources':receipts,'groups':groups,
            'limitations':['No recalibration fitted. Original reports and models unchanged.',
                           'Wilson intervals are descriptive binomial intervals; they ignore dependence between games and are not simultaneous confidence bands.',
                           '2023 selected settings. 2024–2025 is exposed and is not a fresh test for later model choices.']}


def render(report):
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>NFL probability calibration</title><style>body{font:15px system-ui;max-width:1150px;margin:35px auto;padding:0 20px;color:#172b3a;background:#fff}h1{font-size:26px}h2{font-size:20px;margin-top:36px}small{color:#465866}.plots{display:flex;flex-wrap:wrap;gap:20px}figure{margin:0;width:340px}svg{width:100%;height:auto}table{border-collapse:collapse;font-size:12px;width:100%}th,td{text-align:right;padding:4px;border-bottom:1px solid #ddd}caption{text-align:left;margin:8px 0}p{line-height:1.5}</style>',
           '<h1>NFL probability calibration</h1><p>Source: saved, checksum-verified historical predictions. Generated '+html.escape(report['generatedAt'])+'. Each plot compares mean predicted probability with observed frequency; the diagonal represents perfect calibration.</p>',
           '<p>'+html.escape(' '.join(report['limitations']))+'</p>']
    for name, group in report['groups'].items():
        m=group['metrics']
        if not m['games']: continue
        parts += ['<section><h2>'+html.escape(name)+'</h2>',f'<p>{m["games"]} games · Log loss {m["logLoss"]:.6f} · Brier {m["brier"]:.6f}</p><div class="plots">']
        for outcome, bins in group['classes'].items():
            title=html.escape(outcome)
            parts += [f'<figure><figcaption><strong>{title}</strong></figcaption><svg viewBox="0 0 340 300" role="img" aria-label="{title}: mean predicted probability versus observed frequency, 0 to 100 percent">',
                      '<path d="M50 20V250H320M50 250L320 20" fill="none" stroke="#aaa"/>']
            for tick in (0,.25,.5,.75,1):
                parts += [f'<text x="{50+270*tick}" y="269" text-anchor="middle" font-size="10">{tick:.0%}</text>',f'<text x="43" y="{254-230*tick}" text-anchor="end" font-size="10">{tick:.0%}</text>']
            parts += ['<text x="185" y="290" text-anchor="middle" font-size="11">Mean predicted probability (%)</text><text transform="translate(12 135) rotate(-90)" text-anchor="middle" font-size="11">Observed frequency (%)</text>']
            for b in bins:
                if not b['count']: continue
                x,y=50+270*b['meanProbability'],250-230*b['observedRate']
                lo,hi=b['observedRateInterval95']
                parts.append(f'<line x1="{x}" x2="{x}" y1="{250-230*lo}" y2="{250-230*hi}" stroke="#416f85"/><circle cx="{x}" cy="{y}" r="4" fill="#174e69"><title>n={b["count"]}; predicted {b["meanProbability"]:.3f}; observed {b["observedRate"]:.3f}</title></circle>')
            parts += ['</svg><table><caption>Nonempty bins; bars show descriptive 95% Wilson intervals.</caption><thead><tr><th>Bin</th><th>Games</th><th>Predicted</th><th>Observed</th></tr></thead><tbody>']
            for b in bins:
                if b['count']:
                    parts.append(f'<tr><td>{b["lower"]:.0%}–{b["upper"]:.0%}</td><td>{b["count"]}</td><td>{b["meanProbability"]:.1%}</td><td>{b["observedRate"]:.1%}</td></tr>')
            parts += ['</tbody></table></figure>']
        parts += ['</div></section>']
    return '\n'.join(parts+['</html>'])


def write_historical(output=ROOT/'reports/calibration'):
    report=historical()
    output.mkdir(parents=True,exist_ok=True)
    (output/'historical.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (output/'historical.html').write_text(render(report))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report=write_historical()
    print(json.dumps({'groups':len(report['groups']),'output':str(ROOT/'reports/calibration/historical.html')}))
