# Apple-only formatting investigation for 1.0.5

Status: investigation, not a passing release candidate. The product direction is
Parakeet plus Apple's on-device system model, with no additional model download.
The earlier separate-model benchmark is closed. Keep the combined release held.

## What the deeper investigation established

The problem spans transcription, editorial generation and deterministic pipeline
policy. A failed final document does not identify which of these failed.

1. **Some important meaning is already damaged before Apple sees it.** On the
   supplied recording, changing the audio window recovered a missing negative
   verb phrase and clarified whether dialogue had ended. These were actual
   Parakeet re-decodes of the original audio, not manually corrected inputs.
   Other window positions still produced the incorrect wording. This is evidence
   for investigating audio boundaries, not evidence that shorter chunks always win.
2. **Apple comprehension and generation must be evaluated separately.** A small
   clean classification control correctly distinguished all five film-review and
   personal-conversation examples with either enum order and with plain text.
   The same idea on noisy source sentences discarded real observations or kept
   background material. It is not suitable as a deletion gate yet.
3. **Output constraints are not meaning constraints.** Valid `@Generable` output
   still changed meaning, invented edits and omitted qualifications. Plain text
   made different errors. A reasoning field sometimes recovered a qualification,
   but did not make the nine-note review faithful as a whole.
4. **Several implementation errors were real.** The candidate already fixes
   general-note loss, source-ID titles, time/location handling and acceptance of
   incomplete timed results. Those fixes remain necessary even with better model
   output. The MacWhisper isolation fix is independent and remains in the candidate.
5. **Historical output mixed model work and deterministic rewriting.** Version
   1.0.0 classified source IDs and rendered source text. Versions beginning with
   1.0.1 included canned rewrites keyed to particular review content. Restoring
   those examples would not solve general formatting. Previous acceptable user
   output remains a valid quality target.

## Controlled native experiments

All inference used installed local models. No transcript was submitted to a
remote inference service. Private inputs, prompts, full outputs and Swift probes
are in ignored `build/diagnostics/release-1.0.5/apple-deep-dive/`.

| Experiment | Result and implication |
| --- | --- |
| Six comprehension cases, text/structured output, default/permissive guardrails: 24 responses | Each guardrail pair produced identical wording. The clean lip-sync control worked; several noisy-source interpretations failed. A guardrail switch is not the fix. |
| Five simple relevance controls, each enum order and plain text: 15 responses | All correctly classified. These controls establish a narrow capability, not reliability on real mixed speech. |
| Four clean synthetic notes using the same minimal body-only editing prompt | Three retained their full meaning, including an uncertain reaction and an optional transition. The fourth dropped the clause about who might make an adjustment. Clean input helps; retention still needs separate protection. |
| Sentence classification with adjacent context, then without it | Context changed which observations were incorrectly removed. Do not silently filter speech using this classifier. |
| Sentence editing, transcript restoration, interpretation, reasoning-before-answer, domain context and actionable-note prompts | None passed the complete supplied review. Richer context/examples also contaminated other notes. Asking for more actionable prose introduced unsupported edits. |
| Two short whole-document prompts | Missing qualifications, misread observations and incorrect time placement remained. |
| Five overlapping 60-second Parakeet windows and five 14-second windows | Some windows recovered important wording; others lost or changed words. These were diagnostic crops, not an automatic production repair algorithm. |
| FluidAudio v3 no-mel-context and dual-decode modes | Neither improved the full recording enough. Preserve the current default until broader audio tests establish a benefit. |
| Apple editing of two recovered audio passages | The continuing-mouth observation improved; the other lip-sync note still followed a false start instead of the later correction. Better ASR helps but is not sufficient alone. |

The enum control deliberately used simple inputs. A separate Boolean probe mixed
classification-label instructions with a Boolean response type; its results are
not evidence of a framework Boolean bug. Likewise, prior OS empty-mask errors
are a separate runtime observation, not proof of the cause of every semantic error.

The Parakeet dependency already exposes token confidence and word/audio timing;
CutNotesLocal currently retains only the text, duration and aggregate confidence.
One troublesome inserted word had low token confidence in the diagnostic decode.
Confidence can prioritize investigation, but is not calibrated proof that a word
is wrong and must never itself delete a negation or other source content.

## Public Apple API choices

Use `SystemLanguageModel` through `LanguageModelSession`. Both are available on
macOS 26, run the system model locally, and require no app-supplied language-model
weights. Keep the existing provider boundary and explicit selection behavior.

Apple recommends small tasks, simple schemas and splitting work when a single
request is unreliable. Its documented reasoning-field technique was included
in the native probes; it was not sufficient here. See
[Prompting an on-device foundation model](https://developer.apple.com/documentation/foundationmodels/prompting-an-on-device-foundation-model).

`@Generable` and `DynamicGenerationSchema` constrain the shape and allowed values
of responses. They can restrict evidence IDs to actual source IDs, but cannot
guarantee correct evidence selection or paraphrasing. See
[Guided generation](https://developer.apple.com/documentation/foundationmodels/generating-swift-data-structures-with-guided-generation).

The permissive transformation mode affects string-response safety handling;
guided generation still uses the default guardrail behavior. It is not a better
editorial model. See
[Permissive content transformations](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel/guardrails/permissivecontenttransformations).

`contentTagging` specializes in topics, actions, objects and emotions. It is not
a documented relevance or factuality judge. Do not make it responsible for
discarding review observations. See
[Content tags](https://developer.apple.com/documentation/foundationmodels/categorizing-and-organizing-data-with-content-tags).

Apple's model changes with OS releases; prompt profiles may need versioning.
The installed SDK exposes model-variant information, but the inspected public
system-model initializer does not let the app select an older OS model or force
the Core Advanced variant. See
[Model-version guidance](https://developer.apple.com/documentation/foundationmodels/updating-prompts-for-new-model-versions).

Writing Tools is a text-view integration, not an established replacement for
this app's headless CLI and guaranteed-local processing contract. Do not automate
its UI as the formatter. The adapter toolkit's last version targets the 26-era
model and does not provide a supported macOS 27 solution. Core AI/MLX models and
Private Cloud Compute do not meet the revised product requirement. See
[Writing Tools coordinator](https://developer.apple.com/documentation/appkit/nswritingtoolscoordinator)
and [Adapter toolkit](https://developer.apple.com/apple-intelligence/foundation-models-adapter/).

## Recommended next prototype

The existing passage grouping and Markdown renderer should stay. The change to
evaluate is **source-backed statements with retained qualifications**, rather
than another prompt asking Apple to author an entire note from scratch.

1. **Preserve useful transcription evidence.** Add optional, versioned native
   word/token timing and confidence data with decoding tests. Preserve the raw
   transcript. Benchmark bounded re-decoding around uncertain speech against
   unchanged audio. Compare candidates by aligned source evidence; do not add a
   second ASR implementation, globally shorten all chunks, or silently replace
   ambiguous words. A transcript-only request must not require audio.
2. **Extract before editing.** For each existing passage, represent observations,
   requested changes, reasons and qualifications as source-backed statements.
   Every source sentence must have an explicit disposition. Validate IDs and
   quoted spans against the source. Prototype this independently of prose quality;
   exact quotation proves provenance, not correct relevance or complete coverage.
3. **Protect qualifications from summarization.** Keep optionality, uncertainty,
   ownership, negation and relative-location evidence attached to their statement.
   Have Apple perform a narrowly scoped wording edit. The core assembles the note
   from the retained statements, so a later summary cannot silently discard a
   caveat. Prefer plainer faithful prose to a more elegant changed meaning.
4. **Validate with one bounded repair attempt.** Check source coverage and
   attachment, exact time/location provenance, and missing protected statements.
   Retry only a failed passage with the specific missing source evidence. The
   same Apple model judging its own work is not an independent factuality gate.
   Unresolved ambiguity must remain visible and cannot count as a release pass.

Steps 2–4 are a proposed prototype, not a tested solution. First prove extraction
and retention on synthetic cases; do not integrate another pipeline merely because
its schema looks safer. If this structure fails the same content checks, reject it.

All orchestration, source allocation, recovery and formatting policy belong in
`cutnotes_core`. Swift should expose only the native inference/transcription
operations and versioned payloads. Reuse the existing provider bridge, renderer,
error handling and acceptance evaluator. Keep a single Apple formatter; no user
model picker, agent framework, new download or silent provider fallback.

## Acceptance and compatibility

The supplied review must retain all nine distinct notes: two general observations
and seven timed/relative observations, including two different issues around the
same moment. Preserve the constraints and reasons on the correct note. No invented
editing techniques, changed direction, background conversation or placeholder prose.
Exact agreement with the Codex-written reference is unnecessary.

Compare the original transcript, separately re-decoded audio, and clean synthetic
counterparts as different lanes. A pass with a manually corrected transcript is
not an end-to-end pass. Run the 12 development fixtures and eight held-out fixtures;
repeat native runs and inspect the actual prose as well as machine checks. Keep
holdout wording out of prompt examples. Apple also recommends systematic evaluation:
[Evaluating prompts](https://developer.apple.com/documentation/foundationmodels/evaluating-prompts-to-measure-performance-and-improve-model-responses).

Use macOS 26 APIs for the implementation. Add an OS-specific prompt only if measured
results justify it, with prompt policy remaining in the core. Both CI build/contract
lanes passed at `7b037c8`; this machine is macOS 27.0 (26A428). No macOS 26 device is
available, so macOS 26 native output quality remains unverified. Do not describe a
successful compatibility build as a native model-quality pass.

Once native content passes, run the existing signing, notarization, stapling,
DMG install/launch and Sparkle validation gates, deploy the combined release, then
complete recoverable cleanup. Until then, retain the installed public release,
source, active branch, development runtime and relevant diagnostic evidence.
