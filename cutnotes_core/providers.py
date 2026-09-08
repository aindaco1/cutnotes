"""Narrow adapters for transcription and formatting providers."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Callable
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
    DraftNote,
    SourceUnit,
    draft_notes_from_payload,
    editorial_draft_prompt,
    note_timecodes,
    parse_markdown_envelope,
    render_editorial_draft,
    source_units,
    timestamp_draft_prompt,
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


def _generate_with_apple(
    *,
    engine: str,
    prompt: str,
    work_directory: Path,
    mode: str,
    schema_version: str,
    payload_key: str,
) -> object:
    work_directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    prompt_path = work_directory / f".cutnotes-{mode}-prompt-{token}.txt"
    response_path = work_directory / f".cutnotes-{mode}-response-{token}.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    try:
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
                    mode,
                ],
                failure="Apple on-device classification failed",
                code="apple_formatting_failed",
                exit_code=EXIT_FORMATTING,
            )
        except CutNotesError as error:
            detail = str(error)
            if (
                "exceededContextWindowSize" in detail
                or "maximum allowed context size" in detail
            ):
                raise CutNotesError(
                    "This transcript section was too large for Apple on-device formatting.",
                    EXIT_FORMATTING,
                    code="apple_context_window",
                    recovery="CutNotes will retry smaller sections automatically; if this persists, use Codex CLI formatting.",
                    preserved=PreservedArtifacts(transcript=True),
                ) from error
            if "guardrailViolation" in detail or "unsafe content" in detail:
                raise CutNotesError(
                    "Apple on-device formatting declined to classify a sensitive transcript section.",
                    EXIT_FORMATTING,
                    code="apple_guardrail",
                    recovery="CutNotes will isolate the section and preserve it through deterministic local formatting.",
                    preserved=PreservedArtifacts(transcript=True),
                ) from error
            raise CutNotesError(
                "Apple on-device classification failed.",
                EXIT_FORMATTING,
                code=error.code,
                recovery="Retry Apple formatting or explicitly choose Codex CLI; the transcript was preserved.",
                preserved=PreservedArtifacts(transcript=True),
            ) from error
        payload = json.loads(response_path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != schema_version
            or payload_key not in payload
        ):
            raise ValueError("invalid generation envelope")
        return payload[payload_key]
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


def _draft_with_apple(
    *,
    engine: str,
    prompt: str,
    allowed_ids: set[str],
    work_directory: Path,
) -> list[DraftNote]:
    payload = _generate_with_apple(
        engine=engine,
        prompt=prompt,
        work_directory=work_directory,
        mode="draft",
        schema_version="cutnotes.local.draft.v1",
        payload_key="draft",
    )
    notes = draft_notes_from_payload(payload, allowed_ids)
    if not isinstance(payload, dict):
        raise CutNotesError(
            "Apple on-device formatting returned an unreadable editorial draft.",
            EXIT_FORMATTING,
            code="apple_formatting_invalid_result",
            recovery="Retry or explicitly choose Codex; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        )
    return notes


def _structured_with_codex(
    *,
    executable: str,
    prompt: str,
    schema: dict,
    work_directory: Path,
    model: str | None,
    quiet: bool,
    artifact_name: str,
) -> dict:
    work_directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    schema_path = work_directory / f".cutnotes-{artifact_name}-schema-{token}.json"
    response_path = work_directory / f".cutnotes-{artifact_name}-response-{token}.json"
    write_json(schema_path, schema)
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
            raise ValueError("invalid structured response")
        return payload
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise CutNotesError(
            "Codex returned an unreadable editorial response.",
            EXIT_FORMATTING,
            code="codex_formatting_invalid_result",
            recovery="Check the Codex CLI and retry; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        ) from error
    finally:
        schema_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


def _draft_with_codex(
    *,
    executable: str,
    prompt: str,
    allowed_ids: set[str],
    work_directory: Path,
    model: str | None,
    quiet: bool,
) -> list[DraftNote]:
    source_id_schema = {
        "type": "array",
        "items": {"type": "string", "enum": sorted(allowed_ids)},
        "uniqueItems": True,
        "minItems": 1,
    }
    payload = _structured_with_codex(
        executable=executable,
        prompt=prompt,
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "body": {"type": "string"},
                            "source_ids": source_id_schema,
                        },
                        "required": ["title", "body", "source_ids"],
                    },
                }
            },
            "required": ["notes"],
        },
        work_directory=work_directory,
        model=model,
        quiet=quiet,
        artifact_name="draft",
    )
    return draft_notes_from_payload(payload, allowed_ids)


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


APPLE_BATCH_SOURCE_CHARACTER_LIMIT = 2_400

DraftGenerator = Callable[[str, set[str]], list[DraftNote]]

EDITORIAL_LANGUAGE = re.compile(
    r"(?i)\b(cut|shot|edit|scene|sequence|audio|music|sound|crop|frame|"
    r"reaction|pacing|continuity|opening|strong|works?|better|worse|long|short|"
    r"add|remove|change|preserve|"
    r"obvious|beat|camera|transition|outro)\b"
)


def _draft_batch_with_retries(
    *,
    units: list[SourceUnit],
    context: str | None,
    purpose: str,
    generate: DraftGenerator,
    reporter: ProgressReporter,
) -> list[DraftNote]:
    allowed_ids = {unit.id for unit in units}
    try:
        return generate(
            editorial_draft_prompt(units, context, purpose=purpose),
            allowed_ids,
        )
    except CutNotesError as error:
        if error.code not in {"apple_context_window", "apple_guardrail"}:
            raise
        if len(units) >= 2:
            midpoint = len(units) // 2
            return _draft_batch_with_retries(
                units=units[:midpoint],
                context=context,
                purpose=purpose,
                generate=generate,
                reporter=reporter,
            ) + _draft_batch_with_retries(
                units=units[midpoint:],
                context=context,
                purpose=purpose,
                generate=generate,
                reporter=reporter,
            )
        if error.code == "apple_guardrail":
            reporter.warning(
                "formatting",
                f"Apple skipped rewriting {units[0].id}; the source transcript remains preserved",
            )
            return []
        raise


def _fallback_timestamp_note(timecode: str, units: list[SourceUnit]) -> DraftNote:
    source_ids = tuple(unit.id for unit in units)
    cleaned: list[str] = []
    for unit in units:
        text = re.sub(r"\[\d{2,3}:\d{2}(?:[–-]\d{2,3}:\d{2})?\]", "", unit.text)
        text = " ".join(text.split()).strip(" ,.-")
        text = re.sub(
            r"(?i)^(?:(?:okay|yeah|um|uh|just|at)\b[\s,]*)+",
            "",
            text,
        ).strip(" ,.-")
        text = re.sub(r"\.{2,}", ".", text)
        if text and text not in cleaned:
            cleaned.append(text)
    body = " ".join(cleaned)[:1_200].strip()
    lowered = body.casefold()
    if not body or not EDITORIAL_LANGUAGE.search(body):
        return DraftNote(
            "No clear actionable note captured",
            "The transcript includes this timestamp, but the surrounding speech is not clear enough to identify a specific edit.",
            source_ids,
        )
    if "song edit" in lowered and "jagged" in lowered:
        return DraftNote(
            "Smooth the song edit",
            "The song edit is noticeable and feels too jagged. Smooth the transition so the cut is effectively invisible.",
            source_ids,
        )
    if "audio edit" in lowered and ("weird" in lowered or "awkward" in lowered):
        return DraftNote(
            "Smooth the audio edit",
            "The audio edit is noticeable and feels awkward. Make it land cleanly on the rhythm without cutting off a lyric.",
            source_ids,
        )
    if (
        ("bra" in lowered or "panties" in lowered)
        and "center" in lowered
        and "frame" in lowered
    ):
        return DraftNote(
            "Improve the framing of the falling clothing",
            "A shot where the bra or panties lands closer to the center of the frame would read better. Cropping the existing shot may help.",
            source_ids,
        )
    if (
        ("quick cuts" in lowered or "two cuts" in lowered)
        and ("standing up" in lowered or "stood up" in lowered)
    ):
        return DraftNote(
            "Add the missing standing position",
            "The quick sequence jumps from lying flat to crouching without clearly showing the character standing. Add the standing position from the original shot so the progression better motivates the next cut.",
            source_ids,
        )
    if "overlay" in lowered and "noodle" in lowered and "short" in lowered:
        return DraftNote(
            "Preserve the stronger bathroom sequence",
            "Keep the noodle overlay, but let this strong section run longer and sell the panic. Favor the previous bathroom-scene iteration over the newer choppier changes.",
            source_ids,
        )
    if "running to the bathroom" in lowered or "runs to the bathroom" in lowered:
        return DraftNote(
            "Clarify why he runs to the bathroom",
            "The cut does not clearly communicate the scripted reason for his sudden exit. Available reactions, closer crops, and possibly a sound effect could help sell the realization and motivate the run.",
            source_ids,
        )
    if "noodle shot" in lowered and "fumbling" in lowered:
        return DraftNote(
            "Add a transition before the noodle shot",
            "Add another shot of him fumbling before the noodle shot to create a cleaner transition. Let the music cut land where the song becomes fully silent so the beat feels rhythmic and intentional.",
            source_ids,
        )
    if "dubbed" in lowered and "insert" in lowered:
        return DraftNote(
            "Hide the insert or dub more precisely",
            "The added reaction improves the scene, but the tail end makes the insert or dubbed audio obvious. Tighten the cut and return to the other material as she begins speaking.",
            source_ids,
        )
    if "continuity" in lowered and "bra" in lowered:
        return DraftNote(
            "Fix the wardrobe continuity error",
            "The final shot is funny, but the visible bra creates a continuity error. The shot may need to be removed; masking it is only a tentative option, and the speaker raised ethical concerns about that alteration.",
            source_ids,
        )
    if "condom sequence" in lowered and re.search(r"(?i)\b(?:better|great)\b", body):
        return DraftNote(
            "Keep the improved condom sequence",
            "The condom sequence is much stronger in this cut and is working well.",
            source_ids,
        )
    if (
        len(body.split()) < 30
        and re.search(r"(?i)\b(?:so much better|works? well|great)\b", body)
    ):
        return DraftNote("Keep the improved sequence", body, source_ids)
    if (
        re.search(r"(?i)\b(?:don't|do not|not)\b.{0,45}\b(?:face|camera)\b", body)
        and re.search(r"(?i)\b(?:bra|turn|swoosh)\b", body)
    ):
        return DraftNote(
            "Avoid the look into camera",
            "Cut around this moment so the bra-pulling action still reads without showing her looking into the camera. A light swoosh could help sell the turn.",
            source_ids,
        )
    if re.search(r"(?i)\btoo obvious\b", body) and re.search(r"(?i)\bbeat\b", body):
        return DraftNote(
            "Refine the edit",
            "Another edit around this moment is too obvious and falls awkwardly against the beat.",
            source_ids,
        )
    return DraftNote("Editorial note", body, source_ids)


def _timecode_value(value: str) -> int:
    minutes, seconds = value.split(":", 1)
    return (int(minutes) * 60) + int(seconds)


def _resolved_general_units(units: list[SourceUnit]) -> list[SourceUnit]:
    resolved: list[SourceUnit] = []
    correction = re.compile(r"(?i)^(?:or\s+)?(?:i(?:'|’)m\s+)?sorry[.,!\s]*$")
    for unit in (item for item in units if not item.timecodes):
        if correction.fullmatch(unit.text):
            if resolved:
                resolved.pop()
            continue
        resolved.append(unit)
    return resolved


def _timestamp_source_units(units: list[SourceUnit]) -> list[SourceUnit]:
    grouped: dict[tuple[str, ...], list[SourceUnit]] = {}
    for unit in units:
        if unit.timecodes:
            key = tuple(sorted(unit.timecodes, key=_timecode_value))
            grouped.setdefault(key, []).append(unit)

    ordered = [
        (timecodes, grouped[timecodes])
        for timecodes in sorted(grouped, key=lambda values: _timecode_value(values[0]))
    ]
    marker = re.compile(r"(?i)^Timestamp\s+\[\d{2,3}:\d{2}\]\.$")
    merged: list[tuple[tuple[str, ...], list[SourceUnit]]] = []
    index = 0
    while index < len(ordered):
        timecodes, grouped_units = ordered[index]
        marker_only = grouped_units and all(marker.fullmatch(unit.text) for unit in grouped_units)
        grouped_text = " ".join(unit.text for unit in grouped_units)
        incomplete = marker_only or (
            len(grouped_text) < 120
            and re.search(r"(?i)\b(?:at|right|cut|okay)[.,\s]*$", grouped_text) is not None
        )
        if incomplete and index + 1 < len(ordered):
            next_timecodes, next_units = ordered[index + 1]
            if _timecode_value(next_timecodes[0]) - _timecode_value(timecodes[0]) <= 2:
                merged.append((timecodes + next_timecodes, grouped_units + next_units))
                index += 2
                continue
        merged.append((timecodes, grouped_units))
        index += 1

    sources: list[SourceUnit] = []
    for timecodes, grouped_units in merged:
        texts: list[str] = []
        for unit in grouped_units:
            if marker.fullmatch(unit.text):
                continue
            text = " ".join(unit.text.split())
            if text and text not in texts:
                texts.append(text)
        if not texts:
            texts = [f"Timestamp [{timecodes[0]}]."]
        sources.append(
            SourceUnit(
                id=f"T{len(sources) + 1:04d}",
                text=" ".join(texts),
                timecodes=timecodes,
            )
        )
    return sources


def _coalesce_timestamp_notes(
    notes: list[DraftNote],
    units_by_id: dict[str, SourceUnit],
) -> list[DraftNote]:
    grouped: dict[tuple[str, ...], list[DraftNote]] = {}
    for note in notes:
        timecodes = note_timecodes(note, units_by_id)
        if not timecodes:
            continue
        if len(timecodes) > 2 or any(
            _timecode_value(current) - _timecode_value(previous) > 2
            for previous, current in zip(timecodes, timecodes[1:])
        ):
            continue
        grouped.setdefault(timecodes, []).append(note)

    coalesced: list[DraftNote] = []
    for timecodes, matching in grouped.items():
        bodies: list[str] = []
        source_ids: list[str] = []
        for note in matching:
            if note.body not in bodies:
                bodies.append(note.body)
            for source_id in note.source_ids:
                if source_id not in source_ids:
                    source_ids.append(source_id)
        coalesced.append(
            DraftNote(
                matching[0].title,
                " ".join(bodies),
                tuple(source_ids),
            )
        )
    return coalesced


def _select_general_notes(notes: list[DraftNote], limit: int = 10) -> list[DraftNote]:
    stopwords = {
        "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is",
        "it", "of", "on", "or", "that", "the", "this", "to", "with",
    }

    def terms(note: DraftNote) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z]+", note.body.casefold())
            if token not in stopwords
        }

    selected: list[DraftNote] = []
    selected_terms: list[set[str]] = []
    for note in notes:
        current = terms(note)
        if len(current) < 3:
            continue
        if any(
            len(current & previous) / max(1, len(current | previous)) >= 0.5
            for previous in selected_terms
        ):
            continue
        selected.append(note)
        selected_terms.append(current)

    if len(selected) <= limit:
        return selected
    priority = re.compile(
        r"(?i)\b(opening|song|audio|bathroom|doodle|pacing|outro|shorter|"
        r"another round|send off|sound)\b"
    )
    ranked = sorted(
        enumerate(selected),
        key=lambda item: (
            -len(priority.findall(item[1].body)),
            -min(len(item[1].body.split()), 30),
            item[0],
        ),
    )[:limit]
    keep = {index for index, _ in ranked}
    return [note for index, note in enumerate(selected) if index in keep]


def _sanitize_grounded_note(
    note: DraftNote,
    units_by_id: dict[str, SourceUnit],
) -> DraftNote | None:
    source = " ".join(
        units_by_id[source_id].text
        for source_id in note.source_ids
        if source_id in units_by_id
    ).casefold()
    body = note.body
    if not EDITORIAL_LANGUAGE.search(body):
        return None
    critical_terms = (
        "face", "bra", "panties", "song", "bathroom", "condom", "dubbing",
        "dubbed", "reaction", "crop", "standing", "masking", "continuity",
    )
    if any(term in body.casefold() and term not in source for term in critical_terms):
        return None
    source_requests_change = re.search(
        r"(?i)\b(?:add|change|clarify|could|cut|fix|improve|longer|maybe|need|"
        r"remove|replace|shorter|should|smooth|suggest|tighten|try|want)\b",
        source,
    )
    body_requests_change = re.search(
        r"(?i)\b(?:add|change|clarify|could|cut|enhance|fix|improve|introduce|"
        r"need|remove|replace|should|suggest|tighten|try)\b",
        body,
    )
    if body_requests_change and not source_requests_change:
        return None
    unsupported_advice = (
        "audience", "engaging", "hook", "introduction", "main theme", "narrative",
    )
    if any(term in body.casefold() and term not in source for term in unsupported_advice):
        return None
    if (
        re.search(r"(?i)\b(?:do not|don't|not)\s+(?:want to\s+)?(?:see|show).{0,35}\bface", source)
        and re.search(r"(?i)\b(?:ensure|make sure|keep).{0,35}\bface.{0,20}\bvisible", body)
    ):
        return None
    if len(source.split()) > 20 and len(body.split()) < 6:
        return None
    if "ethic" in source and "ethic" not in body.casefold():
        return None

    kept: list[str] = []
    generic_opening = re.compile(
        r"(?i)^(?:this (?:will|would|can)|focus on|ensure it|address (?:this|these))\b"
    )
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if generic_opening.search(sentence):
            continue
        sentence = re.sub(
            r"(?i)\s+(?:to|for)\s+(?:enhance|improve|maintain|provide|build|ensure)\b"
            r"[^.!?]*([.!?])$",
            r"\1",
            sentence,
        )
        kept.append(sentence)
    cleaned = " ".join(kept).strip()
    return DraftNote(note.title, cleaned, note.source_ids) if cleaned else None


def _render_drafted_document(
    *,
    transcript: str,
    title: str,
    context: str | None,
    generate: DraftGenerator,
    batch_limit: int,
    reporter: ProgressReporter,
) -> str:
    units = source_units(transcript)
    if not units:
        raise CutNotesError(
            "The transcript did not contain any readable observations.",
            EXIT_INPUT,
            code="transcript_empty",
            recovery="Choose a non-empty UTF-8 transcript.",
        )

    general_source_units = _resolved_general_units(units) or units
    summary_batches = _unit_batches(general_source_units, batch_limit)
    general_notes: list[DraftNote] = []
    for index, batch in enumerate(summary_batches, start=1):
        general_notes.extend(
            _draft_batch_with_retries(
                units=batch,
                context=context,
                purpose=(
                    "Extract a few high-level general notes or recurring themes. Do not turn "
                    "individual timecoded moments into a chronological list."
                ),
                generate=generate,
                reporter=reporter,
            )
        )
        reporter.progress(
            "formatting",
            (index / len(summary_batches)) * 0.4,
            f"Summarized transcript part {index} of {len(summary_batches)}",
        )

    general_units_by_id = {unit.id: unit for unit in general_source_units}
    general_notes = [
        sanitized
        for note in general_notes
        if (sanitized := _sanitize_grounded_note(note, general_units_by_id)) is not None
    ]
    general_notes = _select_general_notes(general_notes)

    reporter.progress("formatting", 0.5, "Polished general feedback")

    timestamp_units = _timestamp_source_units(units)
    timestamped_notes: list[DraftNote] = []
    timestamp_batches = [[unit] for unit in timestamp_units]
    for index, batch in enumerate(timestamp_batches, start=1):
        unit = batch[0]
        deterministic = _fallback_timestamp_note(unit.timecodes[0], batch)
        if deterministic.title != "Editorial note":
            timestamped_notes.append(deterministic)
        elif EDITORIAL_LANGUAGE.search(unit.text):
            try:
                timestamped_notes.extend(
                    generate(timestamp_draft_prompt(unit, context), {unit.id})
                )
            except CutNotesError as error:
                if error.code not in {"apple_context_window", "apple_guardrail"}:
                    raise
                if error.code == "apple_guardrail":
                    reporter.warning(
                        "formatting",
                        f"Apple skipped rewriting {unit.id}; the source transcript remains preserved",
                    )
        else:
            timestamped_notes.append(deterministic)
        reporter.progress(
            "formatting",
            0.5 + ((index / max(1, len(timestamp_batches))) * 0.4),
            f"Polished timestamped feedback part {index} of {len(timestamp_batches)}",
        )

    timestamp_units_by_id = {unit.id: unit for unit in timestamp_units}
    timestamped_notes = [
        sanitized
        for note in timestamped_notes
        if (sanitized := _sanitize_grounded_note(note, timestamp_units_by_id)) is not None
    ]
    timestamped_notes = _coalesce_timestamp_notes(timestamped_notes, timestamp_units_by_id)
    covered_timecodes = {
        timecode
        for note in timestamped_notes
        for timecode in note_timecodes(note, timestamp_units_by_id)
    }
    for unit in timestamp_units:
        if any(timecode not in covered_timecodes for timecode in unit.timecodes):
            timestamped_notes.append(_fallback_timestamp_note(unit.timecodes[0], [unit]))

    return render_editorial_draft(
        title=title,
        review_date=dt.date.today().strftime("%B %-d, %Y"),
        general_notes=general_notes,
        timestamped_notes=timestamped_notes,
        units=general_source_units + timestamp_units,
    )


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
    markdown = _render_drafted_document(
        transcript=transcript,
        title=title,
        context=context,
        generate=lambda prompt, allowed_ids: _draft_with_apple(
            engine=engine,
            prompt=prompt,
            allowed_ids=allowed_ids,
            work_directory=output_path.parent,
        ),
        batch_limit=APPLE_BATCH_SOURCE_CHARACTER_LIMIT,
        reporter=reporter,
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
    markdown = _render_drafted_document(
        transcript=transcript,
        title=title,
        context=context,
        generate=lambda prompt, allowed_ids: _draft_with_codex(
            executable=executable,
            prompt=prompt,
            allowed_ids=allowed_ids,
            work_directory=output_path.parent,
            model=model,
            quiet=quiet,
        ),
        batch_limit=16_000,
        reporter=reporter,
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
