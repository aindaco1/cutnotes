# Testing

Run the standard development suite:

```bash
python3 scripts/test.py
./script/build_and_run.sh --verify
```

The suite runs Python and Swift tests, Jev calibration, builds the current native
helper, and runs Apple formatting followed by Jev review. Results get a new
`build/diagnostics/development-*` directory. `--engine /path/to/CutNotesLocal`
uses a specific helper; `--output-dir` chooses a new evidence directory.
A completed quality failure does not prevent collecting the later native result,
but the suite fails overall. Authentication/API errors stop remote evaluation.

For fast contract tests without live inference, use `python3 scripts/test.py
--offline`, or invoke `python3 -m unittest discover -s tests -v` and
`swift test --package-path macos` directly. The offline report explicitly lists
omitted quality gates. Hosted CI uses this subset and separately builds the app;
it has no ready Apple model or configured Jev credential. This is not a full
content-quality pass.

After an OS upgrade, Apple Intelligence can report `modelNotReady` while its
models prepare. A failed Apple formatting request must report
`apple_model_unavailable`, explain how to retry when the model is ready, and
preserve the original transcript. A recording or import that already produced
audio and a transcript must report both as preserved. Test successful formatting
separately once the system model is ready; a graceful unavailable result does
not prove model inference.

Release acceptance is deliberately split into separate claims:

1. Python unit/integration tests pass.
2. Swift command/contract tests pass.
3. The app bundle builds arm64 with the pinned runtime and no non-system absolute load paths.
4. A generated speech fixture transcribes through the bundled CLI and installed Parakeet model.
5. Apple formatting succeeds when the system model reports ready.
6. Optional MacWhisper and Codex selections either work or return provider-specific errors without fallback.
7. Developer ID signatures verify under strict/deep validation.
8. Apple separately accepts the app and DMG notarization submissions, and both tickets staple and validate.
9. A clean mounted DMG can be copied to `/Applications`, launched, and used to install the terminal command.
10. The appcast signature verifies and a previously released app can discover, download, and install the new release.

The recording gate includes pause/resume with more than one pause, finish while paused, cancel while paused, and verification that the joined WAV contains no paused interval. The formatting gate includes a transcript large enough to require multiple Apple Foundation Models requests; no individual request may consume the full model context window.

Formatting fixtures must cover colon, compact-digit, explicit minute/second, and spoken shorthand timecodes; out-of-order source mentions; adjacent ranges; orphaned markers; false starts; background lyrics; and guardrail rejection. Acceptance requires a concise general summary, chronological notes with distinct issues at the same moment kept separate, no source IDs in reader-facing prose, no cross-time merging, no reversed negation, and exact preservation of the source transcript.

For 1.0.0 there is no earlier Sparkle-enabled public version, so the real previous-version update hop becomes a mandatory 1.0.1 release gate. Feed generation and archive signatures are still required for 1.0.0.

## Formatting and optional-provider regressions

The 1.0.5 tests cover mouth and facial-animation observations without keyword gating; generated source IDs used as titles; malformed and unknown grounding IDs; adjacent spoken ranges; conversational second markers; natural general-note transitions; opening conversation followed by actual feedback; bounded long single edit moments; and context-limit retries. Both full and detected partial formatting failure must preserve the source and prior output and return an error. A separate missing passage at a timestamp already covered by another note must also fail, without disclosing source text in errors.

Regression coverage also preserves faithful paraphrases with low lexical overlap.
Native fixture checks accept equivalent wording such as “image” for “picture”
and “possibly” for “might,” while still rejecting changed direction, certainty or
attachment. Review the actual prose; a regex pass alone is not a quality verdict.

Transcription evidence tests cover low-confidence negations, offsets across audio
chunks, source binding, malformed/stale metadata, compatibility with older helpers,
and preservation after optional writes fail. Python owns validation and retention;
Swift tests the versioned native payload. Real Parakeet inference must also verify
the companion against unchanged source audio and the exact saved transcript.

Apple request tests assert that session instructions exclude untrusted source/context
and that temporary request files are removed afterward. The prompt file retains
the complete task for older draft-v1 helpers; new helpers remove only the exact
duplicate instruction prefix before sending source data to the model. Swift tests
cover both request forms. Run native inference separately: mocked contract tests
do not establish model output quality. Inspect the final summary and every
timestamped body for instruction echoes, unsupported meaning changes, raw
transcript dumps, omitted edits, and incorrectly attached general feedback.

Provider-isolation tests prohibit executing MacWhisper during setup and the Parakeet workflow, and verify that explicit MacWhisper selection invokes only its CLI transcription command. A detected CLI with null version and an empty model list must continue to decode in Swift.

The reference handoff test covers two general notes, adjacent lip-sync timestamps, a qualified reaction observation, separate face/impact notes at the same time, a retrospective approximate marker, and an optional relative end note. Native sample acceptance is required in addition to this mocked controller test.

Run the real Apple acceptance suite on Apple Silicon with a ready model:

```bash
python3 scripts/check-apple-formatting.py \
  --engine macos/.build/release/CutNotesLocal \
  --output-dir build/diagnostics/apple-acceptance-new-run
```

Use a new output directory for each run. The command returns failure when the model
is unavailable or any content check fails; it never substitutes another provider.
The local report records OS/helper versions, fixture/checker hashes, source hashes,
and individual failures. On macOS 27, `engine_status.apple.model` also identifies
the actual on-device variant, context size and capabilities. Compare those values
between runs: the OS version alone does not identify the available model. Helpers
on macOS 26 omit this optional metadata; both contract forms are regression-tested.
Synthetic fixtures cover meaning at the correct moment,
opposite timing directions, negative instructions, qualifications, optional end
feedback, praise, and unrelated conversation. Their checks accept paraphrases;
also read the generated notes, since pattern checks cannot prove semantic fidelity.
Private transcripts require a separate local fixture file with `--fixtures` and
`--skip-jev`; do not commit private input or output. The portable Apple model test
kit explicitly uses `--skip-jev` so another Mac needs no cloud credentials. Its
saved public outputs can be evaluated with Jev back in the development checkout.

## Default Jev development evaluation

Jev is part of standard development testing. It is not a CutNotes formatter
provider, is not bundled with the app, and is never invoked by user recording,
transcription or formatting. Individual unit tests use mocks and make no calls.
Cloudflare routes the synthetic test requests to TypeSafe's hosted Jev model.

Configure `CLOUDFLARE_ACCOUNT_ID` in your environment, or save only its account
ID in the ignored local `.cutnotes-development.json`:

```json
{"cloudflare_account_id": "YOUR_CLOUDFLARE_ACCOUNT_ID"}
```

Authentication uses `CLOUDFLARE_API_TOKEN` when set, otherwise an existing Wrangler
login. `--wrangler-auth` forces that login. Wrangler 4.136.2 uses its existing npx
cache; no Worker or Node app dependency is needed. Never put tokens in command
arguments, config files, committed files or diagnostic output. Missing credentials
are an error, never a silent skip. This workstation's existing account is configured.

Evaluate saved public native output (live by default):

```bash
python3 scripts/jev_evaluation.py \
  --evidence-dir build/diagnostics/apple-acceptance-new-run \
  --output-dir build/diagnostics/apple-jev-results
```

Add `--dry-run` for a local request preview without authentication or network.
The native Apple checker also runs Jev by default, preserving the local report
and writing `jev/report.json` and `jev/review.md`. `--skip-jev` explicitly opts
out. The historical `--live` / `--jev-live` flags remain accepted for scripts.

Before authentication, the evaluator checks every transcript against the exact
built-in public fixture and native source hash, and checks saved output hashes
when available. Private/custom fixtures are rejected. Only public synthetic
content and questions are transmitted; paths, native metadata and the private
reference recording are excluded. Prior evidence is never overwritten.

`apple-formatting-semantics.json` binds each fact to a general, timed or document
scope. Coverage requests receive only the matching candidate notes; they cannot
credit information found only in the source. Exclusion questions separately check
for absence, so correctly removed conversation is not counted as missing feedback. Qualifiers must belong to the correct
observation. Separate document checks assess grounding, relevance, duplication
and readability. Duplication respects timestamps and distinct issues. Both exact
and semantic checks reuse the same Markdown parser.

### Calibration and comparison

`jev-calibration.json` has thirteen labeled pairs for calibration and eight pairs with
different sources for validation: faithful concise versions and single-defect
versions. They cover qualifications, purpose, ownership, optionality, polarity,
timing, background speech, explicit exclusion checks, duplication, grounding and attachment. Labels are
source-based engineering judgments, not independent human ratings.

The standard suite checks all 42 examples against the frozen policy. It reports
false passes, false failures and review counts, including per-category results.
Once repeatedly inspected, these examples are regression tests rather than an
unseen final holdout. Add a fresh validation set when tuning questions again.

```bash
python3 scripts/calibrate-jev.py --output-dir build/diagnostics/jev-calibration
```

The initial policy uses a 0.10 minimum probability margin, selected from a
predeclared grid using only calibration labels, then checked on the separate
validation split. A near tie or unseen Jev model becomes `review`, never pass.
This small set does not prove probabilities are calibrated for every transcript.
`--split calibration --propose-policy` writes a candidate policy without installing
it. Review that candidate, then use `--split validation` before adopting it.
Prompt/parser or calibration-fixture changes invalidate the committed policy.

Freeze questions, policy and fixtures before comparing Apple changes. Add
`--compare path/to/previous/jev/report.json` to compare two complete v2 runs with
matching evaluator hashes; reports also expose model-version differences.
Re-evaluating identical saved notes measures judge changes, not formatter gains.
Repeat native runs for stability and measure Apple latency separately from Jev.

Reports preserve requests, raw probabilities, resolved model, evidence/code hashes,
usage and timing. `review.md` pairs flagged requirements with the actual scoped
candidate text; it does not invent explanations from Jev. Failed or review answers
prevent a combined pass. Jev cannot override native or deterministic failures.
Missing output, malformed answers, API failure and partial runs cannot pass.

There are no automatic retries, provider fallbacks, purchases or credit top-ups.
Each evaluation reserves a conservative 32k input context per question at the
2026-09-22 input estimate of $0.042/million tokens. The default estimate limit is
$0.25 per evaluation, with a hard client maximum of $1. This is not a provider
billing cap. The standard suite runs calibration and native evaluation as separate
batches. Exit status is 0 for success (or explicit dry run), 1 for completed checks
needing review, and 2 for evaluator errors.

The native development corpus has 12 cases, plus eight historical cases in
`apple-formatting-holdout.json`. Those eight have already been inspected and are
regressions, not a fresh holdout. A combined pass never replaces native review of
the supplied recording or other release gates; reports retain `release_accepted:
false`.

Run this native gate on macOS 26 and macOS 27 wherever a ready model is available.
The user currently has no macOS 26 Mac available: record that native quality on
26 is unverified while CI checks build and contract compatibility on both lanes.
A hosted runner without a ready model does not establish native output quality.
The release hold requires successful native content acceptance on the available
macOS 27 host; do not equate passing cross-version builds with that acceptance.
Keep the macOS 15 app deployment target, the macOS 26 Foundation Models availability
checks, and the existing `cutnotes.local.draft.v1` contract. Do not introduce a
macOS 27-only formatter path without an independently tested macOS 26 path.
