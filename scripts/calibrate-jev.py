#!/usr/bin/env python3
"""Check Jev against public, labeled examples; live by default, never auto-tune."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import jev_evaluation as jev


def prepare(split):
    entries = json.loads(jev.CALIBRATION.read_text())
    rows = []
    for entry in entries:
        if split != "all" and entry["split"] != split:
            continue
        for expected, candidate in entry["candidates"].items():
            requirements = [{"scope": entry["scope"], "requirement": entry["requirement"], "kind": entry.get("kind", "coverage")}]
            requests = jev.requests_for(entry["source"], candidate, requirements,
                                        common=entry["check"] != "fact_01")
            request = requests[0] if entry["check"] == "fact_01" else requests[-1]
            request["input"]["questions"] = {entry["check"]: request["input"]["questions"][entry["check"]]}
            rows.append({"name": f"{entry['name']} / {expected}", "split": entry["split"],
                         "category": entry["category"], "expected": expected, "check": entry["check"],
                         "source_sha256": jev.digest(entry["source"].encode()),
                         "output_sha256": jev.digest(candidate.encode()), "requests": [request],
                         "native_failures": [], "deterministic_failures": []})
    return rows, {"calibration_sha256": jev.digest(jev.CALIBRATION.read_bytes()),
                  "protocol_sha256": jev.protocol_digest(), "split": split,
                  "judge_code_sha256": jev.digest(Path(jev.__file__).read_bytes())}


def metrics(rows, policy, *, raw=False):
    result = {"count": len(rows), "correct": 0, "false_passes": 0, "false_failures": 0, "review": 0}
    for row in rows:
        answer = row["findings"][row["check"]]
        verdict = answer["choice"] if raw else jev.decision(answer, answer["model"], policy)[0]
        key = ("review" if verdict in ("review", "uncertain") else "correct" if verdict == row["expected"]
               else "false_passes" if verdict == "pass" else "false_failures")
        result[key] += 1
    return result


def assess(report):
    result = {}
    for split in ("calibration", "validation"):
        rows = [row for row in report["cases"] if row["split"] == split]
        if not rows:
            continue
        result[split] = {"raw": metrics(rows, None, raw=True), "policy": metrics(rows, report["policy"]),
                         "categories": {category: metrics([row for row in rows if row["category"] == category], report["policy"])
                                        for category in sorted({row["category"] for row in rows})}}
    return result


def fit_policy(report):
    """Fit only calibration labels. Never consult validation or write the policy."""
    rows = [row for row in report["cases"] if row["split"] == "calibration"]
    if not report["complete"] or not rows:
        raise ValueError("A completed calibration split is required")
    # Predeclared grid: choose greatest coverage with no incorrect confident decisions.
    # A minimum 0.10 separation reserves near-ties for review even in a small sample.
    for threshold in [value / 100 for value in range(10, 101, 5)]:
        policy = {"protocol_sha256": report["protocol_sha256"],
                  "calibration_sha256": report["calibration_sha256"],
                  "resolved_models": report["resolved_models"], "minimum_margin": threshold}
        scores = metrics(rows, policy)
        if not scores["false_passes"] and not scores["false_failures"]:
            return {**policy, "calibration_metrics": scores,
                    "calibration_report_sha256": jev.digest(jev.encode(report))}
    raise ValueError("No review margin can separate incorrect calibration decisions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split", choices=("calibration", "validation", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wrangler-auth", action="store_true")
    parser.add_argument("--propose-policy", action="store_true", help="Save a candidate policy fitted only to calibration labels, never install it")
    args = parser.parse_args()
    try:
        prepared, metadata = prepare(args.split)
        report = jev.run_review(prepared, metadata, args.output_dir, live=not args.dry_run,
                                wrangler_auth=args.wrangler_auth, calibrating=args.propose_policy)
        if args.dry_run:
            return 0
        assessment = assess(report)
        (args.output_dir / "calibration.json").write_text(json.dumps(assessment, indent=2) + "\n")
        if args.propose_policy:
            (args.output_dir / "proposed-policy.json").write_text(json.dumps(fit_policy(report), indent=2) + "\n")
        print(json.dumps(assessment, indent=2))
        # Uncalibrated/model-changed, abstained or incorrectly judged examples need review.
        passed = bool(report["policy"]) and all(
            scores["policy"]["correct"] == scores["policy"]["count"] for scores in assessment.values())
        return 0 if passed else 1
    except (OSError, ValueError) as error:
        print(f"Calibration stopped: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
