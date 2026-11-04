import unittest
from cutnotes_core.formatting import source_timecodes,canonicalize_timecodes
from cutnotes_core.grounded_notes import time_cues


class CountTimeBoundaryTests(unittest.TestCase):
    def test_weak_this_is_count_is_not_a_cut_location(self):
        for source in ['This is one problem with two possible fixes.', 'This is two problems.',
                       'This is a single problem.', 'This is 20 choices.']:
            with self.subTest(source=source):
                self.assertEqual(source_timecodes(source),[])
                self.assertEqual(time_cues(source),[])
                self.assertEqual(canonicalize_timecodes(source),source)

    def test_clear_time_forms_still_work(self):
        for source,expected in [('This is one thirty.',['01:30']),('This is 131.',['01:31']),
                                ('This is at twenty.',['00:20']),('This is twenty seconds.',['00:20']),
                                ('At 01:12 this is one problem.',['01:12'])]:
            with self.subTest(source=source):self.assertEqual(source_timecodes(source),expected)
