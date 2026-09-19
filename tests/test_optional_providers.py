from pathlib import Path
import io
import subprocess
import tempfile
import unittest
from unittest import mock

from cutnotes_core import cli, pipeline
from cutnotes_core.contracts import ProgressReporter


class OptionalProviderTests(unittest.TestCase):
    def test_doctor_detects_macwhisper_without_executing_it(self):
        with (
            mock.patch.object(cli, "find_tool", side_effect=lambda env, *args:
                              "/optional/mw" if env == "CUTNOTES_MACWHISPER" else None),
            mock.patch.object(cli, "find_local_engine", return_value=None),
            mock.patch.object(cli, "local_engine_status", return_value={
                "path": None, "version": None, "apple": {"state": "unavailable"},
            }),
            mock.patch.object(cli, "model_status", return_value={"state": "missing"}),
            mock.patch("subprocess.run", side_effect=AssertionError("Unselected provider executed")) as run,
        ):
            payload, _ = cli.doctor_payload()

        run.assert_not_called()
        self.assertEqual(payload["schema_version"], "cutnotes.doctor.v1")
        self.assertEqual(payload["macwhisper"], {
            "path": "/optional/mw", "version": None, "optional": True, "models": [],
        })
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            cli.print_doctor_report(payload, compact=True)
        self.assertIn("MacWhisper (optional): installed", output.getvalue())
        self.assertNotIn("MacWhisper (optional): not found", output.getvalue())

    def test_parakeet_pipeline_never_resolves_or_calls_macwhisper(self):
        args = cli.build_parser().parse_args(["import", "/input.wav", "--title", "Demo"])
        with (
            mock.patch.object(pipeline, "require_tool", return_value="/ffmpeg") as require,
            mock.patch.object(pipeline, "find_local_engine", return_value="/local-engine"),
            mock.patch.object(pipeline, "validate_model"),
            mock.patch.object(pipeline, "transcribe_with_parakeet") as parakeet,
            mock.patch.object(pipeline, "transcribe_with_macwhisper") as macwhisper,
        ):
            ffmpeg, transcriber, formatter = pipeline._required_pipeline_tools(args)
            pipeline._transcribe(
                args, ffmpeg=ffmpeg, provider_tool=transcriber,
                audio_path=Path("/input.wav"), transcript_path=Path("/transcript.txt"),
                reporter=ProgressReporter(None), quiet=True,
            )

        require.assert_called_once_with("CUTNOTES_FFMPEG", "ffmpeg")
        parakeet.assert_called_once()
        macwhisper.assert_not_called()
        self.assertEqual(formatter, "/local-engine")

    def test_selected_macwhisper_uses_only_cli_transcription(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "source with spaces.wav"
            transcript = root / "transcript.txt"
            args = cli.build_parser().parse_args([
                "import", str(audio), "--title", "Demo", "--transcriber", "macwhisper",
                "--transcript-only", "--language", "fr", "--whisper-model", "engine:model",
            ])

            def transcribe(command, **kwargs):
                transcript.write_text("Synthetic CLI transcript.", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stderr="")

            with (
                mock.patch.object(pipeline, "require_tool", side_effect=["/ffmpeg", "/optional/mw"]) as require,
                mock.patch.object(pipeline, "find_local_engine") as local,
                mock.patch.object(pipeline, "transcribe_with_parakeet") as parakeet,
                mock.patch("subprocess.run", side_effect=transcribe) as run,
            ):
                ffmpeg, transcriber, formatter = pipeline._required_pipeline_tools(args)
                pipeline._transcribe(
                    args, ffmpeg=ffmpeg, provider_tool=transcriber,
                    audio_path=audio, transcript_path=transcript,
                    reporter=ProgressReporter(None), quiet=True,
                )

            self.assertEqual(require.call_args_list, [
                mock.call("CUTNOTES_FFMPEG", "ffmpeg"),
                mock.call("CUTNOTES_MACWHISPER", "mw", pipeline.MACWHISPER_CANDIDATES),
            ])
            local.assert_not_called()
            parakeet.assert_not_called()
            self.assertIsNone(formatter)
            run.assert_called_once_with([
                "/optional/mw", "transcribe", "--language", "fr", "--format", "txt",
                "--style", "transcript", "--no-timestamps", "--no-speakers",
                "--output", str(transcript), "--overwrite", "--model", "engine:model", str(audio),
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            self.assertEqual(transcript.read_text(), "Synthetic CLI transcript.")
