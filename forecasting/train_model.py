"""Train a chronological NFL outcome model; never open the final test files."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import build_features
from model import (OUTCOMES, calibration, evaluate_predictions, feature_vector,
                   predict_many, weekly_bootstrap)

ROOT = Path(__file__).resolve().parent
FEATURE_NAMES = build_features.FEATURE_NAMES


def digest(body):
    return hashlib.sha256(body).hexdigest()


def json_body(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def parse_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Expected a UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_checked(folder, filename, manifest):
    body = (folder / filename).read_bytes()
    entry = manifest["files"][filename]
    if digest(body) != entry["sha256"]:
        raise ValueError(f"Checksum mismatch: {filename}")
    rows = [json.loads(line) for line in body.decode().splitlines()]
    if len(rows) != entry["rows"]:
        raise ValueError(f"Row count mismatch: {filename}")
    return rows


def join_split(rows, labels, seasons):
    if not rows or {row["season"] for row in rows} != set(seasons):
        raise ValueError("Split contains missing or forbidden seasons")
    ids = [row["eventId"] for row in rows]
    label_ids = [row["eventId"] for row in labels]
    if len(set(ids)) != len(ids) or len(set(label_ids)) != len(label_ids) or set(ids) != set(label_ids):
        raise ValueError("Feature and label IDs must form a unique one-to-one join")
    by_id = {label["eventId"]: label for label in labels}
    ordered = sorted(rows, key=lambda row: (row["kickoffAt"], row["eventId"]))
    targets = []
    for row in ordered:
        event_id = row["eventId"]
        feature_vector(row["features"], FEATURE_NAMES)
        kickoff, cutoff = parse_time(row["kickoffAt"]), parse_time(row["featureCutoffAt"])
        if kickoff - cutoff != timedelta(hours=24):
            raise ValueError(f"{event_id}: expected a 24-hour pregame feature cutoff")
        if type(row["week"]) is not int or not 1 <= row["week"] <= (18 if row["season"] >= 2021 else 17):
            raise ValueError(f"{event_id}: invalid NFL week")
        if event_id.split("_")[:2] != [str(row["season"]), f'{row["week"]:02d}']:
            raise ValueError(f"{event_id}: event ID does not match season/week")
        for side in ("home", "away"):
            proof = row["evidence"][side]
            available = proof["latestAssumedResultAvailability"]
            if available is not None and parse_time(available) > cutoff:
                raise ValueError(f"{event_id}: result availability exceeds the feature cutoff")
            for prior_id in proof["resultGameIds"]:
                season, week = map(int, prior_id.split("_")[:2])
                if (season, week) >= (row["season"], row["week"]):
                    raise ValueError(f"{event_id}: same-week or future result in feature history")
        label = by_id[event_id]
        if any(type(label[key]) is not int or label[key] < 0 for key in ("homeScore", "awayScore")):
            raise ValueError(f"{event_id}: invalid score")
        expected = "tie" if label["homeScore"] == label["awayScore"] else "homeWin" if label["homeScore"] > label["awayScore"] else "awayWin"
        if label["outcome"] != expected:
            raise ValueError(f"{event_id}: label disagrees with final scores")
        targets.append(expected)
    return ordered, targets


def fit_model(rows, targets, c):
    if set(targets) != set(OUTCOMES):
        raise ValueError("Training must include all three outcomes")
    x = np.array([feature_vector(row["features"], FEATURE_NAMES) for row in rows], dtype=float)
    estimator = make_pipeline(StandardScaler(), LogisticRegression(
        C=c, solver="lbfgs", l1_ratio=0, class_weight=None, max_iter=2000, tol=1e-9))
    with warnings.catch_warnings(), threadpool_limits(limits=1):
        warnings.simplefilter("error", ConvergenceWarning)
        estimator.fit(x, targets)
    scaler, classifier = estimator.steps[0][1], estimator.steps[1][1]
    artifact = {
        "schemaVersion": 1, "kind": "multinomial-logistic-regression",
        "featureNames": FEATURE_NAMES, "classes": classifier.classes_.tolist(),
        "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
        "coefficients": classifier.coef_.tolist(), "intercepts": classifier.intercept_.tolist(),
        "parameters": {"C": c, "regularization": "L2", "solver": "lbfgs", "tol": 1e-9,
                       "maxIter": 2000, "classWeight": None},
        "iterations": classifier.n_iter_.tolist(),
        "constantFeatures": [name for name, variance in zip(FEATURE_NAMES, scaler.var_) if variance == 0],
    }
    return artifact, estimator


def compare_probabilities(reference, alternative):
    changes = [max(abs(a[key] - b[key]) for key in OUTCOMES) for a, b in zip(reference, alternative)]
    if len(reference) != len(alternative):
        raise ValueError("Timing predictions have different lengths")
    return {"gamesChanged": sum(x > 1e-12 for x in changes), "comparisonTolerance": 1e-12,
            "maxAbsoluteProbabilityChange": max(changes, default=0)}


def report_markdown(report):
    selected = report["selectedValidation"]
    model, baseline = selected["model"], selected["baseline"]
    improvement = selected["improvement"]
    interval = report["uncertainty"]["improvementIntervals"]["logLoss"]
    return f'''# NFL outcome model v1 — training report

This is a retrospective development experiment, generated {report["generatedAt"]}. It is not a record of forecasts issued before those games.

## Data and method

- Training: {report["trainingGames"]:,} regular-season games, 2015–2022. Validation: all {report["validationGames"]} regular-season games in 2023.
- Model: three-outcome logistic regression using 11 pregame features, with scaling fitted only on training rows. Constant input columns: {', '.join(report["constantFeatures"]) or 'none'}.
- Settings were declared in `training-plan.json` before fitting: C = 0.01, 0.1, 1, 10. Selected C = {report["selectedC"]:g}, using lowest validation log loss.
- Baseline: the empirical home-win, away-win, and tie frequencies from training results only.
- Final test seasons 2024–2025 were not opened by this training run. No random train/test split or final-test tuning was used.

## 2023 validation results

- Model accuracy: **{model["accuracy"]:.1%}** ({model["correct"]}/{model["games"]}); baseline: **{baseline["accuracy"]:.1%}** ({baseline["correct"]}/{baseline["games"]}). Both classify every game.
- Log loss, lower is better: model **{model["logLoss"]:.6f}**, baseline **{baseline["logLoss"]:.6f}**. Improvement: {improvement["logLoss"]:.6f} ({improvement["logLoss"] / baseline["logLoss"]:.1%} relative).
- Unscaled three-class Brier score (0–2), lower is better: model **{model["brier"]:.6f}**, baseline **{baseline["brier"]:.6f}**.
- Exploratory 95% whole-week bootstrap interval for log-loss improvement: [{interval[0]:.6f}, {interval[1]:.6f}]. It does not adjust for model selection, training uncertainty, or correlation across weeks.
- Training class counts: {json.dumps(report["trainingClassCounts"])}. Validation class counts: {json.dumps(report["validationClassCounts"])}.

The validation season selected the model settings, so these are development results, not an unbiased final-test estimate. Accuracy here concerns game outcomes; this experiment has no price-based benchmark or profitability evaluation. Rare ties have limited training support. Calibration-bin counts and rates are in `report.json`; no probability recalibration was fitted.

## Result-delay sensitivity

The reference remains 48 hours. Each alternative is evaluated with the reference model held fixed, then with a model refitted at the same selected C. No alternative delay is selected using these scores.

''' + "\n".join(
        f'- **{lag} hours:** fixed-model log loss {data["fixedModel"]["model"]["logLoss"]:.6f}; same-C refit log loss {data["refitModel"]["model"]["logLoss"]:.6f}; maximum probability movement versus reference {data["fixedPredictionChange"]["maxAbsoluteProbabilityChange"]:.6f} fixed / {data["refitPredictionChange"]["maxAbsoluteProbabilityChange"]:.6f} refitted.'
        for lag, data in report["timingSensitivity"].items()) + '''

Similar scores across delays do not establish when historical results were actually published. All inputs still come from a corrected historical snapshot, using assumed availability and a simulated 24-hour pregame cutoff.

## Saved artifacts and next step

`model.json` saves coefficients, scaling, class order, source provenance, actual training time, and selection metadata. `validation.predictions.jsonl` saves every reference prediction with separate actual generation and simulated cutoff timestamps. `timing.predictions.jsonl` saves both comparisons for every delay. `report.json` includes every candidate's scores, week-level results, calibration bins, and runtime versions. `artifacts.json` records checksums of every run output.

The next evaluation should freeze this model and score the reserved 2024–2025 period once, without retuning from those results. The model remains local; it is not connected to the hosted dashboard or to a live forecast service.
'''


def train(input_dir, output_dir, plan_path):
    if output_dir.exists():
        raise ValueError("Output already exists; use a new directory to preserve previous runs")
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    # The split contract is deliberately fixed; this command cannot evaluate test seasons.
    if (plan["trainingSeasons"] != list(range(2015, 2023)) or plan["validationSeasons"] != [2023]
            or plan["finalTestEvaluation"] is not False or plan["referenceLagHours"] != 48
            or plan["timingScenariosHours"] != [24, 48, 72]):
        raise ValueError("Unsupported development experiment plan")
    if not plan["candidateC"] or not all(type(c) in (int, float) and np.isfinite(c) and c > 0 for c in plan["candidateC"]):
        raise ValueError("Invalid regularization candidates")
    manifest_bytes = (input_dir / "timing-sensitivity.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest["finalTestPeriodIncluded"] is not False or manifest["baselineLagHours"] != 48
            or manifest["scenarioLagHours"] != [24, 48, 72] or manifest["forecastLeadHours"] != 24
            or manifest["sameWeekResultsExcluded"] is not True):
        raise ValueError("Input manifest does not match the development plan")
    if digest(Path(build_features.__file__).read_bytes()) != manifest["builderSha256"]:
        raise ValueError("Feature builder changed; rebuild the timing study before training")
    labels = {split: read_checked(input_dir, f"{split}.labels.jsonl", manifest) for split in ("train", "validation")}
    scenarios = {}
    for lag in plan["timingScenariosHours"]:
        scenarios[lag] = {}
        for split, seasons in (("train", plan["trainingSeasons"]), ("validation", plan["validationSeasons"])):
            rows = read_checked(input_dir, f"{split}.lag-{lag}h.features.jsonl", manifest)
            scenarios[lag][split] = join_split(rows, labels[split], seasons)
    train_rows, train_y = scenarios[48]["train"]
    val_rows, val_y = scenarios[48]["validation"]
    training_through = max(parse_time(row["kickoffAt"]) for row in train_rows) + timedelta(hours=48)
    if training_through >= min(parse_time(row["featureCutoffAt"]) for row in val_rows):
        raise ValueError("Training results overlap validation feature cutoffs")
    for scenario in scenarios.values():
        for split in ("train", "validation"):
            reference_rows, reference_y = scenarios[48][split]
            rows, y = scenario[split]
            if [r["eventId"] for r in rows] != [r["eventId"] for r in reference_rows] or y != reference_y:
                raise ValueError("Timing scenarios must have aligned events and outcomes")
    counts = Counter(train_y)
    baseline = {key: counts[key] / len(train_y) for key in OUTCOMES}
    started = build_features.iso(datetime.now(timezone.utc))
    candidates, models, predictions = [], {}, {}
    for c in plan["candidateC"]:
        artifact, estimator = fit_model(train_rows, train_y, c)
        p = predict_many(artifact, [row["features"] for row in val_rows])
        # Assert exported coefficients retain scikit-learn probability semantics/class order.
        expected = estimator.predict_proba(np.array([feature_vector(r["features"], FEATURE_NAMES) for r in val_rows]))
        exported = np.array([[row[key] for key in artifact["classes"]] for row in p])
        if not np.allclose(expected, exported, rtol=0, atol=1e-12):
            raise ValueError("Exported inference does not match fitted estimator")
        candidates.append({"C": c, "iterations": artifact["iterations"], "validation": evaluate_predictions(p, val_y, baseline)})
        models[c], predictions[c] = artifact, p
    winner = min(candidates, key=lambda row: (row["validation"]["model"]["logLoss"], row["C"]))
    c = winner["C"]
    selected, p = models[c], predictions[c]
    input_files = {name: entry for name, entry in manifest["files"].items()
                   if name.startswith(("train.", "validation."))}
    provenance = {"inputManifestSha256": digest(manifest_bytes), "inputFiles": input_files,
                  "sourceSha256": manifest["sourceSha256"], "sourceRetrievedAt": manifest["sourceRetrievedAt"],
                  "builderSha256": manifest["builderSha256"], "planSha256": digest(plan_bytes),
                  "codeSha256": {name: digest((ROOT / name).read_bytes()) for name in ("train_model.py", "model.py")}}
    generated = build_features.iso(datetime.now(timezone.utc))
    selected.update({"modelVersion": plan["version"], "trainedAt": generated, "trainingStartedAt": started,
                     "datasetKind": "retrospective-reconstruction", "referenceLagHours": 48,
                     "trainingSeasons": plan["trainingSeasons"], "selectionSeasons": [2023],
                     "trainingDataThroughAssumed": build_features.iso(training_through),
                     "baselineProbabilities": baseline, "provenance": provenance})
    timing, timing_predictions = {}, []
    for lag, scenario in scenarios.items():
        tr, ty = scenario["train"]
        vr, vy = scenario["validation"]
        fixed_p = predict_many(selected, [row["features"] for row in vr])
        refit = selected if lag == 48 else fit_model(tr, ty, c)[0]
        refit_p = predict_many(refit, [row["features"] for row in vr])
        timing[str(lag)] = {"fixedModel": evaluate_predictions(fixed_p, vy, baseline),
                            "refitModel": evaluate_predictions(refit_p, vy, baseline),
                            "fixedPredictionChange": compare_probabilities(p, fixed_p),
                            "refitPredictionChange": compare_probabilities(p, refit_p)}
        for row, fixed, fitted in zip(vr, fixed_p, refit_p):
            timing_predictions.append({"eventId": row["eventId"], "mode": "historical-simulation",
                                       "kickoffAt": row["kickoffAt"], "simulatedFeatureCutoffAt": row["featureCutoffAt"],
                                       "lagHours": lag, "fixedModelProbabilities": fixed, "refitModelProbabilities": fitted})
    generated = build_features.iso(datetime.now(timezone.utc))
    report = {
        "schemaVersion": 1, "modelVersion": plan["version"], "mode": "historical-simulation",
        "generatedAt": generated, "trainingStartedAt": started, "finalTestEvaluated": False,
        "reservedFinalTestSeasons": [2024, 2025], "trainingGames": len(train_y), "validationGames": len(val_y),
        "trainingClassCounts": {key: counts[key] for key in OUTCOMES},
        "validationClassCounts": {key: Counter(val_y)[key] for key in OUTCOMES},
        "baselineProbabilities": baseline, "plan": plan, "provenance": provenance,
        "constantFeatures": selected["constantFeatures"],
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "packages": {name: importlib.metadata.version(name) for name in ("scikit-learn", "numpy", "scipy", "joblib", "threadpoolctl", "narwhals", "cloudpickle")}},
        "candidates": candidates, "selectedC": c, "selectedValidation": winner["validation"],
        "calibrationBins": calibration(p, val_y), "timingSensitivity": timing,
        "uncertainty": weekly_bootstrap(val_rows, p, val_y, baseline, plan["bootstrap"]["draws"], plan["bootstrap"]["seed"]),
        "byWeek": {str(week): evaluate_predictions([pr for row, pr in zip(val_rows, p) if row["week"] == week],
                                                    [y for row, y in zip(val_rows, val_y) if row["week"] == week], baseline)
                   for week in sorted({row["week"] for row in val_rows})},
        "limitations": ["Validation selected C, so these metrics have selection optimism.",
                        "Corrected retrospective source; historical publication times are unknown.",
                        "Simple regular-season history only; no injuries, players, weather or opponent adjustment.",
                        "Rare ties have limited support; calibration is descriptive, not independently validated.",
                        "No sportsbook-price comparison or profitability evaluation.",
                        "No live integration or final-test performance evaluation in this run."],
    }
    validation_predictions = [{"eventId": row["eventId"], "mode": "historical-simulation",
                               "modelVersion": plan["version"], "generatedAt": generated,
                               "simulatedFeatureCutoffAt": row["featureCutoffAt"], "kickoffAt": row["kickoffAt"],
                               "probabilities": pr, "observedOutcome": y}
                              for row, pr, y in zip(val_rows, p, val_y)]
    for row in timing_predictions:
        row["generatedAt"] = generated
    artifacts = {"model.json": json_body(selected), "report.json": json_body(report),
                 "training-plan.json": plan_bytes, "REPORT.md": report_markdown(report).encode()}
    for name, rows in (("validation.predictions.jsonl", validation_predictions), ("timing.predictions.jsonl", timing_predictions)):
        artifacts[name] = "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows).encode()
    artifacts["artifacts.json"] = json_body({"schemaVersion": 1, "generatedAt": generated,
                                             "files": {name: {"sha256": digest(body), "bytes": len(body)} for name, body in artifacts.items()}})
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, body in artifacts.items():
        with (output_dir / name).open("xb") as handle:
            handle.write(body)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/experiments/timing-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/outcome-logit-v1")
    args = parser.parse_args()
    try:
        report = train(args.input, args.output, ROOT / "training-plan.json")
    except (OSError, ValueError, KeyError, TypeError, ConvergenceWarning) as exc:
        parser.exit(1, f"Training failed: {exc}\n")
    print(json.dumps({"output": str(args.output.resolve()), "selectedC": report["selectedC"],
                      "validation": report["selectedValidation"], "finalTestEvaluated": False}, indent=2))


if __name__ == "__main__":
    main()
