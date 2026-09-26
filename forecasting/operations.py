"""Local cycle status and overdue checks; never modify forecasting artifacts."""
import argparse
from contextlib import contextmanager
import csv
from datetime import timedelta, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import snapshots

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "live"
EASTERN = ZoneInfo("America/New_York")
GRACE_MINUTES = 20


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".status-")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def cycle_lock(store=LIVE):
    store.mkdir(parents=True, exist_ok=True)
    with (store / ".cycle.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another collection cycle is already running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def record_status(started, report=None, error=None, store=LIVE):
    path = store / "operations/status.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    state = {"schemaVersion": 1, "lastAttemptAt": started,
             "lastSuccessAt": previous.get("lastSuccessAt"), "state": "running"}
    if report is not None or error is not None:
        state["finishedAt"] = snapshots.now()
        state["errors"] = ([{"stage": "uncaught-cycle-error", "error": str(error)}]
                           if error is not None else report.get("errors", []))
        state["state"] = "failed" if state["errors"] else "succeeded"
        if state["state"] == "succeeded":
            state["lastSuccessAt"] = state["finishedAt"]
        if report is not None:
            state["schedule"] = report.get("schedule")
    atomic_json(path, state)
    if state["state"] == "failed":
        snapshots.immutable_write(store / "operations/failures" / (started.replace(":", "-") + ".json"),
                                  (json.dumps(state, indent=2) + "\n").encode())
    return state


def latest_due(at, game_dates, grace_minutes=GRACE_MINUTES):
    """Enumerate UTC hours so both repeated fall-back hours remain distinct."""
    eligible = snapshots.parse_time(at).astimezone(timezone.utc) - timedelta(minutes=grace_minutes)
    candidate = eligible.replace(minute=5, second=0, microsecond=0)
    if candidate > eligible:
        candidate -= timedelta(hours=1)
    for _ in range(50):
        local = candidate.astimezone(EASTERN)
        if local.date().isoformat() in game_dates or local.hour == 0:
            return candidate
        candidate -= timedelta(hours=1)
    raise ValueError("No scheduled cycle found within 50 hours")


def check_health(store=LIVE, archive=snapshots.DEFAULT_STORE, at=None):
    at = at or snapshots.now()
    checked = snapshots.parse_time(at)
    reasons, due, cadence = [], None, None
    status_path = store / "operations/status.json"
    try:
        status = json.loads(status_path.read_text()) if status_path.exists() else {}
        if status and status.get("state") not in ("running", "succeeded", "failed"):
            raise ValueError("Unknown cycle status")
        last = snapshots.parse_time(status["lastSuccessAt"]) if status.get("lastSuccessAt") else None
        if last and last > checked:
            raise ValueError("Last success is in the future")
        if status.get("state") == "failed":
            reasons.append("Latest collection cycle failed")
        selected = snapshots.select_as_of(archive, at, max_age_hours=25)
        if not selected["found"]:
            raise ValueError(selected["reason"])
        body = snapshots.verified_body(archive, selected["observation"])
        dates = {r["gameday"] for r in csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
                 if r["game_type"] in ("REG", "WC", "DIV", "CON", "SB")}
        if not dates or max(dates) < checked.astimezone(EASTERN).date().isoformat():
            raise ValueError("Schedule does not cover today's date")
        cadence = "hourly" if checked.astimezone(EASTERN).date().isoformat() in dates else "daily"
        due = latest_due(at, dates)
        if last is None or last < due:
            reasons.append("No successful collection after the latest due run (20-minute grace)")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        reasons.append("Health evidence unavailable: " + str(exc))
    result = {"checkedAt": at, "healthy": not reasons, "reasons": reasons,
              "cadence": cadence,
              "latestRequiredRunAt": due.isoformat() if due else None,
              "graceMinutes": GRACE_MINUTES,
              "limitation": ("GitHub schedules are best effort; a GitHub-wide outage can affect collection and its watchdog."
                             if os.environ.get("GITHUB_ACTIONS") == "true" else
                             "Local monitor cannot execute or notify while this computer or Codex is off.")}
    previous_path = store / "operations/health.json"
    try:
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    except (ValueError, OSError):
        previous = None
    result["notify"] = (not result["healthy"] if previous is None else
                        previous.get("healthy") != result["healthy"] or previous.get("reasons") != reasons)
    atomic_json(previous_path, result)
    if result["notify"]:
        snapshots.immutable_write(store / "operations/alerts" / (at.replace(":", "-") + ".json"),
                                  (json.dumps(result, indent=2) + "\n").encode())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check",))
    args = parser.parse_args()
    result = check_health()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["healthy"] else 1)
