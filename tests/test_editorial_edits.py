import unittest

from cutnotes_core.editorial_edits import evidence_for, relevance_review, revision_issues, revision_review, validate_extracted_facts
from cutnotes_core.formatter_candidate import format_candidate


class EditorialEditsTests(unittest.TestCase):
    def test_evidence_preserves_every_sentence_without_inventing_a_request(self):
        source = "The lamp is off. It looks odd. It would be nice if it were on."
        rows = evidence_for(source)
        self.assertEqual(" ".join(r["quote"] for r in rows), source)
        self.assertEqual(rows[0]["syntax_hints"], ["statement"])
        self.assertIn("explicit_change_or_keep_request", rows[2]["syntax_hints"])

    def test_evidence_quotes_and_roles_cannot_hide_lost_statements(self):
        source = "The lamp is off. Keep it off."
        self.assertEqual(validate_extracted_facts(source, [
            {"quote": "The lamp is off.", "role": "observation"},
            {"quote": "Keep it off.", "role": "request"}]), [])
        for facts in ([{"quote": "The lamp is off.", "role": "observation"}],
                      [{"quote": source, "role": "observation"}],
                      [{"quote": "The lamp is broken.", "role": "observation"}]):
            self.assertTrue(validate_extracted_facts(source, facts))

    def test_duplicate_evidence_requires_matching_source_occurrences(self):
        fact = {"quote": "Keep it.", "role": "request"}
        self.assertEqual(validate_extracted_facts("Keep it. Keep it.", [fact, fact]), [])
        self.assertTrue(validate_extracted_facts("Keep it. Keep it.", [fact]))

    def test_negation_scope_and_property_swaps_are_flagged(self):
        pairs = [("The door is open. Do not close it.", "The door is not open. Do close it."),
                 ("Keep the lamp dark and the wall bright.", "Keep the lamp bright and the wall dark."),
                 ("The mouth is moving.", "The mouth is not moving."),
                 ("Do not remove the card.", "Do remove the card.")]
        for source, proposal in pairs:
            with self.subTest(source=source):
                self.assertTrue(revision_issues(source, proposal))

    def test_observation_cannot_become_an_imperative(self):
        self.assertIn("Observation acquired a change request",
                      revision_issues("The coat is blue.", "Make the coat blue."))
        self.assertEqual(revision_issues("Keep the coat blue.", "Keep the coat blue."), [])
        self.assertEqual(revision_issues("The coat is blue. Keep it blue.", "The coat is blue; keep it blue."), [])

    def test_request_cannot_hide_a_dropped_negative_observation(self):
        self.assertTrue(revision_issues("The wheel doesn't turn with the axle. It should only turn a little.",
                                       "The wheel should only turn a little."))

    def test_request_cannot_become_an_observed_state(self):
        self.assertTrue(revision_issues("The chime lands late. Move it earlier.", "The chime lands earlier."))

    def test_epistemic_if_is_uncertainty_not_a_work_condition(self):
        source = "I don't know if the tracks overlap, but it doesn't sound right."
        proposal = "Maybe the tracks overlap; it doesn't sound right."
        self.assertEqual(revision_issues(source, proposal), [])
        self.assertNotIn("condition", evidence_for(source)[0]["syntax_hints"])
        self.assertIn("Condition may be missing", revision_issues(
            "I don't know if the tracks overlap. If time permits, check them.",
            "Maybe the tracks overlap. Check them."))

    def test_explicit_general_feedback_survives_a_wrong_background_classification(self):
        markdown, audit = format_candidate(transcript="Overall, looks wonderful.", title="Review", review_date="2026-09-22",
                                           ask=lambda *args: False,
                                           classify_passage=lambda s: relevance_review(s, editorial=False, conversation=True))
        self.assertIn("looks wonderful", markdown)
        self.assertEqual(audit["relevance"][0]["disposition"], "review")

    def test_direct_cut_cue_survives_but_inherited_time_does_not_protect_an_aside(self):
        markdown, audit = format_candidate(
            transcript="At eight seconds, the title is tiny. My friend ordered lunch.",
            title="Review", review_date="2026-09-22", ask=lambda *args: False,
            classify_passage=lambda s: relevance_review(s, editorial=False, conversation=True))
        self.assertIn("title is tiny", markdown)
        self.assertNotIn("ordered lunch", markdown)
        self.assertEqual([r["disposition"] for r in audit["relevance"]], ["review", "background"])

    def test_word_changes_are_not_automatically_rejected_or_certified(self):
        pairs = [("The picture is too dark.", "The image is too dark."),
                 ("Her eyes are closed. Her eye is closed.", "Her eyes are closed."),
                 ("The lamp is off. It would be nice if it were on.", "The lamp is off; it would be nice if it were on.")]
        for source, proposal in pairs:
            review = revision_review(source, proposal)
            self.assertTrue(review["accepted_for_review"])
            self.assertFalse(review["semantic_correctness_proven"])

    def test_conditions_degrees_numbers_and_dialogue_remain_protected(self):
        pairs = [("If time allows, add a fade.", "Add a fade."),
                 ("Maybe the clips overlap.", "The clips overlap."),
                 ("Lower it slightly.", "Lower it."),
                 ("Use 3 frames.", "Use 5 frames."),
                 ('After “Who is there?” add a pause.', 'After “What is that?” add a pause.')]
        for source, proposal in pairs:
            with self.subTest(source=source):
                self.assertTrue(revision_issues(source, proposal))

    def test_large_invented_scene_is_flagged(self):
        self.assertTrue(revision_issues("Leave more space before the reply.",
                                       "The actress stands in a dim corridor with a tense expression and a red dress."))

    def test_unresolved_relevance_is_not_silently_removed(self):
        for source in ("My monitor could be misleading me.", "Keep the coat blue.",
                       "The coat is blue. Keep it blue.", "One other thing, keep the music."):
            self.assertEqual(relevance_review(source, editorial=False, conversation=True)["disposition"], "review")
        self.assertEqual(relevance_review("My friend called the dentist.", editorial=False, conversation=True)["disposition"], "background")
        self.assertEqual(relevance_review("The dentist scene is long.", editorial=True, conversation=False)["disposition"], "keep")
        self.assertEqual(relevance_review("Something happened.", editorial=None, conversation=True)["disposition"], "review")

    def test_background_proposals_are_audited_and_never_marked_accepted(self):
        markdown, audit = format_candidate(
            transcript="My friend called the dentist. Overall, the film looks excellent.",
            title="Review", review_date="2026-09-22", ask=lambda *args: False,
            classify_passage=lambda s: relevance_review(s, editorial="dentist" not in s, conversation="dentist" in s),
            revise=lambda s: revision_review(s, s))
        self.assertNotIn("dentist", markdown)
        self.assertIn("dentist", audit["relevance"][0]["source"])
        self.assertTrue(audit["requires_review"])
        self.assertNotIn("S0001", audit["rendered_source_ids"])

    def test_rejected_revision_keeps_original_and_the_proposal(self):
        markdown, audit = format_candidate(transcript="The coat is blue.", title="Review", review_date="2026-09-22",
                                           ask=lambda *args: False, revise=lambda s: revision_review(s, "Make the coat blue."))
        self.assertIn("The coat is blue", markdown)
        self.assertFalse(audit["revisions"][0]["accepted"])
        self.assertEqual(audit["revisions"][0]["proposed"], "Make the coat blue.")

    def test_invalid_native_revision_is_an_error(self):
        for result in (None, "", "  "):
            with self.assertRaises(ValueError):
                revision_review("Keep it.", result)


if __name__ == "__main__":
    unittest.main()
