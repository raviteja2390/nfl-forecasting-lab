import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import snapshots


def payload(home_score="20"):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=sorted(snapshots.REQUIRED))
    writer.writeheader()
    writer.writerow({"game_id": "2020_01_BUF_NE", "season": "2020", "game_type": "REG", "week": "1",
                     "gameday": "2020-09-13", "gametime": "13:00", "away_team": "BUF", "home_team": "NE",
                     "away_score": "17" if home_score else "", "home_score": home_score, "location": "Home"})
    return output.getvalue().encode()


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Path(self.directory.name)

    def save(self, body=None, minute=0):
        return snapshots.store_capture(self.store, body or payload(),
                                       f"2020-09-14T12:{minute:02d}:00Z", f"2020-09-14T12:{minute:02d}:01Z",
                                       {"status": 200, "finalUrl": snapshots.SOURCE_URL, "etag": "fixture"})

    def test_identical_downloads_deduplicate_bytes_but_preserve_receipts(self):
        first, second = self.save(), self.save(minute=10)
        self.assertNotEqual(first["observationId"], second["observationId"])
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(len(list((self.store / "blobs").glob("*.csv"))), 1)
        self.assertEqual(snapshots.verify_archive(self.store)["observations"], 2)

    def test_as_of_uses_older_version_and_never_future_correction(self):
        old = self.save()
        new = self.save(payload("21"), minute=10)
        selected = snapshots.select_as_of(self.store, "2020-09-14T12:05:00Z")
        self.assertEqual(selected["observation"]["sha256"], old["sha256"])
        self.assertEqual(snapshots.select_as_of(self.store, "2020-09-14T12:10:01Z")["observation"]["sha256"], new["sha256"])
        self.assertEqual(snapshots.verified_body(self.store, old), payload())
        self.assertEqual(len(list((self.store / "blobs").glob("*.csv"))), 2)

    def test_missing_and_stale_history_do_not_fall_back_to_current(self):
        self.save()
        self.assertFalse(snapshots.select_as_of(self.store, "2019-01-01T00:00:00Z")["found"])
        result = snapshots.select_as_of(self.store, "2020-09-16T12:00:00Z")
        self.assertFalse(result["found"])
        self.assertIn("too old", result["reason"])

    def test_detects_corrupted_payload_and_invalid_metadata(self):
        row = self.save()
        blob = self.store / "blobs" / f'{row["sha256"]}.csv'
        blob.write_bytes(payload("99"))
        with self.assertRaisesRegex(ValueError, "checksum"):
            snapshots.select_as_of(self.store, "2020-09-14T12:05:00Z")
        manifest = self.store / "observations" / f'{row["observationId"]}.json'
        row["sha256"] = "../../outside"
        manifest.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "Malformed"):
            snapshots.read_observations(self.store)

    def test_rejects_bad_feeds_without_creating_observations(self):
        for body in (b"<html>error</html>", b"", payload() + payload().split(b"\r\n")[1] + b"\r\n"):
            with self.assertRaises(ValueError):
                self.save(body=body if body else b"bad")
        self.assertFalse((self.store / "observations").exists())

    def test_allows_pending_scores_without_claiming_finality(self):
        row = self.save(payload(""))
        self.assertEqual(row["validation"]["rows"], 1)
        self.assertIsNone(row["providerPublishedAt"])
        self.assertNotIn("final", row)

    def test_rejects_inconsistent_clocks_and_timezone_free_cutoffs(self):
        with self.assertRaisesRegex(ValueError, "clock"):
            snapshots.store_capture(self.store, payload(), "2020-01-02T00:00:00Z", "2020-01-01T00:00:00Z",
                                    {"status": 200, "finalUrl": snapshots.SOURCE_URL})
        with self.assertRaisesRegex(ValueError, "timezone"):
            snapshots.select_as_of(self.store, "2020-01-01T00:00:00")

    def test_immutable_write_will_not_replace_different_content(self):
        path = self.store / "record"
        snapshots.immutable_write(path, b"first")
        snapshots.immutable_write(path, b"first")
        with self.assertRaisesRegex(ValueError, "replace"):
            snapshots.immutable_write(path, b"second")
        self.assertEqual(path.read_bytes(), b"first")

    def test_cadence_uses_eastern_day_not_utc_day(self):
        sunday = snapshots.cadence_for_body(payload(), "2020-09-14T02:00:00Z")
        monday = snapshots.cadence_for_body(payload(), "2020-09-14T05:00:00Z")
        self.assertEqual(sunday["localDate"], "2020-09-13")
        self.assertEqual(sunday["cadence"], "hourly")
        self.assertEqual(monday["cadence"], "daily")

    def test_cadence_follows_games_on_saturday_instead_of_fixed_weekdays(self):
        saturday = payload().replace(b"2020-09-13", b"2020-09-12")
        self.assertEqual(snapshots.cadence_for_body(saturday, "2020-09-12T15:00:00Z")["cadence"], "hourly")
        self.assertEqual(snapshots.cadence_for_body(saturday, "2020-09-13T15:00:00Z")["cadence"], "daily")

    def test_schedule_requires_fresh_observed_archive(self):
        self.save()
        with self.assertRaisesRegex(ValueError, "fresh observed"):
            snapshots.schedule_decision(self.store, "2020-09-16T15:00:00Z")


if __name__ == "__main__":
    unittest.main()
