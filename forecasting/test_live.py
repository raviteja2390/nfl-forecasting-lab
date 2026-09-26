import copy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import feeds
import live
import snapshots


class LiveTests(unittest.TestCase):
    def test_live_features_match_historical_builder_without_current_outcomes(self):
        games = live.parse_games((live.ROOT / "data/raw/nflverse-games.csv").read_bytes())
        by_id = {g["eventId"]: g for g in games}
        rows = [json.loads(line) for line in (live.ROOT / "data/processed/v1/validation.features.jsonl").read_text().splitlines()]
        for row in rows:
            cutoff = snapshots.parse_time(row["featureCutoffAt"])
            current = live.feature_row(by_id[row["eventId"]], games, cutoff)
            self.assertEqual(current["features"], row["features"])
        changed = copy.deepcopy(games)
        target = by_id[rows[0]["eventId"]]
        for game in changed:
            if game["kickoff"] >= target["kickoff"]:
                game["homeScore"], game["awayScore"] = 99, 0
        self.assertEqual(live.feature_row(target, changed, target["kickoff"] - timedelta(hours=24))["features"], rows[0]["features"])

    def test_scoreboard_does_not_treat_live_scores_as_final(self):
        payload = {"events": [{"id": "1", "date": "2026-09-27T17:00Z",
                              "status": {"type": {"state": "in", "completed": False}},
                              "competitions": [{"neutralSite": False, "competitors": [
                                  {"homeAway": "home", "score": "20", "team": {"abbreviation": "WSH"}},
                                  {"homeAway": "away", "score": "7", "team": {"abbreviation": "SEA"}}]}]}]}
        row = next(iter(live.espn_games(json.dumps(payload).encode()).values()))
        self.assertFalse(row["final"])
        self.assertIsNone(row["homeScore"])
        payload["events"][0]["status"]["type"] = {"state": "post", "completed": True}
        row = next(iter(live.espn_games(json.dumps(payload).encode()).values()))
        self.assertTrue(row["final"])
        self.assertEqual(row["homeScore"], 20)

    def test_no_forecast_backdating_after_deadline(self):
        games = live.parse_games((live.ROOT / "data/raw/nflverse-games.csv").read_bytes())
        with tempfile.TemporaryDirectory() as directory, patch.object(live, "current_games", return_value=({}, games)):
            with self.assertRaisesRegex(ValueError, "deadline"):
                live.publish("2023-09-10", Path(directory))

    def test_feed_urls_cannot_request_unrelated_endpoints(self):
        for kind, key in (("scoreboard", "../../secret"), ("stats", "2026?secret"), ("custom", "2026")):
            with self.assertRaises(ValueError):
                feeds.source_url(kind, key)

    def test_feed_replay_rejects_future_stale_and_corrupt_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            body = b'{"events": []}'
            import hashlib
            digest = hashlib.sha256(body).hexdigest()
            metadata = {"kind": "scoreboard", "key": "20260927", "id": "a" * 32,
                        "sourceUrl": feeds.source_url("scoreboard", "20260927"), "sha256": digest, "bytes": len(body),
                        "requestStartedAt": "2026-09-26T13:00:00Z", "observedAt": "2026-09-26T13:00:01Z",
                        "storedAt": "2026-09-26T13:00:02Z"}
            snapshots.immutable_write(store / "blobs" / digest, body)
            snapshots.immutable_write(store / "observations/one.json", live.encode(metadata))
            with self.assertRaisesRegex(ValueError, "No observed"):
                feeds.latest("scoreboard", "20260927", at="2026-09-26T12:00:00Z", store=store)
            with self.assertRaisesRegex(ValueError, "Stale"):
                feeds.latest("scoreboard", "20260927", at="2026-09-28T12:00:00Z", max_age_hours=24, store=store)
            (store / "blobs" / digest).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "checksum"):
                feeds.latest("scoreboard", "20260927", at="2026-09-26T14:00:00Z", store=store)


if __name__ == "__main__":
    unittest.main()
