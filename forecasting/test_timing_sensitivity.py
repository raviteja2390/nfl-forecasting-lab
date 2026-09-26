import copy
import unittest

import build_features as pipeline
from test_build_features import game
from timing_sensitivity import compare_rows


class TimingTests(unittest.TestCase):
    def test_lag_changes_history_without_changing_targets_or_rest(self):
        rows = [game(2015, 1, "2015-09-14", "20:31"), game(2015, 2, "2015-09-17", "20:30", "NE", "BUF")]
        scenarios = {lag: pipeline.build_records(pipeline.normalize(rows, lag))["train"] for lag in (24, 48, 72)}
        report = compare_rows(scenarios[48]["features"], scenarios[24]["features"])
        self.assertEqual(report["gamesWithChangedFeatures"], 1)
        self.assertEqual(report["gamesWithChangedHistories"], 1)
        self.assertEqual(report["byFeature"]["homeDaysSincePriorGameCapped30"]["changedGames"], 0)
        self.assertEqual(scenarios[24]["labels"], scenarios[72]["labels"])
        self.assertEqual(compare_rows(scenarios[48]["features"], scenarios[48]["features"])["changedCells"], 0)

    def test_compares_by_id_not_row_order_and_detects_missing_games(self):
        rows = [game(), game(2015, 2, "2015-09-20", "13:00", "BUF", "NE")]
        records = pipeline.build_records(pipeline.normalize(rows))["train"]["features"]
        self.assertEqual(compare_rows(records, list(reversed(records)))["changedCells"], 0)
        with self.assertRaisesRegex(ValueError, "identical games"):
            compare_rows(records, records[:1])

    def test_invalid_lags_fail_instead_of_admitting_future_results(self):
        for lag in (-1, 0, 169, 1.5, True):
            with self.assertRaises(ValueError):
                pipeline.normalize([game()], lag)

    def test_changed_averages_are_counted_even_with_same_history_size(self):
        records = pipeline.build_records(pipeline.normalize([game()]))["train"]["features"]
        altered = copy.deepcopy(records)
        records[0]["features"]["homePointsForMean"] = 20
        altered[0]["features"]["homePointsForMean"] = 21.5
        report = compare_rows(records, altered)
        self.assertEqual(report["changedCells"], 1)
        self.assertEqual(report["gamesWithChangedHistories"], 0)
        self.assertEqual(report["byFeature"]["homePointsForMean"]["maxAbsoluteChange"], 1.5)


if __name__ == "__main__":
    unittest.main()
