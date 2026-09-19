import json
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
evaluate = runpy.run_path(str(ROOT / "scripts/check-apple-formatting.py"))["evaluate"]


class AppleAcceptanceChecks(unittest.TestCase):
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
