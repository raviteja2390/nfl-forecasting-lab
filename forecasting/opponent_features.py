"""Opponent scoring residuals using strictly pre-match opponent histories."""
from collections import defaultdict
from datetime import timedelta

from build_features import WINDOW, FORECAST_LEAD_HOURS, iso


def eligible(history, target, cutoff):
    return [g for g in history if g['kickoff'] < cutoff
            and g['assumedAvailableAt'] <= cutoff
            and (g['season'], g['week']) < (target['season'], target['week'])][-WINDOW:]


def points(game, team):
    if team == game['homeTeamId']:
        return game['homeScore'], game['awayScore']
    if team == game['awayTeamId']:
        return game['awayScore'], game['homeScore']
    raise ValueError('Team not present in historical game')


class OpponentHistory:
    def __init__(self, games):
        self.by_id = {}
        self.history = defaultdict(list)
        for game in sorted(games, key=lambda g: (g['kickoff'], g['eventId'])):
            if game['eventId'] in self.by_id:
                raise ValueError('Duplicate historical game')
            self.by_id[game['eventId']] = game
            for side in ('home', 'away'):
                self.history[game[side+'TeamId']].append(game)

    def augment(self, row):
        target = self.by_id[row['eventId']]
        cutoff = target['kickoff'] - timedelta(hours=FORECAST_LEAD_HOURS)
        if row['featureCutoffAt'] != iso(cutoff):
            raise ValueError('Historical feature cutoff differs from registered policy')
        values, evidence = dict(row['features']), {}
        for side in ('home', 'away'):
            team = row[side+'TeamId']
            if team != target[side+'TeamId']:
                raise ValueError('Team mismatch')
            recent = eligible(self.history[team], target, cutoff)
            if [g['eventId'] for g in recent] != row['evidence'][side]['resultGameIds']:
                raise ValueError('Opponent model and baseline histories differ')
            residuals, proof = [], []
            for old in recent:
                opponent = old['awayTeamId'] if old['homeTeamId'] == team else old['homeTeamId']
                nested_cutoff = old['kickoff'] - timedelta(hours=FORECAST_LEAD_HOURS)
                prior = eligible(self.history[opponent], old, nested_cutoff)
                item = {'gameId': old['eventId'], 'opponent': opponent,
                        'opponentCutoffAt': iso(nested_cutoff),
                        'opponentHistoryIds': [g['eventId'] for g in prior]}
                if prior:
                    pf, pa = points(old, team)
                    opp_pf = sum(points(g, opponent)[0] for g in prior) / len(prior)
                    opp_pa = sum(points(g, opponent)[1] for g in prior) / len(prior)
                    residuals.append((pf - opp_pa, pa - opp_pf))
                    item.update(opponentPointsForMean=opp_pf, opponentPointsAgainstMean=opp_pa)
                proof.append(item)
            n = len(residuals)
            values[side+'OpponentAdjustedPointsFor'] = sum(r[0] for r in residuals)/n if n else 0.0
            values[side+'OpponentAdjustedPointsAgainst'] = sum(r[1] for r in residuals)/n if n else 0.0
            values[side+'OpponentAdjustedGames'] = n
            evidence[side] = proof
        return values, evidence
