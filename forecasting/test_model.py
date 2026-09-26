import copy
import json
import math
import unittest

from model import (aggregate, calibration, evaluate_predictions, predict_many,
                   score, weekly_bootstrap)


class ModelTests(unittest.TestCase):
    def test_portable_softmax_respects_saved_class_order_and_scaling(self):
        artifact = {"schemaVersion": 1, "kind": "multinomial-logistic-regression",
                    "featureNames": ["x"], "classes": ["tie", "homeWin", "awayWin"],
                    "mean": [10], "scale": [2], "coefficients": [[0], [1], [-1]], "intercepts": [0, 0, 0]}
        probabilities = predict_many(json.loads(json.dumps(artifact)), [{"x": 12}])[0]
        denominator = 1 + math.e + 1 / math.e
        self.assertAlmostEqual(probabilities["homeWin"], math.e / denominator)
        self.assertAlmostEqual(probabilities["tie"], 1 / denominator)
        self.assertAlmostEqual(sum(probabilities.values()), 1)
        for invalid in ({}, {"x": float("nan")}, {"x": True}, {"x": 1, "score": 20}):
            with self.assertRaises(ValueError):
                predict_many(artifact, [invalid])
        broken = copy.deepcopy(artifact)
        broken["scale"] = [0]
        with self.assertRaises(ValueError):
            predict_many(broken, [{"x": 12}])

    def test_probability_losses_have_known_values_and_abstention(self):
        result = score({"homeWin": 0.5, "awayWin": 0.5, "tie": 0}, "homeWin")
        self.assertAlmostEqual(result["brier"], 0.5)
        self.assertAlmostEqual(result["logLoss"], math.log(2))
        self.assertIsNone(result["correct"])
        stats = aggregate([result])
        self.assertEqual(stats["coverage"], 0)
        self.assertIsNone(stats["accuracy"])
        floor = score({"homeWin": 1, "awayWin": 0, "tie": 0}, "tie")
        self.assertEqual(floor["brier"], 2)
        self.assertAlmostEqual(floor["logLoss"], -math.log(1e-15))
        self.assertIsNone(aggregate([])["brier"])

    def test_invalid_distributions_and_mismatched_lengths_are_rejected(self):
        for p in ({"homeWin": 0.8, "awayWin": 0.8, "tie": 0},
                  {"homeWin": 1, "awayWin": -0.1, "tie": 0.1},
                  {"homeWin": float("nan"), "awayWin": 0, "tie": 0}):
            with self.assertRaises(ValueError):
                score(p, "homeWin")
        with self.assertRaises(ValueError):
            evaluate_predictions([], ["homeWin"], {"homeWin": 1, "awayWin": 0, "tie": 0})

    def test_calibration_includes_zero_and_one_without_empty_bin_fake_rates(self):
        bins = calibration([{"homeWin": 1, "awayWin": 0, "tie": 0}], ["homeWin"])
        self.assertEqual(bins["homeWin"][-1]["count"], 1)
        self.assertEqual(bins["homeWin"][-1]["observedRate"], 1)
        self.assertEqual(bins["awayWin"][0]["count"], 1)
        self.assertIsNone(bins["homeWin"][0]["observedRate"])

    def test_paired_week_bootstrap_zero_when_predictions_equal_baseline(self):
        baseline = {"homeWin": 0.6, "awayWin": 0.39, "tie": 0.01}
        result = weekly_bootstrap([{"season": 2023, "week": 1}, {"season": 2023, "week": 2}],
                                  [baseline, baseline], ["homeWin", "awayWin"], baseline, 100, 7)
        self.assertEqual(result["weeks"], 2)
        self.assertEqual(result["improvementIntervals"], {"brier": [0, 0], "logLoss": [0, 0]})


if __name__ == "__main__":
    unittest.main()
