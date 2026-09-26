import copy
import json
from pathlib import Path
import tempfile
import unittest

import calibration_report as calibration
import promotion_report as promotion
from operations import atomic_json


class ResearchReportTests(unittest.TestCase):
    def test_promotion_pass_requires_fixed_review_and_real_improvement(self):
        plan=json.loads((promotion.ROOT/'promotion-plan.json').read_text())
        # Small synthetic cohort exercises every decision gate without touching real data.
        plan.update(minimumGames=2,minimumWeeks=2,bootstrapDraws=100)
        with tempfile.TemporaryDirectory() as temp:
            store=Path(temp)
            for week,day in [(3,'2026-09-27'),(4,'2026-10-04')]:
                event=f'2026_{week:02}_LAC_BUF'
                for version,digest in plan['modelHashes'].items():
                    p=.6 if version=='outcome-logit-v1' else .8
                    atomic_json(store/'forecasts'/version/(event+'.json'),{
                        'eventId':event,'dateEastern':day,'mode':'prospective','modelVersion':version,'modelSha256':digest,
                        'generatedAt':'2026-09-25T14:00:00Z','featureCutoffAt':'2026-09-25T13:59:00Z','kickoffAt':day+'T17:00:00Z',
                        'probabilities':{'homeWin':p,'awayWin':.99-p,'tie':.01}})
                atomic_json(store/'results'/event/'one.json',{'eventId':event,'homeScore':24,'awayScore':17,
                    'finalizedAt':day+'T21:00:00Z','timingBasis':'observed-final-in-two-sources','espnObservationId':'one'})
            report=promotion.evaluate(store,'2027-02-08T12:00:00Z',plan)
            self.assertFalse(report['automaticPromotion'])
            for c in report['comparisons'].values():
                self.assertEqual(c['status'],'eligible-for-manual-review')
                self.assertTrue(all(c['gates'].values()))
            path=store/'forecasts/player-form-v1/2026_04_LAC_BUF.json'
            row=json.loads(path.read_text()); row['featureCutoffAt']='2026-09-25T13:58:00Z'; atomic_json(path,row)
            report=promotion.evaluate(store,'2027-02-08T12:00:00Z',plan)
            self.assertFalse(report['comparisons']['player-form-v1']['gates']['integrity'])
            self.assertFalse(report['comparisons']['player-form-v1']['gates']['minimumCoverage'])

    def test_calibration_boundaries_counts_and_empty_bins(self):
        rows=[{'eventId':'one','probabilities':{'homeWin':1,'awayWin':0,'tie':0},'observedOutcome':'homeWin'},
              {'eventId':'two','probabilities':{'homeWin':.5,'awayWin':.5,'tie':0},'observedOutcome':'awayWin'}]
        report=calibration.summarize(rows)
        self.assertEqual(report['classes']['homeWin'][9]['count'],1)
        self.assertEqual(report['classes']['homeWin'][5]['observedRate'],0)
        self.assertIsNone(report['classes']['homeWin'][1]['observedRateInterval95'])
        for values in report['classes'].values():
            self.assertEqual(sum(b['count'] for b in values),2)
            for b in values:
                if b['count']:
                    lo,hi=b['observedRateInterval95']; self.assertLessEqual(lo,b['observedRate']); self.assertGreaterEqual(hi,b['observedRate'])
        with self.assertRaisesRegex(ValueError,'Duplicate'): calibration.summarize(rows+rows)

    def test_paired_week_interval_constant_improvement(self):
        rows=[{'week':str(w),'improvement':.1} for w in range(3) for _ in range(w+1)]
        lo,hi=promotion.paired_interval(rows,draws=100)
        self.assertAlmostEqual(lo,.1); self.assertAlmostEqual(hi,.1)
        self.assertIsNone(promotion.paired_interval(rows[:1]))

    def test_promotion_blocks_early_decision_hash_mismatch_and_late_result(self):
        plan=json.loads((promotion.ROOT/'promotion-plan.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            store=Path(temp)
            f={'eventId':'2026_03_LAC_BUF','dateEastern':'2026-09-27','mode':'prospective','generatedAt':'2026-09-26T14:00:00Z',
               'featureCutoffAt':'2026-09-26T13:59:00Z','kickoffAt':'2026-09-27T17:00:00Z','probabilities':{'homeWin':.6,'awayWin':.39,'tie':.01}}
            for version,digest in plan['modelHashes'].items():
                atomic_json(store/'forecasts'/version/(f['eventId']+'.json'),{**f,'modelVersion':version,'modelSha256':digest})
            result={'eventId':f['eventId'],'homeScore':24,'awayScore':17,'finalizedAt':'2026-09-27T21:00:00Z','timingBasis':'observed-final-in-two-sources','espnObservationId':'one'}
            atomic_json(store/'results'/f['eventId']/'one.json',result)
            report=promotion.evaluate(store,'2026-09-28T00:00:00Z')
            for c in report['comparisons'].values():
                self.assertEqual(c['sameGames'],1); self.assertEqual(c['status'],'awaiting-fixed-review')
            atomic_json(store/'results'/f['eventId']/'two.json',{**result,'homeScore':0,'finalizedAt':'2027-02-09T00:00:00Z','espnObservationId':'two'})
            report=promotion.evaluate(store,'2027-02-10T00:00:00Z')
            self.assertEqual(report['comparisons']['player-form-v1']['reference']['accuracy'],1)
            self.assertEqual(report['comparisons']['player-form-v1']['status'],'not-eligible-or-inconclusive')
            atomic_json(store/'forecasts/player-form-v1'/(f['eventId']+'.json'),{**f,'modelVersion':'player-form-v1','modelSha256':'wrong'})
            report=promotion.evaluate(store,'2026-09-28T00:00:00Z')
            self.assertTrue(report['errors']); self.assertFalse(report['comparisons']['player-form-v1']['gates']['integrity'])


if __name__=='__main__': unittest.main()
