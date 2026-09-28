import json
from pathlib import Path
import tempfile
import unittest
from postgame_cloud import assemble
from postgame_report import build


class CloudTests(unittest.TestCase):
    def test_disputed_final_is_withheld(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rechecks = root / 'forecasting/live/rechecks'
            rechecks.mkdir(parents=True)
            (rechecks / 'a.json').write_text(json.dumps({'checkedAt': '2026-09-28T01:00:00Z', 'date': '2026-09-27', 'sourceDisagreements': ['event']}))
            result = assemble(root, {'games': [{'eventId': 'event'}]}, {}, '2026-09-28T02:00:00Z', 'abc')
            self.assertEqual(result['games'], [])
            self.assertEqual(result['excluded'][0]['reason'], 'disputed-result')

    def test_future_dispute_not_applied_to_earlier_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rechecks = root / 'forecasting/live/rechecks'
            rechecks.mkdir(parents=True)
            (rechecks / 'a.json').write_text(json.dumps({'checkedAt': '2026-09-29T01:00:00Z', 'date': '2026-09-27', 'sourceDisagreements': ['event']}))
            result = assemble(root, {'games': [{'eventId': 'event'}]}, {}, '2026-09-28T02:00:00Z', 'abc')
            self.assertEqual(result['excluded'][0]['reason'], 'no-verified-final')

    def test_corrupted_stats_fail_before_reporting(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'integrity'):
                build(b'altered', {'sha256': '0' * 64, 'bytes': 7}, {}, Path(tmp))


if __name__ == '__main__':
    unittest.main()
