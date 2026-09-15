from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

from cutnotes_core.cli import build_parser
from cutnotes_core.contracts import CutNotesError, EXIT_FORMATTING
from cutnotes_core import pipeline, providers


class MacOSReadinessTests(unittest.TestCase):
    def test_unavailable_apple_model_has_actionable_private_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            native_error = CutNotesError(
                "Apple on-device classification failed: CutNotesLocal: "
                "Apple on-device formatting is unavailable. "
                "Enable Apple Intelligence on a supported Mac.",
                EXIT_FORMATTING,
                code="apple_formatting_failed",
            )
            with mock.patch.object(providers, "_run_checked", side_effect=native_error):
                with self.assertRaises(CutNotesError) as raised:
                    providers._generate_with_apple(
                        engine="/fixture/CutNotesLocal", prompt="PRIVATE_SOURCE",
                        work_directory=directory, mode="draft",
                        schema_version="cutnotes.local.draft.v1", payload_key="draft",
                    )
            payload = raised.exception.payload()
            self.assertEqual(payload["code"], "apple_model_unavailable")
            self.assertEqual(payload["exit_code"], EXIT_FORMATTING)
            self.assertIn("finish preparing", payload["recovery"])
            self.assertTrue(payload["preserved"]["transcript"])
            self.assertNotIn("PRIVATE_SOURCE", json.dumps(payload))
            self.assertEqual(list(directory.iterdir()), [])

    def test_other_provider_failure_does_not_claim_model_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            native_error = CutNotesError(
                "Apple on-device classification failed: private internal detail",
                EXIT_FORMATTING, code="apple_formatting_failed",
            )
            with mock.patch.object(providers, "_run_checked", side_effect=native_error):
                with self.assertRaises(CutNotesError) as raised:
                    providers._generate_with_apple(
                        engine="/fixture/CutNotesLocal", prompt="fixture",
                        work_directory=Path(temporary), mode="draft",
                        schema_version="cutnotes.local.draft.v1", payload_key="draft",
                    )
            self.assertEqual(raised.exception.code, "apple_formatting_failed")
            self.assertNotIn("private internal detail", json.dumps(raised.exception.payload()))

    def test_formatting_failure_preserves_record_and_import_artifacts(self):
        for command in ("record", "import"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                original = root / "source.wav"
                original.write_bytes(b"synthetic audio bytes")
                arguments = ([command, "Readiness"] if command == "record" else
                             [command, str(original), "--title", "Readiness"])
                args = build_parser().parse_args(arguments + ["--root", str(root / "sessions"), "--json"])

                def transcribe(_args, **kwargs):
                    kwargs["transcript_path"].write_text("Preserve this synthetic transcript.")

                def capture(_ffmpeg, audio, *_args, **_kwargs):
                    audio.write_bytes(original.read_bytes())

                failure = CutNotesError(
                    "Apple on-device formatting is not ready on this Mac.",
                    EXIT_FORMATTING, code="apple_model_unavailable",
                )
                with (mock.patch.object(pipeline, "_required_pipeline_tools", return_value=("ffmpeg", "engine", "engine")),
                      mock.patch.object(pipeline, "find_ffprobe", return_value="ffprobe"),
                      mock.patch.object(pipeline, "media_duration_seconds", return_value=10),
                      mock.patch.object(pipeline, "list_microphones", return_value=[]),
                      mock.patch.object(pipeline, "choose_microphone", return_value=(0, "Synthetic input")),
                      mock.patch.object(pipeline, "record_audio", side_effect=capture),
                      mock.patch.object(pipeline, "_transcribe", side_effect=transcribe),
                      mock.patch.object(pipeline, "_format", side_effect=failure)):
                    with self.assertRaises(CutNotesError) as raised:
                        (pipeline.run_record if command == "record" else pipeline.run_import)(args)
                self.assertEqual(raised.exception.payload()["preserved"], {"audio": True, "transcript": True})
                self.assertEqual(original.read_bytes(), b"synthetic audio bytes")
                session = next((root / "sessions").iterdir())
                self.assertEqual((session / "voice-notes.wav").read_bytes(), original.read_bytes())
                self.assertEqual((session / "transcript.txt").read_text(), "Preserve this synthetic transcript.")
                self.assertEqual(json.loads((session / "session.json").read_text())["error_code"], "apple_model_unavailable")

    def test_missing_or_linked_session_files_are_not_reported_as_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_text("outside artifact")
            audio = root / "audio"
            audio.symlink_to(source)
            error = CutNotesError("fixture")
            pipeline._preserve_session_artifact_flags(error, audio, root / "missing-transcript")
            self.assertEqual(error.payload()["preserved"], {"audio": False, "transcript": False})
