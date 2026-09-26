import copy
from datetime import datetime, timedelta, timezone
import unittest

from build_features import iso
from opponent_features import OpponentHistory, eligible


def game(name, week, day, home, away, hs, aws):
    kickoff=datetime(2020,9,1,tzinfo=timezone.utc)+timedelta(days=day)
    return dict(eventId=name,season=2020,week=week,kickoff=kickoff,
                assumedAvailableAt=kickoff+timedelta(hours=48),
                homeTeamId=home,awayTeamId=away,homeScore=hs,awayScore=aws)


def fixture():
    # B's prior defense allowed 10; A then scored 30 against B => +20.
    games=[game('prior',1,0,'B','C',20,10),
           game('match',2,7,'A','B',30,25),
           game('target',3,14,'A','D',0,0)]
    target=games[-1]
    row=dict(eventId='target',homeTeamId='A',awayTeamId='D',
             featureCutoffAt=iso(target['kickoff']-timedelta(hours=24)),
             features={'homeField':1},evidence={'home':{'resultGameIds':['match']},'away':{'resultGameIds':[]}})
    return games,row


class OpponentTests(unittest.TestCase):
    def test_residual_direction_and_missing_coverage(self):
        games,row=fixture(); values,proof=OpponentHistory(games).augment(row)
        self.assertEqual(values['homeOpponentAdjustedPointsFor'],20)
        self.assertEqual(values['homeOpponentAdjustedPointsAgainst'],5)
        self.assertEqual(values['homeOpponentAdjustedGames'],1)
        self.assertEqual(values['awayOpponentAdjustedGames'],0)
        self.assertEqual(values['awayOpponentAdjustedPointsFor'],0)
        self.assertEqual(proof['home'][0]['opponentHistoryIds'],['prior'])
        self.assertEqual(row['features'],{'homeField':1})

    def test_target_and_future_scores_do_not_change_inputs(self):
        games,row=fixture(); expected=OpponentHistory(games).augment(row)
        games[-1]['homeScore']=999
        games.append(game('future',4,21,'B','A',999,999))
        self.assertEqual(OpponentHistory(games).augment(row),expected)

    def test_opponent_results_after_historical_match_excluded(self):
        games,row=fixture(); expected=OpponentHistory(games).augment(row)
        games.append(game('later',3,10,'B','C',999,999))
        self.assertEqual(OpponentHistory(games).augment(row),expected)

    def test_same_week_and_lag_boundary(self):
        target=game('target',3,14,'A','D',0,0)
        cutoff=target['kickoff']-timedelta(hours=24)
        before=game('before',2,10,'A','B',10,20)
        exact=game('exact',2,11,'A','C',10,20)
        late=game('late',2,12,'A','C',10,20)
        same=game('same',3,9,'A','C',10,20)
        self.assertEqual([g['eventId'] for g in eligible([before,exact,late,same],target,cutoff)],['before','exact'])

    def test_nested_unavailable_score_is_not_used(self):
        games,row=fixture()
        games[0]['assumedAvailableAt']=games[1]['kickoff']
        values,proof=OpponentHistory(games).augment(row)
        self.assertEqual(values['homeOpponentAdjustedGames'],0)
        self.assertEqual(proof['home'][0]['opponentHistoryIds'],[])

    def test_disagreed_reference_history_rejected(self):
        games,row=fixture(); row['evidence']['home']['resultGameIds']=[]
        with self.assertRaises(ValueError): OpponentHistory(games).augment(row)

    def test_recent_window_limited_to_eight(self):
        games=[game(str(i),i+1,i*7,'B','C',i,i) for i in range(10)]
        target=game('target',12,80,'B','D',0,0)
        self.assertEqual([g['eventId'] for g in eligible(games,target,target['kickoff']-timedelta(hours=24))],[str(i) for i in range(2,10)])


if __name__=='__main__': unittest.main()
