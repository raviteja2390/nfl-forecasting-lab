"""Compare two predeclared player challengers with the frozen team model."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import live
import model
from player_features import PlayerData, augment
import snapshots

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "runs/player-comparison-v1"
VERSIONS = {"player-form": "player-form-v1", "player-form-and-available-injuries": "player-availability-v1"}


def checked_rows(path, entry):
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != entry["sha256"]:
        raise ValueError("Processed input checksum mismatch")
    return [json.loads(line) for line in body.splitlines()]


def fit(rows, outcomes, names, c):
    x = np.array([model.feature_vector(row, names) for row in rows])
    pipe = make_pipeline(StandardScaler(), LogisticRegression(C=c, solver="lbfgs", l1_ratio=0, max_iter=2000, tol=1e-9))
    with warnings.catch_warnings(), threadpool_limits(limits=1):
        warnings.simplefilter("error", ConvergenceWarning)
        pipe.fit(x, outcomes)
    scaler, classifier = pipe.steps[0][1], pipe.steps[1][1]
    return {"schemaVersion": 1, "kind": "multinomial-logistic-regression", "featureNames": names,
            "classes": classifier.classes_.tolist(), "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
            "coefficients": classifier.coef_.tolist(), "intercepts": classifier.intercept_.tolist(),
            "parameters": {"C": c, "solver": "lbfgs", "regularization": "L2", "tol": 1e-9},
            "iterations": classifier.n_iter_.tolist()}


def compare(output=RUN):
    if output.exists():
        raise ValueError("Comparison already exists; preserve it rather than tuning from exposed results")
    plan_body = (ROOT / "player-plan.json").read_bytes()
    plan = json.loads(plan_body)
    data_root = ROOT / "data/processed/v1"
    manifest = json.loads((data_root / "manifest.json").read_text())
    rows, outcomes = {}, {}
    for split in ("train", "validation", "test"):
        rows[split] = checked_rows(data_root / f"{split}.features.jsonl", manifest["files"][f"{split}.features.jsonl"])
        labels = checked_rows(data_root / f"{split}.labels.jsonl", manifest["files"][f"{split}.labels.jsonl"])
        by_id = {row["eventId"]: row["outcome"] for row in labels}
        if len(by_id) != len(labels) or set(by_id) != {row["eventId"] for row in rows[split]}:
            raise ValueError("Player comparison requires an exact one-to-one label join")
        outcomes[split] = [by_id[row["eventId"]] for row in rows[split]]
    source = PlayerData(range(2014, 2026))
    baseline = json.loads(live.MODEL_PATH.read_text())
    reference_predictions = {split: model.predict_many(baseline, [row["features"] for row in values]) for split, values in rows.items()}
    baseline_metrics = {split: model.evaluate_predictions(reference_predictions[split], outcomes[split], baseline["baselineProbabilities"])["model"]
                        for split in ("validation", "test")}
    families, artifacts, predictions, feature_outputs = {}, {}, {}, {}
    for family in plan["families"]:
        augmented = {split: [augment(row, source, family)[0] for row in values] for split, values in rows.items()}
        names = list(augmented["train"][0])
        candidates, fitted = [], {}
        for c in plan["candidateC"]:
            artifact = fit(augmented["train"], outcomes["train"], names, c)
            p = model.predict_many(artifact, augmented["validation"])
            scores = model.evaluate_predictions(p, outcomes["validation"], baseline["baselineProbabilities"])["model"]
            candidates.append({"C": c, "validation": scores})
            fitted[c] = artifact
        selected = min(candidates, key=lambda value: (value["validation"]["logLoss"], value["C"]))
        artifact = fitted[selected["C"]]
        version = VERSIONS[family]
        artifact.update({"modelVersion": version, "family": family, "trainedAt": snapshots.now(),
                         "trainingSeasons": plan["trainingSeasons"], "selectionSeasons": [plan["selectionSeason"]],
                         "baselineProbabilities": baseline["baselineProbabilities"], "role": "prospective-shadow-only",
                         "provenance": {"planSha256": hashlib.sha256(plan_body).hexdigest(),
                                        "inputFiles": manifest["files"],
                                        "sourceReceipts": [{key: r[key] for key in ("kind", "key", "observedAt", "sha256", "sourceUrl")} for r in source.receipts],
                                        "codeSha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                                       for name in ("player_features.py", "compare_players.py", "model.py")}}})
        artifacts[version + ".json"] = live.encode(artifact)
        metrics = {}
        for split in ("validation", "test"):
            p = model.predict_many(artifact, augmented[split])
            predictions[(family, split)] = p
            metrics[split] = model.evaluate_predictions(p, outcomes[split], baseline["baselineProbabilities"])["model"]
        seasons = {}
        for season in (2024, 2025):
            indices = [i for i, row in enumerate(rows["test"]) if row["season"] == season]
            p = [predictions[(family, "test")][i] for i in indices]
            y = [outcomes["test"][i] for i in indices]
            reference = [reference_predictions["test"][i] for i in indices]
            seasons[str(season)] = {"player": model.evaluate_predictions(p, y, baseline["baselineProbabilities"])["model"],
                                   "teamOnly": model.evaluate_predictions(reference, y, baseline["baselineProbabilities"])["model"]}
        families[family] = {"modelVersion": version, "selectedC": selected["C"], "candidates": candidates,
                            "validation": metrics["validation"], "exploratory2024and2025": metrics["test"], "bySeason": seasons,
                            "validationChangeFromTeam": {"accuracy": metrics["validation"]["accuracy"] - baseline_metrics["validation"]["accuracy"],
                                                          "logLossImprovement": baseline_metrics["validation"]["logLoss"] - metrics["validation"]["logLoss"]},
                            "exploratoryChangeFromTeam": {"accuracy": metrics["test"]["accuracy"] - baseline_metrics["test"]["accuracy"],
                                                          "logLossImprovement": baseline_metrics["test"]["logLoss"] - metrics["test"]["logLoss"]}}
        for split in ("train", "validation", "test"):
            feature_outputs[f"{version}.{split}.features.jsonl"] = b"".join(json.dumps({"eventId": row["eventId"], "features": values}, separators=(",", ":"), allow_nan=False).encode() + b"\n" for row, values in zip(rows[split], augmented[split]))
    preferred = min(families, key=lambda family: (families[family]["validation"]["logLoss"], family))
    report = {"schemaVersion": 1, "createdAt": snapshots.now(), "kind": "player-model-development-comparison",
              "finalTestUntouched": False, "plan": plan, "teamOnly": baseline_metrics,
              "families": families, "preferredShadowBy2023LogLoss": preferred, "productionModel": "outcome-logit-v1",
              "playerDataAudit": source.audit,
              "limitations": ["2024–2025 was previously exposed; this is development evidence, not a new independent test.",
                              "2025 injury rows lack update timestamps and are unavailable in historical injury features.",
                              "Historical player stats use a 48-hour assumed availability delay and a corrected snapshot.",
                              "Historical injury date_modified is a reported update-time proxy, not a captured historical receipt.",
                              "Prior quarterback/leading receiver/rusher are inferred from earlier usage, not confirmed future starters.",
                              "This does not identify causal with/without player effects or estimate every player's individual value.",
                              "Player models remain shadow comparisons regardless of historical results."]}
    lines = ["# Team-only versus player-aware models", "", "Both challengers train on 2015–2022 and select regularization on 2023. The team-only model is unchanged.",
             "", "2024–2025 results below are exploratory because those seasons were already exposed during the original model test.", "",
             f'Team-only: 2023 accuracy {baseline_metrics["validation"]["accuracy"]:.1%}, log loss {baseline_metrics["validation"]["logLoss"]:.6f}; 2024–2025 accuracy {baseline_metrics["test"]["accuracy"]:.1%}, log loss {baseline_metrics["test"]["logLoss"]:.6f}.', ""]
    for family, info in families.items():
        v, t = info["validation"], info["exploratory2024and2025"]
        lines += [f'## {family}', "", f'2023: accuracy **{v["accuracy"]:.1%}** ({v["correct"]}/{v["games"]}), log loss **{v["logLoss"]:.6f}**.',
                  f'2024–2025: accuracy **{t["accuracy"]:.1%}** ({t["correct"]}/{t["games"]}), log loss **{t["logLoss"]:.6f}**.', ""]
        for year, scores in info["bySeason"].items():
            m = scores["player"]
            lines.append(f'- {year}: accuracy {m["accuracy"]:.1%}, log loss {m["logLoss"]:.6f}.')
        lines.append("")
    lines += ["## Interpretation", "", "Accuracy is compared on exactly the same games. Lower log loss and Brier scores indicate better probability forecasts. A higher win-pick accuracy alone does not establish better calibrated probabilities or profitability.", "",
              "The form model adds past quarterback efficiency, quarterback changes, and leading receiver/rusher usage and efficiency. The availability model also adds known Out/Doubtful/Questionable players' prior offensive usage shares and counts of offensive-line and defensive players listed Out. These are learned predictive associations, not causal individual player valuations.", "",
              "The 2025 injury file has no update timestamps, so its historical injury inputs are marked unavailable, rather than assuming healthy players or using after-the-fact statuses. Current reports captured now can be used prospectively with real receipt timestamps.", "",
              f'The preferred shadow model by 2023 log loss is **{preferred}**. The team-only model stays primary. Both challengers can be tracked on future games without changing the original predictions.', ""]
    artifacts.update(feature_outputs)
    artifacts["plan.json"] = plan_body
    artifacts["report.json"] = live.encode(report)
    artifacts["REPORT.md"] = "\n".join(lines).encode()
    for family in plan["families"]:
        records = [{"eventId": row["eventId"], "season": row["season"], "split": split,
                    "mode": "retrospective-development", "probabilities": p, "observedOutcome": y}
                   for split in ("validation", "test") for row, p, y in zip(rows[split], predictions[(family, split)], outcomes[split])]
        artifacts[VERSIONS[family] + ".predictions.jsonl"] = b"".join(json.dumps(row, separators=(",", ":"), allow_nan=False).encode() + b"\n" for row in records)
    output.mkdir(parents=True, exist_ok=False)
    for name, body in artifacts.items():
        snapshots.immutable_write(output / name, body)
    snapshots.immutable_write(output / "artifacts.json", live.encode({"files": {name: {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)} for name, body in artifacts.items()}}))
    return report


def publish_shadow(date):
    records = [json.loads(path.read_text()) for path in (live.LIVE / "forecasts/outcome-logit-v1").glob("*.json")]
    records = sorted([row for row in records if row["dateEastern"] == date], key=lambda row: row["eventId"])
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "publish"))
    parser.add_argument("--date")
    args = parser.parse_args()
    if args.command == "train":
        report = compare()
        print(json.dumps({"teamOnly": report["teamOnly"], "families": {key: {field: value[field] for field in ("selectedC", "validation", "exploratory2024and2025")} for key,value in report["families"].items()}}, indent=2))
    else:
        if not args.date:
            parser.error("--date is required")
        print(json.dumps(publish_shadow(args.date), indent=2))


if __name__ == "__main__":
    main()
