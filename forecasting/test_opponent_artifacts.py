"""Audit the saved experiment against frozen inputs and nested evidence."""
import csv
import hashlib
import json
from pathlib import Path
import unittest

import build_features
import model
from opponent_features import OpponentHistory

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs/opponent-adjusted-v1'


class SavedExperimentTests(unittest.TestCase):
    def test_saved_inputs_rebuild_and_predictions_reproduce(self):
        if not RUN.exists(): self.skipTest('Experiment has not been fitted')
        artifact=json.loads((RUN/'model.json').read_text())
        for name,sha in artifact['provenance']['codeSha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha)
        with (ROOT/'data/raw/nflverse-games.csv').open() as f:
            games=build_features.normalize(csv.DictReader(f))
        source=OpponentHistory(games)
        values={}
        for split in ('train','validation','test'):
            original=[json.loads(line) for line in (ROOT/f'data/processed/v1/{split}.features.jsonl').read_text().splitlines()]
            saved=[json.loads(line) for line in (RUN/f'{split}.features.jsonl').read_text().splitlines()]
            self.assertEqual(len(original),len(saved))
            for row,actual in zip(original,saved):
                self.assertEqual(row['eventId'],actual['eventId'])
                features,evidence=source.augment(row)
                self.assertEqual(features,actual['features'])
                self.assertEqual(evidence,actual['opponentEvidence'])
                values[row['eventId']]=features
        predictions=[json.loads(line) for line in (RUN/'predictions.jsonl').read_text().splitlines()]
        self.assertEqual(len(predictions),816)
        for row in predictions:
            actual=model.predict_many(artifact,[values[row['eventId']]])[0]
            for outcome in actual: self.assertAlmostEqual(actual[outcome],row['probabilities'][outcome],delta=1e-14)
        report=json.loads((RUN/'report.json').read_text())
        for summary in report['groups'].values():
            for bins in summary['classes'].values():
                self.assertEqual(sum(b['count'] for b in bins),summary['metrics']['games'])
        self.assertEqual((RUN/'calibration.html').read_text().count('<svg'),24)


if __name__=='__main__': unittest.main()
