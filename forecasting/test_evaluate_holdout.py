"""Use synthetic holdout rows only; never read the real reserved outcomes."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluate_holdout import (ROOT, checked_bytes, encode, evaluate, join_outcomes,
                              sha, validate_contract, validate_features)
import model as scoring


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.data = self.root / "run", self.root / "data"
        self.run.mkdir()
        self.data.mkdir()
        self.output = self.run / "holdout-2024-2025"
        self.model_bytes = (ROOT / "runs/outcome-logit-v1/model.json").read_bytes()
        self.artifact = json.loads(self.model_bytes)
        (self.run / "model.json").write_bytes(self.model_bytes)
        (self.run / "artifacts.json").write_bytes(encode({"files": {"model.json": {
            "sha256": sha(self.model_bytes), "bytes": len(self.model_bytes)}}}))
        self.manifest = json.loads((ROOT / "data/processed/v1/manifest.json").read_bytes())
        self.plan = json.loads((ROOT / "holdout-plan.json").read_bytes())
        self.rows, self.labels = [], []
        for season in (2024, 2025):
            for week in (1, 2):
                kickoff = datetime(season, 9, 1 + 7 * week, 17, tzinfo=timezone.utc)
                fmt = lambda value: value.isoformat(timespec="seconds").replace("+00:00", "Z")
                event_id = f"{season}_{week:02d}_BUF_NE"
                self.rows.append({"eventId": event_id, "season": season, "week": week,
                                  "kickoffAt": fmt(kickoff), "featureCutoffAt": fmt(kickoff - timedelta(hours=24)),
                                  "features": dict(zip(self.artifact["featureNames"], self.artifact["mean"])),
                                  "evidence": {side: {"latestAssumedResultAvailability": fmt(kickoff - timedelta(days=5)),
                                                       "resultGameIds": [f"{season - 1}_18_NE_BUF"]}
                                               for side in ("home", "away")}})
                self.labels.append({"eventId": event_id, "homeScore": 20 if week == 1 else 10,
                                    "awayScore": 10 if week == 1 else 20,
                                    "outcome": "homeWin" if week == 1 else "awayWin"})
        self.manifest["splits"]["test"] = {"bySeason": {"2024": 2, "2025": 2}, "rows": 4}
        self.plan["expectedGamesBySeason"] = {"2024": 2, "2025": 2}
        self.plan["bootstrap"]["draws"] = 20
        self.save_inputs()

    def save_inputs(self):
        for name, rows in (("test.features.jsonl", self.rows), ("test.labels.jsonl", list(reversed(self.labels)))):
            body = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
            (self.data / name).write_bytes(body)
            entry = {"sha256": sha(body), "bytes": len(body)}
            self.manifest["files"][name] = entry
            self.plan["testFiles"][name] = entry
        manifest_bytes = encode(self.manifest)
        (self.data / "manifest.json").write_bytes(manifest_bytes)
        self.plan["processedManifestSha256"] = sha(manifest_bytes)
        self.plan_path = self.root / "plan.json"
        self.plan_path.write_bytes(encode(self.plan))

    def test_predictions_saved_before_single_label_read_and_model_unchanged(self):
        original = Path.read_bytes
        label_reads = []

        def guarded(path):
            if path == self.data / "test.labels.jsonl":
                label_reads.append(path)
                self.assertTrue((self.output / "exposure.json").exists())
                predictions = [json.loads(line) for line in (self.output / "predictions.jsonl").read_text().splitlines()]
                self.assertEqual(len(predictions), 4)
                self.assertTrue(all("observedOutcome" not in row for row in predictions))
                self.assertTrue(all(row["generatedAt"] > row["kickoffAt"] > row["simulatedFeatureCutoffAt"] for row in predictions))
            return original(path)

        with patch.object(Path, "read_bytes", guarded), patch.object(scoring, "predict_many", wraps=scoring.predict_many) as predictor:
            report = evaluate(self.run, self.data, self.plan_path)
        self.assertEqual(len(label_reads), 1)
        self.assertEqual(predictor.call_count, 1)
        self.assertFalse(report["refitted"])
        self.assertEqual(report["overall"]["model"]["games"], 4)
        self.assertEqual(report["overall"]["model"]["correct"], 2)
        self.assertEqual(set(report["bySeason"]), {"2024", "2025"})
        self.assertEqual(report["overall"]["uncertainty"]["weeks"], 4)
        self.assertEqual((self.run / "model.json").read_bytes(), self.model_bytes)
        manifest = json.loads((self.output / "artifacts.json").read_bytes())
        for name, entry in manifest["files"].items():
            checked_bytes(self.output / name, entry)

    def test_second_run_refused_without_reading_inputs(self):
        evaluate(self.run, self.data, self.plan_path)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("Should not read again")):
            with self.assertRaisesRegex(ValueError, "already exists"):
                evaluate(self.run, self.data, self.plan_path)

    def test_model_or_feature_corruption_rejected_before_exposure(self):
        (self.run / "model.json").write_bytes(self.model_bytes + b" ")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            evaluate(self.run, self.data, self.plan_path)
        self.assertFalse(self.output.exists())
        (self.run / "model.json").write_bytes(self.model_bytes)
        (self.data / "test.features.jsonl").write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            evaluate(self.run, self.data, self.plan_path)
        self.assertFalse(self.output.exists())

    def test_label_failure_retains_predictions_and_exposure_marker(self):
        self.labels[0]["outcome"] = "tie"
        self.save_inputs()
        with self.assertRaisesRegex(ValueError, "contradicts"):
            evaluate(self.run, self.data, self.plan_path)
        self.assertTrue((self.output / "predictions.jsonl").exists())
        self.assertTrue((self.output / "exposure.json").exists())
        self.assertFalse((self.output / "report.json").exists())
        with self.assertRaisesRegex(ValueError, "already exists"):
            evaluate(self.run, self.data, self.plan_path)

    def test_missing_duplicate_or_misaligned_labels_fail(self):
        for labels in (self.labels[:-1], self.labels + [self.labels[0]],
                       [{**row, "eventId": "unknown"} for row in self.labels]):
            with self.assertRaisesRegex(ValueError, "exactly once"):
                join_outcomes(self.rows, labels)
        self.assertEqual(join_outcomes(self.rows, list(reversed(self.labels))),
                         ["homeWin", "awayWin", "homeWin", "awayWin"])

    def test_late_and_same_week_evidence_and_wrong_cutoff_fail(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["evidence"]["home"]["latestAssumedResultAvailability"] = rows[0]["kickoffAt"]
        with self.assertRaisesRegex(ValueError, "after their cutoff"):
            validate_features(rows, self.artifact, self.plan)
        rows = copy.deepcopy(self.rows)
        rows[0]["evidence"]["home"]["resultGameIds"] = [rows[0]["eventId"]]
        with self.assertRaisesRegex(ValueError, "same-week"):
            validate_features(rows, self.artifact, self.plan)
        rows[0]["featureCutoffAt"] = rows[0]["kickoffAt"]
        with self.assertRaisesRegex(ValueError, "cutoff"):
            validate_features(rows, self.artifact, self.plan)

    def test_contract_rejects_different_source_development_data_and_refit(self):
        for change in ("source", "development", "refit"):
            manifest, plan = copy.deepcopy(self.manifest), copy.deepcopy(self.plan)
            if change == "source":
                manifest["source"]["sha256"] = "changed"
            elif change == "development":
                manifest["files"]["train.features.jsonl"]["sha256"] = "changed"
            else:
                plan["modelRefitting"] = True
            with self.assertRaises(ValueError):
                validate_contract(self.artifact, manifest, plan)

    def test_coverage_and_duplicate_features_fail(self):
        with self.assertRaisesRegex(ValueError, "every declared"):
            validate_features(self.rows[:-1], self.artifact, self.plan)
        rows = copy.deepcopy(self.rows)
        rows[1] = copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_features(rows, self.artifact, self.plan)


if __name__ == "__main__":
    unittest.main()
