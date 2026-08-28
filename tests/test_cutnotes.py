from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import cutnotes_core.cli as cli_module
from cutnotes_core.contracts import CutNotesError, ProgressReporter
from cutnotes_core.pipeline import enforce_duration_limit


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "cutnotes"

loader = importlib.machinery.SourceFileLoader("cutnotes_module", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
cutnotes = importlib.util.module_from_spec(spec)
loader.exec_module(cutnotes)


class CutNotesUnitTests(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(
            cutnotes.slugify("First Time Sexpot — Rough Cut V2"),
            "first-time-sexpot-rough-cut-v2",
        )

    def test_project_folder_name_is_readable_and_safe(self) -> None:
        self.assertEqual(
            cutnotes.project_folder_name("First Time Sexpot: Rough/Cut"),
            "First Time Sexpot - Rough - Cut",
        )

    def test_project_directory_and_session_files_live_on_desktop_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = cutnotes.project_directory(root, "Demo Project")
            paths = cutnotes.allocate_session_paths(
                project,
                "Demo Project",
                ".wav",
                include_markdown=True,
            )

            self.assertEqual(project, root.resolve() / "Demo Project")
            self.assertEqual(paths["audio"], project / "voice-notes.wav")
            self.assertEqual(paths["transcript"], project / "transcript.txt")
            self.assertEqual(paths["markdown"], project / "demo-project.md")
            self.assertEqual(paths["metadata"], project / "session.json")

    def test_later_project_sessions_do_not_overwrite_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = cutnotes.project_directory(
                Path(temporary_directory),
                "Demo Project",
            )
            (project / "transcript.txt").write_text("existing", encoding="utf-8")
            paths = cutnotes.allocate_session_paths(
                project,
                "Demo Project",
                ".wav",
                include_markdown=True,
            )

            self.assertNotEqual(paths["transcript"], project / "transcript.txt")
            self.assertRegex(paths["transcript"].name, r"^transcript-\d{8}-\d{6}\.txt$")
            self.assertTrue(all(path.parent == project for path in paths.values() if path))

    def test_parse_avfoundation_microphones(self) -> None:
        output = """
        [AVFoundation indev] AVFoundation video devices:
        [AVFoundation indev] [0] FaceTime HD Camera
        [AVFoundation indev] AVFoundation audio devices:
        [AVFoundation indev] [0] Icarus Microphone
        [AVFoundation indev] [1] MacBook Pro Microphone
        """
        self.assertEqual(
            cutnotes.parse_avfoundation_microphones(output),
            [(0, "Icarus Microphone"), (1, "MacBook Pro Microphone")],
        )

    def test_microphone_defaults_to_system_setting(self) -> None:
        microphones = [(0, "Icarus Microphone"), (1, "MacBook Pro Microphone")]

        self.assertEqual(
            cutnotes.choose_microphone(microphones, None, None),
            (None, "System Default"),
        )
        self.assertEqual(
            cutnotes.choose_microphone(microphones, "default", None),
            (None, "System Default"),
        )
        self.assertEqual(
            cutnotes.choose_microphone(microphones, None, 1),
            (1, "MacBook Pro Microphone"),
        )

    def test_parakeet_languages_are_core_owned_and_native_named(self) -> None:
        languages = cutnotes.model_status(Path("/definitely/missing"))["languages"]
        self.assertEqual(len(languages), 25)
        self.assertEqual(languages[0], {"code": "bg", "name": "Български"})
        self.assertIn({"code": "fr", "name": "Français"}, languages)
        self.assertIn({"code": "uk", "name": "Українська"}, languages)
        self.assertEqual(
            {item["code"] for item in languages},
            set(cutnotes.SUPPORTED_LANGUAGE_CODES),
        )

    def test_language_option_rejects_unsupported_codes(self) -> None:
        with self.assertRaises(SystemExit):
            cutnotes.build_parser().parse_args(
                ["import", "/tmp/review.mov", "--title", "Demo", "--language", "xx"]
            )

    def test_parse_codex_markdown(self) -> None:
        raw = json.dumps(
            {
                "markdown": (
                    "# Demo\n\n## Overall\nGood.\n\n"
                    "## Highest-Priority Changes\n1. Cut.\n\n"
                    "## Timestamped Notes\n\n## Recurring Themes\n\n"
                    "## Open Questions\n\n## Positive Notes\n"
                )
            }
        )
        parsed = cutnotes.parse_codex_markdown(raw)
        self.assertTrue(parsed.startswith("# Demo"))
        self.assertEqual(cutnotes.validate_markdown(parsed), [])

    def test_prompt_treats_timecodes_as_cut_time(self) -> None:
        prompt = cutnotes.formatter_prompt(
            "Demo",
            "Timestamp zero five. Trim it.",
            "July 28, 2026",
            None,
        )
        self.assertIn("CUT time", prompt)
        self.assertIn("<transcript>", prompt)
        self.assertIn("Timestamp zero five", prompt)

    def test_numeric_spoken_timecode_is_canonicalized_and_grounded(self) -> None:
        transcript = "Timestamp 12 minutes 34 seconds. Trim the reaction."
        self.assertEqual(cutnotes.source_timecodes(transcript), ["12:34"])
        self.assertIn("[12:34]", cutnotes.canonicalize_timecodes(transcript))
        self.assertEqual(
            cutnotes.validate_timecodes("### [12:34] — Reaction", transcript),
            ([], []),
        )
        self.assertEqual(
            cutnotes.validate_timecodes("### [00:41] — Reaction", transcript),
            (["00:41"], ["12:34"]),
        )

    def test_apple_plan_renderer_can_classify_but_cannot_author_notes(self) -> None:
        units = cutnotes.source_units(
            "Timestamp 12 minutes 34 seconds. The reaction shot is too long. "
            "General note. The music is working well."
        )
        markdown = cutnotes.render_editorial_plan(
            title="Demo",
            review_date="August 28, 2026",
            units=units,
            plan={
                "highest_priority_changes": ["N0001", "MADE_UP"],
                "sound_and_foley_direction": ["N0001", "N0002"],
                "positive_notes": ["N0002"],
                "recurring_themes": [],
                "open_questions": [],
            },
        )
        self.assertEqual(cutnotes.validate_markdown(markdown), [])
        self.assertNotIn("MADE_UP", markdown)
        sound_section = markdown.split("## Sound and Foley Direction", 1)[1].split(
            "## Timestamped Notes", 1
        )[0]
        self.assertNotIn("reaction shot", sound_section)
        self.assertIn("music is working well", sound_section)
        self.assertEqual(cutnotes.validate_timecodes(markdown, "Timestamp 12 minutes 34 seconds."), ([], []))

    def test_markdown_validator_requires_exact_ordered_headings(self) -> None:
        malformed = (
            "## Demo\n\n## Overall\n\n## Highest-Priority Changes\n\n"
            "## Timestamped Notes\n\n## Recurring Themes\n\n## Open Questions\n\n## Positive Notes\n"
        )
        self.assertIn("# ", cutnotes.validate_markdown(malformed))

    def test_parser_allows_zero_argument_interactive_mode(self) -> None:
        args = cutnotes.build_parser().parse_args([])
        self.assertIsNone(args.command)

    def test_pipeline_defaults_are_local_and_have_no_fallback(self) -> None:
        args = cutnotes.build_parser().parse_args(
            ["import", "/tmp/review.mov", "--title", "Demo"]
        )
        self.assertEqual(args.transcriber, "parakeet")
        self.assertEqual(args.formatter, "apple")
        self.assertFalse(args.transcript_only)

    def test_four_hour_import_limit_is_exact(self) -> None:
        enforce_duration_limit(4 * 60 * 60)
        with self.assertRaises(CutNotesError) as raised:
            enforce_duration_limit(4 * 60 * 60 + 1)
        self.assertEqual(raised.exception.code, "media_too_long")

    def test_progress_contract_is_bounded_and_monotonic(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            reporter = ProgressReporter(write_fd)
            reporter.stage("recording", "  Recording   voice notes  ")
            reporter.progress("recording", 5, "x" * 300)
            os.close(write_fd)
            write_fd = -1
            events = [json.loads(line) for line in os.read(read_fd, 16_384).splitlines()]
        finally:
            os.close(read_fd)
            if write_fd >= 0:
                os.close(write_fd)
        self.assertEqual([event["sequence"] for event in events], [0, 1])
        self.assertEqual(events[0]["message"], "Recording voice notes")
        self.assertEqual(events[1]["fraction"], 1.0)
        self.assertEqual(len(events[1]["message"]), 240)

    def test_noninteractive_recording_requires_control_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                mock.patch.object(sys.stdin, "isatty", return_value=False),
                self.assertRaises(CutNotesError) as raised,
            ):
                cutnotes.record_audio(
                    "/fake/ffmpeg",
                    Path(temporary_directory) / "audio.wav",
                    0,
                    "Test microphone",
                    True,
                )
        self.assertEqual(raised.exception.code, "recording_control_missing")

    def test_recording_uses_avfoundation_system_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "audio.wav"
            output.write_bytes(b"x" * 256)
            process = mock.Mock()
            process.poll.return_value = 0
            process.wait.return_value = 0
            with (
                mock.patch.object(sys.stdin, "isatty", return_value=True),
                mock.patch.object(cutnotes.subprocess, "Popen", return_value=process) as popen,
            ):
                cutnotes.record_audio(
                    "/fake/ffmpeg",
                    output,
                    None,
                    "System Default",
                    True,
                )

        command = popen.call_args.args[0]
        self.assertEqual(command[command.index("-i") + 1], ":default")

    def test_interactive_mode_prompts_then_starts_recording(self) -> None:
        doctor = {
            "healthy": True,
            "default_workflow_ready": True,
            "cutnotes": cutnotes.VERSION,
            "ffmpeg": {"path": "/fake/ffmpeg", "version": "ffmpeg test"},
            "macwhisper": {
                "path": "/fake/mw",
                "version": "MacWhisper test",
                "models": ["▸ parakeet-pro:test Active"],
            },
            "codex": {"path": "/fake/codex", "version": "codex test"},
            "local_engine": {
                "path": "/fake/CutNotesLocal",
                "version": "1.0.0",
                "apple": {"state": "ready"},
            },
            "parakeet": {"state": "ready"},
            "apple_formatter": {"state": "ready"},
            "ffprobe": {"path": "/fake/ffprobe", "version": "ffprobe test"},
            "microphones": [{"index": 1, "name": "MacBook Pro Microphone"}],
        }
        with (
            mock.patch.object(sys.stdin, "isatty", return_value=True),
            mock.patch.object(cli_module, "doctor_payload", return_value=(doctor, True)),
            mock.patch.object(
                cli_module,
                "choose_microphone",
                return_value=(1, "MacBook Pro Microphone"),
            ),
            mock.patch("builtins.input", side_effect=["Demo Rough Cut", ""]),
            mock.patch.object(cli_module, "run_record_command", return_value=0) as run_record,
        ):
            result = cutnotes.run_interactive(cutnotes.argparse.Namespace())

        self.assertEqual(result, 0)
        interactive_args = run_record.call_args.args[0]
        self.assertEqual(interactive_args.title, "Demo Rough Cut")
        self.assertFalse(interactive_args.transcript_only)
        self.assertEqual(interactive_args.transcriber, "parakeet")
        self.assertEqual(interactive_args.formatter, "apple")


class CutNotesIntegrationTests(unittest.TestCase):
    def make_executable(self, directory: Path, name: str, body: str) -> Path:
        path = directory / name
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_format_command_with_fake_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp = Path(temporary_directory)
            transcript = temp / "transcript.txt"
            output = temp / "feedback.md"
            transcript.write_text(
                "Timestamp zero minutes five seconds. Shorten the shot.",
                encoding="utf-8",
            )

            fake_codex = self.make_executable(
                temp,
                "codex",
                """#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
output = pathlib.Path(args[args.index("--output-last-message") + 1])
plan = {
    "highest_priority_changes": ["N0001"],
    "sound_and_foley_direction": [],
    "recurring_themes": [],
    "open_questions": [],
    "positive_notes": [],
}
output.write_text(json.dumps(plan), encoding="utf-8")
""",
            )
            environment = os.environ.copy()
            environment["CUTNOTES_CODEX"] = str(fake_codex)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "format",
                    str(transcript),
                    "--title",
                    "Demo",
                    "--output",
                    str(output),
                    "--formatter",
                    "codex",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(Path(payload["markdown"]), output.resolve())
            self.assertIn("### `[00:05]`", output.read_text(encoding="utf-8"))
            self.assertIn("Shorten the shot.", output.read_text(encoding="utf-8"))

    def test_format_rejects_non_utf8_transcript_with_machine_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            transcript = Path(temporary_directory) / "transcript.txt"
            transcript.write_bytes(b"\xff\xfe\x00")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "format",
                    str(transcript),
                    "--title",
                    "Demo",
                    "--formatter",
                    "codex",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 7)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema_version"], "cutnotes.error.v1")
        self.assertEqual(payload["code"], "transcript_encoding")


if __name__ == "__main__":
    unittest.main()
