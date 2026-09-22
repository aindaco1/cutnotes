import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from scripts import jev_evaluation as jev


GOOD = """# Review
## General feedback
- Looks great.
- Keep the music exactly as it is.
## Timestamped feedback
No timestamp-specific notes were identified.
"""


def response_for(payload, choice="pass"):
    keys = payload["input"]["questions"]
    return {"success": True, "result": {"state": "Completed", "result": {
        "model": "mock-jev", "usage": {"input_tokens": 100, "output_tokens": 20},
        "answers": {key: {"type": "choice", "choice": choice,
                          "probabilities": {value: float(value == choice) for value in ("pass", "fail", "uncertain")}}
                    for key in keys}}}}


class JevEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence = self.root / "native"
        self.case = jev.public_cases()["Short praise and unchanged instructions survive"]
        directory = self.evidence / "case-01"
        directory.mkdir(parents=True)
        source = (self.case["transcript"] + "\n").encode()
        (directory / "transcript.txt").write_bytes(source)
        (directory / "notes.md").write_text(GOOD)
        self.native = {"schema_version": "cutnotes.apple.acceptance.v1", "cases": [{
            "name": self.case["name"], "source_sha256": jev.digest(source),
            "output_sha256": jev.digest(GOOD.encode()), "failures": [], "passed": True}]}
        self.save_native()

    def save_native(self):
        (self.evidence / "report.json").write_text(json.dumps(self.native))

    def run_mock(self, destination="judge", choice="pass"):
        with patch.object(jev, "credentials", return_value=("a" * 32, "test-token")), \
                patch.object(jev, "call_jev", side_effect=lambda payload, *_: response_for(payload, choice)):
            return jev.review(self.evidence, self.root / destination, live=True)

    def test_dry_run_cannot_authenticate_or_send(self):
        with patch.object(jev, "credentials", side_effect=AssertionError("auth")), \
                patch.object(jev, "call_jev", side_effect=AssertionError("network")):
            report = jev.review(self.evidence, self.root / "dry")
        self.assertEqual(report["network_attempts"], 0)
        self.assertFalse(report["complete"])
        self.assertFalse(report["combined_passed"])
        payload = json.loads((self.root / "dry/case-01-request.json").read_text())
        self.assertEqual(set(payload), {"model", "input"})
        self.assertEqual(set(payload["input"]), {"state", "questions"})
        self.assertEqual(set(payload["input"]["state"]), {"source", "candidate"})

    def test_private_source_rejected_even_when_renamed_as_public_case(self):
        source = b"Private real recording text\n"
        (self.evidence / "case-01/transcript.txt").write_bytes(source)
        self.native["cases"][0]["source_sha256"] = jev.digest(source)
        self.save_native()
        with patch.object(jev, "credentials", side_effect=AssertionError("auth")), \
                patch.object(jev, "call_jev", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(ValueError, "public fixture"):
                jev.review(self.evidence, self.root / "private", live=True)

    def test_changed_output_and_unknown_cases_fail_before_auth(self):
        with patch.object(jev, "credentials", side_effect=AssertionError("auth")):
            (self.evidence / "case-01/notes.md").write_text(GOOD + "tampered")
            with self.assertRaisesRegex(ValueError, "output changed"):
                jev.review(self.evidence, self.root / "changed", live=True)
            self.native["cases"][0]["name"] = "Private review"
            self.save_native()
            with self.assertRaisesRegex(ValueError, "built-in public"):
                jev.review(self.evidence, self.root / "unknown", live=True)

    def test_fail_and_uncertain_never_become_pass_or_release_acceptance(self):
        for choice in ("pass", "fail", "uncertain"):
            with self.subTest(choice=choice):
                report = self.run_mock(choice, choice)
                self.assertTrue(report["complete"])
                self.assertEqual(report["combined_passed"], choice == "pass")
                self.assertFalse(report["release_accepted"])
                self.assertEqual(report["input_tokens"], 100)
                self.assertEqual(report["resolved_models"], ["mock-jev"])
                self.assertNotIn("test-token", (self.root / choice / "report.json").read_text())

    def test_judge_cannot_override_native_failure(self):
        self.native["cases"][0]["failures"] = ["Native formatting failed: formatter_incomplete"]
        self.save_native()
        report = self.run_mock()
        self.assertTrue(report["cases"][0]["semantic_passed"])
        self.assertFalse(report["combined_passed"])

    def test_missing_output_does_not_become_a_pass(self):
        (self.evidence / "case-01/notes.md").unlink()
        with patch.object(jev, "credentials", return_value=("a" * 32, "token")), \
                patch.object(jev, "call_jev", side_effect=AssertionError("network")):
            report = jev.review(self.evidence, self.root / "empty", live=True)
        self.assertEqual(report["network_attempts"], 0)
        self.assertFalse(report["combined_passed"])

    def test_invalid_response_shapes_fail_closed(self):
        questions = jev.questions_for(["Keep the music unchanged"])
        response = response_for({"input": {"questions": questions}})
        self.assertEqual(jev.parse_response(response, questions)["model"], "mock-jev")
        mutations = []
        for state in ("Failed", "Running"):
            value = copy.deepcopy(response); value["result"]["state"] = state; mutations.append(value)
        value = copy.deepcopy(response); del value["result"]["result"]["answers"]["fact_01"]; mutations.append(value)
        value = copy.deepcopy(response); value["result"]["result"]["answers"]["fact_01"]["probabilities"]["pass"] = float("nan"); mutations.append(value)
        value = copy.deepcopy(response); value["result"]["result"]["usage"] = {}; mutations.append(value)
        mutations += [None, {"success": False}, {"result": {"state": "Completed", "result": None}}]
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError):
                jev.parse_response(value, questions)

    def test_http_failure_stops_without_retry_and_preserves_report(self):
        with patch.object(jev, "credentials", return_value=("a" * 32, "token")), \
                patch.object(jev, "call_jev", side_effect=urllib.error.HTTPError("https://example.test", 429, "rate limit", {}, None)) as request:
            with self.assertRaisesRegex(ValueError, "HTTP 429"):
                jev.review(self.evidence, self.root / "failed", live=True)
        request.assert_called_once()
        report = json.loads((self.root / "failed/report.json").read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(report["network_attempts"], 1)

    def test_spending_estimate_and_comparison_checked_before_auth(self):
        with patch.object(jev, "credentials", side_effect=AssertionError("auth")):
            with self.assertRaisesRegex(ValueError, "spending limit"):
                jev.review(self.evidence, self.root / "budget", live=True, max_estimated_usd=0.000001)
        baseline = self.run_mock("baseline")
        baseline["rubric_sha256"] = "changed"
        path = self.root / "different.json"; path.write_text(json.dumps(baseline))
        with patch.object(jev, "credentials", side_effect=AssertionError("auth")):
            with self.assertRaisesRegex(ValueError, "evaluator changed"):
                jev.review(self.evidence, self.root / "comparison", live=True, baseline=path)

    def test_comparison_reports_regression_and_new_model(self):
        before = self.run_mock("before")
        after = self.run_mock("after", "fail")
        after["resolved_models"] = ["new-model"]
        diff = jev.compare_reports(after, before)
        self.assertEqual(diff["regressed"], [self.case["name"]])
        self.assertFalse(diff["same_judge_models"])

    def test_all_public_cases_have_atomic_rubrics(self):
        rubrics = json.loads(jev.RUBRIC.read_text())
        self.assertEqual(set(rubrics), set(jev.public_cases()))
        self.assertTrue(all(isinstance(facts, list) and facts and all(isinstance(fact, str) and fact for fact in facts) for facts in rubrics.values()))

    def test_redirect_cannot_forward_authorization(self):
        self.assertIsNone(jev.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example"))
