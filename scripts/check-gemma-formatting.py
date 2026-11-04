#!/usr/bin/env python3
"""Local Gemma acceptance on the fixed public synthetic suite; Jev is development-only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cutnotes_core.contracts import CutNotesError, ProgressReporter
from cutnotes_core.formatting import validate_timecodes
from cutnotes_core.gemma_formatting import format_with_gemma, RECIPE_VERSION
from cutnotes_core.gemma_model import MANIFEST
from scripts.apple_test_support import parse_notes, scoped_notes

def evaluation_markdown(markdown):
    """Adapt the new presentation to the frozen evaluator's note/location schema."""
    timed, _, general = markdown.partition("## General / Overall Notes")
    notes = [("general", line[2:].strip()) for line in general.splitlines() if line.startswith("* ")]
    notes += [(m[1], m[2].strip()) for m in re.finditer(r"^### (.+)\n([\s\S]*?)(?=^### |\Z)", timed, re.M)]
    overall, rows = [], []
    for location, body in notes:
        if location == "general" and re.search(r"\b(?:at the end|end of (?:the )?(?:film|video|cut)|final image)\b", body, re.I):
            location = "End of video"
        if location == "general": overall.append(body)
        else: rows.append("| " + location + " | " + body.replace("|", "\\|") + " |")
    return "# Evaluation view\n\n## Overall feedback\n\n" + "\n\n".join(overall) + "\n\n## Timestamped feedback\n| Video time | Feedback |\n| --- | --- |\n" + "\n".join(rows)


def evaluate(markdown: str, case: dict) -> list[str]:
    """Check content within its correct section/moment, without exact wording."""
    failures = []
    if "## Timestamp Notes" not in markdown or "## General / Overall Notes" not in markdown:
        failures.append("Missing Gemma note sections")
    invented, omitted = validate_timecodes(markdown, case["transcript"])
    failures.extend(f"Invented time: {value}" for value in invented)
    failures.extend(f"Missing time: {value}" for value in omitted)
    notes = parse_notes(evaluation_markdown(markdown))
    if "Formatting incomplete" in markdown:
        failures.append("Incomplete formatting")
    for check in case["checks"]:
        candidates = [note["text"] for note in scoped_notes(notes, check["scope"])]
        if len(candidates) < check.get("minimum_notes", 0):
            failures.append(f"{check['name']}: missing distinct notes")
        if check.get("same_note"):
            if not any(
                all(re.search(pattern, body, re.IGNORECASE | re.DOTALL)
                    for pattern in check.get("contains", []))
                and not any(re.search(pattern, body, re.IGNORECASE | re.DOTALL)
                            for pattern in check.get("excludes", []))
                for body in candidates
            ):
                failures.append(f"{check['name']}: no single note preserves the expected meaning")
            continue
        content = "\n".join(candidates)
        for pattern in check.get("contains", []):
            if not re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                failures.append(f"{check['name']}: missing {pattern}")
        for pattern in check.get("excludes", []):
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                failures.append(f"{check['name']}: unexpected {pattern}")
    for pattern in case.get("excludes", []):
        if re.search(pattern, markdown, re.IGNORECASE):
            failures.append(f"Unexpected content: {pattern}")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/apple-formatting.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--skip-jev", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"schema_version":"cutnotes.gemma.acceptance.v1", "recipe":RECIPE_VERSION,
              "revision":MANIFEST["revision"], "cases":[], "passed":False}
    for index, case in enumerate(json.loads(args.fixtures.read_text())):
        directory = args.output_dir / f"case-{index+1:02d}"
        directory.mkdir()
        source, output = directory / "transcript.txt", directory / "notes.md"
        source.write_text(case["transcript"] + "\n")
        original = source.read_bytes()
        started = time.monotonic()
        row = {"name":case["name"], "source_sha256":hashlib.sha256(original).hexdigest()}
        try:
            format_with_gemma(transcript_path=source, output_path=output, title="Synthetic acceptance review",
                              context=None, reporter=ProgressReporter(None))
            row["failures"] = evaluate(output.read_text(), case)
            row["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
        except CutNotesError as error:
            row["failures"] = [error.code]
        if source.read_bytes() != original: row["failures"].append("Source changed")
        row["passed"] = not row["failures"]
        row["elapsed_seconds"] = round(time.monotonic()-started,3)
        report["cases"].append(row)
        report["passed"] = all(c["passed"] for c in report["cases"])
        (args.output_dir/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(f"{'PASS' if row['passed'] else 'REVIEW'}: {case['name']}",flush=True)
    if not args.skip_jev:
        from scripts.jev_evaluation import review
        judged = review(args.output_dir, args.output_dir / "jev", live=True, wrangler_auth=False)
        if not judged.get("passed", False): return 1
    return 0 if report["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
