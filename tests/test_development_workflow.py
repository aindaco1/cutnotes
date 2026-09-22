import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import jev_evaluation as jev

ROOT = Path(__file__).resolve().parents[1]
workflow = runpy.run_path(str(ROOT / 'scripts/test.py'))
calibrator = runpy.run_path(str(ROOT / 'scripts/calibrate-jev.py'))


class DevelopmentWorkflowTests(unittest.TestCase):
    def run_workflow(self, flags=(), calibration_code=0, native_code=0):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'results'
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                code = (calibration_code if 'scripts/calibrate-jev.py' in args else
                        native_code if 'scripts/check-apple-formatting.py' in args else 0)
                return subprocess.CompletedProcess(args, code)
            with patch('sys.argv', ['test', '--output-dir', str(output), '--engine', '/test/helper', *flags]), \
                    patch('subprocess.run', side_effect=run):
                code = workflow['main']()
            return code, calls, json.loads((output / 'report.json').read_text())

    def test_default_includes_live_calibration_and_native_judge(self):
        code, calls, report = self.run_workflow()
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 4)
        self.assertIn('scripts/calibrate-jev.py', calls[2])
        self.assertIn('scripts/check-apple-formatting.py', calls[3])
        self.assertNotIn('--skip-jev', calls[3])
        self.assertTrue(report['full_suite'])
        self.assertFalse(report['release_accepted'])

    def test_offline_is_explicit_and_records_missing_quality_gates(self):
        code, calls, report = self.run_workflow(['--offline'])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        self.assertFalse(report['full_suite'])
        self.assertEqual(len(report['skipped']), 2)

    def test_auth_error_stops_and_never_claims_pass(self):
        code, calls, report = self.run_workflow(calibration_code=2)
        self.assertEqual(code, 2)
        self.assertEqual(len(calls), 3)
        self.assertFalse(report['passed'])

    def test_completed_quality_failure_keeps_running_but_fails_suite(self):
        for calibration, native in ((1, 0), (0, 1), (0, 2)):
            code, calls, report = self.run_workflow(calibration_code=calibration, native_code=native)
            self.assertNotEqual(code, 0)
            self.assertEqual(len(calls), 4)
            self.assertFalse(report['passed'])

    def test_policy_fitting_cannot_consult_validation_labels(self):
        def row(split, expected, choice):
            return {'split': split, 'expected': expected, 'check': 'fact_01', 'findings': {
                'fact_01': {'choice': choice, 'model': 'mock', 'probabilities': {'pass': .95, 'fail': .04, 'uncertain': .01}}}}
        report = {'complete': True, 'protocol_sha256': 'abc', 'calibration_sha256': 'def',
                  'resolved_models': ['mock'], 'cases': [row('calibration', 'pass', 'pass'), row('validation', 'fail', 'pass')]}
        policy = calibrator['fit_policy'](report)
        self.assertEqual(policy['minimum_margin'], .1)
        report['cases'][1]['expected'] = 'pass'
        self.assertEqual(calibrator['fit_policy'](report)['minimum_margin'], .1)
        report['cases'][0]['expected'] = 'fail'
        self.assertGreater(calibrator['fit_policy'](report)['minimum_margin'], .9)

    def test_public_calibration_pairs_and_splits_stay_separate(self):
        entries = json.loads(jev.CALIBRATION.read_text())
        self.assertEqual(len({entry['name'] for entry in entries}), len(entries))
        self.assertTrue(all(set(entry['candidates']) == {'pass', 'fail'} for entry in entries))
        train, metadata = calibrator['prepare']('calibration')
        validation, _ = calibrator['prepare']('validation')
        self.assertTrue(train and validation)
        self.assertFalse({row['source_sha256'] for row in train} & {row['source_sha256'] for row in validation})
        self.assertEqual(metadata['protocol_sha256'], jev.protocol_digest())

    def test_missing_policy_and_model_drift_are_abstentions_not_success(self):
        rows = [{'expected': 'pass', 'check': 'fact_01', 'findings': {'fact_01': {
            'choice': 'pass', 'model': 'new-model', 'probabilities': {'pass': 1, 'fail': 0, 'uncertain': 0}}}}]
        for policy in (None, {'resolved_models': ['old-model'], 'minimum_margin': .1}):
            self.assertEqual(calibrator['metrics'](rows, policy)['review'], 1)
            self.assertEqual(calibrator['metrics'](rows, policy)['correct'], 0)

    def test_committed_policy_matches_frozen_questions_and_fixtures(self):
        policy = jev.load_policy()
        self.assertIsNotNone(policy)
        self.assertEqual(policy['protocol_sha256'], jev.protocol_digest())
