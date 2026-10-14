"""Synthetic regressions for source-owned CUT locations and inline references."""
import io
import unittest
from unittest import mock

from cutnotes_core import cli, formatting as f
from cutnotes_core.contracts import CutNotesError, PreservedArtifacts
from cutnotes_core.editorial_edits import revision_review
from cutnotes_core.formatter_candidate import clean_disfluencies, format_candidate


class TimecodeGroundingTests(unittest.TestCase):
    def render(self, source, revise=None):
        return format_candidate(transcript=source, title="Synthetic review", review_date="2026-10-14",
                                ask=lambda kind, text: kind == "same", revise=revise)

    def test_spoken_cues_survive_fillers_restarts_and_canonicalization(self):
        cases = {
            "At only five oh six, the lamp flickers.": ["05:06"],
            "At um one thirty, keep the insert.": ["01:30"],
            "At uh three sixteen, trim the insert.": ["03:16"],
            "At at eleven thirty two, keep the insert.": ["11:32"],
            "At uh thir thirteen forty two, keep the insert.": ["13:42"],
            "The shot nine fifty is dark.": ["09:50"],
            "This sequence here three forty five roughly.": ["03:45"],
            "I like the footage we got fifteen sixteen.": ["15:16"],
            "From ten eighteen to ten ten thirty, keep the score.": ["10:18", "10:30"],
            "At 7:42, use the insert from like two twenty.": ["07:42", "02:20"],
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(f.source_timecodes(source), expected)
                normalized = f.canonicalize_timecodes(source)
                self.assertEqual(f.source_timecodes(normalized), expected)
                self.assertEqual(f.canonicalize_timecodes(normalized), normalized)

    def test_counts_durations_and_clock_times_are_not_cut_times(self):
        for source in (
            "Hold for twelve seconds.", "Wait from twelve to thirteen seconds before answering.",
            "We met at five o'clock.", "We met at five thirty p.m.",
            "The shot takes twenty five frames.", "We got twenty five takes.",
            "Keep the gain at twenty five percent.", "The footage runs for fifteen minutes.",
            "The camera stops at four hours.", "We got one two cameras.",
        ):
            with self.subTest(source=source):
                self.assertEqual(f.source_timecodes(source), [])

    def test_number_repetition_is_not_prose_repetition(self):
        self.assertEqual(clean_disfluencies("Use use the insert from like ten ten."),
                         "Use the insert from like ten ten.")
        self.assertEqual(clean_disfluencies("zero zero and 11 11"), "zero zero and 11 11")

    def test_new_cues_do_not_inherit_an_earlier_location(self):
        source = ("At two ten, the door is dark. At only five oh six, the lamp flickers. "
                  "The shot nine fifty is soft.")
        markdown, audit = self.render(source)
        self.assertIn("**02:10** | The door is dark.", markdown)
        self.assertIn("**05:06** | The lamp flickers.", markdown)
        self.assertIn("**09:50** | The shot is soft.", markdown)
        self.assertEqual(f.validate_timecodes(markdown, source), ([], []))
        self.assertEqual(audit["unassigned_timing_ids"], [])

    def test_primary_location_and_reference_keep_distinct_roles(self):
        source = "At seven forty two, use the insert from like two twenty. Maybe use another frame from two twenty."
        markdown, audit = self.render(source)
        self.assertIn("**07:42** | Use the insert from like [02:20].", markdown)
        self.assertIn("another frame from [02:20]", markdown)
        self.assertNotIn("**02:20", markdown)
        self.assertEqual([r["times"] for r in audit["sentences"]], [["07:42"], []])
        self.assertEqual(f.validate_timecodes(markdown, source), ([], []))

    def test_range_and_until_reference_are_preserved(self):
        source = "From ten eighteen to ten ten thirty, keep the score. Keep the room tone until like eleven fifteen."
        markdown, _ = self.render(source)
        self.assertIn("**10:18–10:30**", markdown)
        self.assertIn("until like [11:15]", markdown)
        self.assertNotIn("**11:15", markdown)
        self.assertEqual(f.validate_timecodes(markdown, source), ([], []))

    def test_model_cannot_change_or_borrow_another_notes_time(self):
        source = "At two ten, the door is dark. At five oh six, use the insert from one thirty."
        for proposal in ("Use the insert from [02:10].", "Use the insert.", "At five oh seven, use the insert from [01:30]."):
            with self.subTest(proposal=proposal):
                def revise(text):
                    return {"proposed": proposal if "insert" in text else text, "issues": []}
                markdown, audit = self.render(source, revise)
                self.assertIn("**05:06** | Use the insert from [01:30].", markdown)
                self.assertFalse(audit["revisions"][-1]["accepted"])
                self.assertIn("CUT time references changed or omitted", audit["revisions"][-1]["issues"])
                self.assertEqual(f.validate_timecodes(markdown, source), ([], []))

    def test_reported_failure_has_a_source_owned_time_before_editing(self):
        source = "The lamp flickers at only five oh six. I wonder whether another take is available."
        seen = []
        def revise(text):
            seen.append(text)
            return revision_review(text, text)
        markdown, _ = self.render(source, revise)
        self.assertNotIn("five oh six", " ".join(seen))
        self.assertIn("**05:06**", markdown)
        self.assertEqual(f.validate_timecodes(markdown, source), ([], []))

    def test_human_cli_reports_preservation_once_without_changing_json(self):
        error = CutNotesError("Formatting failed.", 6, code="formatter_timecode_contract_failed",
                              recovery="Retry formatting.", preserved=PreservedArtifacts(audio=True, transcript=True))
        for args in (["format", "unused.txt", "--title", "Review"],
                     ["format", "unused.txt", "--title", "Review", "--json"]):
            output = io.StringIO()
            with mock.patch.object(cli, "run_format", side_effect=error), mock.patch("sys.stderr", output):
                self.assertEqual(cli.main(args), 6)
            if "--json" in args:
                import json
                self.assertEqual(json.loads(output.getvalue()), error.payload())
            else:
                self.assertEqual(output.getvalue().count("Captured audio was preserved."), 1)
                self.assertEqual(output.getvalue().count("The transcript was preserved."), 1)


if __name__ == "__main__":
    unittest.main()
