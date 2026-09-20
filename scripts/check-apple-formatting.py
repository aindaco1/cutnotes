#!/usr/bin/env python3
"""Run real on-device formatting acceptance; unavailable is not a passing gate."""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cutnotes_core.contracts import CutNotesError, ProgressReporter
from cutnotes_core.formatting import validate_markdown, validate_timecodes
from cutnotes_core.providers import format_with_apple


def evaluate(markdown: str, case: dict) -> list[str]:
    """Check content within its correct section/moment, without exact wording."""
    failures = [f"Missing section: {item}" for item in validate_markdown(markdown)]
    invented, omitted = validate_timecodes(markdown, case["transcript"])
    failures.extend(f"Invented time: {value}" for value in invented)
    failures.extend(f"Missing time: {value}" for value in omitted)
    general, _, timed = markdown.partition("## Timestamped feedback")
    general_notes = [line[2:].strip() for line in general.splitlines() if line.startswith("- ")]
    rows = []
    for line in timed.splitlines():
        cells = re.split(r"(?<!\\)\|", line.strip())
        if len(cells) == 4:
            rows.append((cells[1].strip(" *"), cells[2].strip()))
    if "Formatting incomplete" in markdown:
        failures.append("Incomplete formatting")
    for check in case["checks"]:
        if check["scope"] == "general":
            candidates = general_notes
        else:
            candidates = [body for label, body in rows if re.search(check["scope"], label)]
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True, help="Candidate CutNotesLocal executable")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/apple-formatting.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="New local evidence directory")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": "cutnotes.apple.acceptance.v1",
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "macos_version": platform.mac_ver()[0],
        "architecture": platform.machine(),
        "fixtures_sha256": hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "core_sha256": {name: hashlib.sha256((ROOT / "cutnotes_core" / name).read_bytes()).hexdigest()
                        for name in ("providers.py", "formatting.py")},
        "passed": False,
        "cases": [],
    }
    try:
        report["engine_sha256"] = hashlib.sha256(args.engine.read_bytes()).hexdigest()
        status = subprocess.run([str(args.engine.resolve()), "status", "--json"],
                                capture_output=True, text=True, check=True, timeout=30)
        report["engine_status"] = json.loads(status.stdout)
        if report["engine_status"].get("apple", {}).get("state") != "ready":
            report["error"] = "Apple model unavailable; native acceptance was not run."
        else:
            cases = json.loads(args.fixtures.read_text(encoding="utf-8"))
            for index, case in enumerate(cases):
                directory = args.output_dir / f"case-{index + 1:02d}"
                directory.mkdir()
                source, output = directory / "transcript.txt", directory / "notes.md"
                source.write_text(case["transcript"] + "\n", encoding="utf-8")
                original = source.read_bytes()
                result = {"name": case["name"], "source_sha256": hashlib.sha256(original).hexdigest()}
                try:
                    format_with_apple(engine=str(args.engine.resolve()), transcript_path=source,
                                      output_path=output, title="Synthetic acceptance review", context=None,
                                      reporter=ProgressReporter(None))
                    result["failures"] = evaluate(output.read_text(encoding="utf-8"), case)
                except CutNotesError as error:
                    result["failures"] = [f"Native formatting failed: {error.code}"]
                if source.read_bytes() != original:
                    result["failures"].append("Source transcript was modified")
                result["passed"] = not result["failures"]
                report["cases"].append(result)
                print(f"{'PASS' if result['passed'] else 'FAIL'}: {case['name']}", flush=True)
            report["passed"] = bool(report["cases"]) and all(case["passed"] for case in report["cases"])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Native Apple acceptance {'passed' if report['passed'] else 'FAILED'}: {args.output_dir / 'report.json'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
