"""Command-line interface for CutNotes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import textwrap

from . import VERSION
from .contracts import *
from .filesystem import *
from .formatting import *
from .models import *
from .pipeline import *
from .providers import *


DEFAULT_ROOT = Path.home() / "Desktop"


def eprint(message: str = "") -> None:
    print(message, file=sys.stderr)


def doctor_payload() -> tuple[dict, bool]:
    ffmpeg = find_tool("CUTNOTES_FFMPEG", "ffmpeg")
    ffprobe = find_ffprobe(ffmpeg) if ffmpeg else None
    macwhisper = find_tool("CUTNOTES_MACWHISPER", "mw", MACWHISPER_CANDIDATES)
    codex = find_tool("CUTNOTES_CODEX", "codex", CODEX_CANDIDATES)
    local_engine = find_local_engine()
    engine_status = local_engine_status(local_engine)
    parakeet = model_status()
    microphones = (
        [{"index": index, "name": name} for index, name in list_microphones(ffmpeg)]
        if ffmpeg
        else []
    )
    core_healthy = bool(ffmpeg and ffprobe and local_engine and microphones)
    apple_ready = engine_status["apple"].get("state") == "ready"
    default_ready = core_healthy and parakeet["state"] == "ready" and apple_ready
    payload = {
        "schema_version": "cutnotes.doctor.v1",
        "healthy": core_healthy,
        "default_workflow_ready": default_ready,
        "cutnotes": VERSION,
        "architecture": os.uname().machine,
        "limits": {
            "maximum_duration_seconds": MAXIMUM_DURATION_SECONDS,
            "warning_duration_seconds": WARNING_DURATION_SECONDS,
        },
        "ffmpeg": {
            "path": ffmpeg,
            "version": command_version([ffmpeg, "-version"]) if ffmpeg else None,
        },
        "ffprobe": {
            "path": ffprobe,
            "version": command_version([ffprobe, "-version"]) if ffprobe else None,
        },
        "local_engine": engine_status,
        "parakeet": parakeet,
        "apple_formatter": engine_status["apple"],
        "macwhisper": {
            "path": macwhisper,
            "version": command_version([macwhisper, "version"]) if macwhisper else None,
            "optional": True,
            "models": [],
        },
        "codex": {
            "path": codex,
            "version": command_version([codex, "--version"]) if codex else None,
            "optional": True,
        },
        "microphones": microphones,
    }
    if macwhisper:
        try:
            import subprocess

            models = subprocess.run(
                [macwhisper, "models"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            payload["macwhisper"]["models"] = [
                line.rstrip() for line in models.stdout.splitlines() if line.strip()
            ]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return payload, core_healthy


def print_doctor_report(payload: dict, *, compact: bool = False) -> None:
    mark = lambda present: "✓" if present else "✗"
    print(f"{mark(payload['ffmpeg']['path'])} FFmpeg: {payload['ffmpeg']['version'] or 'not found'}")
    print(f"{mark(payload['ffprobe']['path'])} FFprobe: {payload['ffprobe']['version'] or 'not found'}")
    engine = payload["local_engine"]
    print(f"{mark(engine['path'])} CutNotes local engine: {engine['version'] or 'not found'}")
    parakeet = payload["parakeet"]
    print(f"{mark(parakeet['state'] == 'ready')} Parakeet v3 model: {parakeet['state']}")
    apple = payload["apple_formatter"]
    print(f"{mark(apple.get('state') == 'ready')} Apple on-device formatter: {apple.get('state', 'unavailable')}")
    print(
        f"{mark(payload['macwhisper']['path'])} MacWhisper (optional): "
        f"{payload['macwhisper']['version'] or 'not found'}"
    )
    print(
        f"{mark(payload['codex']['path'])} Codex CLI (optional): "
        f"{payload['codex']['version'] or 'not found'}"
    )
    microphones = payload["microphones"]
    if compact:
        print(f"{mark(microphones)} Microphone: {microphones[0]['name'] if microphones else 'none found'}")
        return
    print("\nMicrophones:")
    if microphones:
        for microphone in microphones:
            print(f"  {microphone['index']}: {microphone['name']}")
    else:
        print("  None found")
    print("\nMacWhisper models (optional):")
    models = payload["macwhisper"]["models"]
    if models:
        for model in models:
            print(f"  {model}")
    else:
        print("  None reported")


def run_doctor(args: argparse.Namespace) -> int:
    payload, healthy = doctor_payload()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"cutnotes {payload['cutnotes']}")
        print_doctor_report(payload)
        if payload["parakeet"]["state"] != "ready":
            print("\nInstall the default model with: cutnotes model download", file=sys.stderr)
        if payload["apple_formatter"].get("state") != "ready":
            print(
                "Apple formatting is unavailable here; use --formatter codex or --transcript-only.",
                file=sys.stderr,
            )
    return 0 if healthy else EXIT_DEPENDENCY


def run_model_status(args: argparse.Namespace) -> int:
    payload = {"schema_version": "cutnotes.model.v1", **model_status()}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Parakeet v3 model: {payload['state']}")
        print(f"Location: {payload['path']}")
        print(f"License: {payload['license']} — {payload['license_url']}")
        if payload["detail"]:
            print(payload["detail"], file=sys.stderr)
    return 0 if payload["state"] == "ready" else EXIT_DEPENDENCY


def run_model_download(args: argparse.Namespace) -> int:
    if not args.accept_license and sys.stdin.isatty() and not args.json:
        print("Parakeet v3 is licensed CC BY 4.0:")
        print(MODEL_LICENSE_URL)
        answer = input("Download and install this pinned model? [y/N] ").strip().casefold()
        args.accept_license = answer in ("y", "yes")
    payload = {
        "schema_version": "cutnotes.model.v1",
        **download_model(
            accept_license=args.accept_license,
            reporter=ProgressReporter(args.progress_fd),
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Parakeet v3 model ready at {payload['path']}")
    return 0


def run_model_import(args: argparse.Namespace) -> int:
    payload = {"schema_version": "cutnotes.model.v1", **import_model(Path(args.folder))}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Parakeet v3 model ready at {payload['path']}")
    return 0


def print_result(payload: dict, as_json: bool, quiet: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    if quiet:
        print(payload["markdown"] or payload["transcript"])
        return
    print("\nDone.")
    if payload.get("session_dir"):
        print(f"Project folder: {payload['session_dir']}")
    if payload.get("markdown"):
        print(f"Markdown:   {payload['markdown']}")
    print(f"Transcript: {payload['transcript']}")
    if payload.get("audio"):
        print(f"Audio:      {payload['audio']}")


def run_record_command(args: argparse.Namespace) -> int:
    print_result(run_record(args), args.json, args.quiet)
    return 0


def run_import_command(args: argparse.Namespace) -> int:
    print_result(run_import(args), args.json, args.quiet)
    return 0


def run_format_command(args: argparse.Namespace) -> int:
    print_result(run_format(args), args.json, args.quiet)
    return 0


def prompt_for_project_name() -> str:
    while True:
        try:
            title = input("\nProject or cut name: ").strip()
        except EOFError as error:
            raise CutNotesError(
                "No project name was entered.",
                EXIT_INPUT,
                code="title_missing",
                recovery="Run `cutnotes` in an interactive terminal and enter a title.",
            ) from error
        if title:
            return title
        print("Please enter a project or cut name.")


def run_interactive(_: argparse.Namespace) -> int:
    if not sys.stdin.isatty():
        raise CutNotesError(
            "Interactive startup needs a terminal.",
            EXIT_INPUT,
            code="interactive_terminal_required",
            recovery="Use `cutnotes record`, `cutnotes import`, or `cutnotes format` for automation.",
        )
    print(f"cutnotes {VERSION} — rough-cut voice feedback")
    print("\nChecking your setup…")
    payload, healthy = doctor_payload()
    print_doctor_report(payload, compact=True)
    if not healthy:
        raise CutNotesError(
            "The setup check found a core dependency problem.",
            EXIT_DEPENDENCY,
            code="setup_unhealthy",
            recovery="Run `cutnotes doctor` for details.",
        )
    if payload["parakeet"]["state"] != "ready":
        raise CutNotesError(
            "The default Parakeet v3 model is not installed.",
            EXIT_DEPENDENCY,
            code="model_missing",
            recovery="Run `cutnotes model download`, then start again.",
        )
    if payload["apple_formatter"].get("state") != "ready":
        raise CutNotesError(
            "Apple on-device formatting is unavailable on this Mac.",
            EXIT_DEPENDENCY,
            code="apple_model_unavailable",
            recovery="Use an advanced command with --formatter codex or --transcript-only.",
        )
    title = prompt_for_project_name()
    print("\nHow to give notes:")
    print('  • Say the CUT timecode first: "Timestamp 12 minutes 34 seconds."')
    print("  • Pause briefly, then give your feedback.")
    print('  • Say "General note" for feedback without a timecode.')
    print("  • CutNotes warns at 3 hours 45 minutes and stops at 4 hours.")
    try:
        input("\nPut on headphones, open the cut, then press Return to start recording…")
    except EOFError as error:
        raise CutNotesError(
            "Recording was not started.",
            EXIT_INPUT,
            code="recording_not_started",
            recovery="Run `cutnotes` again when ready.",
        ) from error
    args = argparse.Namespace(
        title=title,
        mic=None,
        device_index=None,
        root=os.environ.get("CUTNOTES_ROOT", str(DEFAULT_ROOT)),
        language="en",
        transcriber="parakeet",
        formatter="apple",
        whisper_model=None,
        codex_model=None,
        context=None,
        transcript_only=False,
        json=False,
        quiet=False,
        progress_fd=None,
        control_fd=None,
    )
    return run_record_command(args)


def _file_descriptor(value: str) -> int:
    descriptor = int(value)
    if descriptor < 3 or descriptor > 63:
        raise argparse.ArgumentTypeError("file descriptor must be from 3 through 63")
    return descriptor


def add_machine_options(parser: argparse.ArgumentParser, *, recording: bool = False) -> None:
    parser.add_argument("--json", action="store_true", help="Print the versioned result as JSON.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Print only the result path.")
    parser.add_argument("--progress-fd", type=_file_descriptor, help=argparse.SUPPRESS)
    if recording:
        parser.add_argument("--control-fd", type=_file_descriptor, help=argparse.SUPPRESS)


def add_pipeline_options(parser: argparse.ArgumentParser, *, recording: bool = False) -> None:
    parser.add_argument(
        "--root",
        default=os.environ.get("CUTNOTES_ROOT", str(DEFAULT_ROOT)),
        help="Project-folder parent (default: ~/Desktop or CUTNOTES_ROOT).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Source language (English is fully supported; other Parakeet languages are experimental).",
    )
    parser.add_argument(
        "--transcriber",
        choices=("parakeet", "macwhisper"),
        default="parakeet",
        help="Local transcription provider (default: parakeet).",
    )
    parser.add_argument(
        "--formatter",
        choices=("apple", "codex", "none"),
        default="apple",
        help="Formatting provider (default: apple; no automatic fallback).",
    )
    parser.add_argument("--whisper-model", help="Optional MacWhisper engine:model-id override.")
    parser.add_argument("--codex-model", help="Optional Codex CLI model override.")
    parser.add_argument("--context", help="Optional names or editorial context.")
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Stop after local transcription; do not run a formatter.",
    )
    add_machine_options(parser, recording=recording)


def build_parser() -> argparse.ArgumentParser:
    examples = """
      cutnotes
      cutnotes doctor
      cutnotes model download
      cutnotes record "Project — Rough Cut" --context "Mia is the lead"
      cutnotes import voice-note.m4a --title "Episode 4 Rough Cut"
      cutnotes format transcript.txt --title "Episode 4 Rough Cut"
      cutnotes import voice-note.m4a --title "Private Review" --transcript-only
      cutnotes format transcript.txt --title "Review" --formatter codex
    """
    parser = argparse.ArgumentParser(
        prog="cutnotes",
        description=(
            "Record or import rough-cut feedback, transcribe it locally, and optionally "
            "format it into editor-ready Markdown. Run without arguments for guided mode."
        ),
        epilog=textwrap.dedent(examples),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check local engines, models, and microphones.")
    doctor.add_argument("--json", action="store_true", help="Print diagnostics as JSON.")
    doctor.set_defaults(handler=run_doctor)

    model = subparsers.add_parser("model", help="Manage the pinned local Parakeet v3 model.")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_status_parser = model_commands.add_parser("status", help="Verify the installed model.")
    model_status_parser.add_argument("--json", action="store_true")
    model_status_parser.set_defaults(handler=run_model_status)
    model_download_parser = model_commands.add_parser("download", help="Download and verify the model.")
    model_download_parser.add_argument("--accept-license", action="store_true")
    model_download_parser.add_argument("--json", action="store_true")
    model_download_parser.add_argument("--progress-fd", type=_file_descriptor, help=argparse.SUPPRESS)
    model_download_parser.set_defaults(handler=run_model_download)
    model_import_parser = model_commands.add_parser("import", help="Import and verify a downloaded model.")
    model_import_parser.add_argument("folder")
    model_import_parser.add_argument("--json", action="store_true")
    model_import_parser.set_defaults(handler=run_model_import)

    record = subparsers.add_parser("record", help="Record, transcribe, and optionally format notes.")
    record.add_argument("title", help="Title for the project folder and Markdown document.")
    record.add_argument("--mic", help=f"Microphone name (default: {DEFAULT_MIC_NAME}).")
    record.add_argument("--device-index", type=int, help="AVFoundation audio device index.")
    add_pipeline_options(record, recording=True)
    record.set_defaults(handler=run_record_command)

    import_audio = subparsers.add_parser("import", help="Process an existing audio or video file.")
    import_audio.add_argument("audio", help="Path to an audio or video file (copied into the project).")
    import_audio.add_argument("--title", required=True, help="Title for the project and document.")
    add_pipeline_options(import_audio)
    import_audio.set_defaults(handler=run_import_command)

    format_transcript = subparsers.add_parser("format", help="Format an existing UTF-8 transcript.")
    format_transcript.add_argument("transcript", help="Path to a UTF-8 transcript.")
    format_transcript.add_argument("--title", required=True, help="Title for the document.")
    format_transcript.add_argument("-o", "--output", help="Markdown output path.")
    format_transcript.add_argument(
        "--formatter",
        choices=("apple", "codex"),
        default="apple",
        help="Formatting provider (default: apple; no automatic fallback).",
    )
    format_transcript.add_argument("--codex-model", help="Optional Codex CLI model override.")
    format_transcript.add_argument("--context", help="Optional names or editorial context.")
    add_machine_options(format_transcript)
    format_transcript.set_defaults(handler=run_format_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "formatter", None) == "none":
        args.transcript_only = True
    machine = bool(getattr(args, "json", False) or getattr(args, "progress_fd", None) is not None)
    try:
        handler = getattr(args, "handler", run_interactive)
        return int(handler(args))
    except CutNotesError as error:
        if machine:
            print(json.dumps(error.payload(), separators=(",", ":")), file=sys.stderr)
        else:
            eprint(f"cutnotes: {error}")
            eprint(f"Recovery: {error.recovery}")
        return error.exit_code
    except KeyboardInterrupt:
        error = CutNotesError(
            "Interrupted.",
            EXIT_CANCELLED,
            code="cancelled",
            recovery="Run CutNotes again when ready; completed artifacts were preserved.",
        )
        if machine:
            print(json.dumps(error.payload(), separators=(",", ":")), file=sys.stderr)
        else:
            eprint("\ncutnotes: interrupted")
        return EXIT_CANCELLED
