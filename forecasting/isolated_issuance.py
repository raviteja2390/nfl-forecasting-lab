"""Per-game orchestration; frozen player inference and artifacts remain unchanged."""
import hashlib
import json
import live
import snapshots
from compare_players import PlayerData, RUN, ROOT, VERSIONS, augment, model

def publish_shadow_event(date, event_id):
    records = [json.loads(path.read_text()) for path in (live.LIVE / "forecasts/outcome-logit-v1").glob("*.json")]
    records = sorted([row for row in records if row["dateEastern"] == date and row["eventId"] == event_id], key=lambda row: row["eventId"])
    if not records:
        raise ValueError("Issue team-only forecasts first")
    at = min(row["featureCutoffAt"] for row in records)
    seasons = sorted({int(event.split("_")[0]) for row in records for side in ("home", "away")
                      for event in row["featureRow"]["evidence"][side]["resultGameIds"]} | {row["featureRow"]["season"] for row in records})
    # Load the feeds we actually had at the original team forecast's cutoff.
    source = PlayerData(seasons, at=at)
    manifest = json.loads((RUN / "artifacts.json").read_text())
    issued = []
    for family, version in VERSIONS.items():
        body = (RUN / (version + ".json")).read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        if digest != manifest["files"][version + ".json"]["sha256"]:
            raise ValueError("Player-model checksum mismatch")
        artifact = json.loads(body)
        for name, expected in artifact["provenance"]["codeSha256"].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Player model code changed after training")
        for reference in records:
            path = live.LIVE / "forecasts" / version / f'{reference["eventId"]}.json'
            if path.exists():
                continue
            now = snapshots.now()
            if snapshots.parse_time(now) > snapshots.parse_time(reference["kickoffAt"]) - live.timedelta(hours=24):
                raise ValueError("Missed the player shadow's 24-hour issue deadline")
            values, evidence = augment(reference["featureRow"], source, family, prospective=True)
            p = model.predict_many(artifact, [values])[0]
            now = snapshots.now()
            if snapshots.parse_time(now) > snapshots.parse_time(reference["kickoffAt"]) - live.timedelta(hours=24):
                raise ValueError("Player shadow generation crossed the issue deadline")
            result = {**reference, "modelVersion": version, "modelSha256": digest, "generatedAt": now,
                      "leadHours": (snapshots.parse_time(reference["kickoffAt"]) - snapshots.parse_time(now)).total_seconds() / 3600,
                      "trainingCompletedAt": artifact["trainedAt"], "role": "shadow-comparison", "probabilities": p,
                      "pairedTeamForecastGeneratedAt": reference["generatedAt"], "playerFeatureValues": values,
                      "playerEvidence": evidence,
                      "playerSourceObservations": [{key: r[key] for key in ("kind", "key", "observedAt", "sha256")} for r in source.receipts],
                      "limitations": ["Player model is a shadow challenger, not established as more accurate prospectively.",
                                      "Same feature cutoff as the team forecast; later reports are excluded.",
                                      "Earlier usage does not confirm the upcoming starters or identify causal player effects."]}
            snapshots.immutable_write(path, live.encode(result))
            issued.append({"eventId": reference["eventId"], "modelVersion": version})
    return {"date": date, "issued": len(issued), "models": list(VERSIONS.values())}

