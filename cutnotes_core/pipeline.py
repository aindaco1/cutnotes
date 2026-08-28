"""The authoritative CutNotes capture, transcription, and formatting pipeline."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time

from .contracts import (
    CutNotesError,
    EXIT_CANCELLED,
    EXIT_CAPTURE,
    EXIT_DEPENDENCY,
    EXIT_INPUT,
    PreservedArtifacts,
    ProgressReporter,
    result_payload,
)
from .filesystem import allocate_session_paths, project_directory, slugify, write_json
from .models import default_model_directory, validate_model
from .providers import (
    CODEX_CANDIDATES,
    MACWHISPER_CANDIDATES,
    find_local_engine,
    find_tool,
    format_with_apple,
    format_with_codex,
    require_tool,
    transcribe_with_macwhisper,
    transcribe_with_parakeet,
)


MAXIMUM_DURATION_SECONDS = 4 * 60 * 60
WARNING_DURATION_SECONDS = 3 * 60 * 60 + 45 * 60
DEFAULT_MIC_NAME = "System Default"


def parse_avfoundation_microphones(output: str) -> list[tuple[int, str]]:
    microphones: list[tuple[int, str]] = []
    in_audio_section = False
    for line in output.splitlines():
        if "AVFoundation audio devices:" in line:
            in_audio_section = True
            continue
        if in_audio_section and "AVFoundation video devices:" in line:
            break
        if not in_audio_section:
            continue
        import re

        match = re.search(r"\[(\d+)\]\s+(.+?)\s*$", line)
        if match:
            microphones.append((int(match.group(1)), match.group(2)))
    return microphones


def list_microphones(ffmpeg: str) -> list[tuple[int, str]]:
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_avfoundation_microphones(f"{result.stdout}\n{result.stderr}")


def choose_microphone(
    microphones: list[tuple[int, str]],
    requested_name: str | None,
    requested_index: int | None,
) -> tuple[int | None, str]:
    if not microphones:
        raise CutNotesError(
            "FFmpeg did not report any microphones.",
            EXIT_CAPTURE,
            code="microphone_unavailable",
            recovery="Allow microphone access in System Settings, then run `cutnotes doctor`.",
        )
    if requested_index is not None:
        match = next(((index, name) for index, name in microphones if index == requested_index), None)
        if match:
            return match
        choices = ", ".join(f"{index}: {name}" for index, name in microphones)
        raise CutNotesError(
            f"Audio device index {requested_index} was not found. Available: {choices}",
            EXIT_CAPTURE,
            code="microphone_not_found",
            recovery="Choose a microphone reported by `cutnotes doctor`.",
        )
    if requested_name is None:
        return None, DEFAULT_MIC_NAME
    target = requested_name.casefold()
    if target in {"default", "system default"}:
        return None, DEFAULT_MIC_NAME
    exact = next(((index, name) for index, name in microphones if name.casefold() == target), None)
    if exact:
        return exact
    partial = next(((index, name) for index, name in microphones if target in name.casefold()), None)
    if partial:
        return partial
    choices = ", ".join(f"{index}: {name}" for index, name in microphones)
    raise CutNotesError(
        f'Microphone "{requested_name}" was not found. Available: {choices}',
        EXIT_CAPTURE,
        code="microphone_not_found",
        recovery="Choose a microphone reported by `cutnotes doctor`.",
    )


def find_ffprobe(ffmpeg: str) -> str | None:
    override = find_tool("CUTNOTES_FFPROBE", "ffprobe")
    if override:
        return override
    sibling = Path(ffmpeg).resolve().with_name("ffprobe")
    return str(sibling) if sibling.is_file() and os.access(sibling, os.X_OK) else None


def media_duration_seconds(ffprobe: str, media: Path) -> float:
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(media),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise CutNotesError(
            "CutNotes could not determine the media duration.",
            EXIT_INPUT,
            code="media_probe_failed",
            recovery="Choose a readable audio or video file and try again.",
        ) from error
    if duration <= 0:
        raise CutNotesError(
            "The selected media has no usable duration.",
            EXIT_INPUT,
            code="media_empty",
            recovery="Choose a non-empty audio or video file.",
        )
    return duration


def enforce_duration_limit(duration: float) -> None:
    if duration > MAXIMUM_DURATION_SECONDS + 0.5:
        raise CutNotesError(
            "The selected media is longer than CutNotes' four-hour maximum.",
            EXIT_INPUT,
            code="media_too_long",
            recovery="Trim the media to four hours or less, then import it again.",
        )


def record_audio(
    ffmpeg: str,
    output_path: Path,
    microphone_index: int | None,
    microphone_name: str,
    quiet: bool,
    *,
    control_fd: int | None = None,
    reporter: ProgressReporter | None = None,
) -> None:
    if control_fd is None and not sys.stdin.isatty():
        raise CutNotesError(
            "`cutnotes record` needs either an interactive terminal or --control-fd.",
            EXIT_CAPTURE,
            code="recording_control_missing",
            recovery="Run in Terminal, use the CutNotes app, or import an existing recording.",
        )
    progress = reporter or ProgressReporter(None)
    if not quiet:
        print(file=sys.stderr)
        print(f"Recording from: {microphone_name}", file=sys.stderr)
        print("Use headphones while watching the cut.", file=sys.stderr)
        print('Start each note with the CUT timecode, e.g. "Timestamp 12:34."', file=sys.stderr)
        print("Press q when completely finished. Ctrl-C also stops safely.", file=sys.stderr)
        print(
            "CutNotes warns at 3 hours 45 minutes and automatically stops at 4 hours.",
            file=sys.stderr,
        )
        print(file=sys.stderr)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "avfoundation",
        "-i",
        ":default" if microphone_index is None else f":{microphone_index}",
        "-t",
        str(MAXIMUM_DURATION_SECONDS),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if control_fd is not None else None,
        start_new_session=True,
    )
    progress.stage("recording", "Recording voice notes")
    start = time.monotonic()
    warned = False
    cancelled = False
    selector: selectors.BaseSelector | None = None
    buffer = b""
    if control_fd is not None:
        selector = selectors.DefaultSelector()
        try:
            os.set_blocking(control_fd, False)
            selector.register(control_fd, selectors.EVENT_READ)
        except OSError:
            process.send_signal(signal.SIGINT)
            process.wait()
            raise CutNotesError(
                "The recording control channel could not be opened.",
                EXIT_CAPTURE,
                code="recording_control_invalid",
                recovery="Restart the CutNotes app and try again.",
            )
    try:
        while process.poll() is None:
            elapsed = time.monotonic() - start
            progress.progress("recording", elapsed / MAXIMUM_DURATION_SECONDS)
            if elapsed >= WARNING_DURATION_SECONDS and not warned:
                warned = True
                progress.warning("recording", "15 minutes remain before the four-hour automatic stop")
                if not quiet:
                    print("Warning: recording will stop automatically in 15 minutes.", file=sys.stderr)
            if selector is not None:
                for key, _ in selector.select(timeout=0.25):
                    try:
                        incoming = os.read(key.fd, 4096)
                    except BlockingIOError:
                        continue
                    if not incoming:
                        selector.unregister(key.fd)
                        selector.close()
                        selector = None
                        break
                    buffer += incoming
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        command_name = raw.decode("utf-8", errors="ignore").strip().casefold()
                        if command_name == "finish" and process.stdin:
                            process.stdin.write(b"q\n")
                            process.stdin.flush()
                        elif command_name == "cancel":
                            cancelled = True
                            process.send_signal(signal.SIGINT)
            else:
                time.sleep(0.25)
        return_code = process.wait()
    except KeyboardInterrupt:
        process.send_signal(signal.SIGINT)
        return_code = process.wait()
        if not quiet:
            print(file=sys.stderr)
    finally:
        if selector is not None:
            selector.close()
    has_audio = output_path.is_file() and output_path.stat().st_size > 128
    if cancelled:
        raise CutNotesError(
            "Recording was cancelled.",
            EXIT_CANCELLED,
            code="cancelled",
            recovery="Start a new session when ready; any captured audio was preserved.",
            preserved=PreservedArtifacts(audio=has_audio),
        )
    if not has_audio:
        raise CutNotesError(
            "No usable audio was captured.",
            EXIT_CAPTURE,
            code="audio_not_captured",
            recovery="Check microphone access with `cutnotes doctor` and try again.",
        )
    if time.monotonic() - start >= MAXIMUM_DURATION_SECONDS - 1:
        progress.warning("recording", "Recording stopped at the four-hour maximum")
    if return_code not in (0, 130, 255) and not quiet:
        print(
            f"Warning: FFmpeg exited with status {return_code}, but captured audio was preserved.",
            file=sys.stderr,
        )


def _required_pipeline_tools(args) -> tuple[str, str | None, str | None]:
    ffmpeg = require_tool("CUTNOTES_FFMPEG", "ffmpeg")
    transcriber_tool: str | None = None
    formatter_tool: str | None = None
    if args.transcriber == "parakeet":
        transcriber_tool = find_local_engine()
        if not transcriber_tool:
            raise CutNotesError(
                "The bundled CutNotes local engine was not found.",
                EXIT_DEPENDENCY,
                code="local_engine_missing",
                recovery="Reinstall CutNotes or build the macOS package before using Parakeet.",
            )
        validate_model(default_model_directory())
    else:
        transcriber_tool = require_tool("CUTNOTES_MACWHISPER", "mw", MACWHISPER_CANDIDATES)
    if not args.transcript_only and args.formatter != "none":
        if args.formatter == "apple":
            formatter_tool = find_local_engine()
            if not formatter_tool:
                raise CutNotesError(
                    "The bundled CutNotes local engine was not found.",
                    EXIT_DEPENDENCY,
                    code="local_engine_missing",
                    recovery="Reinstall CutNotes or explicitly choose Codex.",
                )
        else:
            formatter_tool = require_tool("CUTNOTES_CODEX", "codex", CODEX_CANDIDATES)
    return ffmpeg, transcriber_tool, formatter_tool


def _transcribe(
    args,
    *,
    ffmpeg: str,
    provider_tool: str,
    audio_path: Path,
    transcript_path: Path,
    reporter: ProgressReporter,
    quiet: bool,
) -> None:
    if args.transcriber == "parakeet":
        if args.language.casefold() not in ("en", "auto"):
            reporter.warning(
                "transcribing",
                "Non-English Parakeet transcription is experimental in CutNotes 1.0",
            )
        transcribe_with_parakeet(
            engine=provider_tool,
            ffmpeg=ffmpeg,
            audio_path=audio_path,
            transcript_path=transcript_path,
            reporter=reporter,
        )
    else:
        reporter.stage("transcribing", "Transcribing locally with MacWhisper")
        transcribe_with_macwhisper(
            executable=provider_tool,
            audio_path=audio_path,
            transcript_path=transcript_path,
            language=args.language,
            model=args.whisper_model,
            quiet=quiet,
        )
        reporter.progress("transcribing", 1.0)


def _format(
    args,
    *,
    provider_tool: str,
    transcript_path: Path,
    markdown_path: Path,
    reporter: ProgressReporter,
    quiet: bool,
) -> None:
    reporter.stage("formatting", f"Formatting notes with {args.formatter}")
    if args.formatter == "apple":
        format_with_apple(
            engine=provider_tool,
            transcript_path=transcript_path,
            output_path=markdown_path,
            title=args.title,
            context=args.context,
            reporter=reporter,
        )
    else:
        format_with_codex(
            executable=provider_tool,
            transcript_path=transcript_path,
            output_path=markdown_path,
            title=args.title,
            context=args.context,
            model=args.codex_model,
            quiet=quiet,
            reporter=reporter,
        )


def _metadata(args, *, status: str, **extra) -> dict:
    payload = {
        "schema_version": "cutnotes.session.v1",
        "title": args.title,
        "created_at": dt.datetime.now().astimezone().isoformat(),
        "language": args.language,
        "providers": {
            "transcriber": args.transcriber,
            "formatter": None if args.transcript_only else args.formatter,
        },
        "models": {
            "transcription": "parakeet-tdt-0.6b-v3" if args.transcriber == "parakeet" else (args.whisper_model or "MacWhisper active model"),
            "formatting": (
                None
                if args.transcript_only or args.formatter == "none"
                else "Apple system language model"
                if args.formatter == "apple"
                else (args.codex_model or "Codex CLI default")
            ),
        },
        "status": status,
    }
    payload.update(extra)
    return payload


def run_record(args) -> dict:
    reporter = ProgressReporter(args.progress_fd)
    ffmpeg, transcriber_tool, formatter_tool = _required_pipeline_tools(args)
    assert transcriber_tool is not None
    session_dir = project_directory(Path(args.root), args.title)
    paths = allocate_session_paths(session_dir, args.title, ".wav", not args.transcript_only)
    audio = paths["audio"]
    transcript = paths["transcript"]
    markdown = paths["markdown"]
    metadata_path = paths["metadata"]
    assert audio and transcript and metadata_path
    microphones = list_microphones(ffmpeg)
    index, microphone = choose_microphone(microphones, args.mic, args.device_index)
    metadata = _metadata(
        args,
        status="recording",
        microphone={"index": index, "name": microphone},
    )
    write_json(metadata_path, metadata)
    quiet = args.quiet or args.json
    try:
        record_audio(
            ffmpeg,
            audio,
            index,
            microphone,
            quiet,
            control_fd=args.control_fd,
            reporter=reporter,
        )
        metadata["status"] = "transcribing"
        write_json(metadata_path, metadata)
        _transcribe(
            args,
            ffmpeg=ffmpeg,
            provider_tool=transcriber_tool,
            audio_path=audio,
            transcript_path=transcript,
            reporter=reporter,
            quiet=quiet,
        )
        if markdown and formatter_tool:
            metadata["status"] = "formatting"
            write_json(metadata_path, metadata)
            _format(
                args,
                provider_tool=formatter_tool,
                transcript_path=transcript,
                markdown_path=markdown,
                reporter=reporter,
                quiet=quiet,
            )
        metadata["status"] = "complete"
        metadata["completed_at"] = dt.datetime.now().astimezone().isoformat()
        write_json(metadata_path, metadata)
    except CutNotesError as error:
        metadata["status"] = "cancelled" if error.exit_code == EXIT_CANCELLED else "failed"
        metadata["error_code"] = error.code
        metadata["updated_at"] = dt.datetime.now().astimezone().isoformat()
        write_json(metadata_path, metadata)
        raise
    return result_payload(
        command="record",
        session_dir=session_dir,
        audio_path=audio,
        transcript_path=transcript,
        markdown_path=markdown,
        transcriber=args.transcriber,
        formatter=None if args.transcript_only else args.formatter,
    )


def run_import(args) -> dict:
    source = Path(args.audio).expanduser()
    if source.is_symlink() or not source.resolve().is_file():
        raise CutNotesError(
            "The selected media must be a regular file, not a symbolic link.",
            EXIT_INPUT,
            code="media_not_regular",
            recovery="Choose the original audio or video file.",
        )
    source = source.resolve()
    reporter = ProgressReporter(args.progress_fd)
    ffmpeg, transcriber_tool, formatter_tool = _required_pipeline_tools(args)
    assert transcriber_tool is not None
    ffprobe = find_ffprobe(ffmpeg)
    if not ffprobe:
        raise CutNotesError(
            "Could not find ffprobe beside FFmpeg.",
            EXIT_DEPENDENCY,
            code="ffprobe_missing",
            recovery="Install the complete CutNotes app or set CUTNOTES_FFPROBE.",
        )
    reporter.stage("validating", "Checking imported media")
    enforce_duration_limit(media_duration_seconds(ffprobe, source))
    session_dir = project_directory(Path(args.root), args.title)
    paths = allocate_session_paths(
        session_dir,
        args.title,
        source.suffix.lower() or ".audio",
        not args.transcript_only,
    )
    audio = paths["audio"]
    transcript = paths["transcript"]
    markdown = paths["markdown"]
    metadata_path = paths["metadata"]
    assert audio and transcript and metadata_path
    shutil.copy2(source, audio, follow_symlinks=False)
    metadata = _metadata(args, status="transcribing", source_kind="import")
    write_json(metadata_path, metadata)
    quiet = args.quiet or args.json
    try:
        _transcribe(
            args,
            ffmpeg=ffmpeg,
            provider_tool=transcriber_tool,
            audio_path=audio,
            transcript_path=transcript,
            reporter=reporter,
            quiet=quiet,
        )
        if markdown and formatter_tool:
            metadata["status"] = "formatting"
            write_json(metadata_path, metadata)
            _format(
                args,
                provider_tool=formatter_tool,
                transcript_path=transcript,
                markdown_path=markdown,
                reporter=reporter,
                quiet=quiet,
            )
        metadata["status"] = "complete"
        metadata["completed_at"] = dt.datetime.now().astimezone().isoformat()
        write_json(metadata_path, metadata)
    except CutNotesError as error:
        metadata["status"] = "failed"
        metadata["error_code"] = error.code
        metadata["updated_at"] = dt.datetime.now().astimezone().isoformat()
        write_json(metadata_path, metadata)
        raise
    return result_payload(
        command="import",
        session_dir=session_dir,
        audio_path=audio,
        transcript_path=transcript,
        markdown_path=markdown,
        transcriber=args.transcriber,
        formatter=None if args.transcript_only else args.formatter,
    )


def run_format(args) -> dict:
    transcript = Path(args.transcript).expanduser()
    if transcript.is_symlink() or not transcript.resolve().is_file():
        raise CutNotesError(
            "The selected transcript must be a regular UTF-8 file, not a symbolic link.",
            EXIT_INPUT,
            code="transcript_not_regular",
            recovery="Choose the original transcript file.",
        )
    transcript = transcript.resolve()
    try:
        transcript.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise CutNotesError(
            "The selected transcript is not valid UTF-8 text.",
            EXIT_INPUT,
            code="transcript_encoding",
            recovery="Save the transcript as UTF-8 and try again.",
        ) from error
    if args.formatter == "apple":
        provider_tool = find_local_engine()
        if not provider_tool:
            raise CutNotesError(
                "The bundled CutNotes local engine was not found.",
                EXIT_DEPENDENCY,
                code="local_engine_missing",
                recovery="Reinstall CutNotes or explicitly choose Codex.",
            )
    else:
        provider_tool = require_tool("CUTNOTES_CODEX", "codex", CODEX_CANDIDATES)
    output = Path(args.output).expanduser().resolve() if args.output else transcript.with_name(f"{slugify(args.title)}.md")
    reporter = ProgressReporter(args.progress_fd)
    _format(
        args,
        provider_tool=provider_tool,
        transcript_path=transcript,
        markdown_path=output,
        reporter=reporter,
        quiet=args.quiet or args.json,
    )
    return result_payload(
        command="format",
        session_dir=None,
        audio_path=None,
        transcript_path=transcript,
        markdown_path=output,
        transcriber=None,
        formatter=args.formatter,
    )
