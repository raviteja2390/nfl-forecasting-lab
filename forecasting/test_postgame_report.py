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


if __name__ == '__main__':
    unittest.main()
