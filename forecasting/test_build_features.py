import copy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("build_features", Path(__file__).with_name("build_features.py"))
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


def game(season=2015, week=1, day="2015-09-10", time="20:30", home="NE", away="PIT", hs="28", aws="21", location="Home"):
    return {"game_id": f"{season}_{week:02d}_{away}_{home}", "season": str(season), "game_type": "REG", "week": str(week),
            "gameday": day, "gametime": time, "home_team": home, "away_team": away,
            "home_score": hs, "away_score": aws, "location": location}


class FeaturesTest(unittest.TestCase):
    def test_eastern_timezone_handles_summer_winter_and_january_season(self):
        rows = [game(), game(2015, 17, "2016-01-03", "13:00")]
        games = pipeline.normalize(rows)
        self.assertEqual(pipeline.iso(games[0]["kickoff"]), "2015-09-11T00:30:00Z")
        self.assertEqual(pipeline.iso(games[1]["kickoff"]), "2016-01-03T18:00:00Z")
        self.assertEqual(games[1]["season"], 2015)

    def test_current_and_future_targets_cannot_change_current_features(self):
        rows = [game(), game(2015, 2, "2015-09-20", "13:00", "BUF", "NE"), game(2015, 3, "2015-09-27", "13:00", "NE", "JAX")]
        first = pipeline.build_records(pipeline.normalize(rows))["train"]
        changed = copy.deepcopy(rows)
        changed[1]["home_score"] = "99"
        changed[2]["away_score"] = "77"
        second = pipeline.build_records(pipeline.normalize(changed))["train"]
        self.assertEqual(first["features"][:2], second["features"][:2])
        self.assertNotEqual(first["labels"][1], second["labels"][1])
        self.assertNotEqual(first["features"][2], second["features"][2])

    def test_result_availability_cutoff_is_inclusive_and_not_kickoff_only(self):
        rows = [game(2015, 1, "2015-09-14", "20:30"), game(2015, 2, "2015-09-17", "20:30", "NE", "BUF")]
        data = pipeline.build_records(pipeline.normalize(rows))["train"]["features"][-1]
        self.assertEqual(data["features"]["homeRecentGames"], 1)
        rows[0]["gametime"] = "20:31"
        data = pipeline.build_records(pipeline.normalize(rows))["train"]["features"][-1]
        self.assertEqual(data["features"]["homeRecentGames"], 0)
        self.assertIsNone(data["features"]["homePointsForMean"])
        self.assertEqual(data["features"]["homeDaysSincePriorGameCapped30"], 3)

    def test_same_week_is_excluded_and_tie_counts_half_a_result(self):
        rows = [game(hs="20", aws="20"), game(2015, 1, "2015-09-14", "20:30", "BUF", "NE"), game(2015, 2, "2015-09-20", "13:00", "PIT", "NE")]
        data = pipeline.build_records(pipeline.normalize(rows))["train"]
        self.assertEqual(data["features"][1]["features"]["awayRecentGames"], 0)
        self.assertEqual(data["features"][2]["features"]["homeResultRate"], 0.5)
        self.assertEqual(data["labels"][0]["outcome"], "tie")

    def test_relocation_aliases_neutral_site_and_cross_season_history(self):
        rows = [game(2014, 17, "2014-12-28", "13:00", "STL", "SD"), game(2015, 1, "2015-09-13", "13:00", "LA", "LAC", location="Neutral")]
        record = pipeline.build_records(pipeline.normalize(rows))["train"]["features"][0]
        self.assertEqual(record["homeTeamId"], "LAR")
        self.assertEqual(record["awayTeamId"], "LAC")
        self.assertEqual(record["features"]["homeField"], 0)
        self.assertEqual(record["features"]["homeRecentGames"], 1)
        self.assertEqual(record["features"]["homeDaysSincePriorGameCapped30"], 30)
        self.assertEqual(pipeline.team_id("OAK"), "LV")

    def test_window_uses_only_last_eight_eligible_games(self):
        rows = [game(2015, i + 1, f"2015-{9 if i < 4 else 10:02d}-{(i % 4) * 7 + 1:02d}", "13:00", hs=str(i + 1), aws="0") for i in range(8)]
        rows += [game(2015, 9, "2015-11-01", "13:00", hs="9", aws="0"), game(2015, 10, "2015-11-08", "13:00")]
        record = pipeline.build_records(pipeline.normalize(rows))["train"]["features"][-1]
        self.assertEqual(record["features"]["homeRecentGames"], 8)
        self.assertEqual(record["features"]["homePointsForMean"], 5.5)

    def test_splits_and_empty_features_have_no_fabricated_values(self):
        self.assertIsNone(pipeline.split_for(2014))
        self.assertEqual(pipeline.split_for(2022), "train")
        self.assertEqual(pipeline.split_for(2023), "validation")
        self.assertEqual(pipeline.split_for(2025), "test")
        record = pipeline.build_records(pipeline.normalize([game()]))["train"]["features"][0]
        self.assertIsNone(record["features"]["homePointsForMean"])
        self.assertNotIn("homeScore", record)
        self.assertEqual(set(record["features"]), set(pipeline.FEATURE_NAMES))

    def test_rejects_duplicates_missing_scores_unknown_teams_and_venue(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            pipeline.normalize([game(), game()])
        for patch in ({"home_score": ""}, {"away_score": "-1"}, {"gametime": ""}, {"home_team": "XXX"}, {"location": "Unknown"}, {"total": "999"}):
            row = game()
            row.update(patch)
            with self.assertRaises(ValueError):
                pipeline.normalize([row])

    def test_order_independence(self):
        rows = [game(), game(2015, 2, "2015-09-20", "13:00", "BUF", "NE")]
        self.assertEqual(pipeline.build_records(pipeline.normalize(rows)), pipeline.build_records(pipeline.normalize(list(reversed(rows)))))


if __name__ == "__main__":
    unittest.main()
