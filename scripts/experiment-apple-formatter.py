#!/usr/bin/env python3
"""Evaluate the source-preserving formatter candidate without changing a user provider."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import runpy
import selectors
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cutnotes_core.formatter_candidate import format_candidate
from cutnotes_core.apple_editorial import EditorialQuestions



def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeQuestions(EditorialQuestions):
    def __init__(self, engine, trace):
        self.process = subprocess.Popen([str(engine.resolve())], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.trace = trace
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def generate(self, kind, request):
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        if not self.selector.select(timeout=45):
            raise ValueError("Native Apple classification timed out")
        line = self.process.stdout.readline()
        response = json.loads(line)
        self.trace.append({"question": kind, "request": request, "response": response})
        if response.get("error"):
            raise ValueError("Native Apple classification failed: " + str(response.get("error")))
        return response

    def close(self):
        self.selector.close()
        self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True, help="Compiled AppleFormatterProbe")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--transcript", type=Path, help="Private local review; never sent to Jev")
    source.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/apple-formatting.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--skip-jev", action="store_true")
    edits = parser.add_mutually_exclusive_group()
    edits.add_argument("--rewrite", action="store_true", help="Original word-protected Apple editing baseline")
    edits.add_argument("--evidence-edit", action="store_true", help="Evidence-first editing with bounded revision checks")
    parser.add_argument("--passage-relevance", action="store_true", help="Reviewable background proposals after passage grouping")
    parser.add_argument("--jev-wrangler-auth", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    private = args.transcript is not None
    cases = ([{"name": "Representative recording", "transcript": args.transcript.read_text().strip(), "checks": []}]
             if private else json.loads(args.fixtures.read_text()))
    evaluate = runpy.run_path(str(ROOT / "scripts/check-apple-formatting.py"))["evaluate"]
    report = {"schema_version": "cutnotes.apple.acceptance.v1", "prototype": True,
              "requires_human_review": True, "private": private,
              "variant": "evidence-edit" if args.evidence_edit else "protected-copyedit" if args.rewrite else "source-preserving",
              "passage_relevance": args.passage_relevance,
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "macos_version": platform.mac_ver()[0], "architecture": platform.machine(),
              "engine_sha256": digest(args.engine),
              "core_sha256": {name: digest(ROOT / "cutnotes_core" / name) for name in ("formatter_candidate.py", "editorial_edits.py", "apple_editorial.py")},
              "runner_sha256": digest(Path(__file__)), "cases": []}
    snapshot = args.output_dir / "implementation"
    snapshot.mkdir()
    for source_file in (ROOT / "cutnotes_core/formatter_candidate.py", ROOT / "cutnotes_core/editorial_edits.py", ROOT / "cutnotes_core/apple_editorial.py", Path(__file__),
                        ROOT / "scripts/experiments/AppleFormatterProbe.swift"):
        shutil.copyfile(source_file, snapshot / source_file.name)
    original_hash = digest(args.transcript) if private else None
    for index, case in enumerate(cases, 1):
        directory = args.output_dir / f"case-{index:02d}"
        directory.mkdir()
        transcript = directory / "transcript.txt"
        transcript.write_text(case["transcript"] + "\n")
        row = {"name": case["name"], "source_sha256": digest(transcript)}
        trace = []
        native = NativeQuestions(args.engine, trace)
        start = time.monotonic()
        try:
            markdown, audit = format_candidate(transcript=case["transcript"],
                                               title="Representative recording" if private else "Synthetic acceptance review",
                                               review_date=dt.date.today().isoformat(), ask=native.ask,
                                               edit=native.edit if args.rewrite else None,
                                               revise=native.revise if args.evidence_edit else None,
                                               classify_passage=native.classify_passage if args.passage_relevance else None)
            output = directory / "notes.md"
            output.write_text(markdown + "\n")
            (directory / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
            evaluation_case = case
            if private:
                # This candidate recognizes additional source timing syntax.
                # Validate private output against its lossless normalization;
                # the public comparison keeps the fixed independent checker.
                evaluation_case = dict(case, transcript="\n".join(s["normalized"] for s in audit["sentences"]))
            row.update(output_sha256=digest(output), failures=evaluate(markdown, evaluation_case),
                       checks_scope="structure_and_source_times_only" if private else "fixed_public_acceptance")
        except (OSError, ValueError, BrokenPipeError) as error:
            row["failures"] = [str(error)]
        finally:
            native.close()
        (directory / "native-trace.json").write_text(json.dumps(trace, indent=2) + "\n")
        row.update(elapsed_seconds=round(time.monotonic() - start, 3), passed=not row["failures"])
        report["cases"].append(row)
        print(f"{'PASS' if row['passed'] else 'FAIL'}: {case['name']} ({row['elapsed_seconds']}s)", flush=True)
    report["passed"] = all(c["passed"] for c in report["cases"]) and not private
    if private:
        report["source_unchanged"] = digest(args.transcript) == original_hash
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if not private and not args.skip_jev:
        from scripts.jev_evaluation import review
        judged = review(args.output_dir, args.output_dir / "jev", live=True, wrangler_auth=args.jev_wrangler_auth)
        return 0 if report["passed"] and judged["combined_passed"] else 1
    return 0 if all(c["passed"] for c in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
