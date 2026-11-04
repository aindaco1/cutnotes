"""Local Gemma notes with source-owned timing and a validated output contract."""
from __future__ import annotations

from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import tempfile

from .contracts import CutNotesError, EXIT_FORMATTING, PreservedArtifacts
from .experimental_budget import budget_processor, checked_budget_answer, text_only_bias
from .gemma_model import MANIFEST, require_ready
from .grounded_notes import build_evidence, projected_time_markers, render_marked_markdown
from .source_decisions import BODY_INSTRUCTIONS, parse_body_contract

RECIPE_VERSION = "gemma-grounded-1.1"


def messages_for(source, context=None):
    evidence = build_evidence(source)
    messages = [{"role": "system", "content": BODY_INSTRUCTIONS}]
    examples = json.loads((Path(__file__).parent / "data/gemma-demonstrations.json").read_text())
    for example in examples:
        example_evidence = build_evidence(example["source"])
        answer = json.dumps(example["target"], ensure_ascii=False)
        parse_body_contract(answer, example_evidence)
        messages.extend([{"role": "user", "content": projected_time_markers(example["source"], example_evidence)},
                         {"role": "assistant", "content": answer}])
    payload = projected_time_markers(source, evidence)
    if context:
        payload += "\n\nUser-supplied names and context (use only to clarify the source):\n" + context
    messages.append({"role": "user", "content": payload})
    return messages, evidence


def write_new(path, text):
    """Atomically publish a complete result without replacing any existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.link(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def format_with_gemma(*, transcript_path, output_path, title, context, reporter):
    preserved = PreservedArtifacts(transcript=True)
    if output_path.exists() or output_path.is_symlink():
        raise CutNotesError("The output already exists. Choose a new filename.", EXIT_FORMATTING,
                            code="output_exists", recovery="Choose a new output path; existing notes were preserved.", preserved=preserved)
    source = transcript_path.read_text(encoding="utf-8")
    if not source.strip():
        raise CutNotesError("The transcript is empty.", EXIT_FORMATTING, code="transcript_empty", preserved=preserved)
    reporter.stage("model_verification", "Verifying Gemma before formatting")
    # Local directories only. No remote models, code, telemetry, or inference requests.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        model_dir = require_ready()
        messages, evidence = messages_for(source, context)
        # Third-party informational output must never contaminate final JSON stdout.
        with redirect_stdout(sys.stderr):
            import mlx.core as mx
            from mlx_lm import load, stream_generate
            from mlx_lm.sample_utils import make_logits_processors, make_sampler
            reporter.stage("formatting", "Loading Gemma on this Mac")
            model, tokenizer = load(str(model_dir), trust_remote_code=False)
            prompt = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=True)
            if len(prompt) > 60000:
                raise ValueError("The transcript exceeds the local formatting context limit. Split it into shorter transcripts.")
            max_tokens = max(6144, min(24000, 4096 + len(prompt)))
            # One bounded retry handles a malformed body contract; no provider fallback.
            for attempt in range(2):
                mx.random.seed(42 + attempt)
                processor, _ = budget_processor(tokenizer, len(prompt), 4096, answer_prefix="{")
                processors = make_logits_processors(logit_bias=text_only_bias(tokenizer, True)) + [processor]
                pieces, last = [], None
                reporter.stage("formatting", "Reading feedback and preserving qualifications" if attempt == 0 else "Checking the notes again")
                for n, response in enumerate(stream_generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens,
                        sampler=make_sampler(temp=1.0, top_p=0.95, top_k=64), logits_processors=processors), 1):
                    pieces.append(response.text)
                    last = response
                    if n % 64 == 0:
                        reporter.progress("formatting", min(0.95, n / max_tokens), "Writing source-grounded notes")
                try:
                    if last is None or last.finish_reason != "stop":
                        raise ValueError("The model did not finish within its output budget.")
                    body = parse_body_contract(checked_budget_answer("".join(pieces), expected_prefix="{"), evidence)
                    markdown = render_marked_markdown(title, body, evidence)
                    break
                except ValueError:
                    if attempt:
                        raise
            write_new(output_path, markdown)
            reporter.progress("formatting", 1, "Notes saved")
    except CutNotesError as error:
        error.preserved = preserved
        raise
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        raise CutNotesError("Gemma could not produce validated notes: " + str(error)[:500], EXIT_FORMATTING,
            code="gemma_formatting_failed", recovery="The transcript is preserved. Try formatting it again or split a long transcript.",
            preserved=preserved) from error
