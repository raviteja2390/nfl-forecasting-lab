import unittest
from postgame_report import aggregate, number


class AggregationTests(unittest.TestCase):
    def test_missing_active_passing_epa_stays_unknown(self):
        rows = [{'attempts': '20', 'sacks_suffered': '2', 'passing_epa': '', 'passing_interceptions': '1', 'carries': '0', 'fg_att': '0'}]
        result = aggregate(rows)
        self.assertIsNone(result['passing_epa'])
        self.assertIsNone(result['passing_epa_per_attempt_plus_sack'])

    def test_receiving_epa_is_not_double_counted(self):
        rows = [{'attempts': '20', 'sacks_suffered': '2', 'passing_epa': '4', 'passing_interceptions': '0', 'carries': '2', 'rushing_epa': '-1', 'fg_att': '0'},
                {'attempts': '0', 'sacks_suffered': '0', 'passing_epa': '', 'receiving_epa': '4', 'carries': '0', 'fg_att': '0'}]
        result = aggregate(rows)
        self.assertEqual(result['passing_epa'], 4)
        self.assertAlmostEqual(result['passing_epa_per_attempt_plus_sack'], 4 / 22)
        self.assertIsNone(result['fg_made'])

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            number('inf')


class IdentityTests(unittest.TestCase):
    def render(self, rows):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from postgame_report import build
        body = ('season,week,season_type,game_id,team,opponent_team,player_id\n' + rows).encode()
        provenance = {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body),
                      'observedAt': '2026-09-29T00:00:00Z', 'sourceUrl': 'fixture'}
        comparison = {'season': 2026, 'week': 3, 'asOf': '2026-09-29T00:00:00Z',
                      'sourceStateCommit': 'fixture', 'excluded': [], 'games': [{
                          'eventId': '2026_03_LA_DEN', 'home': 'DEN', 'away': 'LAR',
                          'result': {'timingBasis': 'observed-final-in-two-sources',
                                     'homeScore': 20, 'awayScore': 10,
                                     'finalizedAt': '2026-09-28T04:00:00Z'}}]}
        with tempfile.TemporaryDirectory() as t:
            output = Path(t)
            count = build(body, provenance, comparison, output)
            return count, json.loads((output / 'REPORT.json').read_text())

    def test_source_alias_matches_forecast_without_changing_event_id(self):
        count, report = self.render('2026,3,REG,2026_03_LA_DEN,LA,DEN,a\n2026,3,REG,2026_03_LA_DEN,DEN,LA,b\n')
        self.assertEqual(count, 1)
        self.assertEqual(set(report['games'][0]['teams']), {'LAR', 'DEN'})
        self.assertEqual(report['games'][0]['eventId'], '2026_03_LA_DEN')

    def test_genuine_opponent_mismatch_still_fails(self):
        with self.assertRaisesRegex(ValueError, 'Opponent mismatch: 2026_03_LA_DEN'):
            self.render('2026,3,REG,2026_03_LA_DEN,DEN,KC,b\n')

    def test_alias_cannot_hide_duplicate_player(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate player/game/team'):
            self.render('2026,3,REG,2026_03_LA_DEN,LA,DEN,a\n2026,3,REG,2026_03_LA_DEN,LAR,DEN,a\n')


if __name__ == '__main__':
    unittest.main()
