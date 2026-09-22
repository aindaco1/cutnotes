#!/usr/bin/env python3
"""Standard development tests: contracts, Jev calibration, and native Apple + Jev."""

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Run Python/Swift tests only; skips live Jev and native quality gates")
    parser.add_argument("--engine", type=Path, help="Use a specific native helper instead of building the current source")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/diagnostics" / dt.datetime.now(dt.timezone.utc).strftime("development-%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"full_suite": not args.offline, "release_accepted": False, "passed": False,
              "skipped": ["Jev calibration", "Native Apple + Jev"] if args.offline else [], "gates": []}

    def save():
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    def run(name, command):
        print(f"\n{name}", flush=True)
        code = subprocess.run(command, cwd=ROOT).returncode
        report["gates"].append({"name": name, "exit_code": code, "passed": code == 0})
        save()
        return code

    try:
        save()
        if run("Python tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]):
            return 1
        if run("Swift tests", ["swift", "test", "--package-path", "macos"]):
            return 1
        if not args.offline:
            code = run("Jev calibration", [sys.executable, "scripts/calibrate-jev.py", "--output-dir", str(args.output_dir / "calibration")])
            if code == 2:
                return 2
            engine = args.engine
            if engine is None:
                if run("Build native helper", ["swift", "build", "--package-path", "macos", "--product", "CutNotesLocal"]):
                    return 1
                binary_dir = subprocess.check_output(["swift", "build", "--package-path", "macos", "--show-bin-path"], cwd=ROOT, text=True).strip()
                engine = Path(binary_dir) / "CutNotesLocal"
            run("Native Apple + Jev", [sys.executable, "scripts/check-apple-formatting.py", "--engine", str(engine.resolve()),
                                       "--output-dir", str(args.output_dir / "native")])
        report["passed"] = all(gate["passed"] for gate in report["gates"])
        save()
        print(f"\n{'Offline subset' if args.offline else 'Development suite'}: {args.output_dir / 'report.json'}")
        return 0 if report["passed"] else 1
    except (OSError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        save()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
