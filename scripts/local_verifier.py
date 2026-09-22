#!/usr/bin/env python3
"""Optional, offline MiniCheck development benchmark. Never used by the app.

Acquire weights separately as documented; this program cannot fetch a model.
Support scores do not measure completeness, relevance, or release readiness.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
MODEL = "lytang/MiniCheck-Flan-T5-Large"
REVISION = "96eafd01cee2d16cf81aaa2fb226b14f422a37b3"
WEIGHTS_SHA256 = "41291881e13c6235ed47149cec903bee9493e45d9d7325587a9fa2e266c526c0"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_cases(path):
    rows = json.loads(path.read_text())
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty list of local support cases")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip()
                for k in ("id", "source", "claim", "split", "category")) or
                type(row.get("supported")) is not bool or row["id"] in seen):
            raise ValueError("Malformed or duplicate support case")
        seen.add(row["id"])
    return rows


def summarize(rows):
    result = {}
    for row in rows:
        counts = result.setdefault(row["split"], Counter())
        counts["count"] += 1
        correct = row["prediction"] == row["supported"]
        counts["correct" if correct else "false_support" if row["prediction"] else "false_rejection"] += 1
    return result


class LocalVerifier:
    def __init__(self, model_dir, device):
        # Enforce offline loading before importing either library. Never load
        # custom model code or unrestricted pickle contents from the model repo.
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        import torch
        import transformers
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.torch, self.device = torch, device
        self.versions = {"torch": torch.__version__, "transformers": transformers.__version__}
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=False, weights_only=True).to(device).eval()

    def score(self, source, claim):
        # Flan-T5 protocol and class-token positions from the author inference
        # implementation. Reject long inputs instead of silently losing evidence.
        text = "predict: " + source + self.tokenizer.eos_token + claim
        inputs = self.tokenizer(text, return_tensors="pt", truncation=False)
        if inputs.input_ids.shape[1] > 2048:
            raise ValueError("Support input exceeds 2048 tokens; no truncation permitted")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        decoder = self.torch.zeros((1, 1), dtype=self.torch.long, device=self.device)
        with self.torch.inference_mode():
            logits = self.model(**inputs, decoder_input_ids=decoder).logits[:, 0, [3, 209]]
            score = self.torch.softmax(logits, dim=-1)[0, 1].item()
        return float(score)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True, help="Already downloaded local weights; no automatic download")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/editorial-support.json")
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.fixtures)
    model_dir = args.model_dir.resolve(strict=True)
    weights = model_dir / "pytorch_model.bin"
    weights_hash = digest(weights)
    if weights_hash != WEIGHTS_SHA256:
        raise ValueError("Weights do not match the pinned MiniCheck revision")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"development_only": True, "offline": True, "release_accepted": False,
              "expected_model": MODEL, "expected_upstream_revision": REVISION,
              "weights_sha256": weights_hash, "fixtures_sha256": digest(args.fixtures),
              "runner_sha256": digest(Path(__file__)), "device": args.device,
              "decision_threshold": 0.5, "calibrated_for_editorial_instructions": False,
              "cases": [], "complete": False}
    start = time.monotonic()
    try:
        verifier = LocalVerifier(model_dir, args.device)
        report["runtime"] = verifier.versions
        for case in cases:
            score = verifier.score(case["source"], case["claim"])
            row = dict(case, support_probability=score, prediction=score > 0.5)
            report["cases"].append(row)
            print(f"{case['id']}: {score:.4f}", flush=True)
        report["complete"] = True
        report["assessment"] = summarize(report["cases"])
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - start, 3)
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["assessment"], indent=2))
    return 0  # Completing a diagnostic benchmark never establishes acceptance.


if __name__ == "__main__":
    raise SystemExit(main())
