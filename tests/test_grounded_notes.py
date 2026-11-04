"""Synthetic contract tests for the opt-in grounded-note experiment."""
import copy
import unittest

from cutnotes_core.grounded_notes import (
    build_evidence, time_cues, validate_plan, render_notes, parse_source_ids, parse_remainder,
    marked_transcript, render_marked_markdown,
)


class GroundedNoteTests(unittest.TestCase):
    def test_spoken_locations_have_exact_source_offsets(self):
        text = 'A strong silhouette four oh seven. I dislike the dissolve two forty-one. Especially the three forty five ish.'
        cues = time_cues(text)
        self.assertEqual([c.values for c in cues], [('04:07',), ('02:41',), ('03:45',)])
        self.assertTrue(cues[-1].approximate)
        for c in cues:
            self.assertEqual(text[c.start:c.end], c.quote)

    def test_compact_restart_retains_uncertainty_and_both_alternatives(self):
        cue, = time_cues('At 218 two two twenty-four the cut is sudden.')
        self.assertEqual(cue.values, ('02:24',))
        self.assertTrue(cue.uncertain)
        self.assertEqual(cue.alternatives, ('02:18', '02:24'))

    def test_compact_range_is_one_location_with_both_endpoints(self):
        cues = time_cues('The section of 1129-1134 could be longer.')
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].values, ('11:29', '11:34'))

    def test_counts_durations_clocks_and_quoted_speech_are_not_bare_locations(self):
        for text in [
            'Use one one kind of transition.', 'We spent one twenty five dollars.',
            'Hold for two thirty seconds.', 'The prop cost 1129-1134 dollars.',
            'We met at two fifteen p.m.', 'The line is "two fifteen".',
            'Our meeting is at two fifteen.',
        ]:
            with self.subTest(text=text):
                self.assertEqual(time_cues(text), [])

    def sample(self):
        evidence = build_evidence('At 02:10 the shadow is useful. Overall, the grade may be too cool.')
        plan = {'notes': [
            {'title': 'Shadow', 'location_id': 'T001', 'source_ids': ['S0001']},
            {'title': 'Grade', 'location_id': None, 'source_ids': ['S0002']}], 'exclusions': []}
        return evidence, plan

    def test_invalid_source_or_time_id_is_rejected(self):
        e, p = self.sample()
        for key, value in [('source_ids', ['S9999']), ('location_id', 'T999')]:
            q = copy.deepcopy(p); q['notes'][0][key] = value
            self.assertTrue(validate_plan(q, e))

    def test_time_requires_its_own_source_sentence(self):
        e, p = self.sample()
        p['notes'][0]['source_ids'] = ['S0002']
        self.assertIn('Note 0: location lacks its source sentence', validate_plan(p, e))

    def test_missing_substantive_source_and_time_are_reported(self):
        e, p = self.sample()
        p['notes'] = p['notes'][1:]
        errors = validate_plan(p, e)
        self.assertTrue(any('Unaccounted source IDs: S0001' == error for error in errors))
        self.assertIn('Missing timed notes: T001', errors)

    def test_relaxed_citation_coverage_still_rejects_ungrounded_locations(self):
        e, p = self.sample()
        p['notes'] = p['notes'][:1]
        self.assertTrue(validate_plan(p, e))
        self.assertEqual(validate_plan(p, e, require_coverage=False), [])
        p['notes'][0]['location_id'] = 'T999'
        self.assertTrue(validate_plan(p, e, require_coverage=False))

    def test_duplicate_primary_location_is_rejected(self):
        e, p = self.sample()
        p['notes'].append(copy.deepcopy(p['notes'][0]))
        self.assertTrue(any('duplicate primary location' in x for x in validate_plan(p, e)))

    def test_inline_reference_cannot_become_primary_location(self):
        e = build_evidence('At 07:42 use the insert from two twenty.')
        self.assertTrue(e['times'][1]['reference'])
        p = {'notes': [{'title': 'Insert', 'location_id': 'T002', 'source_ids': ['S0001']}], 'exclusions': []}
        self.assertTrue(any('inline reference' in x for x in validate_plan(p, e)))

    def test_body_cannot_invent_a_time_even_when_plan_is_valid(self):
        e, p = self.sample()
        with self.assertRaisesRegex(ValueError, 'Model prose contains a time'):
            render_notes('Synthetic', p, ['Keep it at 04:00.', 'It may be too cool.'], e)

    def test_general_note_has_no_inherited_location(self):
        e, p = self.sample()
        doc = render_notes('Synthetic', p, ['The shadow is useful.', 'The grade may be too cool.'], e)
        self.assertEqual(doc.count('02:10'), 1)
        self.assertIn('## General / Overall Notes\n\n- **Grade:** The grade may be too cool.', doc)

    def test_uncertain_location_remains_visible_to_reader(self):
        e = build_evidence('At 218 two two twenty-four the cut is sudden.')
        p = {'notes': [{'title': 'Cut', 'location_id': 'T001', 'source_ids': ['S0001']}], 'exclusions': []}
        doc = render_notes('Synthetic', p, ['The cut feels sudden.'], e)
        self.assertIn('Around 02:24', doc)
        self.assertIn('02:18 / 02:24', doc)

    def test_sentence_evidence_is_literal_and_covers_last_unpunctuated_text(self):
        text = 'Okay. At 02:10, keep the shadow. The color may be cool'
        e = build_evidence(text)
        self.assertEqual(len(e['sources']), 3)
        self.assertTrue(e['sources'][0]['filler_only'])
        for row in e['sources']:
            self.assertEqual(row['text'], text[row['start']:row['end']].strip())

    def test_source_selection_rejects_invented_ids_or_prose(self):
        self.assertEqual(parse_source_ids('S0001 S0002 S0001', {'S0001', 'S0002'}), ['S0001', 'S0002'])
        for text in ['', 'S0001 S9999', 'Use S0001']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_source_ids(text, {'S0001'})

    def test_remainder_must_cover_anchor_without_invented_or_assigned_ids(self):
        allowed = {'S0002', 'S0003'}
        self.assertEqual(parse_remainder('ATTACH N001 S0002 S0003', allowed, 'S0002', 2),
                         {'action': 'attach', 'note_index': 0, 'source_ids': ['S0002', 'S0003']})
        for text in ['GENERAL S0003', 'ATTACH N003 S0002', 'GENERAL S0001 S0002',
                     'EXCLUDE S0003 | filler', 'GENERAL S0002\nGENERAL S0003']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_remainder(text, allowed, 'S0002', 2)

    def test_capitalized_restart_preserves_all_source_words(self):
        text = 'The shadow works This costume is lovely. Some great framing throughout I\'m curious about the score'
        sources = build_evidence(text)['sources']
        self.assertEqual(len(sources), 4)
        self.assertEqual(' '.join(s['text'] for s in sources), text)

    def test_light_annotation_preserves_verbatim_transcript(self):
        text = 'At 02:10 the shadow is useful. The section of 1129-1134 could be longer.'
        evidence = build_evidence(text)
        marked = marked_transcript(text, evidence)
        self.assertEqual(marked.replace('{T001} ', '').replace('{T002} ', ''), text)

    def test_markdown_times_are_rendered_from_source(self):
        evidence = build_evidence('At 218 two two twenty-four the cut is sudden.')
        draft = '## Timestamp Notes\n\n### T001 — Cut\n\nThe cut feels sudden.'
        doc = render_marked_markdown('Synthetic', draft, evidence)
        self.assertIn('### Around 02:24\n', doc)
        self.assertIn('02:18 / 02:24', doc)

    def test_model_title_cannot_add_a_false_range_to_source_time(self):
        evidence = build_evidence('At 02:10 the shadow is useful.')
        draft = '### T001 — 200 to 210\n\nThe shadow is useful.'
        result = render_marked_markdown('Synthetic', draft, evidence)
        self.assertIn('### 02:10\n', result)
        self.assertNotIn('200 to 210', result)

    def test_internal_references_are_source_owned_and_unknown_ones_rejected(self):
        evidence=build_evidence('At 02:10 the shadow works. At 03:20 the reflection works.')
        draft='### T001 — Shadow\nIt works.\n\n### T002 — Reflection\nLike {T001}, this works.'
        result=render_marked_markdown('Synthetic',draft,evidence)
        self.assertIn('Like 02:10, this works.',result)
        self.assertNotIn('T001',result)
        with self.assertRaises(ValueError):
            render_marked_markdown('Synthetic',draft.replace('{T001}','T999'),evidence)

    def test_empty_heading_and_model_tokens_are_rejected(self):
        evidence=build_evidence('At 02:10 the shadow works.')
        for draft in ['### T001 — Empty\n\n## General / Overall Notes\n* A general point.',
                      '### T001 — Shadow\nm<image|>mune.']:
            with self.subTest(draft=draft),self.assertRaises(ValueError):
                render_marked_markdown('Synthetic',draft,evidence)

    def test_markdown_missing_duplicate_unknown_and_literal_times_fail(self):
        evidence = build_evidence('At 02:10 the shadow is useful.')
        for text in ['No timing.', '### T999 — Shadow\nUseful.',
                     '### T001 — Shadow\nUseful.\n### T001 — Another\nUseful.',
                     '### T001 — Shadow\nUse it at 04:00.']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                render_marked_markdown('Synthetic', text, evidence)


if __name__ == '__main__':
    unittest.main()
