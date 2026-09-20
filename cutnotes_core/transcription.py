"""Validate local transcription evidence without changing the recognized words."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path


EVIDENCE_SCHEMA = "cutnotes.transcript-evidence.v1"
LOCAL_EVIDENCE_SCHEMA = "cutnotes.local.transcript-evidence.v1"


def evidence_path(transcript: Path) -> Path:
    return transcript.with_name(f"{transcript.stem}.evidence.json")


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audio_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Evidence contains an invalid number")
    return float(value)


def decode_local_evidence(payload: object, *, text: str) -> dict:
    """Accept only evidence for the exact transcript returned by this invocation."""
    if not isinstance(payload, dict) or payload.get("schema_version") != LOCAL_EVIDENCE_SCHEMA:
        raise ValueError("Unknown transcription evidence schema")
    if not isinstance(payload.get("text"), str) or payload["text"].strip() != text.strip():
        raise ValueError("Evidence does not match the transcript")
    duration = _number(payload.get("duration_seconds"))
    if not 0 < duration <= 901:
        raise ValueError("Evidence duration exceeds the transcription chunk")
    result = {"duration_seconds": duration}
    for key in ("tokens", "words"):
        raw = payload.get(key)
        if not isinstance(raw, list) or len(raw) > 100_000:
            raise ValueError("Invalid transcription evidence collection")
        items = []
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                raise ValueError("Invalid transcription evidence item")
            start, end = _number(item.get("start")), _number(item.get("end"))
            if not 0 <= start <= end <= duration + 0.25:
                raise ValueError("Evidence offset lies outside its audio chunk")
            clean = {"text": item["text"], "start": start, "end": end}
            if key == "tokens":
                confidence = _number(item.get("confidence"))
                if not 0 <= confidence <= 1:
                    raise ValueError("Invalid token confidence")
                clean["confidence"] = confidence
            items.append(clean)
        result[key] = items
    return result


def merge_evidence(chunks: list[dict], transcript: str, audio_sha256: str) -> dict:
    """Translate recording offsets across chunks, retaining token order/overlap."""
    result = {"schema_version": EVIDENCE_SCHEMA, "transcript_sha256": text_digest(transcript),
              "audio_sha256": audio_sha256,
              "duration_seconds": 0.0, "tokens": [], "words": []}
    offset = 0.0
    for chunk in chunks:
        for key in ("tokens", "words"):
            result[key].extend({**item, "start": item["start"] + offset, "end": item["end"] + offset}
                               for item in chunk[key])
        offset += chunk["duration_seconds"]
    result["duration_seconds"] = offset
    return result
