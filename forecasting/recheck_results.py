"""Revisit pending games and seven Eastern calendar dates of settled games."""
from datetime import date
import json

import live
import snapshots


def unresolved_disputes(store, at):
    latest = {}
    for path in (store / "rechecks").glob("*.json"):
        row = json.loads(path.read_text())
        when = snapshots.parse_time(row["checkedAt"])
        if when > snapshots.parse_time(at):
            continue
        if row["date"] not in latest or when > snapshots.parse_time(latest[row["date"]]["checkedAt"]):
            latest[row["date"]] = row
    return {event for row in latest.values()
            for key in ("sourceDisagreements", "previouslyFinalNowPending") for event in row.get(key, [])}


def latest_results(store):
    result = {}
    for folder in (store / "results").glob("*"):
        rows = [json.loads(p.read_text()) for p in folder.glob("*.json")]
        if rows:
            result[folder.name] = max(rows, key=lambda r: (snapshots.parse_time(r["finalizedAt"]), r["espnObservationId"]))
    return result


def dates_to_recheck(store, today):
    settled = latest_results(store)
    dates = set()
    for path in (store / "forecasts").glob("*/*.json"):
        row = json.loads(path.read_text())
        age = (today - date.fromisoformat(row["dateEastern"])).days
        if age >= 0 and (row["eventId"] not in settled or age < 7):
            dates.add(row["dateEastern"])
    return sorted(dates)


def settle_and_audit(day, store=live.LIVE):
    before = latest_results(store)
    report = live.settle(day, store)
    after = latest_results(store)
    corrections = []
    for event, new in after.items():
        old = before.get(event)
        if old and any(old[key] != new[key] for key in ("homeScore", "awayScore")):
            corrections.append({"eventId": event, "previous": old, "corrected": new})
    report["corrections"] = corrections
    report["previouslyFinalNowPending"] = sorted(set(report["pending"]) & set(before))
    report["checkedAt"] = snapshots.now()
    snapshots.immutable_write(store / "rechecks" / (report["checkedAt"].replace(":", "-") + ".json"), live.encode(report))
    return report
