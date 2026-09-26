"""Generate a concise status page without issuing or promoting forecasts."""
import argparse
import json
from pathlib import Path
import live
import snapshots
from research_register import review
from score_live import score_store


def write_status(store=live.LIVE,output=None):
    audit=review();scores=score_store(store);at=snapshots.now()
    lines=['# NFL research status','',f'Generated {at}. Log loss is the primary metric. No demonstrated profitability.','',
           '**Primary:** outcome-logit-v1. Repository is public. Cloud collection runs on GitHub Actions.',
           '', '**Live status:** [latest cloud-generated page](https://github.com/raviteja2390/nfl-forecasting-lab/blob/forecast-state/reports/STATUS.md). The main-branch page is a dated snapshot.','',
           '[This week’s three-model comparison](https://github.com/raviteja2390/nfl-forecasting-lab/blob/forecast-state/reports/weekly-comparison.md)','', '## Prospective evidence','']
    for version in ('outcome-logit-v1','player-form-v1','player-availability-v1'):
        m=scores['models'].get(version,{})
        loss=m.get('logLoss')
        lines.append(f"- {version}: log loss {loss if loss is not None else 'not yet available'}; {m.get('games',0)} scored, {m.get('pending',0)} pending, {m.get('issued',0)} issued.")
    lines += ['', 'Unique games are shared across models; do not count each model forecast as an independent game. The two player challengers remain in their fixed prospective protocol (review February 8, 2027; >=200 paired games and >=12 weeks). No new candidate is being added while evidence accumulates.','', '## Candidate and confidence status','']
    promotion=store/'reports/promotion-status.json'
    if promotion.exists():
        p=json.loads(promotion.read_text())
        for v,c in p['comparisons'].items():
            lines.append(f"- {v}: {c['status']}; paired log-loss improvement {c['logLossImprovement']}; prospective interval {c['interval']} at {c['confidenceLevel']:.1%}. Evidence as of {p['generatedAt']}.")
    a=audit['opponentAdjustedLogLoss']
    lines += ['- Opponent-adjusted-v1: offline; protocol approved; shadow issuance disabled pending tested integration. Log loss mixed across 2023/2024/2025. Exploratory unadjusted 95% interval [-0.002601, 0.003320] includes zero.',
              f"- Its Bonferroni sensitivity interval ({a['confidenceLevel']:.1%}, family size {a['familySize']}): [{a['interval'][0]:.6f}, {a['interval'][1]:.6f}]; includes zero.",
              '- Margin-ridge-v1: SHELVED; log loss worse in all three cohorts; bootstrap not computed. Tie overprediction quantified. No shadow/live use.',
              '', '## Evaluation register and promotion safeguards','',
              f"Logged comparisons by cohort: {audit['counts']}. Counts include the original model versus training frequency, hyperparameter trials on 2023 and timing diagnostics. Year subgroups overlap the combined cohort and are not independent replications.",
              'Register audit: '+('PASS' if not audit['errors'] else 'BLOCKED: '+'; '.join(audit['errors'])),
              'Historical promotion is prohibited even if a corrected interval excludes zero. Fresh prospective evidence and manual review are required. The existing two-player Bonferroni protocol is unchanged.',
              '', '## Open actions','',
              '- Accumulate prospective games; wait for the registered review rather than optimizing against interim outcomes.',
              '- Implement and verify the approved opponent protocol (docs/protocols/OPPONENT_PROSPECTIVE_V1.md); registered cohort starts October 1, 2026. Issuance remains technically disabled.',
              '- User to rotate the previously exposed Odds API key and check actual GitHub billing. No new key should be posted in chat.',
              '- Odds/closing-line tracking remains a separate integration task.',
              '- Ensembling team-only and player-form probabilities: deferred until enough prospective evidence exists; future blend weights and evaluation must be preregistered as a new candidate.',
              '- Backup: dated write-once checkpoint is restore-tested; administrator deletion remains possible. See docs/REVIEW_CLOSURE.md.', '']
    destination=output or store/'reports/STATUS.md';destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text('\n'.join(lines))
    return {'generatedAt':at,'errors':audit['errors'],'path':str(destination)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--store',type=Path,default=live.LIVE);p.add_argument('--output',type=Path);a=p.parse_args()
    print(json.dumps(write_status(a.store,a.output)))
