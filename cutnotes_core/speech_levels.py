"""Local, reviewable background-speech candidates from exact ASR word alignment.

Relative loudness is evidence of distance/background, not speaker identity or
editorial relevance. Formatting may use the proposal; ASR remains unchanged.
"""
from __future__ import annotations

import array
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

from .transcription import EVIDENCE_SCHEMA, _number, audio_digest, text_digest


def analyze_recording(*, transcript: str, evidence: dict, source_audio: Path, ffmpeg: str) -> dict:
    """Measure a temporary PCM copy without gain normalization or source changes."""
    with tempfile.TemporaryDirectory(prefix="cutnotes-speech-levels-") as temporary:
        pcm = Path(temporary) / "measurement.wav"
        subprocess.run([ffmpeg, "-nostdin", "-n", "-v", "error", "-i", str(source_audio.resolve()),
                        "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(pcm)],
                       check=True, capture_output=True, timeout=300)
        return analyze_speech_levels(transcript=transcript, evidence=evidence, source_audio=source_audio, pcm_audio=pcm)


def _percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    # Nearest-rank percentiles keep the audible word in a two-word utterance
    # from being masked by its quiet neighbour.
    return values[max(0, math.ceil(len(values) * fraction) - 1)]


def analyze_speech_levels(*, transcript: str, evidence: dict, source_audio: Path,
                          pcm_audio: Path, quiet_gap_db: float = 18.0,
                          utterance_pause_seconds: float = 0.8) -> dict:
    """Measure complete utterances relative to the recording's speaking level.

    Use a mono PCM16 copy without gain changes. The original source hashes and
    word text must match before any filtering proposal is returned. Individual
    quiet words are never removed from an otherwise audible utterance.
    """
    if not math.isfinite(quiet_gap_db) or quiet_gap_db < 12:
        raise ValueError("The quiet-speech gap must be at least 12 dB")
    if not math.isfinite(utterance_pause_seconds) or utterance_pause_seconds <= 0:
        raise ValueError("Invalid utterance pause")
    if (not isinstance(evidence, dict) or evidence.get("schema_version") != EVIDENCE_SCHEMA or
            evidence.get("transcript_sha256") != text_digest(transcript) or
            evidence.get("audio_sha256") != audio_digest(source_audio)):
        raise ValueError("Audio, transcript and word evidence must match exactly")
    words = evidence.get("words")
    if not isinstance(words, list) or not words or len(words) > 250_000:
        raise ValueError("Missing or oversized word evidence")
    if any(not isinstance(w, dict) or not isinstance(w.get("text"), str) or not w["text"].strip() for w in words):
        raise ValueError("Invalid word evidence")
    if " ".join(w["text"] for w in words).split() != transcript.split():
        raise ValueError("Word evidence does not cover the exact transcript")
    groups: list[list[dict]] = []
    measured: list[dict] = []
    with wave.open(str(pcm_audio), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getcomptype() != "NONE":
            raise ValueError("Speech measurement requires mono PCM16 without gain changes")
        rate, frames = audio.getframerate(), audio.getnframes()
        duration = frames / rate
        if not 0 < duration <= 14_401 or abs(_number(evidence.get("duration_seconds")) - duration) > 0.25:
            raise ValueError("PCM duration does not match the source evidence")
        previous_start = -1.0
        for index, word in enumerate(words):
            start, end = word.get("start"), word.get("end")
            if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end)) or
                    not 0 <= start <= end <= duration + 0.25 or start < previous_start):
                raise ValueError("Invalid or unordered word timing")
            previous_start = start
            first = min(frames - 1, int(start * rate))
            last = min(frames, max(first + 1, int(end * rate)))
            audio.setpos(first)
            count = energy = 0
            remaining = last - first
            while remaining:
                block = array.array("h", audio.readframes(min(remaining, 65_536)))
                if sys.byteorder != "little":
                    block.byteswap()
                if not block:
                    raise ValueError("Truncated PCM audio")
                count += len(block)
                energy += sum(sample * sample for sample in block)
                remaining -= len(block)
            dbfs = 20 * math.log10(max(math.sqrt(energy / count) / 32768, 1e-8))
            item = dict(word, index=index, rms_dbfs=dbfs)
            measured.append(item)
            if not groups or start - groups[-1][-1]["end"] >= utterance_pause_seconds:
                groups.append([])
            groups[-1].append(item)
    reference = _percentile([w["rms_dbfs"] for w in measured], 0.75)
    # Require several utterances so one naturally quiet recording cannot be
    # classified against a single transient or louder introductory word.
    enough_context = len(groups) >= 3 and len(words) >= 12
    rows, excluded = [], set()
    for group in groups:
        level = _percentile([w["rms_dbfs"] for w in group], 0.8)
        delta = reference - level
        candidate = (enough_context and len(group) >= 2 and
                     group[-1]["end"] - group[0]["start"] >= 0.5 and delta >= quiet_gap_db)
        if candidate:
            excluded.update(w["index"] for w in group)
        rows.append({"start": group[0]["start"], "end": group[-1]["end"],
                     "text": " ".join(w["text"] for w in group),
                     "word_indices": [w["index"] for w in group],
                     "speech_level_dbfs": round(level, 2), "below_reference_db": round(delta, 2),
                     "background_candidate": candidate})
    return {"schema_version": "cutnotes.speech-level-review.v1", "requires_review": True,
            "source_audio_sha256": evidence["audio_sha256"], "source_transcript_sha256": evidence["transcript_sha256"],
            "reference_dbfs": round(reference, 2), "quiet_gap_db": quiet_gap_db,
            "utterance_pause_seconds": utterance_pause_seconds, "utterances": rows,
            "proposed_foreground_transcript": " ".join(w["text"] for i, w in enumerate(words) if i not in excluded) + "\n"}
