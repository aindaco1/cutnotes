import unittest

from cutnotes_core.formatter_candidate import clean_disfluencies, copyedit_issues, format_candidate, normalize_review_times


class CandidateFormatterTests(unittest.TestCase):
    def render(self, source, answer=None):
        return format_candidate(transcript=source, title="Review", review_date="2026-09-22",
                                ask=answer or (lambda kind, text: kind == "same"))

    def test_spoken_digits_survive_disfluency_cleanup(self):
        markdown, audit = self.render(
            "For that opening shot, it's like zero zero zero zero five. "
            "Four seconds I think. The curtains are open. I would prefer them closed.")
        self.assertIn("00:04–00:05", markdown)
        self.assertIn("curtains are open", markdown)
        self.assertIn("prefer them closed", markdown)
        self.assertTrue(audit["warnings"])
        self.assertEqual(audit["unassigned_timing_ids"], [])

    def test_retrospective_time_only_updates_its_own_note(self):
        def answer(kind, text):
            return kind == "same" and "Add more space" not in text.split("Target sentence: ")[-1]
        markdown, audit = self.render(
            "At two seconds, the curtains are open. Keep them open. "
            "Add more space before the answer. That would be like I don't know, twenty three seconds.", answer)
        self.assertIn("**00:02** | The curtains are open. Keep them open.", markdown)
        self.assertIn("Around 00:23", markdown)
        self.assertIn("Add more space before the answer.", markdown)
        self.assertEqual(len(audit["rendered_source_ids"]), 4)

    def test_spoken_range_keeps_both_endpoints_and_short_observation(self):
        markdown, _ = self.render("At thirty seconds, the lamp flickers. So 30 through 31 seconds. It looks odd.")
        self.assertIn("**00:30–00:31**", markdown)
        self.assertIn("The lamp flickers.", markdown)
        self.assertIn("It looks odd.", markdown)

    def test_short_timed_feedback_is_not_a_timing_only_cue(self):
        markdown, _ = self.render("At eight seconds, too dark. At nine seconds, fix it.")
        self.assertIn("**00:08** | Too dark.", markdown)
        self.assertIn("**00:09** | Fix it.", markdown)

    def test_inline_retrospective_cue_never_drops_its_request(self):
        markdown, _ = self.render("Give the reply more space; that would be twenty three seconds.")
        self.assertIn("00:23", markdown)
        self.assertIn("Give the reply more space", markdown)

    def test_quoted_dialogue_remains_with_the_note_before_its_time(self):
        markdown, _ = self.render('Allow more space before the line “What happened?” That would be twenty three seconds.')
        self.assertIn("00:23", markdown)
        self.assertIn('Allow more space before the line “What happened?”', markdown)

    def test_praise_and_ending_do_not_inherit_previous_time(self):
        markdown, _ = self.render(
            "At twenty seconds, the score is loud. The rest is great. "
            "I love the last frame with the chalk texture. It looks great.")
        general = markdown.split("## Timestamped feedback")[0]
        self.assertIn("The rest is great", general)
        self.assertIn("**End of video — Editorial feedback** | I love the last frame", markdown)
        self.assertNotIn("00:20** | I love", markdown)

    def test_model_cannot_silently_drop_a_caveat(self):
        markdown, audit = self.render("The colour is too warm. My screen could be responsible.",
                                      lambda kind, text: kind in {"same", "unrelated"})
        self.assertIn("My screen could be responsible", markdown)
        self.assertEqual(len(audit["rendered_source_ids"]), 2)
        self.assertEqual(len(audit["warnings"]), 2)
        self.assertTrue(audit["requires_review"])

    def test_filler_cleanup_preserves_negation_comparison_and_conditions(self):
        source = "Um the glow is like fog. Do not remove it. If time allows, keep keep the effect."
        self.assertEqual(clean_disfluencies(source),
                         "the glow is like fog. Do not remove it. If time allows, keep the effect.")

    def test_partial_word_cleanup_does_not_complete_a_new_fact(self):
        self.assertEqual(clean_disfluencies("with the d with the drawing on on the wall"),
                         "with the drawing on the wall")
        self.assertEqual(clean_disfluencies("with the red with the drawing"),
                         "with the red with the drawing")

    def test_durations_and_clock_times_are_not_cut_cues(self):
        for source in ("Hold for twelve seconds.", "Wait from twelve to thirteen seconds before answering.",
                       "We met at five o'clock."):
            self.assertEqual(normalize_review_times(source), source)

    def test_copyedit_flags_new_reasoning_and_lost_conditions(self):
        self.assertTrue(copyedit_issues("I don't there's something odd with the audio.",
                                        "I don't think there's something odd with the audio."))
        self.assertTrue(copyedit_issues("If time allows, add a fade.", "Add a fade."))
        self.assertTrue(copyedit_issues("It sounds off.", "The actor stands in a dim hallway."))
        self.assertEqual(copyedit_issues("Um, the lamps are are dark.", "The lamps are dark."), [])

    def test_rejected_copyedit_is_visible_and_source_is_retained(self):
        markdown, audit = format_candidate(transcript="At eight seconds, it sounds off.", title="Review",
                                           review_date="2026-09-22", ask=lambda *args: False,
                                           edit=lambda text: "The actor walks down a dim hallway.")
        self.assertIn("It sounds off", markdown)
        self.assertNotIn("hallway", markdown)
        self.assertFalse(audit["revisions"][0]["accepted"])
        self.assertTrue(audit["warnings"])


if __name__ == "__main__":
    unittest.main()
