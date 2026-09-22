#!/usr/bin/env python3
"""Development-only readability rubric v2; never replaces the frozen Jev gate."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import jev_evaluation as jev
from scripts.apple_test_support import parse_notes

FIXTURE = ROOT / "tests/fixtures/jev-readability-v2.json"
VERSION = "editorial-readability-v2"
DIMENSIONS = {
    "fluency": "Each editorial note is understandable, grammatically coherent prose. Short complete observations and natural questions are valid. Judge sentence clarity only, not repetition, correctness, relevance or how many words were changed from the source.",
    "repetition": "Within a note and among notes at the same location, no statement repeats the same information without adding a distinct detail, qualification or reason. Similar wording about different moments is valid. Judge redundant meaning only.",
    "dictation": "Editorial note bodies contain no abandoned sentence starts, verbal stutters, or unedited dictation fillers. Quoted dialogue and intentional hesitation inside quoted dialogue are valid. Short praise is valid. Judge dictation artifacts only.",
    "organization": "General feedback is separated from timestamped feedback, and timed notes have readable location labels. Empty-section notices are allowed. Separate issues at the same timestamp are allowed. Judge document organization only, not the accuracy of time placement.",
    "leakage": "Editorial notes contain no model instructions, JSON/schema fields, internal source IDs or analysis of how the formatter operates. Ordinary headings and review dates are allowed. Judge machine-text leakage only, not creative or quoted film content.",
}


def protocol_digest():
    return jev.digest(jev.encode({"version": VERSION, "dimensions": DIMENSIONS,
                                 "criteria": jev.CRITERIA,
                                 "parser": jev.digest((ROOT / "scripts/apple_test_support.py").read_bytes())}))


def requests(markdown, *, dimension=None):
    # Administrative placeholders are document structure, not dictated prose.
    notes = [n for n in parse_notes(markdown)
             if n["text"].strip() not in {"No general summary was generated.", "No timestamped feedback was provided."}]
    selected = {dimension: DIMENSIONS[dimension]} if dimension else DIMENSIONS
    body = {k: jev.question(v, common=True) for k, v in selected.items() if k != "organization"}
    result = []
    if body:
        result.append({"model": jev.MODEL, "input": {"state": {"candidate_notes": notes}, "questions": body}})
    if "organization" in selected:
        result.append({"model": jev.MODEL, "input": {
            "state": {"candidate": markdown, "candidate_notes": notes},
            "questions": {"organization": jev.question(DIMENSIONS["organization"], common=True)}}})
    return result


def prepare(*, evidence_dir=None, split="all"):
    if evidence_dir is not None:
        # Validate all source/output hashes against the original public allowlist
        # before accessing credentials, even though this rubric only sends notes.
        rows, metadata = jev.prepare(evidence_dir)
        for index, row in enumerate(rows, 1):
            output = evidence_dir / f"case-{index:02d}" / "notes.md"
            row["requests"] = requests(output.read_text()) if output.exists() else []
    else:
        rows, metadata = [], {}
        for case in json.loads(FIXTURE.read_text()):
            if split != "all" and case["split"] != split:
                continue
            for expected, markdown in case["candidates"].items():
                rows.append({"name": f"{case['name']} / {expected}", "split": case["split"],
                             "check": case["dimension"], "expected": expected,
                             "source_sha256": jev.digest(case["name"].encode()),
                             "output_sha256": jev.digest(markdown.encode()),
                             "native_failures": [], "deterministic_failures": [],
                             "requests": requests(markdown, dimension=case["dimension"])})
    metadata.update(protocol_sha256=protocol_digest(), calibration_sha256=jev.digest(FIXTURE.read_bytes()),
                    readability_version=VERSION, replaces_frozen_gate=False,
                    readability_code_sha256=jev.digest(Path(__file__).read_bytes()))
    return rows, metadata


def assessment(report, policy):
    groups = {}
    for row in report["cases"]:
        split = row.get("split", "candidate")
        scores = groups.setdefault(split, {"count": 0, "correct": 0, "false_passes": 0,
                                           "false_failures": 0, "review": 0, "pass": 0, "fail": 0})
        selected = {row["check"]: row["findings"][row["check"]]} if "check" in row else row["findings"]
        for finding in selected.values():
            verdict, _ = jev.decision(finding, finding["model"], policy)
            scores["count"] += 1
            key = ("review" if verdict == "review" else
                   verdict if "expected" not in row else "correct" if verdict == row["expected"] else
                   "false_passes" if verdict == "pass" else "false_failures")
            scores[key] += 1
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--split", choices=("all", "calibration", "validation"), default="all")
    parser.add_argument("--policy", type=Path, help="Separately calibrated v2 policy; never the production policy")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wrangler-auth", action="store_true")
    args = parser.parse_args()
    try:
        rows, metadata = prepare(evidence_dir=args.evidence_dir, split=args.split)
        policy = json.loads(args.policy.read_text()) if args.policy else None
        if policy and (policy.get("protocol_sha256") != protocol_digest() or
                       policy.get("calibration_sha256") != jev.digest(FIXTURE.read_bytes()) or
                       type(policy.get("minimum_margin")) not in (int, float) or
                       not 0.1 <= policy["minimum_margin"] <= 1 or
                       not isinstance(policy.get("resolved_models"), list) or not policy["resolved_models"] or
                       not all(isinstance(model, str) and model for model in policy["resolved_models"])):
            raise ValueError("Readability policy does not match this rubric and calibration")
        report = jev.run_review(rows, metadata, args.output_dir, live=not args.dry_run,
                                wrangler_auth=args.wrangler_auth, calibrating=True)
        if args.dry_run:
            return 0
        if policy is None and args.evidence_dir is None:
            fit = runpy.run_path(str(ROOT / "scripts/calibrate-jev.py"))["fit_policy"]
            policy = fit(report)  # Existing fitter only consults calibration labels.
            (args.output_dir / "proposed-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
        scores = assessment(report, policy)
        summary = {"version": VERSION, "replaces_frozen_gate": False, "policy": policy,
                   "assessment": scores, "human_labels": "Engineering judgments on public synthetic examples"}
        summary["cases"] = [{"name": row["name"], "findings": {
            key: dict(finding, decision=jev.decision(finding, finding["model"], policy)[0],
                      margin=jev.decision(finding, finding["model"], policy)[1])
            for key, finding in row["findings"].items()}} for row in report["cases"]]
        (args.output_dir / "readability.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0 if policy and all(not s["false_passes"] and not s["false_failures"] and not s["review"] and not s["fail"] for s in scores.values()) else 1
    except (OSError, ValueError) as error:
        print(f"Readability evaluation stopped: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
