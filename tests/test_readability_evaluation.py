import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import jev_evaluation as jev
from scripts import readability_evaluation as readability


class ReadabilityEvaluationTests(unittest.TestCase):
    def test_rubric_is_separate_from_the_frozen_gate(self):
        before = jev.protocol_digest()
        rows, metadata = readability.prepare()
        self.assertEqual(len(rows), 40)
        self.assertNotEqual(metadata["protocol_sha256"], before)
        self.assertEqual(jev.protocol_digest(), before)
        self.assertFalse(metadata["replaces_frozen_gate"])
        self.assertEqual({r["split"] for r in rows}, {"calibration", "validation"})
        for row in rows:
            self.assertEqual(sum(len(q["input"]["questions"]) for q in row["requests"]), 1)

    def test_prose_and_document_structure_are_scored_separately(self):
        md = "## General feedback\n\nNo general summary was generated.\n\n## Timestamped feedback\n\n| Video time | Feedback |\n| --- | --- |\n| **00:09** | Keep the coat blue. |\n"
        body, document = readability.requests(md)
        self.assertNotIn("candidate", body["input"]["state"])
        self.assertEqual(len(body["input"]["state"]["candidate_notes"]), 1)
        self.assertEqual(set(document["input"]["questions"]), {"organization"})
        self.assertEqual(document["input"]["state"]["candidate"], md)

    def test_private_evidence_is_rejected_before_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "report.json").write_text(json.dumps({"schema_version": "cutnotes.apple.acceptance.v1",
                                                        "cases": [{"name": "Private recording"}]}))
            with patch.object(jev, "credentials") as auth, patch.object(jev, "call_jev") as remote:
                with self.assertRaisesRegex(ValueError, "public synthetic"):
                    readability.prepare(evidence_dir=root)
            auth.assert_not_called()
            remote.assert_not_called()

    def test_unknown_model_and_near_tie_remain_review(self):
        finding = {"choice": "pass", "probabilities": {"pass": .53, "fail": .46, "uncertain": .01}, "model": "fixture-model"}
        report = {"cases": [{"split": "validation", "expected": "pass", "check": "fluency", "findings": {"fluency": finding}}]}
        policy = {"minimum_margin": .1, "resolved_models": ["fixture-model"]}
        self.assertEqual(readability.assessment(report, policy)["validation"]["review"], 1)
        finding["probabilities"] = {"pass": 1., "fail": 0., "uncertain": 0.}
        finding["model"] = "unseen-model"
        self.assertEqual(readability.assessment(report, policy)["validation"]["review"], 1)

    def test_fit_does_not_consult_validation_labels(self):
        import runpy
        fit = runpy.run_path(str(readability.ROOT / "scripts/calibrate-jev.py"))["fit_policy"]
        finding = {"choice": "pass", "probabilities": {"pass": 1., "fail": 0., "uncertain": 0.}, "model": "fixture-model"}
        calibration = {"split": "calibration", "expected": "pass", "check": "fluency", "findings": {"fluency": finding}}
        validation = dict(calibration, split="validation", expected="fail")
        report = {"complete": True, "protocol_sha256": "rubric", "calibration_sha256": "fixtures",
                  "resolved_models": ["fixture-model"], "cases": [calibration, validation]}
        a = fit(report)
        report["cases"][1]["expected"] = "pass"
        b = fit(report)
        self.assertEqual(a["minimum_margin"], b["minimum_margin"])
        self.assertEqual(a["calibration_metrics"], b["calibration_metrics"])


if __name__ == "__main__":
    unittest.main()
