"""Score issued forecasts only after verified results; compare shared games."""
import argparse
import json
from pathlib import Path

import live
import model
import snapshots
from recheck_results import unresolved_disputes


def score_store(store=live.LIVE, as_of=None):
    at = as_of or snapshots.now()
    cutoff = snapshots.parse_time(at)
    groups, complete = {}, {}
    disputed = unresolved_disputes(store, at)
    for path in sorted((store / "forecasts").glob("*/*.json")):
        row = json.loads(path.read_text())
        if row["mode"] != "prospective" or snapshots.parse_time(row["generatedAt"]) >= snapshots.parse_time(row["kickoffAt"]):
            raise ValueError("Non-prospective or late forecast in live store")
        if snapshots.parse_time(row["featureCutoffAt"]) > snapshots.parse_time(row["generatedAt"]):
            raise ValueError("Forecast uses a future feature cutoff")
        if snapshots.parse_time(row["generatedAt"]) > cutoff:
            continue
        version = row["modelVersion"]
        bucket = groups.setdefault(version, {"issued": 0, "pending": 0, "disputed": 0, "scored": []})
        bucket["issued"] += 1
        if row["eventId"] in disputed:
            bucket["pending"] += 1
            bucket["disputed"] += 1
            continue
        results = [json.loads(p.read_text()) for p in (store / "results" / row["eventId"]).glob("*.json")]
        eligible = [r for r in results if snapshots.parse_time(r["finalizedAt"]) <= cutoff]
        if not eligible:
            bucket["pending"] += 1
            continue
        result = max(eligible, key=lambda r: (snapshots.parse_time(r["finalizedAt"]), r["espnObservationId"]))
        if (result["eventId"] != row["eventId"] or result["timingBasis"] != "observed-final-in-two-sources"
                or snapshots.parse_time(result["finalizedAt"]) <= snapshots.parse_time(row["kickoffAt"])):
            raise ValueError("Invalid result provenance or finalization time")
        if any(type(result[k]) is not int or result[k] < 0 for k in ("homeScore", "awayScore")):
            raise ValueError("Invalid final scores")
        h, a = result["homeScore"], result["awayScore"]
        outcome = "tie" if h == a else "homeWin" if h > a else "awayWin"
        score = model.score(row["probabilities"], outcome)
        bucket["scored"].append(score)
        complete.setdefault(version, {})[row["eventId"]] = {"forecast": row, "score": score, "outcome": outcome}
    report = {"asOf": at, "models": {}, "pairedComparisons": {}}
    for version, group in groups.items():
        report["models"][version] = {"issued": group["issued"], "pending": group["pending"], "disputed": group["disputed"], **model.aggregate(group["scored"])}
    reference = complete.get("outcome-logit-v1", {})
    for version, values in complete.items():
        if version == "outcome-logit-v1":
            continue
        common = sorted(set(reference) & set(values))
        if any(reference[event]["forecast"]["featureCutoffAt"] != values[event]["forecast"]["featureCutoffAt"] for event in common):
            raise ValueError("Paired model comparison has different feature cutoffs")
        base = model.aggregate([reference[event]["score"] for event in common])
        candidate = model.aggregate([values[event]["score"] for event in common])
        report["pairedComparisons"][version] = {"sameGames": len(common), "teamOnly": base, "challenger": candidate,
                                               "logLossImprovement": base["logLoss"] - candidate["logLoss"] if common else None,
                                               "brierImprovement": base["brier"] - candidate["brier"] if common else None}
    folder = store / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "prospective-scores.json").write_bytes(live.encode(report))
    lines = ["# Prospective forecast tracking", "", f"As of {at}. Only forecasts saved before kickoff and independently confirmed final results are scored.", ""]
    for version, metrics in report["models"].items():
        if metrics["disputed"]:
            lines.append(f'- **{version}: {metrics["disputed"]} disputed games withheld from scores pending source agreement.**')
        if metrics["games"]:
            lines.append(f'- **{version}:** {metrics["games"]} scored, {metrics["pending"]} pending; accuracy {metrics["accuracy"]:.1%}, log loss {metrics["logLoss"]:.6f}.')
        else:
            lines.append(f'- **{version}:** {metrics["issued"]} issued, {metrics["pending"]} pending. No completed results to score yet.')
    for version, comparison in report["pairedComparisons"].items():
        if comparison["sameGames"]:
            lines.append(f'- **Paired comparison — {version}:** {comparison["sameGames"]} shared games, log-loss improvement versus team-only {comparison["logLossImprovement"]:.6f}.')
        else:
            lines.append(f'- **Paired comparison — {version}:** no shared finalized games yet.')
    lines += ["", "Positive paired loss improvement favors the player challenger. These descriptive results need a substantial prospective sample; no automatic model promotion or profitability claim is made.", ""]
    (folder / "prospective-scores.md").write_text("\n".join(lines))
    return report


def write_matchup_comparison(date, store=live.LIVE):
    by_event = {}
    for path in (store / "forecasts").glob("*/*.json"):
        row = json.loads(path.read_text())
        if row["dateEastern"] == date:
            by_event.setdefault(row["eventId"], {})[row["modelVersion"]] = row
    lines = [f"# Model comparison — {date}", "", "Outcome probabilities issued before kickoff. Times are Eastern. Team-only is the primary model; player models are shadow comparisons.", ""]
    for event, versions in sorted(by_event.items(), key=lambda item: (next(iter(item[1].values()))["kickoffAt"], item[0])):
        reference = versions.get("outcome-logit-v1")
        if not reference:
            continue
        when = snapshots.parse_time(reference["kickoffAt"]).astimezone(live.features.EASTERN).strftime("%-I:%M %p")
        lines += [f'## {reference["awayTeam"]} at {reference["homeTeam"]} — {when}', ""]
        for version, row in sorted(versions.items()):
            p = row["probabilities"]
            lines.append(f'- **{version}:** {row["awayTeam"]} {p["awayWin"]:.1%}; {row["homeTeam"]} {p["homeWin"]:.1%}; tie {p["tie"]:.1%}.')
        lines.append("")
    lines += ["The player versions use past production, not confirmed starting lineups. Injury-aware inputs include only reports observed by the same cutoff as the original team forecast. Saved predictions are not rewritten after new news or results.", ""]
    path = store / "reports" / f"{date}-comparison.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return str(path.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date")
    args = parser.parse_args()
    print(json.dumps(score_store(), indent=2))
    if args.date:
        print(write_matchup_comparison(args.date))
