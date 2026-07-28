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

    def test_parser_allows_zero_argument_interactive_mode(self) -> None:
        args = cutnotes.build_parser().parse_args([])
        self.assertIsNone(args.command)

    def test_interactive_mode_prompts_then_starts_recording(self) -> None:
        doctor = {
            "healthy": True,
            "cutnotes": cutnotes.VERSION,
            "ffmpeg": {"path": "/fake/ffmpeg", "version": "ffmpeg test"},
            "macwhisper": {
                "path": "/fake/mw",
                "version": "MacWhisper test",
                "models": ["▸ parakeet-pro:test Active"],
            },
            "codex": {"path": "/fake/codex", "version": "codex test"},
            "microphones": [{"index": 1, "name": "MacBook Pro Microphone"}],
        }
        with (
            mock.patch.object(sys.stdin, "isatty", return_value=True),
            mock.patch.object(cutnotes, "doctor_payload", return_value=(doctor, True)),
            mock.patch.object(
                cutnotes,
                "choose_microphone",
                return_value=(1, "MacBook Pro Microphone"),
            ),
            mock.patch("builtins.input", side_effect=["Demo Rough Cut", ""]),
            mock.patch.object(cutnotes, "run_record", return_value=0) as run_record,
        ):
            result = cutnotes.run_interactive(cutnotes.argparse.Namespace())

        self.assertEqual(result, 0)
        interactive_args = run_record.call_args.args[0]
        self.assertEqual(interactive_args.title, "Demo Rough Cut")
        self.assertFalse(interactive_args.transcript_only)


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
markdown = \"\"\"# Demo

**Review date:** July 28, 2026

## Overall
Tighten the cut.

## Highest-Priority Changes
1. Shorten the shot.

## Timestamped Notes
### `[00:05]` — Shorten Shot
- Trim it.

## Recurring Themes
- Pacing.

## Open Questions
- None.

## Positive Notes
- None noted.
\"\"\"
output.write_text(json.dumps({"markdown": markdown}), encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
