import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from compare_margins import fit,fit_candidate
import margin_model

ROOT=Path(__file__).resolve().parent


class MarginTests(unittest.TestCase):
    def test_symmetric_distribution(self):
        p=margin_model.handicap_probabilities(0,14)
        self.assertAlmostEqual(p['cover'],p['loss'])
        self.assertGreater(p['push'],0)
        self.assertAlmostEqual(sum(p.values()),1)

    def test_handicap_sign_and_push(self):
        p=margin_model.handicap_probabilities(3,14,-3)
        self.assertAlmostEqual(p['cover'],p['loss'])
        self.assertGreater(p['push'],0)
        half=margin_model.handicap_probabilities(3,14,-3.5)
        self.assertEqual(half['push'],0)
        self.assertAlmostEqual(half['cover'],p['cover'])
        self.assertGreater(margin_model.handicap_probabilities(3,14,3.5)['cover'],half['cover'])

    def test_extreme_finite_and_monotone(self):
        for mu in (-10000,0,10000):
            p=margin_model.handicap_probabilities(mu,1)
            self.assertTrue(all(math.isfinite(v) and 0<=v<=1 for v in p.values()))
            self.assertAlmostEqual(sum(p.values()),1)
        self.assertLess(margin_model.handicap_probabilities(-5,14)['cover'],margin_model.handicap_probabilities(5,14)['cover'])

    def test_invalid_parameters(self):
        for args in [(0,0,0),(0,-1,0),(float('nan'),1,0),(0,1,float('inf'))]:
            with self.assertRaises(ValueError): margin_model.handicap_probabilities(*args)

    def test_inference_and_schema(self):
        a={'schemaVersion':1,'kind':'ridge-gaussian-margin','featureNames':['x'],'mean':[2.0], 'scale':[2.0],'coefficients':[3.0],'intercept':1.0,'sigma':14.0}
        self.assertEqual(margin_model.predict_margin(a,{'x':4}),4)
        with self.assertRaises(ValueError): margin_model.predict_margin(a,{'y':4})
        a['sigma']=0
        with self.assertRaises(ValueError): margin_model.predict_margin(a,{'x':4})

    def test_forward_folds_never_fit_their_own_outcomes(self):
        rows=[{'eventId':str(y),'season':y,'features':{'x':float(y-2015)}} for y in range(2015,2023)]
        targets=[float(i) for i in range(8)]
        calls=[]
        def tracked(rs,ys,alpha,names):
            calls.append([r['season'] for r in rs]);return fit(rs,ys,alpha,names)
        with patch('compare_margins.fit',side_effect=tracked):
            artifact,errors=fit_candidate(rows,targets,1,['x'])
        for year,seasons in zip(range(2017,2023),calls[:-1]):
            self.assertTrue(all(y<year for y in seasons))
        self.assertEqual(calls[-1],list(range(2015,2023)))
        self.assertEqual(len(errors),6)
        changed=targets.copy();changed[-1]=1000
        _,new_errors=fit_candidate(rows,changed,1,['x'])
        self.assertEqual(errors[:-1],new_errors[:-1])
        self.assertGreaterEqual(artifact['sigma'],1)

    def test_saved_predictions_and_sigma_reproduce(self):
        run=ROOT/'runs/margin-ridge-v1'
        if not run.exists(): self.skipTest('Experiment not fitted yet')
        artifact=json.loads((run/'model.json').read_text())
        features={r['eventId']:r['features'] for split in ('validation','test') for r in map(json.loads,(ROOT/f'data/processed/v1/{split}.features.jsonl').read_text().splitlines())}
        for r in map(json.loads,(run/'predictions.jsonl').read_text().splitlines()):
            self.assertEqual(margin_model.predict_margin(artifact,features[r['eventId']]),r['predictedMargin'])
            self.assertEqual(margin_model.predict_many(artifact,[features[r['eventId']]])[0],r['probabilities'])
        errors=list(map(json.loads,(run/'training-oof-errors.jsonl').read_text().splitlines()))
        self.assertEqual(artifact['sigma'],max(1,math.sqrt(sum(r['error']**2 for r in errors)/len(errors))))
        self.assertTrue(all(2017<=r['season']<=2022 for r in errors))
        for fold in artifact['errorEstimation']['folds']:
            self.assertLess(max(fold['trainingSeasons']),fold['evaluationSeason'])
        self.assertEqual((run/'calibration.html').read_text().count('<svg'),24)


if __name__=='__main__': unittest.main()
