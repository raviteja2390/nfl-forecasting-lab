from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
import weekly_comparison as weekly


def game(event,day,week):
    t=datetime.fromisoformat(day+'T17:00:00+00:00')
    return {'eventId':event,'season':2026,'week':week,'localDate':t.date(),'kickoff':t,'homeTeamId':'BUF','awayTeamId':'LAC'}


class WeeklyTests(unittest.TestCase):
    def test_week_includes_monday_and_moves_forward_between_weeks(self):
        games=[game('thu','2026-09-24',3),game('mon','2026-09-28',3),game('next','2026-10-01',4)]
        self.assertEqual(weekly.select_week(games,'2026-09-28T22:00:00Z'),(2026,3))
        self.assertEqual(weekly.select_week(games,'2026-09-29T12:00:00Z'),(2026,4))
        self.assertIsNone(weekly.select_week(games,'2027-05-01T12:00:00Z'))

    def test_missing_models_visible_and_original_values_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            store=Path(d);g=game('event','2026-09-27',3)
            for v in weekly.VERSIONS[:2]:
                f={'eventId':'event','modelVersion':v,'mode':'prospective','generatedAt':'2026-09-26T12:00:00Z','featureCutoffAt':'2026-09-26T11:59:00Z','kickoffAt':'2026-09-27T17:00:00Z','modelSha256':'hash','probabilities':{'homeWin':.6,'awayWin':.39,'tie':.01}}
                path=store/'forecasts'/v/'event.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(f))
            r=weekly.build([g],'2026-09-26T13:00:00Z',store)
            self.assertEqual(r['fullyPairedGames'],0)
            self.assertEqual(r['games'][0]['models'][weekly.VERSIONS[0]]['probabilities'],f['probabilities'])
            self.assertIn('not issued',weekly.render(r))
            self.assertEqual(weekly.build([g],'2026-09-26T10:00:00Z',store)['games'][0]['models'][weekly.VERSIONS[0]]['status'],'not-issued-as-of-report')

    def test_no_forecasts_created_by_report(self):
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)
            weekly.write_report([game('event','2026-09-27',3)],'2026-09-26T13:00:00Z',store)
            self.assertFalse((store/'forecasts').exists())
            self.assertTrue((store/'reports/weekly-comparison.md').exists())
            self.assertTrue((store/'reports/2026-week-03-comparison.json').exists())


if __name__=='__main__':unittest.main()
