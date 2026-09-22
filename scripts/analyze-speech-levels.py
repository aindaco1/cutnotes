#!/usr/bin/env python3
"""Create a local, reviewable quiet-background proposal; never overwrite ASR/source audio."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cutnotes_core.providers import require_tool
from cutnotes_core.speech_levels import analyze_speech_levels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pcm = args.output_dir / "measurement.wav"
    subprocess.run([require_tool("CUTNOTES_FFMPEG", "ffmpeg"), "-nostdin", "-n", "-v", "error",
                    "-i", str(args.audio.resolve()), "-map", "0:a:0", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(pcm.resolve())], check=True)
    report = analyze_speech_levels(transcript=args.transcript.read_text(), evidence=json.loads(args.evidence.read_text()),
                                   source_audio=args.audio, pcm_audio=pcm)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output_dir / "foreground-transcript.txt").write_text(report["proposed_foreground_transcript"])
    selected = [u for u in report["utterances"] if u["background_candidate"]]
    print(f"{len(selected)} quiet background candidate(s); review required. {args.output_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
