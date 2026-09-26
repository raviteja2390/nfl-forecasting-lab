from collections import defaultdict
import copy
from types import SimpleNamespace
import unittest

from player_features import FIELDS, augment, side_features


class PlayerFeatureTests(unittest.TestCase):
    def setUp(self):
        self.data = SimpleNamespace(stats=defaultdict(list), injuries=defaultdict(list))
        history = [f"2023_{week:02d}_BUF_NE" for week in range(1, 5)]
        self.row = {"season": 2023, "week": 5, "featureCutoffAt": "2023-10-07T17:00:00Z", "homeTeamId": "NE", "awayTeamId": "BUF",
                    "features": {"x": 1}, "evidence": {side: {"resultGameIds": list(history)} for side in ("home", "away")}}
        for game in history:
            for team in ("NE", "BUF"):
                qb = {"id": team + "qb", "name": "Prior QB", "position": "QB", **{field: 0.0 for field in FIELDS}}
                qb.update(attempts=30, passing_epa=3, passing_epa_plays=30, carries=4, rushing_epa_plays=4)
                receiver = {"id": team + "wr", "name": "Prior WR", "position": "WR", **{field: 0.0 for field in FIELDS}}
                receiver.update(targets=10, receiving_epa=2, receiving_epa_plays=10)
                self.data.stats[(game, team)] = [qb, receiver]
        self.injury = {"id": "NEwr", "name": "Prior WR", "position": "WR", "status": "Out",
                       "modifiedAt": "2023-10-06T20:00:00Z", "observedAt": "2026-09-26T14:00:00Z"}

    def test_absence_uses_previous_usage_and_eligible_report(self):
        self.data.injuries[(2023, 5, "NE")] = [self.injury]
        values, _ = side_features(self.row, "home", self.data)
        self.assertEqual(values["OutTargetsShare"], 1)
        self.assertEqual(values["InjuryReportObserved"], 1)
        self.assertAlmostEqual(values["PriorQBEPAperDropbackShrunk"], 12 / 220)

    def test_late_or_undated_historical_reports_are_unavailable(self):
        for timestamp in (None, "2023-10-08T13:00:00Z"):
            self.data.injuries[(2023, 5, "NE")] = [{**self.injury, "modifiedAt": timestamp}]
            values, proof = side_features(self.row, "home", self.data)
            self.assertEqual(values["OutTargetsShare"], 0)
            self.assertEqual(values["InjuryReportObserved"], 0)
            self.assertEqual(proof["knownInjuryStatuses"], [])

    def test_live_undated_reports_require_actual_receipt_before_cutoff(self):
        self.data.injuries[(2023, 5, "NE")] = [{**self.injury, "modifiedAt": None, "observedAt": "2023-10-07T16:00:00Z"}]
        self.assertEqual(side_features(self.row, "home", self.data, prospective=True)[0]["OutTargetsShare"], 1)
        self.data.injuries[(2023, 5, "NE")][0]["observedAt"] = "2023-10-07T18:00:00Z"
        self.assertEqual(side_features(self.row, "home", self.data, prospective=True)[0]["InjuryReportObserved"], 0)

    def test_current_and_future_player_stats_cannot_change_inputs(self):
        before = augment(self.row, self.data, "player-form-and-available-injuries")[0]
        self.data.stats[("2023_05_BUF_NE", "NE")] = [{"passing_epa": 999}]
        self.data.stats[("2023_06_BUF_NE", "NE")] = [{"passing_epa": -999}]
        self.assertEqual(augment(self.row, self.data, "player-form-and-available-injuries")[0], before)
        self.row["evidence"]["home"]["resultGameIds"][-1] = "2023_05_BUF_NE"
        with self.assertRaisesRegex(ValueError, "Same-week"):
            side_features(self.row, "home", self.data)

    def test_performance_only_model_ignores_all_injury_statuses(self):
        before = augment(self.row, self.data, "player-form")[0]
        self.data.injuries[(2023, 5, "NE")] = [self.injury]
        self.assertEqual(augment(self.row, self.data, "player-form")[0], before)

    def test_missing_prior_game_stats_fail_instead_of_imputing_roster(self):
        del self.data.stats[("2023_03_BUF_NE", "NE")]
        with self.assertRaisesRegex(ValueError, "Missing player"):
            side_features(self.row, "home", self.data)

    def test_prior_passing_role_does_not_depend_on_season_position_label(self):
        for players in self.data.stats.values():
            players[0]["position"] = "TE"
        values, proof = side_features(self.row, "home", self.data)
        self.assertEqual(values["PriorQBDropbacks"], 120)
        self.assertEqual(proof["priorQB"]["id"], "NEqb")


if __name__ == "__main__":
    unittest.main()
