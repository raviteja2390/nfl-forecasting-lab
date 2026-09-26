"""Capture and replay observed NFL feed versions. Python 3.9+ and system curl."""
import argparse
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from zoneinfo import ZoneInfo

from build_features import ROOT, REQUIRED, SOURCE_URL

UTC = timezone.utc
SOURCE_ID = "nflverse-games"
DEFAULT_STORE = ROOT / "data/snapshots"
MAX_BYTES = 20_000_000


def now():
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include its timezone")
    return parsed.astimezone(UTC)


def validate_csv(body):
    if not body or len(body) > MAX_BYTES:
        raise ValueError("Empty or oversized feed")
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")), strict=True)
    fields = reader.fieldnames or []
    if not REQUIRED.issubset(fields) or len(fields) != len(set(fields)):
        raise ValueError("Missing or duplicate CSV header fields")
    ids, seasons = set(), set()
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("CSV row has an inconsistent number of columns")
        event = row["game_id"]
        if not event or event in ids:
            raise ValueError("Missing or duplicate game ID")
        ids.add(event)
        seasons.add(int(row["season"]))
        scores = [row[side + "_score"] for side in ("home", "away")]
        missing = [score in ("", "NA") for score in scores]
        if missing[0] != missing[1]:
            raise ValueError("Only one team's score is present")
        if not any(missing) and any(not score.isdigit() for score in scores):
            raise ValueError("Invalid score")
    if not ids:
        raise ValueError("Feed contains no games")
    # Scores being present does not establish that a live game is final.
    return {"rows": len(ids), "firstSeason": min(seasons), "lastSeason": max(seasons)}


def immutable_write(path, body):
    """Atomic publication with no overwrite; identical content may be reused."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != body:
                raise ValueError("Refusing to replace an existing archive object")
    finally:
        os.unlink(temporary)


def store_capture(store, body, request_started_at, observed_at, transport):
    """Internal ingestion API; only capture() supplies real network receipt times."""
    summary = validate_csv(body)
    stored_at = now()
    if not parse_time(request_started_at) <= parse_time(observed_at) <= parse_time(stored_at):
        raise ValueError("Capture clock is inconsistent; no observation saved")
    if transport.get("status") != 200 or transport.get("finalUrl") != SOURCE_URL:
        raise ValueError("Unexpected HTTP result or source URL")
    digest = hashlib.sha256(body).hexdigest()
    observation_id = uuid.uuid4().hex
    metadata = {
        "schemaVersion": 1, "observationId": observation_id,
        "sourceId": SOURCE_ID, "sourceUrl": SOURCE_URL,
        "requestStartedAt": request_started_at, "observedAt": observed_at,
        "storedAt": stored_at, "providerPublishedAt": None,
        "sha256": digest, "bytes": len(body), "validation": summary,
        "transport": {key: transport.get(key) for key in ("status", "finalUrl", "httpDate", "httpLastModified", "etag")},
        "timingBasis": "local-full-response-receipt",
    }
    immutable_write(store / "blobs" / f"{digest}.csv", body)
    immutable_write(store / "observations" / f"{observation_id}.json", (json.dumps(metadata, indent=2) + "\n").encode())
    return metadata


def capture(store=DEFAULT_STORE):
    request_started = now()
    with tempfile.TemporaryDirectory(prefix="nfl-capture-") as directory:
        body_path, headers_path = Path(directory) / "response.csv", Path(directory) / "headers.txt"
        command = ["curl", "--fail", "--location", "--silent", "--show-error",
                   "--proto", "=https", "--proto-redir", "=https", "--max-time", "45",
                   "--max-filesize", str(MAX_BYTES), "--dump-header", str(headers_path),
                   "--output", str(body_path), "--write-out", "%{http_code}\n%{url_effective}", SOURCE_URL]
        result = subprocess.run(command, capture_output=True, text=True, timeout=50)
        observed = now()
        if result.returncode:
            raise ValueError(f"Download failed: {result.stderr.strip()}")
        status, final_url = result.stdout.strip().split("\n", 1)
        blocks = headers_path.read_text().strip().split("\n\n")
        headers = {}
        for line in blocks[-1].splitlines()[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.lower()] = value.strip()
        transport = {"status": int(status), "finalUrl": final_url,
                     "httpDate": headers.get("date"), "httpLastModified": headers.get("last-modified"), "etag": headers.get("etag")}
        return store_capture(store, body_path.read_bytes(), request_started, observed, transport)


def read_observations(store):
    records = []
    for path in sorted((store / "observations").glob("*.json")):
        metadata = json.loads(path.read_text())
        identifier = metadata.get("observationId", "")
        digest = metadata.get("sha256", "")
        if (metadata.get("schemaVersion") != 1 or metadata.get("sourceId") != SOURCE_ID
                or metadata.get("sourceUrl") != SOURCE_URL or not re.fullmatch(r"[a-f0-9]{32}", identifier)
                or path.stem != identifier or not re.fullmatch(r"[a-f0-9]{64}", digest)
                or metadata.get("timingBasis") != "local-full-response-receipt"):
            raise ValueError("Malformed archive metadata")
        if not parse_time(metadata["requestStartedAt"]) <= parse_time(metadata["observedAt"]) <= parse_time(metadata["storedAt"]) <= parse_time(now()):
            raise ValueError("Invalid archive timestamp order")
        if metadata.get("transport", {}).get("status") != 200 or metadata["transport"].get("finalUrl") != SOURCE_URL:
            raise ValueError("Invalid archive source response")
        records.append(metadata)
    return sorted(records, key=lambda row: (parse_time(row["observedAt"]), parse_time(row["storedAt"]), row["observationId"]))


def verified_body(store, metadata):
    path = store / "blobs" / f'{metadata["sha256"]}.csv'
    body = path.read_bytes()
    if len(body) != metadata["bytes"] or hashlib.sha256(body).hexdigest() != metadata["sha256"]:
        raise ValueError("Snapshot checksum mismatch")
    if validate_csv(body) != metadata["validation"]:
        raise ValueError("Snapshot validation metadata mismatch")
    return body


def select_as_of(store, cutoff, max_age_hours=24):
    if not isinstance(max_age_hours, (int, float)) or not 0 < max_age_hours <= 8760:
        raise ValueError("Maximum snapshot age must be between 0 and 8760 hours")
    at = parse_time(cutoff)
    records = [row for row in read_observations(store) if parse_time(row["observedAt"]) <= at]
    if not records:
        return {"found": False, "reason": "No snapshot was observed by this cutoff", "cutoff": cutoff}
    selected = records[-1]
    age = (at - parse_time(selected["observedAt"])).total_seconds() / 3600
    if age > max_age_hours:
        return {"found": False, "reason": "Latest eligible snapshot is too old", "cutoff": cutoff, "ageHours": age}
    verified_body(store, selected)
    return {"found": True, "cutoff": cutoff, "ageHours": age, "observation": selected,
            "blobPath": str((store / "blobs" / f'{selected["sha256"]}.csv').resolve())}


def verify_archive(store):
    records = read_observations(store)
    verified = set()
    for row in records:
        # Verify metadata even when identical bytes are reused by multiple captures.
        verified_body(store, row)
        verified.add(row["sha256"])
    return {"observations": len(records), "uniquePayloads": len(verified),
            "firstObservedAt": records[0]["observedAt"] if records else None,
            "lastObservedAt": records[-1]["observedAt"] if records else None}


def cadence_for_body(body, at):
    """Use the observed schedule, including atypical days, in the user's timezone."""
    eastern = parse_time(at).astimezone(ZoneInfo("America/New_York"))
    today = eastern.date().isoformat()
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    supported = [row for row in rows if row["game_type"] in ("REG", "WC", "DIV", "CON", "SB")]
    if not supported:
        raise ValueError("No regular-season or postseason schedule rows available")
    games = [{"eventId": row["game_id"], "awayTeam": row["away_team"], "homeTeam": row["home_team"],
              "kickoffEastern": row["gametime"]} for row in supported if row["gameday"] == today]
    return {"localDate": today, "timeZone": "America/New_York", "cadence": "hourly" if games else "daily",
            "gamesToday": sorted(games, key=lambda row: (row["kickoffEastern"], row["eventId"])),
            "scheduledGameCount": len(games), "lastScheduledDateInFeed": max(row["gameday"] for row in supported),
            "policy": "Hourly at five minutes past each hour on scheduled game dates; otherwise daily at 00:05 Eastern.",
            "coverage": "Regular season and postseason only. Does not infer preseason coverage."}


def schedule_decision(store, at=None):
    cutoff = at or now()
    selected = select_as_of(store, cutoff, max_age_hours=25)
    if not selected["found"]:
        raise ValueError("Cannot set cadence without a fresh observed schedule")
    policy = cadence_for_body(verified_body(store, selected["observation"]), cutoff)
    policy["observationId"] = selected["observation"]["observationId"]
    policy["observedAt"] = selected["observation"]["observedAt"]
    return policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capture", help="Fetch once and append a real observation")
    commands.add_parser("verify", help="Verify every archive payload and observation")
    commands.add_parser("schedule", help="Choose hourly or daily from today's observed NFL schedule")
    query = commands.add_parser("as-of", help="Find the last version received before a cutoff")
    query.add_argument("cutoff")
    query.add_argument("--max-age-hours", type=float, default=24)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            output = capture(args.store)
        elif args.command == "verify":
            output = verify_archive(args.store)
        elif args.command == "schedule":
            output = schedule_decision(args.store)
        else:
            output = select_as_of(args.store, args.cutoff, args.max_age_hours)
    except (ValueError, OSError, KeyError, csv.Error, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"Snapshot operation failed: {exc}\n")
    print(json.dumps(output, indent=2, allow_nan=False))
    if output.get("found") is False:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
