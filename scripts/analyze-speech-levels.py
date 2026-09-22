#!/usr/bin/env python3
"""Create a local, reviewable quiet-background proposal; never overwrite ASR/source audio."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cutnotes_core.providers import require_tool
from cutnotes_core.speech_levels import analyze_recording


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = analyze_recording(transcript=args.transcript.read_text(), evidence=json.loads(args.evidence.read_text()),
                               source_audio=args.audio, ffmpeg=require_tool("CUTNOTES_FFMPEG", "ffmpeg"))
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output_dir / "foreground-transcript.txt").write_text(report["proposed_foreground_transcript"])
    selected = [u for u in report["utterances"] if u["background_candidate"]]
    print(f"{len(selected)} quiet background candidate(s); review required. {args.output_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
