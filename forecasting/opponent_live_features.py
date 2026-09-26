"""Read-only, observation-aware opponent features. No forecast issuance API."""
from datetime import timedelta
import copy

import live
import snapshots
from opponent_features import eligible, points


def prepare(event_id, cutoff):
    at=snapshots.parse_time(cutoff)
    if at>snapshots.parse_time(snapshots.now()): raise ValueError('Future cutoff prohibited')
    receipt,games=live.current_games(cutoff)  # Verified hash, observed <= cutoff, age <=24h.
    target=next((g for g in games if g['eventId']==event_id),None)
    if target is None: raise ValueError('Target absent from observed schedule')
    if at>target['kickoff']-timedelta(hours=24): raise ValueError('Missed 24-hour feature deadline')
    row=live.feature_row(target,games,at)
    values=dict(row['features']);proof={};verification=copy.deepcopy(row)
    for side in ('home','away'):
        team=target[side+'TeamId'];history=[g for g in games if team in (g['homeTeamId'],g['awayTeamId']) and g['homeScore'] is not None]
        recent=eligible(history,target,at)
        if [g['eventId'] for g in recent]!=row['evidence'][side]['resultGameIds']: raise ValueError('Reference history mismatch')
        residuals=[];details=[];ids=list(row['evidence'][side]['resultGameIds'])
        for old in recent:
            opponent=old['awayTeamId'] if old['homeTeamId']==team else old['homeTeamId']
            nested_cutoff=old['kickoff']-timedelta(hours=24)
            prior=eligible([g for g in games if opponent in (g['homeTeamId'],g['awayTeamId']) and g['homeScore'] is not None],old,nested_cutoff)
            item={'gameId':old['eventId'],'opponent':opponent,'opponentCutoffAt':live.features.iso(nested_cutoff),'opponentHistoryIds':[g['eventId'] for g in prior]}
            ids.extend(item['opponentHistoryIds'])
            if prior:
                pf,pa=points(old,team)
                opp_pf=sum(points(g,opponent)[0] for g in prior)/len(prior)
                opp_pa=sum(points(g,opponent)[1] for g in prior)/len(prior)
                residuals.append((pf-opp_pa,pa-opp_pf))
                item.update(opponentPointsForMean=opp_pf,opponentPointsAgainstMean=opp_pa)
            details.append(item)
        n=len(residuals)
        values[side+'OpponentAdjustedPointsFor']=sum(r[0] for r in residuals)/n if n else 0.0
        values[side+'OpponentAdjustedPointsAgainst']=sum(r[1] for r in residuals)/n if n else 0.0
        values[side+'OpponentAdjustedGames']=n
        proof[side]=details
        verification['evidence'][side]['resultGameIds']=list(dict.fromkeys(ids))
    boards=live.verify_inputs([target],[verification],games,cutoff)
    return {'eventId':event_id,'featureCutoffAt':cutoff,'featureRow':row,'features':values,'opponentEvidence':proof,
            'sourceObservation':{k:receipt[k] for k in ('observationId','observedAt','sha256')},
            'scoreboardObservations':boards,'issuanceEnabled':False,
            'timingLimitation':'Archived observations precede target cutoff; older nested matchup publication timing retains the 48-hour assumption.'}
