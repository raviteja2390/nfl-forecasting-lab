"""Collection, first-issue forecasts and result scoring; never train models."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json

import feeds
import live
import snapshots
import operations
from recheck_results import dates_to_recheck, settle_and_audit
from score_live import score_store, write_matchup_comparison


def _run_cycle(collect=True):
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
    # Pending games remain eligible without an age limit. Settled games are
    # rechecked on their game date and the following six Eastern dates.
    for date in dates_to_recheck(live.LIVE, local.date()):
        if collect:
            feeds.capture("scoreboard", date.replace("-", ""))
        result = settle_and_audit(date)
        report["resultRuns"].append(result)
        if result["sourceDisagreements"]:
            report["errors"].append({"stage": "result-source-disagreement", "events": result["sourceDisagreements"]})
        if result["previouslyFinalNowPending"]:
            report["errors"].append({"stage": "previous-final-now-pending", "events": result["previouslyFinalNowPending"]})
    report["scores"] = score_store()
    from promotion_report import write_report
    promotion = write_report()
    report["promotion"] = {"reviewAt": promotion["reviewAt"], "errors": promotion["errors"],
                           "statuses": {key: value["status"] for key, value in promotion["comparisons"].items()}}
    if promotion["errors"]:
        report["errors"].append({"stage": "promotion-integrity", "errors": promotion["errors"]})
    from project_status import write_status
    report["projectStatus"] = write_status()
    report["finishedAt"] = snapshots.now()
    path = live.LIVE / "cycles" / (report["startedAt"].replace(":", "-") + ".json")
    snapshots.immutable_write(path, live.encode(report))
    return report


def run_cycle(collect=True):
    with operations.cycle_lock(live.LIVE):
        # Offline verification must never make a missed live collection look healthy.
        if not collect:
            return _run_cycle(False)
        started = snapshots.now()
        operations.record_status(started, store=live.LIVE)
        try:
            report = _run_cycle(True)
        except Exception as exc:
            operations.record_status(started, error=exc, store=live.LIVE)
            raise
        operations.record_status(started, report=report, store=live.LIVE)
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
