"""Collection, first-issue forecasts and result scoring; never train models."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json

import feeds
import live
import snapshots
from score_live import score_store, write_matchup_comparison


def run_cycle(collect=True):
    at = snapshots.now()
    local = snapshots.parse_time(at).astimezone(live.features.EASTERN)
    report = {"startedAt": at, "errors": [], "forecastRuns": [], "resultRuns": []}
    if collect:
        snapshots.capture()
    report["archive"] = snapshots.verify_archive(snapshots.DEFAULT_STORE)
    report["schedule"] = snapshots.schedule_decision(snapshots.DEFAULT_STORE)
    _, games = live.current_games(snapshots.now())
    tomorrow = (local.date() + timedelta(days=1)).isoformat()
    targets = [game for game in games if game["localDate"].isoformat() == tomorrow]
    if targets:
        current_season = max(game["season"] for game in targets)
        # Historical source versions are reused; refresh current-year player
        # data before fixing tomorrow's paired feature cutoff.
        if collect:
            jobs = [(kind, str(current_season)) for kind in ("stats", "injuries")]
            for kind in ("stats", "injuries"):
                try:
                    feeds.latest(kind, str(current_season - 1))
                except ValueError:
                    jobs.append((kind, str(current_season - 1)))
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [(job, pool.submit(feeds.capture, *job)) for job in jobs]
                for job, future in futures:
                    try:
                        future.result()
                    except Exception as exc:
                        report["errors"].append({"stage": "player-capture", "feed": list(job), "error": str(exc)})
        missing = [game for game in targets if not (live.LIVE / "forecasts/outcome-logit-v1" / f'{game["eventId"]}.json').exists()]
        if missing and collect:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda key: feeds.capture("scoreboard", key), live.required_dates(tomorrow, snapshots.now())))
        report["forecastRuns"].append(live.publish(tomorrow))
        try:
            for kind in ("stats", "injuries"):
                feeds.latest(kind, str(current_season), max_age_hours=24)
            from compare_players import publish_shadow
            report["forecastRuns"].append(publish_shadow(tomorrow))
        except Exception as exc:
            report["errors"].append({"stage": "player-shadow", "error": str(exc)})
        report["comparisonReport"] = write_matchup_comparison(tomorrow)
    # Refresh only previously issued game dates with unscored outcomes. The
    # local date uses Eastern time, including night games that end after UTC midnight.
    pending_dates = set()
    for path in (live.LIVE / "forecasts/outcome-logit-v1").glob("*.json"):
        forecast = json.loads(path.read_text())
        if forecast["dateEastern"] > local.date().isoformat():
            continue
        if not any((live.LIVE / "results" / forecast["eventId"]).glob("*.json")):
            pending_dates.add(forecast["dateEastern"])
    for date in sorted(pending_dates):
        if collect:
            feeds.capture("scoreboard", date.replace("-", ""))
        result = live.settle(date)
        report["resultRuns"].append(result)
        if result["sourceDisagreements"]:
            report["errors"].append({"stage": "result-source-disagreement", "events": result["sourceDisagreements"]})
    report["scores"] = score_store()
    report["finishedAt"] = snapshots.now()
    path = live.LIVE / "cycles" / (report["startedAt"].replace(":", "-") + ".json")
    snapshots.immutable_write(path, live.encode(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-capture", action="store_true", help="Use existing fresh archives to verify the pipeline offline")
    args = parser.parse_args()
    report = run_cycle(not args.no_capture)
    print(json.dumps({"schedule": report["schedule"], "forecastRuns": report["forecastRuns"],
                      "resultRuns": report["resultRuns"], "errors": report["errors"], "scores": report["scores"]}, indent=2))
    if report["errors"]:
        raise SystemExit(1)
