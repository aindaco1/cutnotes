import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from scripts.local_verifier import LocalVerifier, ROOT, load_cases, summarize


class LocalVerifierTests(unittest.TestCase):
    def test_support_corpus_has_separate_balanced_splits(self):
        rows = load_cases(ROOT / "tests/fixtures/editorial-support.json")
        self.assertEqual(len(rows), 80)
        for split in ("development", "validation"):
            cases = [row for row in rows if row["split"] == split]
            self.assertEqual(len(cases), 40)
            self.assertEqual(sum(row["supported"] for row in cases), 20)
        # Supported omissions must not be mislabeled as contradictions.
        self.assertTrue(any(row["supported"] and row["category"] == "support-not-coverage" for row in rows))

    def test_duplicate_or_string_labels_are_rejected(self):
        row = dict(id="pair", source="Keep it.", claim="Keep it.", split="development", category="request", supported=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for rows in ([row, row], [dict(row, supported="false")]):
                path.write_text(json.dumps(rows))
                with self.assertRaises(ValueError):
                    load_cases(path)

    def test_long_evidence_is_not_silently_truncated(self):
        verifier = object.__new__(LocalVerifier)
        class Tokenizer:
            eos_token = "</s>"
            def __call__(self, *args, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(input_ids=SimpleNamespace(shape=(1, 2049)))
        verifier.tokenizer = Tokenizer()
        with self.assertRaisesRegex(ValueError, "no truncation"):
            verifier.score("source", "claim")
        self.assertFalse(verifier.tokenizer.kwargs["truncation"])

    def test_false_support_is_reported_separately(self):
        rows = [dict(split="validation", supported=False, prediction=True),
                dict(split="validation", supported=True, prediction=False)]
        result = summarize(rows)["validation"]
        self.assertEqual(result["false_support"], 1)
        self.assertEqual(result["false_rejection"], 1)


if __name__ == "__main__":
    unittest.main()
