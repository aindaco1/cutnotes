import unittest
from cutnotes_core.experimental_budget import ThoughtBudget, checked_budget_answer, forbidden_special_ids


class ThoughtBudgetTests(unittest.TestCase):
    def test_budget_forces_only_until_end_token_arrives(self):
        b = ThoughtBudget(3, 99)
        self.assertFalse(b.should_close(0, None))
        self.assertFalse(b.should_close(2, 17))
        self.assertTrue(b.should_close(3, 17))
        self.assertTrue(b.forced)
        self.assertFalse(b.should_close(4, 99))
        self.assertEqual(b.closed_at,4)
        self.assertFalse(b.should_close(5, 17))
        self.assertFalse(b.should_close(6, 99))
        self.assertEqual(b.closed_at,4)

    def test_natural_close_and_prompt_marker_do_not_force(self):
        b = ThoughtBudget(3, 99)
        self.assertFalse(b.should_close(0, 99))
        self.assertFalse(b.closed)
        self.assertFalse(b.should_close(2, 99))
        self.assertFalse(b.should_close(50, 17))
        self.assertFalse(b.forced)

    def test_leaked_reasoning_and_duplicate_transition_are_rejected(self):
        good = '<|channel>thought\nreasoning<channel|>## Timestamp Notes\n### T001 — Note\nBody'
        self.assertTrue(checked_budget_answer(good).startswith('## Timestamp Notes'))
        for bad in [good+'<channel|>More', good.replace('## Timestamp Notes','Let me plan first.\n## Timestamp Notes'),
                    good.replace('<channel|>',''),good+'<|channel>thought']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):checked_budget_answer(bad)

    def test_nonpositive_budget_is_rejected(self):
        for n in [0,-1]:
            with self.assertRaises(ValueError):ThoughtBudget(n, 99)

    def test_json_answer_boundary_still_rejects_planning_prose(self):
        self.assertEqual(checked_budget_answer('<|channel>thought\nplan<channel|>{"timed":{}}',expected_prefix='{'),'{"timed":{}}')
        with self.assertRaises(ValueError):
            checked_budget_answer('<|channel>thought\nplan<channel|>Now consider {"timed":{}}',expected_prefix='{')

    def test_text_mask_never_blocks_termination_or_requested_channels(self):
        self.assertEqual(forbidden_special_ids([1,2,3,4,5],[2,5]),[1,3,4])
        self.assertEqual(forbidden_special_ids([1,2,3,4,5],[2,5],[3,4]),[1])
