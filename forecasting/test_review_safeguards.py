from datetime import timedelta
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import checkpoint
import cloud_runner
import live
import operations
import opponent_live_features as prospective
from opponent_features import OpponentHistory
import snapshots


class ReviewTests(unittest.TestCase):
    def test_checkpoint_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'repo';root.mkdir()
            subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'a.txt').write_text('original')
            subprocess.run(['git','add','a.txt'],cwd=root,check=True)
            subprocess.run(['git','-c','user.name=test','-c','user.email=test@example.invalid','commit','-qm','test'],cwd=root,check=True)
            snap=Path(d)/'2026-09-26T180000Z-checkpoint';checkpoint.create(root,snap)
            with self.assertRaises(FileExistsError): checkpoint.create(root,snap)
            output=Path(d)/'restored';checkpoint.restore(snap,output)
            self.assertEqual((output/'a.txt').read_text(),'original')
            with self.assertRaises(FileExistsError): checkpoint.restore(snap,output)
            (snap/'checkpoint.zip').chmod(0o644);(snap/'checkpoint.zip').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'checksum'): checkpoint.restore(snap,Path(d)/'badrestore')
            snap.chmod(0o755)

    def test_restore_paths_reject_traversal(self):
        for p in ('../secret','/absolute','.env','a/../../x','x.pem'):
            with self.assertRaises(ValueError): checkpoint.safe(p)

    def test_cloud_uses_identical_gate_and_cycle(self):
        import scheduled_run,cycle
        self.assertIs(cloud_runner.collection_due,scheduled_run.collection_due)
        self.assertIs(cloud_runner.cycle.run_cycle,cycle.run_cycle)
        with patch.object(cloud_runner,'collection_due',return_value=False) as gate:
            self.assertFalse(cloud_runner.plan()['collect']);gate.assert_called_once()

    def test_dst_spring_and_fall(self):
        for at,expected in [('2026-03-08T07:35:00Z','2026-03-08T07:05:00+00:00'),('2026-11-01T05:35:00Z','2026-11-01T05:05:00+00:00'),('2026-11-01T06:35:00Z','2026-11-01T06:05:00+00:00')]:
            self.assertEqual(operations.latest_due(at,{at[:10]}).isoformat(),expected)
        self.assertEqual(snapshots.parse_time('2026-11-01T05:30:00Z').astimezone(live.features.EASTERN).hour,1)
        self.assertEqual(snapshots.parse_time('2026-11-01T06:30:00Z').astimezone(live.features.EASTERN).hour,1)

    def test_live_feature_parity_and_expanded_confirmation(self):
        games=live.parse_games((live.ROOT/'data/raw/nflverse-games.csv').read_bytes())
        row=json.loads((live.ROOT/'data/processed/v1/validation.features.jsonl').read_text().splitlines()[20])
        receipt={'observationId':'test','observedAt':row['featureCutoffAt'],'sha256':'test'}
        with patch.object(live,'current_games',return_value=(receipt,games)),patch.object(live,'verify_inputs',return_value={}) as verify:
            result=prospective.prepare(row['eventId'],row['featureCutoffAt'])
            expected,evidence=OpponentHistory(games).augment(row)
            self.assertEqual(result['features'],expected)
            self.assertEqual(result['opponentEvidence'],evidence)
            checked=verify.call_args.args[1][0]
            for side in ('home','away'):
                ids=set(checked['evidence'][side]['resultGameIds'])
                for item in evidence[side]: self.assertTrue(set(item['opponentHistoryIds'])<=ids)
            self.assertFalse(result['issuanceEnabled'])
        target=next(g for g in games if g['eventId']==row['eventId'])
        with patch.object(live,'current_games',return_value=(receipt,games)):
            with self.assertRaisesRegex(ValueError,'deadline'):
                prospective.prepare(row['eventId'],snapshots.now() if target['season']==2026 else live.features.iso(target['kickoff']-timedelta(hours=24)+timedelta(seconds=1)))

    def test_observation_failure_propagates_without_fallback(self):
        with patch.object(live,'current_games',side_effect=ValueError('stale or absent')):
            with self.assertRaisesRegex(ValueError,'stale'): prospective.prepare('event','2026-09-26T12:00:00Z')
        games=live.parse_games((live.ROOT/'data/raw/nflverse-games.csv').read_bytes())
        row=json.loads((live.ROOT/'data/processed/v1/validation.features.jsonl').read_text().splitlines()[20])
        with patch.object(live,'current_games',return_value=({},games)),patch.object(live,'verify_inputs',side_effect=ValueError('No observed scoreboard by cutoff')):
            with self.assertRaisesRegex(ValueError,'No observed'): prospective.prepare(row['eventId'],row['featureCutoffAt'])

    def test_publish_checks_completion_deadline(self):
        games=live.parse_games((live.ROOT/'data/raw/nflverse-games.csv').read_bytes())
        g=next(g for g in games if g['eventId'].startswith('2023_02'))
        deadline=g['kickoff']-timedelta(hours=24)
        with tempfile.TemporaryDirectory() as d,patch.object(live,'current_games',return_value=({},[g]+[x for x in games if x['kickoff']<deadline])),patch.object(live,'verify_inputs',return_value={}):
            with patch.object(snapshots,'now',side_effect=[live.features.iso(deadline),live.features.iso(deadline+timedelta(seconds=1))]):
                with self.assertRaisesRegex(ValueError,'crossed'):live.publish(g['localDate'].isoformat(),Path(d))
            self.assertFalse(list(Path(d).rglob('*.json')))


if __name__=='__main__':unittest.main()
