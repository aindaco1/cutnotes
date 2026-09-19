"""Narrow adapters for transcription and formatting providers."""

from __future__ import annotations

from dataclasses import replace
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
    BRACKETED_TIMECODE,
    DraftNote,
    SourceUnit,
    draft_notes_from_payload,
    editorial_draft_prompt,
    note_timecodes,
    parse_markdown_envelope,
    render_editorial_draft,
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


def _generate_with_apple(
    *,
    engine: str,
    prompt: str,
    work_directory: Path,
    mode: str,
    schema_version: str,
    payload_key: str,
    instructions: str | None = None,
) -> object:
    work_directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    prompt_path = work_directory / f".cutnotes-{mode}-prompt-{token}.txt"
    response_path = work_directory / f".cutnotes-{mode}-response-{token}.json"
    instructions_path = work_directory / f".cutnotes-{mode}-instructions-{token}.txt"
    # Draft-v1 helpers before 1.0.5 ignore --instructions. Keep a complete request
    # in their existing prompt file; newer helpers remove this exact prefix before
    # sending the source to the model with separate session instructions.
    compatible_prompt = f"{instructions.strip()}\n\n{prompt}" if instructions else prompt
    prompt_path.write_text(compatible_prompt, encoding="utf-8")
    try:
        instruction_arguments: list[str] = []
        if instructions is not None:
            instructions_path.write_text(instructions, encoding="utf-8")
            instruction_arguments = ["--instructions", str(instructions_path)]
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
                    *instruction_arguments,
                ],
                failure="Apple on-device classification failed",
                code="apple_formatting_failed",
                exit_code=EXIT_FORMATTING,
            )
        except CutNotesError as error:
            detail = str(error)
            if "Apple on-device formatting is unavailable." in detail:
                raise CutNotesError(
                    "Apple on-device formatting is not ready on this Mac.",
                    EXIT_FORMATTING,
                    code="apple_model_unavailable",
                    recovery=(
                        "Check Apple Intelligence in System Settings and wait for its models "
                        "to finish preparing, then retry formatting; the transcript was preserved."
                    ),
                    preserved=PreservedArtifacts(transcript=True),
                ) from error
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
        instructions_path.unlink(missing_ok=True)


def _draft_with_apple(
    *,
    engine: str,
    prompt: str,
    allowed_ids: set[str],
    work_directory: Path,
) -> list[DraftNote]:
    # Numeric observation labels are easily mistaken for video timestamps by the
    # on-device model. Use alphabetic request-local aliases on this boundary.
    def alphabetic(index: int) -> str:
        result = ""
        while index >= 0:
            result = chr(97 + index % 26) + result
            index = index // 26 - 1
        return "obs_" + result

    aliases = {source_id: alphabetic(index) for index, source_id in enumerate(sorted(allowed_ids))}
    reverse_aliases = {alias: source_id for source_id, alias in aliases.items()}
    prompt = re.sub(r"\b[NT]\d{4}\b", lambda match: aliases.get(match.group(), match.group()), prompt)
    instructions, marker, source = prompt.partition("<source-observations>")
    if not marker:
        raise ValueError("Editorial draft request is missing source observations")
    payload = _generate_with_apple(
        engine=engine,
        prompt=marker + source,
        instructions=instructions.strip(),
        work_directory=work_directory,
        mode="draft",
        schema_version="cutnotes.local.draft.v1",
        payload_key="draft",
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list) or any(
        not isinstance(note, dict) or not {"body", "title", "source_ids"} <= note.keys()
        for note in payload.get("notes", [])
    ):
        raise CutNotesError(
            "Apple on-device formatting returned an unreadable editorial draft.",
            EXIT_FORMATTING,
            code="apple_formatting_invalid_result",
            recovery="Retry or explicitly choose Codex; the transcript was preserved.",
            preserved=PreservedArtifacts(transcript=True),
        )
    for note in payload["notes"]:
        for field in ("title", "body"):
            if isinstance(note.get(field), str):
                note[field] = re.sub(r"\bobs_[a-z]+\b", lambda match: reverse_aliases.get(match.group(), ""), note[field])
        if isinstance(note.get("source_ids"), list):
            note["source_ids"] = [reverse_aliases.get(source_id, source_id) if isinstance(source_id, str)
                                  else source_id for source_id in note["source_ids"]]
    return draft_notes_from_payload(payload, allowed_ids)


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


def _split_source_unit(unit: SourceUnit, limit: int) -> list[SourceUnit]:
    chunks: list[SourceUnit] = []
    remaining = unit.text.strip()
    while len(remaining) > limit:
        boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary <= 0:
            boundary = limit
        chunks.append(SourceUnit(unit.id, remaining[:boundary], unit.timecodes))
        remaining = remaining[boundary:].lstrip()
    if remaining:
        chunks.append(SourceUnit(unit.id, remaining, unit.timecodes))
    return chunks


def _unit_batches(units: list[SourceUnit], limit: int = 16_000) -> list[list[SourceUnit]]:
    batches: list[list[SourceUnit]] = []
    current: list[SourceUnit] = []
    length = 0
    for unit in (chunk for source in units for chunk in _split_source_unit(source, max(100, limit - 80))):
        # Account for IDs repeated in the instruction and source lists, plus times.
        size = 2 * len(unit.id) + len(unit.text) + sum(len(t) + 3 for t in unit.timecodes) + 64
        if current and length + size > limit:
            batches.append(current)
            current = []
            length = 0
        current.append(unit)
        length += size
    if current:
        batches.append(current)
    return batches


APPLE_BATCH_SOURCE_CHARACTER_LIMIT = 4_800

DraftGenerator = Callable[[str, set[str]], list[DraftNote]]


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
        if len(units[0].text) > 200:
            return [
                note
                for fragment in _split_source_unit(units[0], len(units[0].text) // 2)
                for note in _draft_batch_with_retries(
                    units=[fragment], context=context, purpose=purpose,
                    generate=generate, reporter=reporter,
                )
            ]
        if error.code == "apple_guardrail":
            reporter.warning(
                "formatting",
                f"Apple skipped rewriting {units[0].id}; the source transcript remains preserved",
            )
            return []
        raise


def _fallback_timestamp_note(timecode: str, units: list[SourceUnit]) -> DraftNote:
    """Mark incomplete synthesis without pretending a transcript dump is an edit note."""
    return DraftNote(
        "Formatting incomplete",
        "An editorial note could not be generated for this moment. Review the preserved transcript.",
        tuple(unit.id for unit in units),
    )


def _timecode_value(value: str) -> int:
    minutes, seconds = value.split(":", 1)
    return (int(minutes) * 60) + int(seconds)


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


def _select_general_notes(notes: list[DraftNote]) -> list[DraftNote]:
    # Similar vocabulary is not equivalent feedback: "keep the music" and
    # "do not keep the music" must not collapse into one observation.
    selected: list[DraftNote] = []
    seen: set[str] = set()
    for note in notes:
        key = " ".join(note.body.casefold().split()).rstrip(".!?")
        if not key or key in seen:
            continue
        selected.append(note)
        seen.add(key)
    return selected


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
    if any(tag in body.casefold() for tag in ("<context>", "<source", "</source", "spelling context:")):
        return None
    # IDs establish provenance, but do not by themselves prevent an unrelated
    # paraphrase. Check vocabulary overlap without requiring any editorial keywords.
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
        "could", "did", "do", "does", "for", "from", "had", "has", "have", "he",
        "her", "here", "him", "his", "i", "if", "in", "is", "it", "its", "like",
        "may", "might", "my", "of", "on", "or", "our", "s", "she", "should",
        "so", "some", "t", "that", "the", "their", "them", "there", "these", "they",
        "this", "those", "to", "was", "we", "were", "what", "when", "which",
        "while", "who", "will", "with", "would", "you", "your",
    }

    def content_words(text: str) -> set[str]:
        words = re.findall(r"[a-z]+", text.casefold())
        return {
            re.sub(r"(?:ing|ed|es|s)$", "", word).rstrip("e")
            for word in words if word not in stopwords and len(word) > 1
        }

    source_words, body_words = content_words(source), content_words(body)
    if len(body_words) >= 3 and len(body_words & source_words) / len(body_words) < 0.3:
        return None
    for problem, reversal in (("early", "earlier"), ("late", "later")):
        if re.search(rf"\b(?:too|little|slightly) {problem}\b", source) and re.search(
            rf"\b(?:move|shift|place|time|timed|hit|play|start|land)\b[^.!?]{{0,60}}\b{reversal}\b",
            body, re.IGNORECASE,
        ):
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
    if "ethic" in source and "ethic" not in body.casefold():
        return None

    # Grounded consequences and qualifications are part of the feedback too;
    # do not erase sentences merely because they start with "This would".
    return replace(note, body=body.strip()) if body.strip() else None


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

    by_id = {unit.id: unit for unit in units}
    allowed_times = {time for unit in units for time in unit.timecodes}
    # Keep a video moment together and separate it from other moments before
    # asking the small on-device model to rewrite prose. A retrospective time
    # clarification remains with the passage it qualifies.
    passages: list[list[SourceUnit]] = []
    for unit in units:
        retrospective = re.search(r"(?i)\b(?:that(?:'s| is)|this was|I mean)[^.!?]{0,45}\b(?:around|at)\s*\[", unit.text)
        new_topic = re.search(r"(?i)\b(?:overall|general note|one (?:other|more) thing|bonus (?:thing|thought)|final (?:thought|note))\b", unit.text) or (unit.text.endswith("?") and len(unit.text.split()) >= 4)
        if passages and ((unit.timecodes == passages[-1][-1].timecodes and not new_topic) or retrospective):
            passages[-1].append(unit)
        else:
            passages.append([unit])
    batches = [batch for passage in passages for batch in _unit_batches(passage, batch_limit)]
    notes: list[DraftNote] = []
    for index, batch in enumerate(batches, start=1):
        drafts = _draft_batch_with_retries(
            units=batch, context=context,
            purpose="Write one concise note for this passage, keeping every concrete observation and qualification.",
            generate=generate, reporter=reporter,
        )
        drafts = [accepted for draft in drafts
                  if (accepted := _sanitize_grounded_note(draft, by_id)) is not None]
        retrospective_times = tuple(time for unit in batch if re.search(
            r"(?i)\b(?:that(?:'s| is)|this was|I mean)[^.!?]{0,45}\b(?:around|at)\s*\[", unit.text
        ) for time in unit.timecodes)
        last_note = max(drafts, key=lambda note: max(note.source_ids, default=""), default=None)
        for draft in drafts:
            if draft.location == "auto":
                if retrospective_times and draft is last_note:
                    draft = replace(draft, location="timestamp", timecodes=retrospective_times, approximate=True,
                                    source_ids=tuple(dict.fromkeys(draft.source_ids + tuple(unit.id for unit in batch if unit.timecodes == retrospective_times))))
                elif not any(unit.timecodes for unit in batch) and re.search(r"(?i)\b(?:at the end|image.{0,40}end|outro)\b", " ".join(unit.text for unit in batch)):
                    # The core derives the relative location from this passage,
                    # even when the model cites only its explanatory sentence.
                    # Keep that location evidence alongside the body evidence.
                    end_ids = tuple(unit.id for unit in batch if re.search(
                        r"(?i)\b(?:at the end|image.{0,40}end|outro)\b", unit.text
                    ))
                    draft = replace(draft, location="end",
                                    source_ids=tuple(dict.fromkeys(draft.source_ids + end_ids)))
            note = draft
            evidence = " ".join(by_id[key].text for key in note.source_ids if key in by_id)
            evidence_times = {time for key in note.source_ids if key in by_id for time in by_id[key].timecodes}
            if note.location == "general" and evidence_times:
                note = replace(note, location="timestamp", timecodes=tuple(sorted(evidence_times, key=_timecode_value)))
            times = note_timecodes(note, by_id)
            if any(time not in allowed_times or time not in evidence_times for time in times):
                continue
            if note.location == "timestamp" and not times:
                continue
            if len(times) > 2 or any(_timecode_value(b) - _timecode_value(a) > 2 for a, b in zip(times, times[1:])):
                continue
            if note.location in {"general", "end", "beginning"} and note.timecodes:
                continue
            if note.location in {"end", "beginning"} and not re.search(
                r"(?i)\b(?:end|ending|final|outro|beginning|start|opening)\b", evidence
            ):
                continue
            if note.approximate and not re.search(r"(?i)\b(?:around|roughly|near)\s*\[", evidence):
                note = replace(note, approximate=False)
            if not any(existing.body == note.body and note_timecodes(existing, by_id) == times
                       and existing.location == note.location for existing in notes):
                notes.append(note)
        reporter.progress("formatting", index / len(batches) * 0.9,
                          f"Polished feedback part {index} of {len(batches)}")

    if not notes:
        raise CutNotesError(
            "The formatter did not produce any usable editorial notes.",
            EXIT_FORMATTING, code="formatter_contract_failed",
            recovery="The transcript was preserved. Retry formatting or explicitly choose another provider.",
            preserved=PreservedArtifacts(transcript=True),
        )
    general_notes = [note for note in notes if not note_timecodes(note, by_id)
                     and note.location not in {"end", "beginning"}]
    timestamped_notes = [note for note in notes if note not in general_notes]
    covered_times = {time for note in timestamped_notes for time in note_timecodes(note, by_id)}
    for unit in _timestamp_source_units(units):
        missing = tuple(time for time in unit.timecodes if time not in covered_times)
        if missing:
            reporter.warning("formatting", f"Formatting is incomplete for {unit.id}; review the preserved transcript")
            timestamped_notes.append(replace(_fallback_timestamp_note(missing[0], []),
                                             location="timestamp", timecodes=missing))
            covered_times.update(missing)
    return render_editorial_draft(
        title=title, review_date=dt.date.today().strftime("%B %-d, %Y"),
        general_notes=_select_general_notes(general_notes),
        timestamped_notes=timestamped_notes, units=units,
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
