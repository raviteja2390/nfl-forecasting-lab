"""One-time evaluation of an already saved model; no training dependencies."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform

import model as scoring

ROOT = Path(__file__).resolve().parent


def sha(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Expected an explicit UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def write_once(path, body):
    with path.open("xb") as handle:
        handle.write(body)


def checked_bytes(path, expected):
    body = path.read_bytes()
    if sha(body) != expected["sha256"] or len(body) != expected["bytes"]:
        raise ValueError(f"Checksum or byte-count mismatch: {path.name}")
    return body


def validate_contract(artifact, manifest, plan):
    scoring.validate_model(artifact)
    if artifact["modelVersion"] != plan["modelVersion"] or artifact["featureNames"] != manifest["featureNames"]:
        raise ValueError("Model identity or feature order differs from frozen plan/data")
    if (artifact["trainingSeasons"] != list(range(2015, 2023)) or artifact["selectionSeasons"] != [2023]
            or artifact["referenceLagHours"] != 48 or plan["testSeasons"] != [2024, 2025]
            or plan["modelRefitting"] is not False or plan["recalibration"] is not False
            or plan["parameterSearch"] is not False or plan["primaryMetric"] != "logLoss"):
        raise ValueError("Unsupported frozen evaluation contract")
    if manifest["source"]["sha256"] != artifact["provenance"]["sourceSha256"]:
        raise ValueError("Test data comes from a different source snapshot")
    if manifest["datasetKind"] != "retrospective-reconstruction":
        raise ValueError("Expected explicitly retrospective data")
    settings = manifest["settings"]
    if (settings["forecastLeadHours"] != plan["forecastLeadHours"] or plan["forecastLeadHours"] != 24
            or settings["assumedResultAvailabilityLagHours"] != plan["referenceLagHours"]
            or plan["referenceLagHours"] != 48 or settings["sameWeekResultsExcluded"] is not True):
        raise ValueError("Test feature timing does not match the frozen model")
    # The original processed data predates the configurable-lag builder. Verify
    # its 48-hour development inputs are byte-identical to those used in training.
    for split in ("train", "validation"):
        for kind in ("features", "labels"):
            old_name = f"{split}.{kind}.jsonl"
            fit_name = f"{split}.lag-48h.features.jsonl" if kind == "features" else old_name
            if manifest["files"][old_name]["sha256"] != artifact["provenance"]["inputFiles"][fit_name]["sha256"]:
                raise ValueError("Processed development inputs differ from model provenance")
    if manifest["splits"]["test"]["bySeason"] != plan["expectedGamesBySeason"]:
        raise ValueError("Manifest coverage differs from the declared test sample")
    for name, expected in plan["testFiles"].items():
        if manifest["files"][name] != expected:
            raise ValueError("Test file identity differs from frozen plan")
    # Validate the saved baseline without fitting it or using any test outcomes.
    scoring.score(artifact["baselineProbabilities"], "homeWin")


def validate_features(rows, artifact, plan):
    counts = Counter(str(row["season"]) for row in rows)
    if dict(counts) != plan["expectedGamesBySeason"]:
        raise ValueError("Test rows must cover every declared season and game")
    ids = [row["eventId"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate test event ID")
    for row in rows:
        scoring.feature_vector(row["features"], artifact["featureNames"])
        cutoff, kickoff = timestamp(row["featureCutoffAt"]), timestamp(row["kickoffAt"])
        if kickoff - cutoff != timedelta(hours=plan["forecastLeadHours"]):
            raise ValueError("Invalid test feature cutoff")
        if cutoff <= timestamp(artifact["trainingDataThroughAssumed"]):
            raise ValueError("Test cutoff overlaps training data")
        if row["season"] <= max(artifact["selectionSeasons"]):
            raise ValueError("Test season overlaps model selection")
        if type(row["week"]) is not int or not 1 <= row["week"] <= 18:
            raise ValueError("Invalid test week")
        if row["eventId"].split("_")[:2] != [str(row["season"]), f'{row["week"]:02d}']:
            raise ValueError("Event ID disagrees with season/week")
        for side in ("home", "away"):
            proof = row["evidence"][side]
            available = proof["latestAssumedResultAvailability"]
            if available is not None and timestamp(available) > cutoff:
                raise ValueError("Test features contain a result after their cutoff")
            for event in proof["resultGameIds"]:
                prior = tuple(map(int, event.split("_")[:2]))
                if prior >= (row["season"], row["week"]):
                    raise ValueError("Test features contain same-week or future results")
    return sorted(rows, key=lambda row: (row["kickoffAt"], row["eventId"]))


def join_outcomes(rows, labels):
    by_id = {label["eventId"]: label for label in labels}
    if len(by_id) != len(labels) or set(by_id) != {row["eventId"] for row in rows}:
        raise ValueError("Test labels must match feature IDs exactly once")
    outcomes = []
    for row in rows:
        label = by_id[row["eventId"]]
        if any(type(label[key]) is not int or label[key] < 0 for key in ("homeScore", "awayScore")):
            raise ValueError("Invalid test score")
        h, a = label["homeScore"], label["awayScore"]
        outcome = "tie" if h == a else "homeWin" if h > a else "awayWin"
        if label["outcome"] != outcome:
            raise ValueError("Test outcome contradicts scores")
        outcomes.append(outcome)
    return outcomes


def metrics(rows, probabilities, outcomes, baseline, plan):
    result = scoring.evaluate_predictions(probabilities, outcomes, baseline)
    result["classCounts"] = {key: Counter(outcomes)[key] for key in scoring.OUTCOMES}
    result["uncertainty"] = scoring.weekly_bootstrap(
        rows, probabilities, outcomes, baseline, plan["bootstrap"]["draws"], plan["bootstrap"]["seed"])
    result["uncertainty"]["interpretation"] = (
        "Conditional on this frozen model and corrected source snapshot. Resamples whole season-week blocks; "
        "does not account for training uncertainty, dependence across weeks, or unknown historical availability.")
    result["calibrationBins"] = scoring.calibration(probabilities, outcomes)
    return result


def readable_report(report):
    overall = report["overall"]
    model, baseline = overall["model"], overall["baseline"]
    delta = overall["improvement"]["logLoss"]
    low, high = overall["uncertainty"]["improvementIntervals"]["logLoss"]
    conclusion = ("The interval includes zero, so this analysis does not clearly distinguish an improvement from sampling variation."
                  if low <= 0 <= high else "The entire interval favors the frozen model over the frequency baseline on this sample."
                  if low > 0 else "The entire interval favors the frequency baseline over the frozen model on this sample.")
    lines = ["# NFL outcome model v1 — final test", "",
             f'Evaluated {report["evaluatedAt"]}. All {model["games"]} reserved regular-season games from 2024–2025 are included.', "",
             "## Overall results", "",
             f'- Outcome accuracy: **{model["accuracy"]:.1%}** ({model["correct"]}/{model["games"]}), versus **{baseline["accuracy"]:.1%}** ({baseline["correct"]}/{baseline["games"]}) for the unchanged training-frequency baseline.',
             f'- Log loss (primary metric; lower is better): **{model["logLoss"]:.6f}**, baseline **{baseline["logLoss"]:.6f}**. Baseline minus model: {delta:.6f} ({delta / baseline["logLoss"]:.1%} relative).',
             f'- Unscaled three-class Brier score (0–2; lower is better): **{model["brier"]:.6f}**, baseline **{baseline["brier"]:.6f}**.',
             f'- Forecast coverage: {model["coverage"]:.1%}. No games were excluded based on confidence or result.',
             f'- Exploratory 95% paired week-bootstrap interval for log-loss improvement: **[{low:.6f}, {high:.6f}]**.',
             f'- Outcome counts: {json.dumps(overall["classCounts"])}.', "", conclusion, "", "## Results by season", ""]
    for season, values in report["bySeason"].items():
        m, b = values["model"], values["baseline"]
        lines.append(f'- **{season}:** {m["correct"]}/{m["games"]} correct ({m["accuracy"]:.1%}), baseline {b["accuracy"]:.1%}; log loss {m["logLoss"]:.6f} versus {b["logLoss"]:.6f}; Brier {m["brier"]:.6f} versus {b["brier"]:.6f}.')
    lines += ["", "## What was frozen", "",
              f'- Model: `{report["modelVersion"]}`, SHA-256 `{report["modelSha256"]}`.',
              '- Coefficients, scaling, class order, C = 0.01, baseline probabilities, and the 48-hour result-availability assumption were unchanged.',
              '- The evaluation plan was saved before opening test outcomes. Every prediction was saved before the outcome file was read.',
              '- This evaluation has no training, parameter search, or recalibration step. Coefficients remain fitted to 2015–2022; 2023 selected C.',
              '- The original training artifacts were preserved. The 2024–2025 outcomes are now exposed and cannot be reused as an untouched test for future tuning.',
              "", "## Interpretation and limits", "",
              'These are retrospective game-outcome forecasts created today, using a corrected source snapshot. The simulated feature cutoff is 24 hours before kickoff; unknown publication times remain modeled with a 48-hour delay. Earlier test-period results can enter later games’ features after that cutoff, while model coefficients remain fixed.',
              "", 'The uncertainty interval resamples whole season-week blocks. It does not capture all dependence between games, uncertainty from training, or source-timing errors. Per-class calibration and counts are in `report.json`; rare ties limit what can be concluded about tie probabilities.',
              "", 'This comparison measures improvement over historical outcome frequencies. It does not compare against sportsbook prices or establish betting profitability.',
              "", 'The next engineering step is prospective evaluation: build features from timestamped snapshots and save forecasts before kickoff, then score them after verified final results. These predictions are local artifacts, not live predictions on the hosted website.',
              "", "## Artifacts", "",
              '`plan.json` fixes the test design. `frozen-model.json` is an exact model copy. `predictions.jsonl` contains all probabilities without outcomes. `exposure.json` marks the first scoring attempt. `scored-predictions.jsonl` joins outcomes by ID. `report.json` includes aggregate, seasonal, weekly, calibration, and uncertainty results. `artifacts.json` records output checksums.', ""]
    return "\n".join(lines)


def evaluate(run_dir, data_dir, plan_path):
    output = run_dir / "holdout-2024-2025"
    if output.exists():
        raise ValueError("Holdout run already exists; read its report rather than exposing the test again")
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    run_manifest = json.loads((run_dir / "artifacts.json").read_bytes())
    model_bytes = checked_bytes(run_dir / "model.json", run_manifest["files"]["model.json"])
    if sha(model_bytes) != plan["modelSha256"]:
        raise ValueError("Model differs from the frozen evaluation plan")
    artifact = json.loads(model_bytes)
    inference_bytes = Path(scoring.__file__).read_bytes()
    if sha(inference_bytes) != artifact["provenance"]["codeSha256"]["model.py"]:
        raise ValueError("Inference/scoring implementation has changed since model training")
    manifest_bytes = (data_dir / "manifest.json").read_bytes()
    if sha(manifest_bytes) != plan["processedManifestSha256"]:
        raise ValueError("Processed manifest differs from the frozen evaluation plan")
    manifest = json.loads(manifest_bytes)
    validate_contract(artifact, manifest, plan)
    feature_bytes = checked_bytes(data_dir / "test.features.jsonl", plan["testFiles"]["test.features.jsonl"])
    rows = validate_features([json.loads(line) for line in feature_bytes.splitlines()], artifact, plan)
    probabilities = scoring.predict_many(artifact, [row["features"] for row in rows])
    generated_at = now()
    predictions = [{"eventId": row["eventId"], "season": row["season"], "week": row["week"],
                    "modelVersion": artifact["modelVersion"], "mode": "historical-simulation",
                    "generatedAt": generated_at, "kickoffAt": row["kickoffAt"],
                    "simulatedFeatureCutoffAt": row["featureCutoffAt"], "probabilities": p}
                   for row, p in zip(rows, probabilities)]
    prediction_bytes = b"".join(json.dumps(row, separators=(",", ":"), allow_nan=False).encode() + b"\n" for row in predictions)
    output.mkdir(exist_ok=False)
    outputs = {"plan.json": plan_bytes, "frozen-model.json": model_bytes, "predictions.jsonl": prediction_bytes}
    for name, body in outputs.items():
        write_once(output / name, body)
    # The exposure marker remains if scoring fails. A retry is not a new test.
    outputs["exposure.json"] = encode({"firstScoringAttemptAt": now(), "modelSha256": sha(model_bytes),
                                       "predictionsSha256": sha(prediction_bytes), "testSeasons": plan["testSeasons"],
                                       "futureUse": "exposed evaluation data, never an untouched test again"})
    write_once(output / "exposure.json", outputs["exposure.json"])
    label_bytes = checked_bytes(data_dir / "test.labels.jsonl", plan["testFiles"]["test.labels.jsonl"])
    outcomes = join_outcomes(rows, [json.loads(line) for line in label_bytes.splitlines()])
    baseline = artifact["baselineProbabilities"]
    overall = metrics(rows, probabilities, outcomes, baseline, plan)
    by_season, by_week = {}, {}
    for season in plan["testSeasons"]:
        indices = [i for i, row in enumerate(rows) if row["season"] == season]
        by_season[str(season)] = metrics([rows[i] for i in indices], [probabilities[i] for i in indices],
                                        [outcomes[i] for i in indices], baseline, plan)
    for season, week in sorted({(row["season"], row["week"]) for row in rows}):
        indices = [i for i, row in enumerate(rows) if (row["season"], row["week"]) == (season, week)]
        by_week[f"{season}_{week:02d}"] = scoring.evaluate_predictions(
            [probabilities[i] for i in indices], [outcomes[i] for i in indices], baseline)
    # Recheck the saved model after scoring; no original file is ever written.
    if (run_dir / "model.json").read_bytes() != model_bytes:
        raise ValueError("Original model changed during evaluation")
    report = {"schemaVersion": 1, "mode": "historical-simulation", "stage": "frozen-final-test",
              "modelVersion": artifact["modelVersion"], "modelSha256": sha(model_bytes), "evaluatedAt": now(),
              "finalTestEvaluated": True, "finalTestSeasons": plan["testSeasons"], "refitted": False,
              "overall": overall, "bySeason": by_season, "byWeek": by_week,
              "baselineProbabilities": baseline, "holdoutStatus": "exposed; unavailable as an untouched test for future tuning",
              "provenance": {"planSha256": sha(plan_bytes), "processedManifestSha256": sha(manifest_bytes),
                             "testFiles": plan["testFiles"], "sourceSha256": manifest["source"]["sha256"],
                             "processedBuilderSha256": manifest["builderSha256"],
                             "trainingBuilderSha256": artifact["provenance"]["builderSha256"],
                             "developmentInputHashesMatch": True, "inferenceSha256": sha(inference_bytes),
                             "evaluatorSha256": sha(Path(__file__).read_bytes()), "predictionsSha256": sha(prediction_bytes)},
              "runtime": {"python": platform.python_version(), "trainingLibrariesRequired": False}}
    outputs["report.json"] = encode(report)
    outputs["REPORT.md"] = readable_report(report).encode()
    outputs["scored-predictions.jsonl"] = b"".join(
        json.dumps({**prediction, "observedOutcome": outcome,
                    "modelScore": scoring.score(prediction["probabilities"], outcome),
                    "baselineScore": scoring.score(baseline, outcome)}, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        for prediction, outcome in zip(predictions, outcomes))
    for name in ("report.json", "REPORT.md", "scored-predictions.jsonl"):
        write_once(output / name, outputs[name])
    write_once(output / "artifacts.json", encode({"schemaVersion": 1, "completedAt": now(),
                                                 "files": {name: {"sha256": sha(body), "bytes": len(body)} for name, body in outputs.items()}}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "runs/outcome-logit-v1")
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/v1")
    args = parser.parse_args()
    try:
        report = evaluate(args.run, args.data, ROOT / "holdout-plan.json")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Evaluation failed: {exc}\n")
    print(json.dumps({"report": str(args.run / "holdout-2024-2025/REPORT.md"),
                      "model": report["overall"]["model"], "baseline": report["overall"]["baseline"],
                      "improvement": report["overall"]["improvement"],
                      "uncertainty": report["overall"]["uncertainty"]}, indent=2))


if __name__ == "__main__":
    main()
