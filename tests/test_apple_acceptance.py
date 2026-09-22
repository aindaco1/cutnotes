import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
checker = runpy.run_path(str(ROOT / "scripts/check-apple-formatting.py"))
evaluate = checker["evaluate"]


class AppleAcceptanceChecks(unittest.TestCase):
    def test_required_model_stops_inference_on_core_or_legacy_status(self):
        for model in ({"name": "AFM 3 Core"}, None):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                engine = root / "engine"
                engine.write_text("test helper")
                apple = {"state": "ready"}
                if model:
                    apple["model"] = model
                status = subprocess.CompletedProcess([], 0, json.dumps({"apple": apple}))
                args = ["check", "--engine", str(engine), "--output-dir", str(root / "results"),
                        "--require-model", "AFM 3 Core Advanced"]
                with patch("sys.argv", args), patch("subprocess.run", return_value=status), \
                        patch.dict(checker["main"].__globals__, format_with_apple=lambda **kwargs: self.fail("Unexpected inference")):
                    self.assertEqual(checker["main"](), 1)
                report = json.loads((root / "results/report.json").read_text())
                self.assertFalse(report["passed"])
                self.assertEqual(report["cases"], [])
                self.assertIn("Native acceptance was not run", report["error"])

    def test_matching_model_and_legacy_unrestricted_checks_run_inference(self):
        for required in (None, "AFM 3 Core Advanced"):
            with self.subTest(required=required), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                engine = root / "engine"
                engine.write_text("test helper")
                fixtures = root / "fixtures.json"
                fixtures.write_text(json.dumps([{"name": "Simple praise", "transcript": "Looks great.",
                                                "checks": [{"name": "Praise", "scope": "general", "contains": ["great"]}]}]))
                apple = {"state": "ready"}
                if required:
                    apple["model"] = {"name": required}
                status = subprocess.CompletedProcess([], 0, json.dumps({"apple": apple}))
                args = ["check", "--engine", str(engine), "--fixtures", str(fixtures),
                        "--output-dir", str(root / "results"), "--skip-jev"]
                if required:
                    args += ["--require-model", required]
                def format_fixture(**kwargs):
                    kwargs["output_path"].write_text("# Review\n\n## General feedback\n\n- Looks great.\n\n## Timestamped feedback\n\nNone.\n")
                with patch("sys.argv", args), patch("subprocess.run", return_value=status), \
                        patch.dict(checker["main"].__globals__, format_with_apple=format_fixture):
                    self.assertEqual(checker["main"](), 0)
                report = json.loads((root / "results/report.json").read_text())
                self.assertTrue(report["passed"])
                self.assertEqual(len(report["cases"]), 1)

    def test_jev_runs_by_default_and_failure_affects_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / "engine"
            engine.write_text("helper")
            fixture = root / "fixtures.json"
            fixture.write_text(json.dumps([{"name": "Simple", "transcript": "Looks great.", "checks": []}]))
            def format_fixture(**kwargs):
                kwargs["output_path"].write_text("# Review\n## General feedback\n- Great.\n## Timestamped feedback\nNone.\n")
            status = subprocess.CompletedProcess([], 0, json.dumps({"apple": {"state": "ready"}}))
            with patch("sys.argv", ["check", "--engine", str(engine), "--fixtures", str(fixture), "--output-dir", str(root / "results")]), \
                    patch("subprocess.run", return_value=status), \
                    patch.dict(checker["main"].__globals__, format_with_apple=format_fixture), \
                    patch("scripts.jev_evaluation.review", return_value={"combined_passed": False}) as judge:
                self.assertEqual(checker["main"](), 1)
                self.assertTrue(judge.call_args.kwargs["live"])
                self.assertTrue(json.loads((root / "results/report.json").read_text())["passed"])

    def test_removing_embedded_instruction_must_not_leave_background_speech_framing(self):
        case = json.loads((ROOT / "tests/fixtures/apple-formatting.json").read_text())[-1]
        text = """# Review
## General feedback
- The sound design is excellent.
## Timestamped feedback
| Video time | Feedback |
| --- | --- |
| **00:06** | The cut is abrupt. A voice in the recording says: |
"""
        self.assertTrue(any("Unexpected content" in item for item in evaluate(text, case)))
        self.assertEqual(evaluate(text.replace(" A voice in the recording says:", ""), case), [])

    def test_equivalent_phrasing_passes_without_accepting_reversed_or_definite_claims(self):
        cases = json.loads((ROOT / "tests/fixtures/apple-formatting.json").read_text())
        text = """# Review
## General feedback
- Sky appears too bright, possibly a display issue.
- Dialogue is quiet and needs to come forward.
## Timestamped feedback
No timestamp-specific notes were identified.
"""
        self.assertEqual(evaluate(text, cases[5]), [])
        self.assertTrue(evaluate(text.replace("possibly a display issue", "because of the display"), cases[5]))
        text = """# Review
## General feedback
None.
## Timestamped feedback
| Video time | Feedback |
| --- | --- |
| **00:14** | Image too dark. |
| **00:14** | Move the door slam to match the closing door. |
"""
        self.assertEqual(evaluate(text, cases[3]), [])
        self.assertTrue(evaluate(text.replace("slam to match", "slam earlier to match"), cases[3]))

    def test_coverage_alone_does_not_accept_reversed_meaning_or_missing_caveats(self):
        case = json.loads((ROOT / "tests/fixtures/apple-formatting.json").read_text())[0]
        text = """# Review
## General feedback
- Great and charming. Dialogue should be front and center; we can adjust it on our end.
## Timestamped feedback
| Video time | Feedback |
| --- | --- |
| **00:08** | Her lips keep moving after the dialogue ends. |
| **00:18** | The reaction is unclear, so the joke does not land well. |
| **00:32** | Add subtle mouth movement for the important line. |
| **End of video** | Stylize the animation and crossfade to live action. |
"""
        failures = evaluate(text, case)
        self.assertTrue(any("Reaction and limited improvement" in failure for failure in failures))
        self.assertTrue(any("Optional end transition" in failure for failure in failures))
        text = text.replace("so the joke", "though there may be little we can improve; the joke")
        text = text.replace("Stylize the animation", "If time allows, stylize the animation")
        self.assertEqual(evaluate(text, case), [])
        self.assertTrue(evaluate(text + "\nNegatives: retained. Reasons: retained. Qualifications: retained.", case))

    def test_correct_words_at_the_wrong_moment_fail(self):
        case = {"transcript": "At ten seconds, move the sound later. At twenty seconds, move the sound earlier.",
                "checks": [{"name": "Later sound", "scope": "^00:10$", "contains": ["later"], "excludes": ["earlier"]}]}
        text = """# Review
## General feedback
None.
## Timestamped feedback
| Video time | Feedback |
| --- | --- |
| **00:10** | Move the sound earlier. |
| **00:20** | Move the sound later. |
"""
        failures = evaluate(text, case)
        self.assertEqual(len(failures), 2)
        self.assertTrue(all("Later sound" in failure for failure in failures))

    def test_one_timestamp_does_not_establish_two_distinct_notes(self):
        case = {"transcript": "At fourteen seconds, the face is offset. At fourteen seconds, the sound is early.",
                "checks": [{"name": "Separate issues", "scope": "^00:14$", "minimum_notes": 2}]}
        text = """# Review
## General feedback
- Looks good.
## Timestamped feedback
| Video time | Feedback |
| --- | --- |
| **00:14** | The face is offset and the sound is early. |
"""
        self.assertIn("Separate issues: missing distinct notes", evaluate(text, case))
        text = text.replace("The face is offset and the sound is early.", "The face is offset.")
        text += "| **00:14** | The sound is early. |\n"
        self.assertEqual(evaluate(text, case), [])

    def test_qualification_must_be_in_the_note_it_qualifies(self):
        case = {"transcript": "Overall, the sky is too bright, but it could be my display. The dialogue is quiet.",
                "checks": [{"name": "Display uncertainty", "scope": "general", "same_note": True,
                            "contains": ["sky", "bright", "could.{0,30}display"]}]}
        text = """# Review
## General feedback
- The sky is too bright.
- The dialogue is quiet, but it could be my display.
## Timestamped feedback
No timestamp-specific notes were identified.
"""
        self.assertTrue(evaluate(text, case))
        text = text.replace("The sky is too bright.", "The sky is too bright, but it could be my display.")
        text = text.replace("The dialogue is quiet, but it could be my display.", "The dialogue is quiet.")
        self.assertEqual(evaluate(text, case), [])
