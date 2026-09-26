import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from model import predict_many
from train_model import FEATURE_NAMES, ROOT, fit_model, join_split, read_checked, train


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        self.labels = []
        for week, outcome in enumerate(("homeWin", "awayWin", "tie"), 1):
            event_id = f"2015_{week:02d}_BUF_NE"
            self.rows.append({"eventId": event_id, "season": 2015, "week": week,
                              "kickoffAt": f"2015-09-{7 * week:02d}T17:00:00Z",
                              "featureCutoffAt": f"2015-09-{7 * week - 1:02d}T17:00:00Z",
                              "features": {name: float(week) for name in FEATURE_NAMES},
                              "evidence": {side: {"resultGameIds": [], "latestAssumedResultAvailability": None}
                                           for side in ("home", "away")}})
            self.labels.append({"eventId": event_id, "homeScore": 20 if outcome != "awayWin" else 10,
                                "awayScore": 20 if outcome != "homeWin" else 10, "outcome": outcome})

    def test_labels_join_by_id_and_reject_duplicate_missing_and_wrong_outcome(self):
        rows, targets = join_split(self.rows, list(reversed(self.labels)), [2015])
        self.assertEqual(targets, ["homeWin", "awayWin", "tie"])
        for invalid in (self.labels[:2], self.labels + [self.labels[0]]):
            with self.assertRaisesRegex(ValueError, "one-to-one"):
                join_split(self.rows, invalid, [2015])
        broken = copy.deepcopy(self.labels)
        broken[0]["outcome"] = "awayWin"
        with self.assertRaisesRegex(ValueError, "disagrees"):
            join_split(self.rows, broken, [2015])

    def test_forbidden_season_and_late_or_same_week_evidence_fail(self):
        with self.assertRaisesRegex(ValueError, "forbidden seasons"):
            join_split(self.rows, self.labels, [2023])
        broken = copy.deepcopy(self.rows)
        broken[0]["evidence"]["home"]["latestAssumedResultAvailability"] = broken[0]["kickoffAt"]
        with self.assertRaisesRegex(ValueError, "availability"):
            join_split(broken, self.labels, [2015])
        broken[0]["evidence"]["home"]["latestAssumedResultAvailability"] = None
        broken[0]["evidence"]["home"]["resultGameIds"] = [broken[0]["eventId"]]
        with self.assertRaisesRegex(ValueError, "same-week"):
            join_split(broken, self.labels, [2015])

    def test_scaler_only_fits_training_and_export_matches_sklearn(self):
        artifact, estimator = fit_model(self.rows, [x["outcome"] for x in self.labels], 0.1)
        self.assertEqual(artifact["mean"], [2] * len(FEATURE_NAMES))
        extreme = {name: 1000 for name in FEATURE_NAMES}
        actual = predict_many(artifact, [extreme])[0]
        expected = estimator.predict_proba([[1000] * len(FEATURE_NAMES)])[0]
        np.testing.assert_allclose([actual[key] for key in artifact["classes"]], expected, atol=1e-12)
        self.assertEqual(artifact["mean"], [2] * len(FEATURE_NAMES))

    def test_corrupt_input_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "train.labels.jsonl"
            path.write_text("corrupt")
            manifest = {"files": {path.name: {"sha256": "0" * 64, "rows": 1}}}
            with self.assertRaisesRegex(ValueError, "Checksum"):
                read_checked(path.parent, path.name, manifest)

    def test_end_to_end_never_opens_final_test_and_keeps_actual_generation_time(self):
        original = Path.read_bytes
        opened = []

        def guarded(path):
            opened.append(path.name)
            if path.name.startswith("test."):
                raise AssertionError("Final test data was opened")
            return original(path)

        with tempfile.TemporaryDirectory() as folder, patch.object(Path, "read_bytes", guarded):
            output = Path(folder) / "run"
            report = train(ROOT / "data/experiments/timing-v1", output, ROOT / "training-plan.json")
            self.assertFalse(report["finalTestEvaluated"])
            self.assertEqual(report["trainingGames"], 2079)
            self.assertEqual(report["validationGames"], 272)
            self.assertEqual(report["timingSensitivity"]["24"]["fixedPredictionChange"]["maxAbsoluteProbabilityChange"], 0)
            predictions = [json.loads(line) for line in (output / "validation.predictions.jsonl").read_text().splitlines()]
            self.assertTrue(all(row["mode"] == "historical-simulation" and row["generatedAt"] > row["kickoffAt"]
                                and row["simulatedFeatureCutoffAt"] < row["kickoffAt"] for row in predictions))
            manifest = json.loads((output / "artifacts.json").read_text())
            for name, entry in manifest["files"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), entry["sha256"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                train(ROOT / "data/experiments/timing-v1", output, ROOT / "training-plan.json")
        self.assertTrue(opened)
        self.assertFalse(any(name.startswith("test.") for name in opened))


if __name__ == "__main__":
    unittest.main()
