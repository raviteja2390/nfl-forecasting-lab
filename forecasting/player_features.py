"""Past player production and time-eligible injury-report features."""
from collections import defaultdict
import csv
import io
import math

import feeds
import live
import snapshots

FORM = ["PriorQBEPAperDropbackShrunk", "PriorQBDropbacks", "PriorQBChanged", "PriorQBEPACoverage",
        "TopReceiverTargetShare", "TopReceiverEPAperTargetShrunk", "TopReceiverEPACoverage",
        "TopRusherCarryShare", "TopRusherEPAperCarryShrunk", "TopRusherEPACoverage"]
AVAILABILITY = ["InjuryReportObserved"] + [f"{status}{usage}Share" for status in ("Out", "Doubtful", "Questionable")
                                            for usage in ("Passing", "Targets", "Carries")] + ["OutOLCount", "OutDefenseCount"]
OFFENSE = {"QB", "RB", "FB", "WR", "TE"}
OL = {"C", "G", "T", "OT", "OG", "OL"}
DEFENSE = {"DE", "DT", "NT", "DL", "LB", "ILB", "OLB", "CB", "DB", "S", "FS", "SS"}
RAW_FIELDS = ("attempts", "sacks_suffered", "passing_epa", "targets", "receiving_epa", "carries", "rushing_epa")
FIELDS = RAW_FIELDS + ("passing_epa_plays", "receiving_epa_plays", "rushing_epa_plays")


def numeric(value):
    # Blank EPAs on rows with zero relevant plays represent no accumulated EPA.
    result = 0.0 if value in (None, "", "NA") else float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite player statistic")
    return result


class PlayerData:
    def __init__(self, seasons, at=None):
        self.stats = defaultdict(list)
        self.injuries = defaultdict(list)
        self.receipts = []
        self.audit = {}
        for season in seasons:
            receipt, body = feeds.latest("stats", season, at=at)
            self.receipts.append(receipt)
            seen = set()
            for row in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
                if row["season_type"] != "REG":
                    continue
                if int(row["season"]) != season:
                    raise ValueError("Player-stat season mismatch")
                key = (row["game_id"], live.canonical(row["team"]), row["player_id"])
                if key in seen:
                    raise ValueError("Duplicate player/game/team stat row")
                seen.add(key)
                reduced = {"id": row["player_id"], "name": row["player_display_name"], "position": row["position"],
                           **{field: numeric(row.get(field)) for field in RAW_FIELDS}}
                for plays, epa in (("attempts", "passing_epa"), ("targets", "receiving_epa"), ("carries", "rushing_epa")):
                    # Exclude unknown EPA from both its sum and denominator,
                    # retaining a coverage feature so unknown never means zero quality.
                    count = reduced[plays] + (reduced["sacks_suffered"] if plays == "attempts" else 0)
                    reduced[epa + "_plays"] = count if row.get(epa) not in (None, "", "NA") else 0.0
                self.stats[key[:2]].append(reduced)
            receipt, body = feeds.latest("injuries", season, at=at)
            self.receipts.append(receipt)
            rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
            self.audit[str(season)] = {"injuryRows": len(rows), "injuryRowsWithUpdateTimestamp": sum(bool(r.get("date_modified")) for r in rows)}
            for row in rows:
                if row.get("game_type", row.get("season_type")) != "REG":
                    continue
                self.injuries[(season, int(row["week"]), live.canonical(row["team"]))].append({
                    "id": row["gsis_id"], "name": row["full_name"], "position": row["position"],
                    "status": row["report_status"], "modifiedAt": row.get("date_modified"), "observedAt": receipt["observedAt"]})


def aggregate_player(rows):
    values = {}
    for row in rows:
        item = values.setdefault(row["id"], {"id": row["id"], "name": row["name"], "position": row["position"],
                                            **{field: 0.0 for field in FIELDS}})
        for field in FIELDS:
            item[field] += row[field]
    return values


def side_features(row, side, data, prospective=False):
    team = row[side + "TeamId"]
    history = row["evidence"][side]["resultGameIds"][-4:]
    if len(history) < 4:
        raise ValueError("Four prior team games are required for player features")
    prior = []
    qbs = []
    for event in history:
        # The supplied team feature evidence already applies the time/week filter.
        season, week = map(int, event.split("_")[:2])
        if (season, week) >= (row["season"], row["week"]):
            raise ValueError("Same-week or future game in player history")
        players = data.stats[(event, team)]
        if not players:
            raise ValueError(f"Missing player statistics for {event}/{team}")
        prior.extend(players)
        # Infer the earlier game's passing role from attempts. A season-level
        # position label can list a versatile player as TE/WR even when he played QB.
        passers = [p for p in players if p["attempts"] > 0]
        if not passers:
            raise ValueError(f"No prior quarterback with recorded attempts for {event}/{team}")
        qbs.append(max(passers, key=lambda p: (p["attempts"], p["id"]))["id"])
    totals = aggregate_player(prior)
    qb = totals[qbs[-1]]
    receivers = [p for p in totals.values() if p["targets"] > 0]
    rushers = [p for p in totals.values() if p["carries"] > 0]
    receiver = max(receivers, key=lambda p: (p["targets"], p["id"]))
    rusher = max(rushers, key=lambda p: (p["carries"], p["id"]))
    sums = {field: sum(p[field] for p in totals.values()) for field in ("attempts", "targets", "carries")}
    dropbacks = qb["attempts"] + qb["sacks_suffered"]
    values = dict(zip(FORM, [qb["passing_epa"] / (100 + qb["passing_epa_plays"]), dropbacks, int(qbs[-1] != qbs[-2]),
                             qb["passing_epa_plays"] / max(1, dropbacks),
                             receiver["targets"] / max(1, sums["targets"]), receiver["receiving_epa"] / (25 + receiver["receiving_epa_plays"]),
                             receiver["receiving_epa_plays"] / max(1, receiver["targets"]),
                             rusher["carries"] / max(1, sums["carries"]), rusher["rushing_epa"] / (25 + rusher["rushing_epa_plays"]),
                             rusher["rushing_epa_plays"] / max(1, rusher["carries"])]))
    cutoff = snapshots.parse_time(row["featureCutoffAt"])
    known = {}
    for injury in data.injuries[(row["season"], row["week"], team)]:
        # Undated historic rows cannot be used. For genuine live forecasts our
        # receipt time establishes when we had the whole report in hand.
        available = injury["observedAt"] if prospective else injury["modifiedAt"]
        if not available or snapshots.parse_time(available) > cutoff:
            continue
        key = injury["id"] or injury["name"]
        previous = known.get(key)
        if previous is None or (available, injury["status"]) > (previous[0], previous[1]["status"]):
            known[key] = (available, injury)
    injuries = [value[1] for value in known.values()]
    values["InjuryReportObserved"] = int(bool(injuries))
    for status in ("Out", "Doubtful", "Questionable"):
        for usage, field in (("Passing", "attempts"), ("Targets", "targets"), ("Carries", "carries")):
            loss = sum(totals.get(p["id"], {}).get(field, 0) for p in injuries if p["status"] == status)
            values[status + usage + "Share"] = loss / max(1, sums[field])
    values["OutOLCount"] = sum(p["status"] == "Out" and p["position"] in OL for p in injuries)
    values["OutDefenseCount"] = sum(p["status"] == "Out" and p["position"] in DEFENSE for p in injuries)
    proof = {"team": team, "priorGameIds": history,
             "priorQB": {key: qb[key] for key in ("id", "name", "position")},
             "topReceiver": {key: receiver[key] for key in ("id", "name", "position")},
             "topRusher": {key: rusher[key] for key in ("id", "name", "position")},
             "injuryTimingBasis": "observed-receipt" if prospective else "reported-date-modified-proxy",
             "knownInjuryStatuses": [{key: p[key] for key in ("id", "name", "position", "status")} for p in injuries if p["status"]],
             "limitations": ["Prior quarterback is inferred from earlier attempts, not a confirmed upcoming starter.",
                             "No eligible injury rows means unavailable evidence, not a healthy roster.",
                             "Usage shares and grouped absence counts are predictive features, not causal player values."]}
    return values, proof


def augment(row, data, family, prospective=False):
    if family not in ("player-form", "player-form-and-available-injuries"):
        raise ValueError("Unknown player feature family")
    names = FORM + (AVAILABILITY if family.endswith("injuries") else [])
    values = dict(row["features"])
    evidence = {}
    for side in ("home", "away"):
        extra, proof = side_features(row, side, data, prospective)
        values.update({side + name: extra[name] for name in names})
        evidence[side] = proof
    return values, evidence
