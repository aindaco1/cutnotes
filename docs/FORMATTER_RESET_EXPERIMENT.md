# Source-preserving formatter experiment

This development experiment has **not passed acceptance** and is not connected
to the app or CLI formatter. The installed release and normal provider selection
remain unchanged. Publication still requires review of actual generated output.

## Design and findings

`cutnotes_core/formatter_candidate.py` retains source statements, recognizes
additional spoken cut-time cues, and uses the existing Markdown renderer. Apple
answers small grouping questions and optionally copyedits each passage. A narrow
content-word comparison rejects some added or missing claims and records the
rejected proposal alongside its source. This is not a semantic validator: word
sets cannot prove that subjects, polarity, conditions, or meaning survived.
Rejected edits retain source wording and explicitly require review.

The native transport in `scripts/experiments/AppleFormatterProbe.swift` uses
Foundation Models guided generation with fresh sessions and greedy sampling.
Python owns prompts and policy. The helper compiles for macOS 26 with the current
SDK; model quality has only been exercised on this macOS 27 machine using AFM 3
Core. This provides no Core Advanced or native macOS 26 quality claim.

Whole-document extraction, structured topic plans, sentence classification,
copyediting, and a local model critic were compared during exploration. The model
still sometimes changed a desired state, lost qualifications, invented context,
or approved a bad rewrite. Narrower tasks reduced the damage but did not establish
reliable editorial synthesis.

On September 22, 2026, the protected-copyedit experiment passed 12 of 16 fixed
public deterministic cases and 6 of 16 combined Jev cases (Jev 1.13.0). The existing
candidate's last combined result was 10 of 16. This experiment therefore does
not justify replacing that candidate. Four public cases retain background or
irrelevant text; six more receive failed or borderline readability results.
Questions, calibration policy, and thresholds were not weakened. Each run saves
its implementation snapshot; later timing and quote-boundary fixes are covered by
unit tests but are not a new complete native/Jev benchmark.

The private representative recording retains all seven source-derived checked
facts after reviewer-confirmed transcription clarifications. Four of six Apple
copyedits exceeded the word-preservation contract and were rejected. The resulting
draft is still repetitive and rough. A separate editor-written reference in the
local review is a target, not evidence of model performance. No private audio or
transcript is sent to Jev.

## Very quiet speech

`cutnotes_core/speech_levels.py` implements a local review proposal consistent
with treating substantially quieter speech as background. It uses exact Parakeet
word alignment and validates the source audio and transcript hashes. Audio is
measured in a mono PCM16 copy without normalization or gain changes.

Utterances are separated at pauses of at least 0.8 seconds. A passage with at
least two words and 0.5 seconds of speech is a candidate when its 80th-percentile
word RMS (nearest-rank percentile) is at least 18 dB below the recording's 75th-percentile word RMS. Several
utterances and at least 12 words are required before proposing exclusions. These
are initial experimental thresholds, not a calibrated speaker classifier.

On the representative recording, exactly the user-confirmed background phrase was
flagged, 21.55 dB below the reference. Every other recognized word was retained.
Tests cover a uniformly quiet speaker, ordinary volume variation, isolated soft
words within louder speech, insufficient context, and stale or malformed evidence.
Volume cannot resolve background speech at the same level as the main speaker,
and deliberately whispered notes can still be ambiguous. Original audio and the
unedited transcript are preserved; the proposed foreground transcript is separate.

## Reproduce

Use new output directories for every run. These tools require a ready on-device
Apple model for inference; the volume analyzer only requires FFmpeg and existing
Parakeet evidence.

```bash
mkdir -p build/experiments
xcrun swiftc -parse-as-library -target arm64-apple-macos26.0 \
  scripts/experiments/AppleFormatterProbe.swift \
  -o build/experiments/AppleFormatterProbe

# Public synthetic corpus; live Jev evaluation is on by default.
python3 scripts/experiment-apple-formatter.py \
  --engine build/experiments/AppleFormatterProbe \
  --rewrite --output-dir build/diagnostics/formatter-experiment-public

# Private inputs are always excluded from Jev, even without --skip-jev.
python3 scripts/experiment-apple-formatter.py \
  --engine build/experiments/AppleFormatterProbe \
  --transcript /absolute/path/to/transcript.txt \
  --rewrite --output-dir build/diagnostics/formatter-experiment-private

python3 scripts/analyze-speech-levels.py \
  --audio /absolute/path/to/source.wav \
  --transcript /absolute/path/to/transcript.txt \
  --evidence /absolute/path/to/transcript.evidence.json \
  --output-dir build/diagnostics/speech-level-review
```

The private runner's successful exit means the experiment completed its structural
checks, not acceptance. Its report always requires human review and records
`passed: false` for private input. The public path retains the independent fixed
checker and the Jev allowlist. Private artifacts belong in ignored diagnostics,
never in fixtures or a public pull request.

Twenty new formatter, privacy, and volume-analysis tests pass in the 137-test
Python suite. The existing 21 Swift tests also passed; these are separate from
native content acceptance. Next promotion requires concise, faithful generated
prose, stronger mixed-speaker audio validation, a full frozen public comparison,
and manual review of the representative output. Do not promote the word check
as a factuality gate or substitute the editor-written reference for model output.
