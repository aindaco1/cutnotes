import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
experiment = runpy.run_path(str(ROOT / "scripts/experiment-apple-formatter.py"))


class FormatterExperimentTests(unittest.TestCase):
    def test_private_input_never_reaches_jev_and_is_never_marked_accepted(self):
        class LocalOnlyQuestions:
            def __init__(self, *args): pass
            def ask(self, *args): return False
            def close(self): pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine, source, output = root / "probe", root / "private.txt", root / "review"
            engine.write_text("probe fixture")
            source.write_text("At eight seconds, keep the door closed.\n")
            original = source.read_bytes()
            with patch("sys.argv", ["experiment", "--engine", str(engine), "--transcript", str(source),
                                    "--output-dir", str(output), "--jev-wrangler-auth"]), \
                    patch.dict(experiment["main"].__globals__, NativeQuestions=LocalOnlyQuestions), \
                    patch("scripts.jev_evaluation.review") as remote:
                self.assertEqual(experiment["main"](), 0)
            remote.assert_not_called()
            self.assertEqual(source.read_bytes(), original)
            report = json.loads((output / "report.json").read_text())
            self.assertFalse(report["passed"])
            self.assertTrue(report["requires_human_review"])
            self.assertTrue(report["source_unchanged"])
            self.assertEqual(report["cases"][0]["checks_scope"], "structure_and_source_times_only")


if __name__ == "__main__":
    unittest.main()
