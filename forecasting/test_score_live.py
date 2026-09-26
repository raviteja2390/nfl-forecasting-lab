import json
from pathlib import Path
import tempfile
import unittest

import live
from score_live import score_store


class ScoreLiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name)
        self.forecast = {"eventId": "2026_03_LAC_BUF", "mode": "prospective", "modelVersion": "outcome-logit-v1",
                         "generatedAt": "2026-09-26T14:00:00Z", "featureCutoffAt": "2026-09-26T13:59:00Z",
                         "kickoffAt": "2026-09-27T17:00:00Z", "probabilities": {"homeWin": 0.6, "awayWin": 0.39, "tie": 0.01}}
        self.save_forecast(self.forecast)

    def save_forecast(self, value):
        path = self.store / "forecasts" / value["modelVersion"] / (value["eventId"] + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(live.encode(value))

    def save_result(self, result):
        path = self.store / "results" / self.forecast["eventId"] / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(live.encode(result))

    def result(self):
        return {"eventId": self.forecast["eventId"], "homeScore": 24, "awayScore": 17,
                "finalizedAt": "2026-09-27T21:00:00Z", "timingBasis": "observed-final-in-two-sources", "espnObservationId": "one"}

    def test_pending_and_not_yet_issued_are_not_scored(self):
        report = score_store(self.store, "2026-09-26T15:00:00Z")
        m = report["models"]["outcome-logit-v1"]
        self.assertEqual(m["pending"], 1)
        self.assertIsNone(m["accuracy"])
        self.assertEqual(score_store(self.store, "2026-09-26T13:00:00Z")["models"], {})

    def test_future_result_is_excluded_then_scored(self):
        self.save_result(self.result())
        self.assertEqual(score_store(self.store, "2026-09-27T20:00:00Z")["models"]["outcome-logit-v1"]["games"], 0)
        self.assertEqual(score_store(self.store, "2026-09-27T22:00:00Z")["models"]["outcome-logit-v1"]["accuracy"], 1)

    def test_pairing_uses_same_event_and_cutoff(self):
        self.save_forecast({**self.forecast, "modelVersion": "challenger", "probabilities": {"homeWin": 0.8, "awayWin": 0.19, "tie": 0.01}})
        self.save_result(self.result())
        c = score_store(self.store, "2026-09-27T22:00:00Z")["pairedComparisons"]["challenger"]
        self.assertEqual(c["sameGames"], 1)
        self.assertGreater(c["logLossImprovement"], 0)
        self.save_forecast({**self.forecast, "modelVersion": "challenger", "featureCutoffAt": "2026-09-26T13:00:00Z"})
        with self.assertRaisesRegex(ValueError, "different feature cutoffs"):
            score_store(self.store, "2026-09-27T22:00:00Z")

    def test_late_forecast_and_invalid_finality_are_rejected(self):
        self.save_forecast({**self.forecast, "generatedAt": "2026-09-27T17:01:00Z"})
        with self.assertRaisesRegex(ValueError, "late forecast"):
            score_store(self.store, "2026-09-27T22:00:00Z")
        self.save_forecast(self.forecast)
        self.save_result({**self.result(), "timingBasis": "unverified"})
        with self.assertRaisesRegex(ValueError, "provenance"):
            score_store(self.store, "2026-09-27T22:00:00Z")


if __name__ == "__main__":
    unittest.main()
