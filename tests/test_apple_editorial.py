"""Production wiring for the reviewed local formatter and acoustic evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cutnotes_core import providers as p
from cutnotes_core.apple_editorial import EditorialQuestions
from cutnotes_core.contracts import CutNotesError, EXIT_FORMATTING, ProgressReporter
from cutnotes_core.transcription import evidence_path, text_digest


class AppleEditorialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source, self.output = self.root / 'transcript.txt', self.root / 'notes.md'
        self.source.write_text('At five seconds, the light is warm. The lighting is soft.\n')
        self.reporter = mock.Mock(spec=ProgressReporter)

    def run_format(self, **kwargs):
        p.format_with_apple(engine='fake', transcript_path=self.source, output_path=self.output,
                            title='Review', context=None, reporter=self.reporter, **kwargs)

    def response(self, **request):
        if request['mode'] == 'editorial-decision':
            return {'answer': request['prompt'].startswith('Do the previous')}
        if request['mode'] == 'editorial-edit':
            # Deliberately change positive observation into negative meaning.
            return {'text': 'The light is not warm. The lighting is soft.'}
        return {'text': 'YES'}

    def test_shipping_path_rejects_changed_meaning_and_preserves_source(self):
        original = self.source.read_bytes()
        with mock.patch.object(p, '_generate_with_apple', side_effect=self.response) as generate:
            self.run_format()
        markdown = self.output.read_text()
        self.assertIn('The light is warm.', markdown)
        self.assertNotIn('not warm', markdown)
        self.assertEqual(self.source.read_bytes(), original)
        audit = json.loads(next(self.root.glob('*.formatting-review-*.json')).read_text())
        self.assertTrue(any(not row['accepted'] for row in audit['revisions']))
        self.assertEqual(audit['source_transcript_sha256'], text_digest(original.decode()))
        self.assertEqual(audit['output_sha256'], text_digest(markdown))
        for call in generate.call_args_list:
            self.assertEqual(call.kwargs['schema_version'], 'cutnotes.local.editorial.v1')
            self.assertEqual(call.kwargs['payload_key'], 'result')
            self.assertNotIn('the light is warm', call.kwargs['instructions'])

    def test_single_observation_is_never_reinterpreted(self):
        generate = mock.Mock(side_effect=AssertionError('No rewrite is needed'))
        review = EditorialQuestions(generate).revise('The grade is warm.')
        self.assertEqual(review['proposed'], 'The grade is warm.')
        self.assertEqual(review['strategy'], 'single_statement_preserved')
        generate.assert_not_called()

    def test_invalid_decision_preserves_prior_output(self):
        for invalid in ({'answer': 'false'}, None, {'text': 'YES'}):
            with self.subTest(invalid=invalid):
                self.output.write_text('Approved earlier notes')
                with mock.patch.object(p, '_generate_with_apple', return_value=invalid):
                    with self.assertRaises(CutNotesError) as raised:
                        self.run_format()
                self.assertEqual(raised.exception.code, 'apple_formatting_invalid_result')
                self.assertTrue(raised.exception.preserved.transcript)
                self.assertEqual(self.output.read_text(), 'Approved earlier notes')
                self.assertFalse(list(self.root.glob('*.formatting-review-*.json')))

    def test_unavailable_model_does_not_fall_back(self):
        with mock.patch.object(p, '_generate_with_apple', side_effect=CutNotesError(
                'Unavailable', EXIT_FORMATTING, code='apple_model_unavailable')):
            with self.assertRaises(CutNotesError) as raised:
                self.run_format()
        self.assertEqual(raised.exception.code, 'apple_model_unavailable')
        self.assertFalse(self.output.exists())

    def test_context_or_guardrail_limit_keeps_source_and_reports_it(self):
        for reason in ('apple_context_window', 'apple_guardrail'):
            with self.subTest(reason=reason):
                with mock.patch.object(p, '_generate_with_apple', side_effect=CutNotesError(
                        'Limit', EXIT_FORMATTING, code=reason)):
                    self.run_format()
                self.assertIn('The light is warm.', self.output.read_text())
                self.assertIn('The lighting is soft.', self.output.read_text())
                self.reporter.warning.assert_called()
        self.assertEqual(len(list(self.root.glob('*.formatting-review-*.json'))), 2)

    def test_standalone_text_does_not_infer_or_measure_audio(self):
        evidence_path(self.source).write_text('{}')
        with mock.patch.object(p, '_generate_with_apple', side_effect=self.response), \
                mock.patch.object(p, 'analyze_recording') as analyze:
            self.run_format()
        analyze.assert_not_called()

    def test_stale_alignment_keeps_whole_transcript(self):
        evidence_path(self.source).write_text('{}')
        with mock.patch.object(p, '_generate_with_apple', side_effect=self.response), \
                mock.patch.object(p, 'analyze_recording', side_effect=ValueError('Hashes differ')):
            self.run_format(audio_path=self.root / 'audio.wav', ffmpeg='fake-ffmpeg')
        self.assertIn('The light is warm.', self.output.read_text())
        self.reporter.warning.assert_any_call('formatting', 'Audio levels could not be verified; all transcribed speech was kept for formatting.')

    def test_audio_proposal_does_not_overwrite_transcript_and_is_audited(self):
        original = self.source.read_text() + 'Unrelated quiet speech.\n'
        self.source.write_text(original)
        evidence_path(self.source).write_text('{}')
        acoustic = {'utterances': [{'background_candidate': True, 'text': 'Unrelated quiet speech.'}],
                    'proposed_foreground_transcript': 'At five seconds, the light is warm.\n'}
        with mock.patch.object(p, '_generate_with_apple', side_effect=self.response), \
                mock.patch.object(p, 'analyze_recording', return_value=acoustic) as analyze:
            self.run_format(audio_path=self.root / 'audio.wav', ffmpeg='fake-ffmpeg')
        self.assertEqual(analyze.call_args.kwargs['transcript'], original)
        self.assertEqual(self.source.read_text(), original)
        self.assertNotIn('Unrelated quiet speech', self.output.read_text())
        audit = json.loads(next(self.root.glob('*.formatting-review-*.json')).read_text())
        self.assertEqual(audit['speech_levels'], acoustic)
