from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import wave
from unittest import mock

import cutnotes_core.cli as cli_module
import cutnotes_core.providers as providers_module
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
        self.assertIn("[00:05]", prompt)

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

    def test_editorial_timecode_variants_are_normalized_without_model_guessing(self) -> None:
        transcript = (
            "At zero minutes 37 seconds, adjust the frame. "
            "At three minutes 54 seconds, trim the beat. "
            "At three 24, use the reaction. At 126, shorten it. "
            "At four oh nine, hide the insert. Okay, 0031."
        )
        self.assertEqual(
            cutnotes.source_timecodes(transcript),
            ["00:37", "03:54", "03:24", "01:26", "04:09", "00:31"],
        )
        normalized = cutnotes.canonicalize_timecodes(transcript)
        for timecode in cutnotes.source_timecodes(transcript):
            self.assertIn(f"[{timecode}]", normalized)

    def test_real_transcript_style_timecodes_are_detected(self) -> None:
        transcript = (
            "At the zero zero thirty one seconds. 0041 seconds roughly. "
            "It is at fifty two seconds. Oh minute twenty-four, minute twenty-three. "
            "At two at two fourteen."
        )
        expected = ["00:31", "00:41", "00:52", "01:24", "01:23", "02:14"]
        self.assertEqual(cutnotes.source_timecodes(transcript), expected)
        self.assertEqual(
            cutnotes.source_timecodes(cutnotes.canonicalize_timecodes(transcript)),
            expected,
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

    def test_editorial_draft_renders_concise_chronological_handoff(self) -> None:
        units = cutnotes.source_units(
            "General note. The opening is too short. At 00:40, smooth the music edit. "
            "At 00:37, center the falling clothes."
        )
        markdown = cutnotes.render_editorial_draft(
            title="Demo",
            review_date="September 7, 2026",
            general_notes=[
                cutnotes.DraftNote(
                    "Let the opening breathe",
                    "The opening feels too short; retain more of its strongest material.",
                    ("N0001",),
                )
            ],
            timestamped_notes=[
                cutnotes.DraftNote(
                    "Smooth the music edit",
                    "Make the song transition feel seamless and rhythmically motivated.",
                    ("N0002",),
                ),
                cutnotes.DraftNote(
                    "Improve the framing",
                    "Center the falling clothing more clearly in the frame.",
                    ("N0003",),
                ),
            ],
            units=units,
        )
        self.assertEqual(cutnotes.validate_markdown(markdown), [])
        self.assertLess(markdown.index("00:37"), markdown.index("00:40"))
        self.assertNotIn("## Overall", markdown)
        self.assertIn("## Feedback Summary", markdown)

    def test_draft_payload_keeps_grounding_ids_out_of_reader_prose(self) -> None:
        notes = cutnotes.draft_notes_from_payload(
            {
                "notes": [
                    {
                        "title": "Opening length",
                        "body": "The opening is too short, as noted by N0003.",
                        "source_ids": ["N0003"],
                    }
                ]
            },
            {"N0003"},
        )
        self.assertEqual(notes[0].body, "The opening is too short.")

    def test_grounded_timestamp_fallbacks_preserve_clear_editorial_meaning(self) -> None:
        cases = (
            (
                "00:31",
                "The song edit is noticeable and too jagged.",
                "Smooth the song edit",
            ),
            (
                "00:37",
                "Maybe crop so the bra lands closer to the center of the frame.",
                "Improve the framing of the falling clothing",
            ),
            (
                "01:23",
                "Maybe cut so we don't see her face looking into camera, but the bra pull still reads; a swoosh could help the turn.",
                "Avoid the look into camera",
            ),
            (
                "01:26",
                "Unintelligible background lyrics.",
                "No clear actionable note captured",
            ),
        )
        for index, (timecode, text, expected_title) in enumerate(cases, start=1):
            with self.subTest(timecode):
                note = providers_module._fallback_timestamp_note(
                    timecode,
                    [cutnotes.SourceUnit(f"T{index:04d}", text, (timecode,))],
                )
                self.assertEqual(note.title, expected_title)

    def test_grounding_rejects_advice_invented_from_general_praise(self) -> None:
        unit = cutnotes.SourceUnit("N0001", "The opening feels strong.", ())
        units = {unit.id: unit}
        grounded = cutnotes.DraftNote(
            "Opening strength",
            "The opening feels strong.",
            (unit.id,),
        )
        invented = cutnotes.DraftNote(
            "Improve the opening",
            "The opening could be improved by adding a more engaging hook or a clearer introduction to the main theme.",
            (unit.id,),
        )

        self.assertEqual(
            providers_module._sanitize_grounded_note(grounded, units),
            grounded,
        )
        self.assertIsNone(
            providers_module._sanitize_grounded_note(invented, units)
        )

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

    def test_recording_controls_pause_resume_finish_cancel_and_closed_pipe(self) -> None:
        class FakeCaptureProcess:
            def __init__(self) -> None:
                self.stdin = io.BytesIO()
                self.return_code: int | None = None

            def poll(self):
                return self.return_code

            def wait(self):
                self.return_code = 0
                return self.return_code

            def send_signal(self, _signal):
                self.return_code = 130

        scenarios = (
            ("pause, resume, finish", b"pause\nresume\nfinish\n", 2, 320, False),
            ("finish while paused", b"pause\nfinish\n", 1, 160, False),
            ("cancel while paused", b"pause\ncancel\n", 1, 160, True),
            (
                "repeated controls are idempotent",
                b"pause\npause\nresume\nresume\nfinish\n",
                2,
                320,
                False,
            ),
            ("closed control pipe finishes", b"", 1, 160, False),
        )
        for label, controls, process_count, expected_frames, cancelled in scenarios:
            with self.subTest(label):
                processes: list[FakeCaptureProcess] = []

                def start_capture(command, **_kwargs):
                    segment = Path(command[-1])
                    with wave.open(str(segment), "wb") as recording:
                        recording.setnchannels(1)
                        recording.setsampwidth(2)
                        recording.setframerate(16_000)
                        recording.writeframes(b"\x01\x00" * 160)
                    process = FakeCaptureProcess()
                    processes.append(process)
                    return process

                with tempfile.TemporaryDirectory() as temporary_directory:
                    output = Path(temporary_directory) / "audio.wav"
                    read_fd, write_fd = os.pipe()
                    try:
                        if controls:
                            os.write(write_fd, controls)
                        os.close(write_fd)
                        write_fd = -1
                        with mock.patch.object(
                            cutnotes.subprocess,
                            "Popen",
                            side_effect=start_capture,
                        ) as popen:
                            if cancelled:
                                with self.assertRaises(CutNotesError) as raised:
                                    cutnotes.record_audio(
                                        "/fake/ffmpeg",
                                        output,
                                        None,
                                        "System Default",
                                        True,
                                        control_fd=read_fd,
                                    )
                                self.assertEqual(raised.exception.code, "cancelled")
                                self.assertTrue(raised.exception.preserved.audio)
                            else:
                                cutnotes.record_audio(
                                    "/fake/ffmpeg",
                                    output,
                                    None,
                                    "System Default",
                                    True,
                                    control_fd=read_fd,
                                )
                    finally:
                        os.close(read_fd)
                        if write_fd >= 0:
                            os.close(write_fd)

                    with wave.open(str(output), "rb") as recording:
                        self.assertEqual(recording.getnframes(), expected_frames)
                        self.assertEqual(recording.getframerate(), 16_000)

                self.assertEqual(popen.call_count, process_count)

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
schema = json.loads(pathlib.Path(args[args.index("--output-schema") + 1]).read_text(encoding="utf-8"))
source_id = schema["properties"]["notes"]["items"]["properties"]["source_ids"]["items"]["enum"][0]
draft = {
    "notes": [{
        "title": "Shorten the shot",
        "body": "Shorten the shot.",
        "source_ids": [source_id],
    }],
}
output.write_text(json.dumps(draft), encoding="utf-8")
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
            self.assertIn("**00:05 — Shorten the shot**", output.read_text(encoding="utf-8"))
            self.assertIn("Shorten the shot.", output.read_text(encoding="utf-8"))

    def test_apple_format_batches_long_transcript_for_local_context_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp = Path(temporary_directory)
            transcript = temp / "transcript.txt"
            output = temp / "feedback.md"
            transcript.write_text(
                " ".join(
                    (
                        "Editorial observation 40 contains SENSITIVE_MARKER and must still be preserved."
                        if index == 40
                        else f"Editorial observation {index} should preserve this distinct requested change."
                    )
                    for index in range(1, 81)
                ),
                encoding="utf-8",
            )

            fake_engine = self.make_executable(
                temp,
                "CutNotesLocal",
                """#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
prompt = pathlib.Path(args[args.index("--prompt") + 1]).read_text(encoding="utf-8")
if "SENSITIVE_MARKER" in prompt:
    print(
        "CutNotesLocal: guardrailViolation: May contain unsafe content",
        file=sys.stderr,
    )
    raise SystemExit(1)
if len(prompt) > 2_500:
    print(
        "CutNotesLocal: exceededContextWindowSize: maximum allowed context size of 4096",
        file=sys.stderr,
    )
    raise SystemExit(1)
output = pathlib.Path(args[args.index("--output") + 1])
source_ids = []
for token in prompt.replace(":", " ").replace(",", " ").split():
    if len(token) == 5 and token.startswith("N") and token[1:].isdigit() and token not in source_ids:
        source_ids.append(token)
output.write_text(json.dumps({
    "schema_version": "cutnotes.local.draft.v1",
    "draft": {
        "notes": ([{
            "title": "Preserve the requested change",
            "body": "Preserve the distinct requested editorial change.",
            "source_ids": [source_ids[0]],
        }] if source_ids else []),
    },
}), encoding="utf-8")
""",
            )
            environment = os.environ.copy()
            environment["CUTNOTES_LOCAL_ENGINE"] = str(fake_engine)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "format",
                    str(transcript),
                    "--title",
                    "Long Review",
                    "--output",
                    str(output),
                    "--formatter",
                    "apple",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertIn("## Feedback Summary", output.read_text(encoding="utf-8"))
            self.assertIn("Preserve the distinct requested editorial change.", output.read_text(encoding="utf-8"))
            self.assertIn("SENSITIVE_MARKER", transcript.read_text(encoding="utf-8"))

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
