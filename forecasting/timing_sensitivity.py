"""Compare input sensitivity to result delays; no models or test-label inspection."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

import build_features as pipeline

LAGS = (24, 48, 72)


def compare_rows(reference, alternative):
    by_id = {row["eventId"]: row for row in alternative}
    if len(by_id) != len(alternative) or set(by_id) != {row["eventId"] for row in reference}:
        raise ValueError("Timing scenarios do not contain identical games")
    changes, history_changes = [], 0
    counts = Counter()
    maximum = {name: 0 for name in pipeline.FEATURE_NAMES}
    for base in reference:
        other = by_id[base["eventId"]]
        if any(base["evidence"][side]["resultGameIds"] != other["evidence"][side]["resultGameIds"] for side in ("home", "away")):
            history_changes += 1
        differences = {}
        for name in pipeline.FEATURE_NAMES:
            before, after = base["features"][name], other["features"][name]
            if before != after:
                counts[name] += 1
                differences[name] = {"baseline48h": before, "scenario": after}
                if before is not None and after is not None:
                    maximum[name] = max(maximum[name], abs(after - before))
        if differences:
            changes.append({"eventId": base["eventId"], "season": base["season"], "week": base["week"],
                            "featureCutoffAt": base["featureCutoffAt"], "changes": differences})
    return {"games": len(reference), "gamesWithChangedFeatures": len(changes),
            "changedFraction": len(changes) / len(reference) if reference else None,
            "gamesWithChangedHistories": history_changes,
            "changedCells": sum(counts.values()),
            "byFeature": {name: {"changedGames": counts[name], "maxAbsoluteChange": maximum[name]} for name in pipeline.FEATURE_NAMES},
            "changedGames": changes}


def run(input_path, provenance_path, output_path):
    raw = input_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("sha256") != digest:
        raise ValueError("Raw data checksum does not match provenance")
    # Filter before score parsing: the final 2024–2025 test period is excluded.
    rows = [row for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if 2014 <= int(row["season"]) <= 2023 and row["game_type"] == "REG"]
    if {int(row["season"]) for row in rows} != set(range(2014, 2024)):
        raise ValueError("Expected 2014 warm-up and all 2015–2023 development seasons")
    scenarios = {lag: pipeline.build_records(pipeline.normalize(rows, lag)) for lag in LAGS}
    baseline = scenarios[48]
    comparisons = {}
    files = {}
    for lag in LAGS:
        comparisons[str(lag)] = {}
        for split in ("train", "validation"):
            alternative = scenarios[lag][split]
            if alternative["labels"] != baseline[split]["labels"]:
                raise ValueError("Timing changes altered targets")
            comparisons[str(lag)][split] = compare_rows(baseline[split]["features"], alternative["features"])
            files[f"{split}.lag-{lag}h.features.jsonl"] = alternative["features"]
    for split in ("train", "validation"):
        files[f"{split}.labels.jsonl"] = baseline[split]["labels"]
    report = {
        "schemaVersion": 1, "kind": "feature-timing-sensitivity",
        "createdAt": pipeline.iso(datetime.now(timezone.utc)),
        "sourceSha256": digest, "sourceRetrievedAt": provenance["retrievedAt"],
        "builderSha256": hashlib.sha256(Path(pipeline.__file__).read_bytes()).hexdigest(),
        "studyScriptSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baselineLagHours": 48, "scenarioLagHours": list(LAGS),
        "forecastLeadHours": pipeline.FORECAST_LEAD_HOURS,
        "sameWeekResultsExcluded": True,
        "finalTestPeriodIncluded": False,
        "modelMetrics": None,
        "comparisons": comparisons,
        "limitations": [
            "Measures feature sensitivity only. No trained model or accuracy comparison exists yet.",
            "All scenarios use the same latest corrected historical snapshot; none establishes original publication time.",
            "48 hours remains the reference assumption, not a setting selected for superior performance.",
            "Small input differences cannot establish small prediction differences or validate historical availability.",
        ],
        "files": {},
    }
    output_path.mkdir(parents=True, exist_ok=True)
    for name, records in files.items():
        body = "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in records).encode()
        (output_path / name).write_bytes(body)
        report["files"][name] = {"rows": len(records), "sha256": hashlib.sha256(body).hexdigest()}
    (output_path / "timing-sensitivity.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=pipeline.ROOT / "data/raw/nflverse-games.csv")
    parser.add_argument("--provenance", type=Path, default=pipeline.ROOT / "data/raw/nflverse-games.provenance.json")
    parser.add_argument("--output", type=Path, default=pipeline.ROOT / "data/experiments/timing-v1")
    args = parser.parse_args()
    try:
        report = run(args.input, args.provenance, args.output)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Timing study failed: {exc}\n")
    print(json.dumps({lag: {split: {key: values[key] for key in ("games", "gamesWithChangedFeatures", "gamesWithChangedHistories", "changedCells")}
                                 for split, values in splits.items()} for lag, splits in report["comparisons"].items()}, indent=2))


if __name__ == "__main__":
    main()
