"""Narrow adapters for transcription and formatting providers."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from .contracts import (
    CutNotesError,
    EXIT_DEPENDENCY,
    EXIT_FORMATTING,
    EXIT_INPUT,
    EXIT_TRANSCRIPTION,
    PreservedArtifacts,
    ProgressReporter,
)
from .filesystem import write_json
from .formatting import (
    SourceUnit,
    editorial_plan_prompt,
    parse_markdown_envelope,
    render_editorial_plan,
    source_units,
    validate_timecodes,
    validate_markdown,
)
from .models import default_model_directory, validate_model


MACWHISPER_CANDIDATES = (
    Path("/Applications/MacWhisper.app/Contents/MacOS/mw"),
    Path.home() / "Applications/MacWhisper.app/Contents/MacOS/mw",
)
CODEX_CANDIDATES = (
    Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
    Path("/Applications/Codex.app/Contents/Resources/codex"),
    Path.home() / "Applications/ChatGPT.app/Contents/Resources/codex",
    Path.home() / "Applications/Codex.app/Contents/Resources/codex",
)


def find_tool(env_name: str, command: str, candidates: tuple[Path, ...] = ()) -> str | None:
    override = os.environ.get(env_name)
    if override:
        expanded = Path(override).expanduser()
        return str(expanded) if expanded.is_file() and os.access(expanded, os.X_OK) else None
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(command)


def require_tool(env_name: str, command: str, candidates: tuple[Path, ...] = ()) -> str:
    tool = find_tool(env_name, command, candidates)
    if tool:
        return tool
    raise CutNotesError(
        f"Could not find {command}.",
        EXIT_DEPENDENCY,
        code="dependency_missing",
        recovery=f"Install the dependency or set {env_name} to its executable path.",
    )


def local_engine_candidates() -> tuple[Path, ...]:
    repository = Path(__file__).resolve().parents[1]
    return (
        repository / "macos" / ".build" / "arm64-apple-macosx" / "release" / "CutNotesLocal",
        repository / "macos" / ".build" / "arm64-apple-macosx" / "debug" / "CutNotesLocal",
        repository / "macos" / ".build" / "release" / "CutNotesLocal",
        repository / "macos" / ".build" / "debug" / "CutNotesLocal",
    )


def find_local_engine() -> str | None:
    return find_tool("CUTNOTES_LOCAL_ENGINE", "CutNotesLocal", local_engine_candidates())


def command_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return combined.splitlines()[0] if combined else "installed"


def local_engine_status(engine: str | None = None) -> dict:
    executable = engine or find_local_engine()
    if not executable:
        return {
            "path": None,
            "version": None,
            "apple": {"state": "unavailable", "reason": "local_engine_missing"},
        }
    try:
        result = subprocess.run(
            [executable, "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        payload = {}
    apple = payload.get("apple") if isinstance(payload, dict) else None
    return {
        "path": executable,
        "version": payload.get("version") if isinstance(payload, dict) else None,
        "apple": apple if isinstance(apple, dict) else {
            "state": "unavailable",
            "reason": "status_failed",
        },
    }


def _run_checked(command: list[str], *, failure: str, code: str, exit_code: int) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as error:
        raise CutNotesError(
            failure,
            exit_code,
            code=code,
            recovery="Verify the selected provider and retry; existing artifacts were preserved.",
        ) from error
    if result.returncode != 0:
        detail = " ".join(result.stderr.strip().split())[:500]
        raise CutNotesError(
            f"{failure}{f': {detail}' if detail else '.'}",
            exit_code,
            code=code,
            recovery="Verify the selected provider and retry; existing artifacts were preserved.",
        )
    return result


def transcribe_with_macwhisper(
    *,
    executable: str,
    audio_path: Path,
    transcript_path: Path,
    language: str,
    model: str | None,
    quiet: bool,
) -> None:
    command = [
        executable,
        "transcribe",
        "--language",
        language,
        "--format",
        "txt",
        "--style",
        "transcript",
        "--no-timestamps",
        "--no-speakers",
        "--output",
        str(transcript_path),
        "--overwrite",
    ]
    if model:
        command.extend(["--model", model])
    command.append(str(audio_path))
    if not quiet:
        print("Transcribing locally with MacWhisper…", file=os.sys.stderr)
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as error:
        raise CutNotesError(
            "MacWhisper could not be started.",
            EXIT_TRANSCRIPTION,
            code="macwhisper_start_failed",
            recovery="Check MacWhisper, then retry; the audio was preserved.",
            preserved=PreservedArtifacts(audio=True),
        ) from error
    if result.returncode != 0:
        detail = " ".join(result.stderr.strip().split())[:500]
        raise CutNotesError(
            f"MacWhisper transcription failed{f': {detail}' if detail else '.'}",
            EXIT_TRANSCRIPTION,
            code="macwhisper_failed",
            recovery="Check MacWhisper, then retry; the audio was preserved.",
            preserved=PreservedArtifacts(audio=True),
        )
    if not transcript_path.is_file() or not transcript_path.read_text(encoding="utf-8").strip():
        raise CutNotesError(
            "MacWhisper produced an empty transcript.",
            EXIT_TRANSCRIPTION,
            code="transcript_empty",
            recovery="Retry with a recording that contains clear speech; the audio was preserved.",
            preserved=PreservedArtifacts(audio=True),
        )


def _create_audio_chunks(ffmpeg: str, source: Path, directory: Path) -> list[Path]:
    pattern = directory / "chunk-%04d.wav"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-f",
        "segment",
        "-segment_time",
        "900",
        "-reset_timestamps",
        "1",
        str(pattern),
    ]
    _run_checked(
        command,
        failure="FFmpeg could not prepare the recording for local transcription",
        code="audio_preparation_failed",
        exit_code=EXIT_TRANSCRIPTION,
    )
    chunks = sorted(directory.glob("chunk-*.wav"))
    if not chunks:
        raise CutNotesError(
            "The recording did not contain a usable audio track.",
            EXIT_TRANSCRIPTION,
            code="audio_track_missing",
            recovery="Choose a media file with an audio track; the original was not changed.",
            preserved=PreservedArtifacts(audio=True),
        )
    return chunks


def transcribe_with_parakeet(
    *,
    engine: str,
    ffmpeg: str,
    audio_path: Path,
    transcript_path: Path,
    reporter: ProgressReporter,
) -> None:
    model = default_model_directory()
    validate_model(model)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    reporter.stage("transcribing", "Transcribing locally with Parakeet v3")
    with tempfile.TemporaryDirectory(prefix="cutnotes-audio-") as temporary:
        temporary_directory = Path(temporary)
        chunks = _create_audio_chunks(ffmpeg, audio_path, temporary_directory)
        texts: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            result_path = temporary_directory / f"result-{index:04d}.json"
            _run_checked(
                [
                    engine,
                    "transcribe",
                    "--audio",
                    str(chunk),
                    "--model",
                    str(model),
                    "--output",
                    str(result_path),
                ],
                failure="Parakeet local transcription failed",
                code="parakeet_failed",
                exit_code=EXIT_TRANSCRIPTION,
            )
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                text = payload["text"].strip()
            except (OSError, json.JSONDecodeError, KeyError, AttributeError) as error:
                raise CutNotesError(
                    "Parakeet returned an unreadable transcript.",
                    EXIT_TRANSCRIPTION,
                    code="parakeet_invalid_result",
                    recovery="Retry transcription; the audio was preserved.",
                    preserved=PreservedArtifacts(audio=True),
                ) from error
            if text:
                texts.append(text)
            reporter.progress(
                "transcribing",
                index / len(chunks),
                f"Transcribed audio part {index} of {len(chunks)}",
            )
    transcript = "\n\n".join(texts).strip()
    if not transcript:
        raise CutNotesError(
            "Parakeet produced an empty transcript.",
            EXIT_TRANSCRIPTION,
            code="transcript_empty",
            recovery="Retry with a recording that contains clear speech; the audio was preserved.",
            preserved=PreservedArtifacts(audio=True),
        )
    temporary_transcript = transcript_path.with_name(f".{transcript_path.name}.tmp")
    temporary_transcript.write_text(transcript + "\n", encoding="utf-8")
    temporary_transcript.replace(transcript_path)


def _plan_with_apple(engine: str, prompt: str, work_directory: Path) -> dict:
    work_directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    prompt_path = work_directory / f".cutnotes-plan-prompt-{token}.txt"
    response_path = work_directory / f".cutnotes-plan-response-{token}.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    try:
        _run_checked(
            [
                engine,
                "generate",
                "--prompt",
                str(prompt_path),
                "--output",
                str(response_path),
                "--mode",
                "plan",
            ],
            failure="Apple on-device classification failed",
            code="apple_formatting_failed",
            exit_code=EXIT_FORMATTING,
        )
        payload = json.loads(response_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "cutnotes.local.plan.v1" or not isinstance(payload.get("plan"), dict):
            raise ValueError("invalid plan envelope")
        return payload["plan"]
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise CutNotesError(
            "Apple on-device formatting returned an unreadable source plan.",
            EXIT_FORMATTING,
            code="apple_formatting_invalid_result",
            recovery="Retry or explicitly choose Codex; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        ) from error
    finally:
        prompt_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


PLAN_KEYS = (
    "highest_priority_changes",
    "sound_and_foley_direction",
    "recurring_themes",
    "open_questions",
    "positive_notes",
)


def _empty_plan() -> dict[str, list[str]]:
    return {key: [] for key in PLAN_KEYS}


def _merge_plan(target: dict[str, list[str]], source: dict) -> None:
    for key in PLAN_KEYS:
        values = source.get(key, [])
        if isinstance(values, list):
            target[key].extend(value for value in values if isinstance(value, str))


def _plan_with_codex(
    *,
    executable: str,
    prompt: str,
    allowed_ids: list[str],
    work_directory: Path,
    model: str | None,
    quiet: bool,
) -> dict:
    work_directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    schema_path = work_directory / f".cutnotes-plan-schema-{token}.json"
    response_path = work_directory / f".cutnotes-plan-response-{token}.json"
    array_schema = {
        "type": "array",
        "items": {"type": "string", "enum": allowed_ids},
        "uniqueItems": True,
    }
    write_json(
        schema_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {key: array_schema for key in PLAN_KEYS},
            "required": list(PLAN_KEYS),
        },
    )
    command = [
        executable,
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(response_path),
        "--cd",
        str(work_directory),
    ]
    if model:
        command.extend(["--model", model])
    command.append("-")
    try:
        result = subprocess.run(
            command,
            input=prompt,
            check=False,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            detail = " ".join(result.stderr.strip().split())[:500]
            raise CutNotesError(
                f"Codex classification failed{f': {detail}' if detail else '.'}",
                EXIT_FORMATTING,
                code="codex_formatting_failed",
                recovery="Check the Codex CLI and retry; the transcript was preserved.",
                preserved=PreservedArtifacts(transcript=True),
            )
        payload = json.loads(response_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid plan")
        return payload
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise CutNotesError(
            "Codex returned an unreadable source plan.",
            EXIT_FORMATTING,
            code="codex_formatting_invalid_result",
            recovery="Check the Codex CLI and retry; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        ) from error
    finally:
        schema_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


def _unit_batches(units: list[SourceUnit], limit: int = 16_000) -> list[list[SourceUnit]]:
    batches: list[list[SourceUnit]] = []
    current: list[SourceUnit] = []
    length = 0
    for unit in units:
        size = len(unit.id) + len(unit.text) + 4
        if current and length + size > limit:
            batches.append(current)
            current = []
            length = 0
        current.append(unit)
        length += size
    if current:
        batches.append(current)
    return batches


def format_with_apple(
    *,
    engine: str,
    transcript_path: Path,
    output_path: Path,
    title: str,
    context: str | None,
    reporter: ProgressReporter,
) -> None:
    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        raise CutNotesError(
            "The transcript is empty.",
            EXIT_INPUT,
            code="transcript_empty",
            recovery="Choose a non-empty UTF-8 transcript.",
        )
    units = source_units(transcript)
    if not units:
        raise CutNotesError(
            "The transcript did not contain any readable observations.",
            EXIT_INPUT,
            code="transcript_empty",
            recovery="Choose a non-empty UTF-8 transcript.",
        )
    merged_plan = _empty_plan()
    batches = _unit_batches(units)
    for index, batch in enumerate(batches, start=1):
        plan = _plan_with_apple(
            engine,
            editorial_plan_prompt(batch, context),
            output_path.parent,
        )
        _merge_plan(merged_plan, plan)
        reporter.progress(
            "formatting",
            (index / len(batches)) * 0.9,
            f"Classified transcript part {index} of {len(batches)}",
        )
    review_date = dt.date.today().strftime("%B %-d, %Y")
    markdown = render_editorial_plan(
        title=title,
        review_date=review_date,
        units=units,
        plan=merged_plan,
    )
    _write_validated_markdown(markdown, output_path, transcript_path)
    reporter.progress("formatting", 1.0, "Editorial notes are ready")


def format_with_codex(
    *,
    executable: str,
    transcript_path: Path,
    output_path: Path,
    title: str,
    context: str | None,
    model: str | None,
    quiet: bool,
    reporter: ProgressReporter,
) -> None:
    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        raise CutNotesError(
            "The transcript is empty.",
            EXIT_INPUT,
            code="transcript_empty",
            recovery="Choose a non-empty UTF-8 transcript.",
        )
    units = source_units(transcript)
    if not units:
        raise CutNotesError(
            "The transcript did not contain any readable observations.",
            EXIT_INPUT,
            code="transcript_empty",
            recovery="Choose a non-empty UTF-8 transcript.",
        )
    merged_plan = _empty_plan()
    batches = _unit_batches(units)
    for index, batch in enumerate(batches, start=1):
        plan = _plan_with_codex(
            executable=executable,
            prompt=editorial_plan_prompt(batch, context),
            allowed_ids=[unit.id for unit in batch],
            work_directory=output_path.parent,
            model=model,
            quiet=quiet,
        )
        _merge_plan(merged_plan, plan)
        reporter.progress(
            "formatting",
            (index / len(batches)) * 0.9,
            f"Classified transcript part {index} of {len(batches)}",
        )
    markdown = render_editorial_plan(
        title=title,
        review_date=dt.date.today().strftime("%B %-d, %Y"),
        units=units,
        plan=merged_plan,
    )
    _write_validated_markdown(markdown, output_path, transcript_path)
    reporter.progress("formatting", 1.0, "Editorial notes are ready")


def _write_validated_markdown(markdown: str, output_path: Path, transcript_path: Path) -> None:
    missing = validate_markdown(markdown)
    if missing:
        raise CutNotesError(
            "The formatter omitted required document sections: " + ", ".join(missing),
            EXIT_FORMATTING,
            code="formatter_contract_failed",
            recovery="Retry formatting or choose another formatter; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        )
    transcript = transcript_path.read_text(encoding="utf-8")
    invented, omitted = validate_timecodes(markdown, transcript)
    if invented or omitted:
        details: list[str] = []
        if invented:
            details.append("invented " + ", ".join(f"[{value}]" for value in invented))
        if omitted:
            details.append("omitted " + ", ".join(f"[{value}]" for value in omitted))
        raise CutNotesError(
            "The formatter returned ungrounded CUT timecodes (" + "; ".join(details) + ").",
            EXIT_FORMATTING,
            code="formatter_timecode_contract_failed",
            recovery="Retry formatting or choose another formatter; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        )
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    temporary.replace(output_path)
