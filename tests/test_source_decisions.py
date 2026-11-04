import unittest
import json
from cutnotes_core.grounded_notes import build_evidence
from cutnotes_core.source_decisions import parse_decisions, parse_body_contract


class SourceDecisionTests(unittest.TestCase):
    def setUp(self):
        self.source='Maybe lower every impact. Actually, only the first needs lowering.'
        self.evidence=build_evidence(self.source)

    def test_source_quotes_are_program_owned_and_not_semantic_acceptance(self):
        result=parse_decisions('REVISION S0001 S0002 | Lower only the first impact.',self.evidence)
        self.assertEqual(result[0]['source_quotes'],[s['text'] for s in self.evidence['sources']])
        self.assertFalse(result[0]['semantic_correctness_proven'])

    def test_bad_evidence_and_unsupported_structure_are_rejected(self):
        for text in ['REVISION S0002 | Lower the first.', 'CONDITION S0999 | Unknown.',
                     'CONDITION S0001 S0001 | Duplicate.', 'SUMMARY S0001 | Not a valid action.',
                     'CONDITION S0001 | <image|>token', '\n'.join(['CONDITION S0001 | Maybe.']*11)]:
            with self.subTest(text=text),self.assertRaises(ValueError):parse_decisions(text,self.evidence)

    def test_none_does_not_invent_annotations(self):
        self.assertEqual(parse_decisions('NONE',self.evidence),[])

    def test_id_only_annotations_keep_program_owned_quotes(self):
        result=parse_decisions('REVISION S0001 S0002',self.evidence)
        self.assertIsNone(result[0]['reading'])
        self.assertEqual(len(result[0]['source_quotes']),2)


class BodyContractTests(unittest.TestCase):
    def setUp(self):
        self.evidence=build_evidence('At 02:10 lower the hit. Overall the framing is great.')
        self.good={'timed':{'T001':'Lower the hit.'},'general':['The framing is great.']}

    def test_program_supplies_heading_structure(self):
        draft=parse_body_contract(json.dumps(self.good),self.evidence)
        self.assertIn('### T001 — Note\nLower the hit.',draft)
        self.assertIn('* The framing is great.',draft)

    def test_reverse_generation_order_cannot_change_source_chronology(self):
        evidence=build_evidence('At 02:10 lower the hit. At 05:23 the door works. Overall the framing is great.')
        raw={'general':['The framing is great.'],'timed':{'T002':'The door works.','T001':'Lower the hit.'}}
        draft=parse_body_contract(json.dumps(raw),evidence)
        self.assertLess(draft.index('### T001'),draft.index('### T002'))
        self.assertIn('### T002 — Note\nThe door works.',draft)

    def test_missing_extra_or_duplicate_keys_cannot_hide_notes(self):
        cases=[{'timed':{},'general':[]}, {'timed':{'T001':'One.','T002':'Two.'},'general':[]},
               {**self.good,'surprise':'value'}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):parse_body_contract(json.dumps(value),self.evidence)
        with self.assertRaises(ValueError):parse_body_contract('{"timed":{"T001":"One.","T001":"Two."},"general":[]}',self.evidence)

    def test_time_and_token_checks_remain_in_force(self):
        for body in ['', 'At 09:31 change this.', 'm<image|>muddle', 'At T999 change it.', 'First\nSecond']:
            value={'timed':{'T001':body},'general':[]}
            with self.subTest(body=body),self.assertRaises(ValueError):parse_body_contract(json.dumps(value),self.evidence)

    def test_known_body_references_use_existing_source_owned_renderer(self):
        from cutnotes_core.grounded_notes import render_marked_markdown
        value={'timed':{'T001':'Lower the hit, as noted at {T001}.'},'general':[]}
        candidate=parse_body_contract(json.dumps(value),self.evidence)
        rendered=render_marked_markdown('Notes',candidate,self.evidence)
        self.assertIn('as noted at 02:10.',rendered)
        self.assertNotIn('T001',rendered)
