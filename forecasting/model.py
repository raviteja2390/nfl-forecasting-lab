"""Portable JSON-model inference and historical scoring; standard library only."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

OUTCOMES = ("homeWin", "awayWin", "tie")
LOG_LOSS_FLOOR = 1e-15


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def feature_vector(features, names):
    if not isinstance(features, dict) or set(features) != set(names):
        raise ValueError("Features must exactly match the saved feature names")
    values = [features[name] for name in names]
    if not all(finite(value) for value in values):
        raise ValueError("Features must be finite numbers; missing values are not imputed")
    return values


def validate_model(model):
    if model.get("schemaVersion") != 1 or model.get("kind") != "multinomial-logistic-regression":
        raise ValueError("Unsupported model artifact")
    names = model.get("featureNames", [])
    classes = model.get("classes", [])
    if not names or not all(isinstance(n, str) and n for n in names) or len(set(names)) != len(names):
        raise ValueError("Invalid model feature names")
    if len(classes) != 3 or set(classes) != set(OUTCOMES):
        raise ValueError("Model must contain exactly three outcome classes")
    vectors = [model["mean"], model["scale"], *model["coefficients"]]
    if len(model["coefficients"]) != 3 or any(len(v) != len(names) for v in vectors):
        raise ValueError("Invalid model dimensions")
    if len(model["intercepts"]) != 3 or not all(finite(x) for v in vectors + [model["intercepts"]] for x in v):
        raise ValueError("Invalid model numbers")
    if any(x <= 0 for x in model["scale"]):
        raise ValueError("Model scales must be positive")


def predict_many(model, features):
    validate_model(model)
    distributions = []
    for values in features:
        vector = feature_vector(values, model["featureNames"])
        standardized = [(x - mean) / scale for x, mean, scale in zip(vector, model["mean"], model["scale"])]
        logits = [bias + sum(w * x for w, x in zip(weights, standardized))
                  for bias, weights in zip(model["intercepts"], model["coefficients"])]
        if not all(math.isfinite(x) for x in logits):
            raise ValueError("Feature magnitudes overflowed model inference")
        weights = [math.exp(x - max(logits)) for x in logits]
        distribution = dict(zip(model["classes"], [x / sum(weights) for x in weights]))
        distributions.append({name: distribution[name] for name in OUTCOMES})
    return distributions


def score(probabilities, outcome):
    if outcome not in OUTCOMES or set(probabilities) != set(OUTCOMES):
        raise ValueError("Unknown outcome or probability class")
    if not all(finite(p) and 0 <= p <= 1 for p in probabilities.values()) or abs(sum(probabilities.values()) - 1) > 1e-10:
        raise ValueError("Invalid probability distribution")
    leaders = [key for key, value in probabilities.items() if value == max(probabilities.values())]
    prediction = leaders[0] if len(leaders) == 1 else None
    return {
        "brier": sum((probabilities[key] - int(key == outcome)) ** 2 for key in OUTCOMES),
        "logLoss": -math.log(max(LOG_LOSS_FLOOR, probabilities[outcome])),
        "prediction": prediction,
        "correct": None if prediction is None else prediction == outcome,
    }


def aggregate(scores):
    classified = [row for row in scores if row["correct"] is not None]
    return {
        "games": len(scores),
        "brier": sum(row["brier"] for row in scores) / len(scores) if scores else None,
        "logLoss": sum(row["logLoss"] for row in scores) / len(scores) if scores else None,
        "accuracy": sum(row["correct"] for row in classified) / len(classified) if classified else None,
        "correct": sum(row["correct"] for row in classified),
        "classified": len(classified),
        "coverage": len(classified) / len(scores) if scores else None,
    }


def evaluate_predictions(probabilities, outcomes, baseline):
    if len(probabilities) != len(outcomes):
        raise ValueError("Predictions and outcomes must have identical lengths")
    model_rows = [score(p, outcome) for p, outcome in zip(probabilities, outcomes)]
    baseline_rows = [score(baseline, outcome) for outcome in outcomes]
    model, base = aggregate(model_rows), aggregate(baseline_rows)
    return {"model": model, "baseline": base,
            "improvement": {key: base[key] - model[key] if outcomes else None for key in ("brier", "logLoss")}}


def calibration(probabilities, outcomes):
    if len(probabilities) != len(outcomes):
        raise ValueError("Predictions and outcomes must have identical lengths")
    bins = {}
    for key in OUTCOMES:
        rows = []
        for index in range(10):
            members = [(p[key], int(outcome == key)) for p, outcome in zip(probabilities, outcomes)
                       if min(9, int(p[key] * 10)) == index]
            rows.append({"lower": index / 10, "upper": (index + 1) / 10,
                         "upperInclusive": index == 9, "count": len(members),
                         "meanProbability": sum(p for p, _ in members) / len(members) if members else None,
                         "observedRate": sum(y for _, y in members) / len(members) if members else None})
        bins[key] = rows
    return bins


def weekly_bootstrap(rows, probabilities, outcomes, baseline, draws, seed):
    if not rows or not len(rows) == len(probabilities) == len(outcomes):
        raise ValueError("Bootstrap requires nonempty aligned rows")
    blocks = defaultdict(list)
    for row, p, outcome in zip(rows, probabilities, outcomes):
        model, base = score(p, outcome), score(baseline, outcome)
        blocks[(row["season"], row["week"])].append({key: base[key] - model[key] for key in ("brier", "logLoss")})
    summaries = [(len(block), {key: sum(row[key] for row in block) for key in ("brier", "logLoss")})
                 for _, block in sorted(blocks.items())]
    rng = random.Random(seed)
    samples = {key: [] for key in ("brier", "logLoss")}
    for _ in range(draws):
        chosen = rng.choices(summaries, k=len(summaries))
        count = sum(n for n, _ in chosen)
        for key in samples:
            samples[key].append(sum(sums[key] for _, sums in chosen) / count)

    def quantile(values, p):
        ordered = sorted(values)
        at = (len(ordered) - 1) * p
        left, right = math.floor(at), math.ceil(at)
        return ordered[left] + (ordered[right] - ordered[left]) * (at - left)

    return {"method": "paired whole-week percentile bootstrap", "draws": draws, "seed": seed,
            "weeks": len(blocks), "confidenceLevel": 0.95,
            "improvementIntervals": {key: [quantile(values, 0.025), quantile(values, 0.975)] for key, values in samples.items()},
            "interpretation": "Exploratory, conditional on the selected model. Does not adjust for validation selection, training uncertainty, or dependence across weeks."}


def main():
    parser = argparse.ArgumentParser(description="Infer from a saved model and one JSON features object (no network)")
    parser.add_argument("model", type=Path)
    parser.add_argument("features", type=Path)
    args = parser.parse_args()
    try:
        model = json.loads(args.model.read_text())
        features = json.loads(args.features.read_text())
        probabilities = predict_many(model, [features])[0]
        print(json.dumps({"modelVersion": model["modelVersion"], "probabilities": probabilities}, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Inference failed: {exc}\n")


if __name__ == "__main__":
    main()
