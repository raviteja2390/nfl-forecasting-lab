"""Issue immutable pregame forecasts and settle them from observed final scores."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path

import build_features as features
import feeds
import model
import snapshots

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "live"
MODEL_PATH = ROOT / "runs/outcome-logit-v1/model.json"
ESPN_ALIASES = {"WSH": "WAS", "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL", "HST": "HOU", "CLV": "CLE"}


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def canonical(code):
    return features.team_id(ESPN_ALIASES.get(code, code))


def parse_games(body):
    games, seen = [], set()
    for row in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
        season = int(row["season"])
        if season < 2014 or row["game_type"] != "REG":
            continue
        event_id = row["game_id"]
        if event_id in seen:
            raise ValueError("Duplicate schedule event")
        seen.add(event_id)
        week = int(row["week"])
        if event_id != f'{season}_{week:02d}_{row["away_team"]}_{row["home_team"]}':
            raise ValueError("Schedule event ID mismatch")
        local = datetime.strptime(row["gameday"] + " " + row["gametime"], "%Y-%m-%d %H:%M").replace(tzinfo=features.EASTERN)
        kickoff = local.astimezone(features.UTC)
        if row["location"] not in ("Home", "Neutral"):
            raise ValueError("Unknown venue classification")
        scores = [row[side + "_score"] for side in ("home", "away")]
        if any(s not in ("", "NA") and not s.isdigit() for s in scores):
            raise ValueError("Invalid source scores")
        missing = [s in ("", "NA") for s in scores]
        if missing[0] != missing[1]:
            raise ValueError("Incomplete score pair")
        games.append({"eventId": event_id, "season": season, "week": week, "kickoff": kickoff,
                      "localDate": local.date(), "assumedAvailableAt": kickoff + timedelta(hours=48),
                      "homeTeamId": canonical(row["home_team"]), "awayTeamId": canonical(row["away_team"]),
                      "sourceHomeTeam": row["home_team"], "sourceAwayTeam": row["away_team"],
                      "neutral": row["location"] == "Neutral",
                      "homeScore": None if any(missing) else int(scores[0]),
                      "awayScore": None if any(missing) else int(scores[1])})
    return sorted(games, key=lambda game: (game["kickoff"], game["eventId"]))


def espn_games(body):
    result = {}
    for event in json.loads(body)["events"]:
        competition = event["competitions"][0]
        teams = {row["homeAway"]: row for row in competition["competitors"]}
        if set(teams) != {"home", "away"}:
            raise ValueError("Invalid scoreboard competitors")
        kickoff = snapshots.parse_time(event["date"])
        key = (kickoff.astimezone(features.EASTERN).date().isoformat(),
               canonical(teams["away"]["team"]["abbreviation"]), canonical(teams["home"]["team"]["abbreviation"]))
        if key in result:
            raise ValueError("Duplicate scoreboard matchup")
        status = event["status"]["type"]
        final = status["completed"] is True and status["state"] == "post"
        result[key] = {"sourceEventId": event["id"], "kickoff": kickoff, "final": final,
                       "state": status["state"], "neutral": competition.get("neutralSite"),
                       "homeScore": int(teams["home"]["score"]) if final else None,
                       "awayScore": int(teams["away"]["score"]) if final else None}
    return result


def game_key(game):
    return (game["localDate"].isoformat(), game["awayTeamId"], game["homeTeamId"])


def feature_row(game, games, cutoff):
    if cutoff >= game["kickoff"]:
        raise ValueError("Features must be captured before kickoff")
    prior = [g for g in games if g["kickoff"] < cutoff and g["homeScore"] is not None]
    values, evidence = {"homeField": int(not game["neutral"])}, {}
    for side in ("home", "away"):
        team = game[side + "TeamId"]
        history = [g for g in prior if team in (g["homeTeamId"], g["awayTeamId"])]
        side_values, proof = features.team_features(history, game, team, cutoff)
        values.update({side + key: value for key, value in side_values.items()})
        evidence[side] = proof
    model.feature_vector(values, features.FEATURE_NAMES)
    if values["homeRecentGames"] != 8 or values["awayRecentGames"] != 8:
        raise ValueError("Insufficient eight-game team history")
    return {"eventId": game["eventId"], "season": game["season"], "week": game["week"],
            "kickoffAt": features.iso(game["kickoff"]), "featureCutoffAt": features.iso(cutoff),
            "homeTeamId": game["homeTeamId"], "awayTeamId": game["awayTeamId"],
            "sourceHomeTeam": game["sourceHomeTeam"], "sourceAwayTeam": game["sourceAwayTeam"],
            "features": values, "evidence": evidence}


def current_games(at):
    selected = snapshots.select_as_of(snapshots.DEFAULT_STORE, at, max_age_hours=24)
    if not selected["found"]:
        raise ValueError("A fresh observed nflverse snapshot is required")
    return selected["observation"], parse_games(snapshots.verified_body(snapshots.DEFAULT_STORE, selected["observation"]))


def required_dates(date, at):
    _, games = current_games(at)
    by_id = {game["eventId"]: game for game in games}
    targets = [game for game in games if game["localDate"].isoformat() == date]
    dates = {date.replace("-", "")}
    cutoff = snapshots.parse_time(at)
    for game in targets:
        if cutoff > game["kickoff"] - timedelta(hours=24):
            continue
        row = feature_row(game, games, cutoff)
        for side in ("home", "away"):
            for event_id in row["evidence"][side]["resultGameIds"]:
                dates.add(by_id[event_id]["localDate"].strftime("%Y%m%d"))
    return sorted(dates)


def verify_inputs(targets, rows, games, at):
    by_id = {game["eventId"]: game for game in games}
    boards, observations = {}, {}
    dates = {game["localDate"].strftime("%Y%m%d") for game in targets}
    for row in rows:
        for side in ("home", "away"):
            dates.update(by_id[event]["localDate"].strftime("%Y%m%d") for event in row["evidence"][side]["resultGameIds"])
    for date in dates:
        receipt, body = feeds.latest("scoreboard", date, at=at, max_age_hours=24)
        boards.update(espn_games(body))
        observations[date] = {key: receipt[key] for key in ("id", "sourceUrl", "observedAt", "sha256")}
    for game in targets:
        other = boards.get(game_key(game))
        if not other or other["kickoff"] != game["kickoff"] or other["state"] != "pre":
            raise ValueError(f'{game["eventId"]}: schedule mismatch, absent, or already started')
        if other["neutral"] is not None and other["neutral"] != game["neutral"]:
            raise ValueError(f'{game["eventId"]}: venue classification mismatch')
    for row in rows:
        for side in ("home", "away"):
            for event_id in row["evidence"][side]["resultGameIds"]:
                game = by_id[event_id]
                other = boards.get(game_key(game))
                if not other or not other["final"] or any(other[key] != game[key] for key in ("homeScore", "awayScore")):
                    raise ValueError(f"{event_id}: prior result not independently confirmed final with matching scores")
    return observations


def publish(date, store=LIVE):
    issued_at = snapshots.now()
    at = snapshots.parse_time(issued_at)
    observation, games = current_games(issued_at)
    targets = [game for game in games if game["localDate"].isoformat() == date]
    if not targets:
        raise ValueError("No NFL regular-season games on requested date")
    artifact_bytes = MODEL_PATH.read_bytes()
    manifest = json.loads((MODEL_PATH.parent / "artifacts.json").read_text())
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    if digest != manifest["files"]["model.json"]["sha256"]:
        raise ValueError("Frozen baseline model checksum mismatch")
    artifact = json.loads(artifact_bytes)
    if hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest() != artifact["provenance"]["codeSha256"]["model.py"]:
        raise ValueError("Frozen inference implementation changed")
    existing, new_games, rows = [], [], []
    for game in targets:
        path = store / "forecasts" / artifact["modelVersion"] / f'{game["eventId"]}.json'
        if path.exists():
            saved = json.loads(path.read_text())
            if saved["modelSha256"] != digest:
                raise ValueError("Existing forecast belongs to a different model")
            existing.append(saved)
            continue
        if at > game["kickoff"] - timedelta(hours=24):
            raise ValueError(f'{game["eventId"]}: missed the at-least-24-hour issue deadline; refusing to backdate')
        new_games.append(game)
        rows.append(feature_row(game, games, at))
    receipts = verify_inputs(new_games, rows, games, issued_at) if rows else {}
    probabilities = model.predict_many(artifact, [row["features"] for row in rows])
    generated_at = snapshots.now()
    if any(snapshots.parse_time(generated_at) > game["kickoff"] - timedelta(hours=24) for game in new_games):
        raise ValueError("Forecast generation crossed the issue deadline")
    saved_rows = []
    for game, row, p in zip(new_games, rows, probabilities):
        saved = {"schemaVersion": 1, "mode": "prospective", "modelVersion": artifact["modelVersion"],
                 "modelSha256": digest, "eventId": game["eventId"], "dateEastern": date,
                 "generatedAt": generated_at, "featureCutoffAt": issued_at, "kickoffAt": row["kickoffAt"],
                 "leadHours": (game["kickoff"] - snapshots.parse_time(generated_at)).total_seconds() / 3600,
                 "trainingCompletedAt": artifact["trainedAt"], "homeTeam": game["homeTeamId"], "awayTeam": game["awayTeamId"],
                 "probabilities": p, "baselineProbabilities": artifact["baselineProbabilities"], "featureRow": row,
                 "sourceObservation": {key: observation[key] for key in ("observationId", "observedAt", "sourceUrl", "sha256")},
                 "scoreboardObservations": receipts,
                 "limitations": ["Team-only model; no individual-player or injury adjustment.",
                                 "First issue is at least 24 hours before kickoff; lead times vary.",
                                 "Uses last eight regular-season games, including previous season; coefficients trained through 2022.",
                                 "Prior scores independently confirmed final; a conservative 48-hour lag is also retained."]}
        snapshots.immutable_write(store / "forecasts" / artifact["modelVersion"] / f'{game["eventId"]}.json', encode(saved))
        saved_rows.append(saved)
    records = sorted(existing + saved_rows, key=lambda row: (row["kickoffAt"], row["eventId"]))
    # Human-readable view may be regenerated; canonical forecasts are immutable.
    report_path = store / "reports" / f"{date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(forecast_report(records))
    return {"date": date, "scheduled": len(targets), "issued": len(saved_rows), "existing": len(existing),
            "report": str(report_path.resolve()), "modelVersion": artifact["modelVersion"]}


def forecast_report(records):
    lines = [f'# NFL forecasts — {records[0]["dateEastern"]}', "", "Team-only model; all times Eastern. These are game-outcome probabilities, not betting-profit estimates.", "",
             f'First generated: {min(row["generatedAt"] for row in records)}. The model was frozen before these forecasts; player availability is not included.', ""]
    for row in records:
        kickoff = snapshots.parse_time(row["kickoffAt"]).astimezone(features.EASTERN).strftime("%-I:%M %p")
        p = row["probabilities"]
        lines.append(f'- **{row["awayTeam"]} at {row["homeTeam"]}, {kickoff}:** {row["awayTeam"]} {p["awayWin"]:.1%}; {row["homeTeam"]} {p["homeWin"]:.1%}; tie {p["tie"]:.1%}.')
    lines += ["", "Original predictions remain unchanged if subsequent injury news or lineups change. Results will be joined only after an observed final status and matching scores from the two sources. Different versions must be compared on the same games.", ""]
    return "\n".join(lines)


def settle(date, store=LIVE):
    at = snapshots.now()
    observation, games = current_games(at)
    receipt, body = feeds.latest("scoreboard", date.replace("-", ""), at=at, max_age_hours=24)
    boards = espn_games(body)
    by_id = {game["eventId"]: game for game in games}
    saved, pending, mismatches, seen = 0, [], [], set()
    forecasts = [json.loads(path.read_text()) for path in (store / "forecasts").glob("*/*.json")]
    for forecast in forecasts:
        if forecast["dateEastern"] != date:
            continue
        if forecast["eventId"] in seen:
            continue
        seen.add(forecast["eventId"])
        game = by_id.get(forecast["eventId"])
        other = boards.get(game_key(game)) if game else None
        if not other or not other["final"]:
            pending.append(forecast["eventId"])
            continue
        if game["homeScore"] is None or any(game[key] != other[key] for key in ("homeScore", "awayScore")):
            mismatches.append(forecast["eventId"])
            continue
        finalized_at = max(receipt["observedAt"], observation["observedAt"])
        result = {"eventId": game["eventId"], "homeScore": other["homeScore"], "awayScore": other["awayScore"],
                  "finalizedAt": finalized_at, "timingBasis": "observed-final-in-two-sources",
                  "nflverseObservationId": observation["observationId"], "espnObservationId": receipt["id"]}
        snapshots.immutable_write(store / "results" / game["eventId"] / f'{receipt["id"]}-{observation["observationId"]}.json', encode(result))
        saved += 1
    return {"date": date, "resultsStored": saved, "pending": sorted(set(pending)), "sourceDisagreements": sorted(set(mismatches))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "publish", "settle"))
    parser.add_argument("date", help="Game date in America/New_York, YYYY-MM-DD")
    args = parser.parse_args()
    datetime.strptime(args.date, "%Y-%m-%d")
    if args.command == "prepare":
        dates = required_dates(args.date, snapshots.now())
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda key: feeds.capture("scoreboard", key), dates))
        print(json.dumps({"date": args.date, "scoreboardsCaptured": len(receipts), "dates": dates}, indent=2))
    else:
        print(json.dumps(publish(args.date) if args.command == "publish" else settle(args.date), indent=2))


if __name__ == "__main__":
    main()
