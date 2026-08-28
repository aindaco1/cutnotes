"""Versioned machine contracts shared by every CutNotes workflow."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
from typing import Any

from . import ERROR_SCHEMA, PROGRESS_SCHEMA, RESULT_SCHEMA


EXIT_DEPENDENCY = 3
EXIT_CAPTURE = 4
EXIT_TRANSCRIPTION = 5
EXIT_FORMATTING = 6
EXIT_INPUT = 7
EXIT_CANCELLED = 130


@dataclass(frozen=True)
class PreservedArtifacts:
    audio: bool = False
    transcript: bool = False


class CutNotesError(Exception):
    """An expected, actionable failure with a stable machine code."""

    def __init__(
        self,
        message: str,
        exit_code: int = 1,
        *,
        code: str = "cutnotes_failed",
        recovery: str = "Review the message and try again.",
        preserved: PreservedArtifacts = PreservedArtifacts(),
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.recovery = recovery
        self.preserved = preserved

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": ERROR_SCHEMA,
            "code": self.code,
            "message": str(self),
            "recovery": self.recovery,
            "exit_code": self.exit_code,
            "preserved": {
                "audio": self.preserved.audio,
                "transcript": self.preserved.transcript,
            },
        }


class ProgressReporter:
    """Writes bounded NDJSON events to a caller-owned descriptor."""

    def __init__(self, file_descriptor: int | None) -> None:
        self.file_descriptor = file_descriptor
        self._sequence = 0
        self._lock = threading.Lock()

    def emit(
        self,
        kind: str,
        stage: str,
        *,
        fraction: float | None = None,
        message: str | None = None,
    ) -> None:
        if self.file_descriptor is None:
            return
        event: dict[str, Any] = {
            "schema_version": PROGRESS_SCHEMA,
            "sequence": self._sequence,
            "kind": kind,
            "stage": stage,
        }
        self._sequence += 1
        if fraction is not None:
            event["fraction"] = min(1.0, max(0.0, float(fraction)))
        if message:
            event["message"] = " ".join(message.split())[:240]
        data = (json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        with self._lock:
            try:
                os.write(self.file_descriptor, data)
            except OSError:
                # Progress is advisory. A closed UI pipe must not destroy user work.
                self.file_descriptor = None

    def stage(self, stage: str, message: str) -> None:
        self.emit("stage", stage, message=message)

    def progress(self, stage: str, fraction: float, message: str | None = None) -> None:
        self.emit("progress", stage, fraction=fraction, message=message)

    def warning(self, stage: str, message: str) -> None:
        self.emit("warning", stage, message=message)


def result_payload(
    *,
    command: str,
    session_dir: Path | None,
    audio_path: Path | None,
    transcript_path: Path,
    markdown_path: Path | None,
    transcriber: str | None,
    formatter: str | None,
) -> dict[str, Any]:
    """Return v1 paths while retaining the original top-level keys."""

    session = str(session_dir) if session_dir else None
    audio = str(audio_path) if audio_path else None
    transcript = str(transcript_path)
    markdown = str(markdown_path) if markdown_path else None
    return {
        "schema_version": RESULT_SCHEMA,
        "status": "complete",
        "command": command,
        "providers": {"transcriber": transcriber, "formatter": formatter},
        "paths": {
            "session_dir": session,
            "audio": audio,
            "transcript": transcript,
            "markdown": markdown,
        },
        "session_dir": session,
        "audio": audio,
        "transcript": transcript,
        "markdown": markdown,
    }
