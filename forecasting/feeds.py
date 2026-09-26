"""Archive public player data and ESPN scoreboards with actual receipt times."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import uuid

from snapshots import immutable_write, now, parse_time

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "data/feeds"
RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
KINDS = {
    "stats": ("stats_player/stats_player_week_{key}.csv", {"player_id", "season", "week", "position", "attempts", "targets", "carries"}),
    "injuries": ("injuries/injuries_{key}.csv", {"season", "week", "team", "gsis_id", "position", "report_status"}),
    "snaps": ("snap_counts/snap_counts_{key}.csv", {"game_id", "season", "week", "team", "pfr_player_id", "offense_pct", "defense_pct"}),
    "players": ("players/players.csv", {"gsis_id", "pfr_id"}),
}


def source_url(kind, key):
    if kind == "scoreboard":
        if not re.fullmatch(r"\d{8}(-\d{8})?", key):
            raise ValueError("Scoreboard key must be YYYYMMDD or YYYYMMDD-YYYYMMDD")
        return f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={key}&limit=1000"
    if kind not in KINDS or (kind != "players" and not re.fullmatch(r"20\d\d", key)):
        raise ValueError("Unknown feed or season")
    return RELEASE + "/" + KINDS[kind][0].format(key=key)


def validate(kind, body):
    if not body or len(body) > 30_000_000:
        raise ValueError("Empty or oversized feed")
    if kind == "scoreboard":
        value = json.loads(body)
        if not isinstance(value.get("events"), list):
            raise ValueError("Scoreboard does not contain events")
        ids = [event["id"] for event in value["events"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate scoreboard events")
        return {"events": len(ids)}
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    if not KINDS[kind][1].issubset(reader.fieldnames or []):
        raise ValueError(f"Missing required {kind} fields")
    count = 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed CSV row")
        count += 1
    if not count:
        raise ValueError("No player records returned")
    return {"rows": count, "columns": reader.fieldnames}


def capture(kind, key, store=STORE):
    url = source_url(kind, str(key))
    started = now()
    result = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--proto", "=https",
                             "--proto-redir", "=https", "--max-time", "50", "--max-filesize", "30000000", url],
                            capture_output=True, timeout=55)
    observed = now()
    if result.returncode:
        raise ValueError(f"{kind}/{key}: {result.stderr.decode().strip()}")
    body = result.stdout
    summary = validate(kind, body)
    digest = hashlib.sha256(body).hexdigest()
    metadata = {"schemaVersion": 1, "id": uuid.uuid4().hex, "kind": kind, "key": str(key), "sourceUrl": url,
                "requestStartedAt": started, "observedAt": observed, "storedAt": now(),
                "sha256": digest, "bytes": len(body), "validation": summary,
                "providerPublishedAt": None, "timingBasis": "local-full-response-receipt"}
    immutable_write(store / "blobs" / digest, body)
    immutable_write(store / "observations" / f'{metadata["id"]}.json', (json.dumps(metadata, indent=2) + "\n").encode())
    return metadata


def latest(kind, key, at=None, max_age_hours=None, store=STORE):
    cutoff = parse_time(at or now())
    candidates = []
    for path in (store / "observations").glob("*.json"):
        m = json.loads(path.read_text())
        if m["kind"] != kind or m["key"] != str(key):
            continue
        if m["sourceUrl"] != source_url(kind, str(key)) or not re.fullmatch(r"[a-f0-9]{64}", m["sha256"]):
            raise ValueError("Malformed feed provenance")
        if not parse_time(m["requestStartedAt"]) <= parse_time(m["observedAt"]) <= parse_time(m["storedAt"]):
            raise ValueError("Invalid feed clock order")
        if parse_time(m["observedAt"]) <= cutoff:
            candidates.append(m)
    if not candidates:
        raise ValueError(f"No observed {kind}/{key} feed by cutoff")
    m = max(candidates, key=lambda row: (row["observedAt"], row["id"]))
    if max_age_hours is not None and (cutoff - parse_time(m["observedAt"])).total_seconds() > 3600 * max_age_hours:
        raise ValueError(f"Stale {kind}/{key} feed")
    body = (store / "blobs" / m["sha256"]).read_bytes()
    if len(body) != m["bytes"] or hashlib.sha256(body).hexdigest() != m["sha256"]:
        raise ValueError("Feed checksum mismatch")
    return m, body


def csv_rows(kind, key, **kwargs):
    metadata, body = latest(kind, key, **kwargs)
    return metadata, list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=[*KINDS, "scoreboard"])
    parser.add_argument("keys", nargs="+")
    parser.add_argument("--reuse", action="store_true", help="Reuse previously archived historical files")
    args = parser.parse_args()

    def job(key):
        if args.reuse:
            try:
                m, _ = latest(args.kind, key)
                return {"kind": args.kind, "key": key, "reused": True, "sha256": m["sha256"]}
            except ValueError as exc:
                if not str(exc).startswith("No observed"):
                    raise
        m = capture(args.kind, key)
        return {"kind": args.kind, "key": key, "observedAt": m["observedAt"], "bytes": m["bytes"], "validation": {k:v for k,v in m["validation"].items() if k != "columns"}}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(job, args.keys):
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
