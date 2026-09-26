"""Build retrospective NFL game features; standard library only, Python >=3.9."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
SOURCE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
WINDOW = 8
FORECAST_LEAD_HOURS = 24
RESULT_LAG_HOURS = 48
ALIASES = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"}
TEAMS = set("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAR LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split())
REQUIRED = {"game_id", "season", "game_type", "week", "gameday", "gametime", "away_team", "home_team", "away_score", "home_score", "location"}
FEATURE_NAMES = ["homeField"] + [
    f"{side}{name}" for side in ("home", "away") for name in (
        "RecentGames", "PointsForMean", "PointsAgainstMean", "ResultRate", "DaysSincePriorGameCapped30"
    )
]


def iso(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def whole(value, name, minimum=0):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: expected an integer") from exc
    if str(number) != str(value).strip() or number < minimum:
        raise ValueError(f"{name}: invalid integer")
    return number


def team_id(code):
    canonical = ALIASES.get(code, code)
    if canonical not in TEAMS:
        raise ValueError(f"Unknown team code: {code}")
    return canonical


def validate_lag(hours):
    if type(hours) is not int or not 1 <= hours <= 168:
        raise ValueError("Result availability lag must be an integer from 1 to 168 hours")
    return hours


def normalize(rows, result_lag_hours=RESULT_LAG_HOURS):
    """Keep 2014 warm-up and 2015–2025 regular seasons. Never fill missing scores."""
    validate_lag(result_lag_hours)
    games, ids = [], set()
    for row in rows:
        if not REQUIRED.issubset(row):
            raise ValueError("Source is missing required schedule columns")
        season = whole(row["season"], "season", 1999)
        if not 2014 <= season <= 2025 or row["game_type"] != "REG":
            continue
        event_id = row["game_id"]
        if event_id in ids:
            raise ValueError(f"Duplicate event ID: {event_id}")
        ids.add(event_id)
        week = whole(row["week"], f"{event_id} week", 1)
        if week > (18 if season >= 2021 else 17):
            raise ValueError(f"{event_id}: invalid regular-season week")
        expected_id = f'{season}_{week:02d}_{row["away_team"]}_{row["home_team"]}'
        if event_id != expected_id:
            raise ValueError(f"{event_id}: game ID disagrees with source fields")
        local_text = f'{row["gameday"]} {row["gametime"]}'
        try:
            local = datetime.strptime(local_text, "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
        except ValueError as exc:
            raise ValueError(f"{event_id}: missing or invalid kickoff") from exc
        if local.strftime("%Y-%m-%d %H:%M") != local_text:
            raise ValueError(f"{event_id}: kickoff must use YYYY-MM-DD HH:MM")
        if not ((local.year == season and local.month >= 9) or (local.year == season + 1 and local.month == 1)):
            raise ValueError(f"{event_id}: date is inconsistent with NFL season")
        home, away = team_id(row["home_team"]), team_id(row["away_team"])
        if home == away:
            raise ValueError(f"{event_id}: a team cannot play itself")
        if row["location"] not in ("Home", "Neutral"):
            raise ValueError(f"{event_id}: unknown venue classification")
        hs = whole(row["home_score"], f"{event_id} home score")
        aws = whole(row["away_score"], f"{event_id} away score")
        for column, expected in (("total", hs + aws), ("result", hs - aws)):
            if row.get(column) not in (None, ""):
                try:
                    matches = int(row[column]) == expected
                except ValueError:
                    matches = False
                if not matches:
                    raise ValueError(f"{event_id}: {column} disagrees with scores")
        kickoff = local.astimezone(UTC)
        games.append({
            "eventId": event_id, "season": season, "week": week,
            "kickoff": kickoff, "localDate": local.date(),
            "assumedAvailableAt": kickoff + timedelta(hours=result_lag_hours),
            "homeTeamId": home, "awayTeamId": away,
            "sourceHomeTeam": row["home_team"], "sourceAwayTeam": row["away_team"],
            "neutral": row["location"] == "Neutral", "homeScore": hs, "awayScore": aws,
        })
    return sorted(games, key=lambda game: (game["kickoff"], game["eventId"]))


def split_for(season):
    if 2015 <= season <= 2022:
        return "train"
    if season == 2023:
        return "validation"
    if season in (2024, 2025):
        return "test"
    return None


def team_features(prior, game, team, cutoff):
    # Same-week outcomes are excluded even if already available at the cutoff.
    eligible = [old for old in prior if old["assumedAvailableAt"] <= cutoff
                and (old["season"], old["week"]) < (game["season"], game["week"])]
    recent = eligible[-WINDOW:]
    points_for, points_against, outcomes = [], [], []
    for old in recent:
        pf, pa = (old["homeScore"], old["awayScore"]) if old["homeTeamId"] == team else (old["awayScore"], old["homeScore"])
        points_for.append(pf)
        points_against.append(pa)
        outcomes.append(1 if pf > pa else 0.5 if pf == pa else 0)
    # Rest uses previous scheduled kickoff only, not that game's result.
    played = [old for old in prior if old["kickoff"] < cutoff]
    last = played[-1] if played else None
    count = len(recent)
    values = {
        "RecentGames": count,
        "PointsForMean": sum(points_for) / count if count else None,
        "PointsAgainstMean": sum(points_against) / count if count else None,
        "ResultRate": sum(outcomes) / count if count else None,
        "DaysSincePriorGameCapped30": min(30, (game["localDate"] - last["localDate"]).days) if last else None,
    }
    evidence = {
        "resultGameIds": [old["eventId"] for old in recent],
        "latestAssumedResultAvailability": iso(recent[-1]["assumedAvailableAt"]) if recent else None,
        "priorGameForRest": last["eventId"] if last else None,
    }
    return values, evidence


def build_records(games):
    history = defaultdict(list)
    output = {name: {"features": [], "labels": []} for name in ("train", "validation", "test")}
    for game in sorted(games, key=lambda item: (item["kickoff"], item["eventId"])):
        split = split_for(game["season"])
        if split:
            cutoff = game["kickoff"] - timedelta(hours=FORECAST_LEAD_HOURS)
            features, evidence = {"homeField": int(not game["neutral"])}, {}
            for side in ("home", "away"):
                team = game[f"{side}TeamId"]
                values, proof = team_features(history[team], game, team, cutoff)
                features.update({side + key: value for key, value in values.items()})
                evidence[side] = proof
            output[split]["features"].append({
                "eventId": game["eventId"], "season": game["season"], "week": game["week"],
                "kickoffAt": iso(game["kickoff"]), "featureCutoffAt": iso(cutoff),
                "homeTeamId": game["homeTeamId"], "awayTeamId": game["awayTeamId"],
                "sourceHomeTeam": game["sourceHomeTeam"], "sourceAwayTeam": game["sourceAwayTeam"],
                "features": features, "evidence": evidence,
            })
            hs, aws = game["homeScore"], game["awayScore"]
            output[split]["labels"].append({
                "eventId": game["eventId"], "homeScore": hs, "awayScore": aws,
                "outcome": "tie" if hs == aws else "homeWin" if hs > aws else "awayWin",
            })
        # Update only after constructing this game's features.
        history[game["homeTeamId"]].append(game)
        history[game["awayTeamId"]].append(game)
    return output


def materialize(input_path, provenance_path, output_path, result_lag_hours=RESULT_LAG_HOURS):
    raw = input_path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("sha256") != source_hash:
        raise ValueError("Input checksum does not match the recorded download")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError("Source is missing required columns")
    games = normalize(reader, result_lag_hours)
    seasons = Counter(game["season"] for game in games)
    if set(seasons) != set(range(2014, 2026)):
        raise ValueError("Expected all 2014–2025 seasons, including warm-up")
    records = build_records(games)
    artifacts, splits = {}, {}
    for split, files in records.items():
        feature_rows = files["features"]
        splits[split] = {
            "rows": len(feature_rows),
            "bySeason": dict(sorted(Counter(row["season"] for row in feature_rows).items())),
            "rowsWithMissingFeatures": sum(any(value is None for value in row["features"].values()) for row in feature_rows),
        }
        for kind, values in files.items():
            artifacts[f"{split}.{kind}.jsonl"] = "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in values).encode()
    manifest = {
        "schemaVersion": 1, "pipelineVersion": "game-features-v1",
        "datasetKind": "retrospective-reconstruction",
        "builtAt": iso(datetime.now(UTC)),
        "source": {"url": provenance.get("source", SOURCE_URL), "retrievedAt": provenance["retrievedAt"], "sha256": source_hash},
        "builderSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "featureNames": FEATURE_NAMES,
        "settings": {"recentGames": WINDOW, "forecastLeadHours": FORECAST_LEAD_HOURS,
                     "assumedResultAvailabilityLagHours": result_lag_hours,
                     "sameWeekResultsExcluded": True, "warmupSeason": 2014,
                     "restCapDays": 30, "sourceTimeZone": "America/New_York", "teamAliases": ALIASES},
        "warmupGames": seasons[2014], "splits": splits,
        "files": {name: {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)} for name, body in artifacts.items()},
        "limitations": [
            "Latest corrected source snapshot; historical publication and finalization timestamps are unavailable.",
            f"{result_lag_hours}-hour result availability is a modeling assumption, not observed provenance.",
            "Schedule fields use the final source schedule; historical rescheduling announcements are not reconstructed.",
            "History contains regular-season games only and carries over season boundaries.",
            "Points and result rates are not opponent-adjusted. Injury, weather, and quarterback features are not included.",
            "Use only the explicit features object as model input. Labels and evidence are stored for evaluation/audit.",
            "Test rows may use earlier test-period results as chronological features, but training/tuning must not use test labels.",
            "No normalization, imputation, or model fitting has been performed. Fit any preprocessing on training data only.",
        ],
    }
    # Validate the whole source before creating outputs; write a manifest last.
    output_path.mkdir(parents=True, exist_ok=True)
    for name, body in artifacts.items():
        path = output_path / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(body)
        temporary.replace(path)
    manifest_path = output_path / "manifest.json"
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    temporary.replace(manifest_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/nflverse-games.csv")
    parser.add_argument("--provenance", type=Path, default=ROOT / "data/raw/nflverse-games.provenance.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/v1")
    parser.add_argument("--result-lag-hours", type=int, default=RESULT_LAG_HOURS)
    args = parser.parse_args()
    try:
        manifest = materialize(args.input, args.provenance, args.output, args.result_lag_hours)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Feature build failed: {exc}\n")
    print(json.dumps({"output": str(args.output.resolve()), "splits": manifest["splits"], "warmupGames": manifest["warmupGames"]}, indent=2))


if __name__ == "__main__":
    main()
