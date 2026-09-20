from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cutnotes_core import providers as p
from cutnotes_core.contracts import ProgressReporter
from cutnotes_core.filesystem import write_json
from cutnotes_core.transcription import audio_digest, decode_local_evidence, evidence_path, text_digest


def payload(text="Do not cut it.", duration=3):
    word = "not" if "not" in text.split() else "Maybe"
    return {"schema_version": "cutnotes.local.transcript-evidence.v1", "text": text,
            "duration_seconds": duration,
            "tokens": [{"text": word, "start": 1, "end": 1.2, "confidence": 0.01}],
            "words": [{"text": word, "start": 1, "end": 1.2}]}


class TranscriptionEvidenceTests(unittest.TestCase):
    def transcribe(self, folder, *, evidence=True, existing=None, mutate=None):
        transcript = folder / "transcript.txt"
        (folder / "source.wav").write_bytes(b"Original audio")
        if existing is not None:
            evidence_path(transcript).write_text(existing)
        texts = iter(["Do not cut it.", "Maybe leave the ending."])

        def run(command, **kwargs):
            text = next(texts)
            Path(command[command.index("--output") + 1]).write_text(json.dumps({"text": text}))
            if evidence:
                value = payload(text)
                if mutate:
                    mutate(value)
                Path(command[command.index("--evidence-output") + 1]).write_text(json.dumps(value))

        with mock.patch.object(p, "validate_model"), \
             mock.patch.object(p, "_create_audio_chunks", return_value=[folder / "a.wav", folder / "b.wav"]), \
             mock.patch.object(p, "_run_checked", side_effect=run):
            p.transcribe_with_parakeet(engine="native", ffmpeg="ffmpeg", audio_path=folder / "source.wav",
                                      transcript_path=transcript, reporter=ProgressReporter(None))
        return transcript

    def test_low_confidence_negation_is_preserved_and_offsets_span_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            transcript = self.transcribe(Path(temporary))
            self.assertEqual(transcript.read_text(), "Do not cut it.\n\nMaybe leave the ending.\n")
            evidence = json.loads(evidence_path(transcript).read_text())
            self.assertEqual(evidence["transcript_sha256"], text_digest(transcript.read_text()))
            self.assertEqual(evidence["audio_sha256"], audio_digest(Path(temporary) / "source.wav"))
            self.assertEqual([token["start"] for token in evidence["tokens"]], [1, 4])
            self.assertEqual([token["text"] for token in evidence["tokens"]], ["not", "Maybe"])
            self.assertEqual([token["confidence"] for token in evidence["tokens"]], [0.01, 0.01])
            self.assertEqual(evidence["duration_seconds"], 6)

    def test_older_helper_without_evidence_still_transcribes(self):
        with tempfile.TemporaryDirectory() as temporary:
            transcript = self.transcribe(Path(temporary), evidence=False)
            self.assertIn("Do not cut it.", transcript.read_text())
            self.assertFalse(evidence_path(transcript).exists())

    def test_existing_companion_artifact_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            transcript = self.transcribe(Path(temporary), existing="Previous evidence")
            self.assertEqual(evidence_path(transcript).read_text(), "Previous evidence")

    def test_invalid_chunk_evidence_does_not_discard_recognized_words(self):
        def corrupt_second_chunk(value):
            if value["text"].startswith("Maybe"):
                value["words"][0]["end"] = 50

        with tempfile.TemporaryDirectory() as temporary:
            transcript = self.transcribe(Path(temporary), mutate=corrupt_second_chunk)
            self.assertEqual(transcript.read_text(), "Do not cut it.\n\nMaybe leave the ending.\n")
            self.assertFalse(evidence_path(transcript).exists())

    def test_optional_evidence_write_failure_keeps_transcript(self):
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(p, "write_json", side_effect=PermissionError("unwritable")):
            transcript = self.transcribe(Path(temporary))
            self.assertEqual(transcript.read_text(), "Do not cut it.\n\nMaybe leave the ending.\n")
            self.assertFalse(evidence_path(transcript).exists())

    def test_stale_unknown_or_invalid_evidence_is_rejected(self):
        mutations = [
            lambda p: p.update(text="Do cut it."),
            lambda p: p.update(schema_version="future"),
            lambda p: p.update(duration_seconds=float("nan")),
            lambda p: p["tokens"][0].update(start=-1),
            lambda p: p["tokens"][0].update(end=50),
            lambda p: p["tokens"][0].update(confidence=True),
            lambda p: p["tokens"][0].update(confidence=1.01),
            lambda p: p["words"][0].update(start=2, end=1),
        ]
        for mutate in mutations:
            value = deepcopy(payload())
            mutate(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_local_evidence(value, text="Do not cut it.")

    def test_failed_serialization_leaves_no_partial_companion(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            with self.assertRaises(ValueError):
                write_json(path, {"tokens": [float("nan")]}, overwrite=False)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_concurrent_creation_preserves_existing_companion(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            path.write_text("Previous evidence")
            with self.assertRaises(FileExistsError):
                write_json(path, {"tokens": []}, overwrite=False)
            self.assertEqual(path.read_text(), "Previous evidence")
            self.assertEqual(list(Path(temporary).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
