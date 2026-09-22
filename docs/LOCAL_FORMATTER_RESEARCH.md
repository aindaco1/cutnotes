**Local formatter research — September 22, 2026**

Recommendation: retain Parakeet and Apple's on-device model for the user workflow.
Improve how source meaning is represented, which edits are permitted, and how
quality is measured. Keep Jev as a public-fixture development evaluator. An
independent local verifier is a useful optional development experiment, not a new
user dependency. These recommendations are research hypotheses; this work has not
produced a new passing formatter or changed the release decision.

**What the saved evidence actually establishes**

The protected-copyedit experiment passed 12/16 deterministic public cases and
6/16 combined Jev cases. Four failures involve retained unrelated speech. Among
the other twelve cases, five readability decisions were borderline and one failed.
This is not equivalent to ten confirmed semantic failures. The saved private run
also contains genuine inventions and meaning changes, alongside useful rewrites
that our own word check rejected. See [the experiment record](FORMATTER_RESET_EXPERIMENT.md).

I independently exercised the current `copyedit_issues` function with four
synthetic pairs, without model inference or network requests:

| Source → proposed edit | Current check | Assessment |
| --- | --- | --- |
| “The door is open. Do not close it.” → “The door is not open. Do close it.” | No issues | Misses reversed meaning because the same content words remain. |
| “Keep the lamp dark and the wall bright.” → “Keep the lamp bright and the wall dark.” | No issues | Misses properties assigned to the wrong subjects. |
| “Her eyes are closed. Her eye is closed.” → “Her eyes are closed.” | Rejects missing `eye` | Rejects useful deduplication in this example. |
| “The picture is too dark.” → “The image is too dark.” | Rejects `picture`/`image` substitution | Rejects an ordinary faithful paraphrase. |

Thus the current check is simultaneously too permissive about relationships and
too restrictive about wording. Adding more synonyms to a whitelist would not fix
negation scope, speaker intent, or subject–property attachment.

**1. Preserve meaning before improving prose**

The next useful experiment is a small evidence record per editorial passage:
the observation, any explicitly requested change, and any uncertainty or condition.
Each entry must identify its source span. An observation may have no requested
change; a compliment must not become a task. The following is an illustrative
target, not a new model result:

| Source | Information the formatter must retain |
| --- | --- |
| “The lamp is off. It would be nice if it were on.” | Observed state: off. Desired state: on. Suggestion, not mandatory work. |
| “The lamp is off. It looks odd.” | Observed state and reaction. No explicit instruction to switch it on. |
| “Maybe two clips were joined; it sounds wrong.” | Audio problem is asserted; the proposed cause is uncertain. |

Use exact source quotes/IDs before the edited text in guided generation. Validate
that quotes occur in the source and IDs exist. Require every substantive source
clause to be accounted for, including exclusions or unresolved clauses. This
checks provenance and coverage; it does not prove that a model assigned the right
meaning. Test extraction separately before trusting it to authorize rewriting.

Apple documents that guided generation constrains output structure and generates
properties in declaration order. That makes evidence-first ordering possible;
it does not guarantee factual correctness. Keep the schema small because earlier
large plans and enum classifications failed in this project. [Apple guided generation](https://developer.apple.com/documentation/foundationmodels/generating-swift-data-structures-with-guided-generation).

Then compare a narrow edit proposal against the existing free rewrite. Permit
punctuation, filler removal, duplicate removal, and limited clause repair. Preserve
names, dialogue quotations, cut times, negation, action direction, degree, and
conditions. A source observation cannot acquire an imperative unless the source
also supports that request. Treat ambiguous repairs as review items.

This is an application of editing-based generation, not a claim that Apple's
model becomes LaserTagger. The research supports studying explicit edits instead
of unrestricted generation; it does not establish performance for CutNotes.
[Encode, Tag, Realize](https://aclanthology.org/D19-1510/).

Compare concise instructions with a few short, contrasting synthetic examples:
observation versus request, keep versus remove, and possible versus certain.
Use different subjects from evaluation examples. Apple recommends simple tasks
and short examples, and warns that long examples can contaminate output. Earlier
few-shot and reasoning experiments here already failed; the new variable is the
evidence/edit contract, not merely another longer prompt.
[Apple prompting guidance](https://developer.apple.com/documentation/foundationmodels/prompting-an-on-device-foundation-model).

**2. Replace the word gate with several limited checks**

Use separate checks for source support and required-fact coverage. A perfectly
supported sentence can still omit the requested change. Conversely, retaining
every source keyword does not prevent assigning the instruction to the wrong
person or moment.

Keep deterministic validation for source IDs, times, exact quoted dialogue,
numbers, missing passages, and malformed output. Add focused comparisons for
known critical changes, with tests for their limits. Lemmatization can avoid an
`eye`/`eyes` false alarm, but cannot solve semantics. Apple's Natural Language
framework exposes lemmas locally. [NLTagScheme.lemma](https://developer.apple.com/documentation/naturallanguage/nltagscheme/lemma).

For harder cases, compare one source claim with one proposed claim. Ask separately
whether the edit changes the requested action, negation scope, certainty, or
subject. Apple answering its own questions is diagnostic evidence, not an
independent guarantee. The previous native critic accepted bad changes. Research
on intrinsic self-correction also cautions against assuming that another pass
through the same model reliably repairs reasoning; its results are not a direct
benchmark of AFM 3. [ICLR self-correction study](https://openreview.net/forum?id=IkmD3fKBPQ).

An optional **development-only local NLI verifier** would provide a more
independent signal. MiniCheck checks whether claims are supported by documents;
its published 770M-parameter variant is a reasonable benchmark candidate. It
requires downloaded weights on the development Mac, model-specific license and
runtime review, and calibration on editorial instructions. It need not be shipped
to users. No weights were downloaded or private data transmitted in this research.
It checks support, not completeness or readability, and published benchmark
performance is not evidence that it handles our negations correctly.
[MiniCheck paper](https://aclanthology.org/2024.emnlp-main.499/),
[author implementation](https://github.com/Liyan06/MiniCheck).

**3. Separate acoustic background from conversational relevance**

Low-volume background speech, a clearly audible personal aside, quoted movie
dialogue, and an uncertain transcription are different cases. A single Boolean
“unrelated” question conflates them. Classify short passages with neighboring
context; keep qualifications and quoted dialogue when they identify an actual
note. Track a personal aside across its continuation sentences. Uncertain text
must remain recoverable without appearing as accepted editorial feedback.

For recordings with aligned words, keep the relative-level analysis. Its success
on one representative recording is encouraging, not a universal threshold. Test
quiet speakers, whispered notes, microphone gain changes, compressed recordings,
background speech at similar volume, and overlapping film dialogue. Measure
foreground notes lost as well as background words retained.

Without exact word alignment, waveform analysis can still identify quiet time
intervals. It cannot safely identify which transcript words to delete. Preserve
the source and use conservative interval-to-segment matching or explicit local
retranscription of a proposed foreground derivative, retaining the timeline map
and original transcript. Do not pretend recording timestamps are film timestamps.

For **future live capture**, benchmark Apple's `AVAudioEngine` voice-processing
mode. Apple documents local echo cancellation, noise suppression, and automatic
gain control, plus user-controlled microphone modes. This could reduce film
playback leakage before Parakeet sees it. It is not an offline separator for an
already mixed imported WAV. [Apple voice-processing presentation](https://developer.apple.com/videos/play/wwdc2023/10235/).

The installed Xcode 27 `AVAudioIONode.h` confirms that voice processing requires
device rendering, not manual rendering; input and output participate together.
Automatic gain control is enabled by default. Therefore, measure how processing
changes relative levels and do not apply unprocessed-audio thresholds blindly.
Other-audio ducking also needs care: lowering the movie while someone judges its
mix would change what they hear. CutNotes currently captures through FFmpeg's
AVFoundation input, so adopting voice processing requires a deliberate capture
experiment, not a formatter flag. Python should retain capture policy; any Swift
bridge should only execute the chosen mode and return versioned evidence.

Apple `SpeechDetector` is not a speaker-identity or film-relevance classifier.
Its documentation also requires a `SpeechTranscriber` or `DictationTranscriber`
alongside it, so it is not a standalone VAD drop-in for our Parakeet pipeline.
The inspected Speech SDK exposes alternatives and timing but no public speaker
diarization field on `SpeechTranscriber`. A second Apple transcription path may
require system assets and should be a separate benchmark, not silent fallback.
[SpeechDetector](https://developer.apple.com/documentation/speech/speechdetector).

**4. Make readability evaluation more specific without moving the goalposts**

One saved borderline result says: “Do not remove the shadow. Keeping it is
essential because it reveals the approaching visitor.” My assessment is that
this is already usable prose; its near-tie is not proof the formatter needs to
rewrite it. Other flagged outputs really do contain repetition or fragments.
This calls for judge calibration as well as formatter changes.

The current readability question bundles instruction echoes, schema text,
fragments, transcript dumps, and overall usability. TypeSafe recommends one
well-scoped decision per question. Apple similarly demonstrates splitting an
overly broad judge into distinct dimensions and comparing its judgments with
human expectations. [TypeSafe atomic questions](https://docs.typesafe.ai/introduction),
[Apple Evaluations](https://developer.apple.com/videos/play/wwdc2026/298/).

Develop a separately versioned rubric with independent decisions for:

- Complete, understandable editorial sentences.
- Repetition that adds no information.
- Dictation fillers or abandoned fragments.
- Readable general-note and timestamp organization.
- Unsupported instructions or exposed machine/schema text.

Use deterministic checks for obvious schema leakage. Score the note bodies and
document organization separately. Check whether empty-section notices affect
the judge, since several flagged outputs contain them; this is a hypothesis, not
an established explanation. Relevance and factuality remain separate dimensions.

Keep the existing questions and 0.10 margin frozen as the comparison baseline.
Label good and flawed synthetic examples independently, calibrate rubric v2 on a
development split, then evaluate it on fresh held-out examples. Report both
rubrics on identical output. Do not reinterpret old borderline cases as passes,
lower a threshold to obtain green results, or retry until a preferred answer
appears. A probability near 0.5 reflects uncertainty under that question; it is
not “the notes are half correct.” [TypeSafe confidence](https://docs.typesafe.ai/confidence).

**5. Use macOS 27 where it adds evidence, preserve the macOS 26 path**

The useful additions are model/capability inspection, token/context accounting,
and better evaluation tooling. Version prompts when testing shows an OS-model
change needs it. The present machine's saved native result identifies AFM 3 Core
and no reasoning capability; setting a reasoning level does not unlock one.
The Python SDK and `fm` expose the model through different interfaces, not a
better model. Keep the existing Swift bridge rather than add a second inference
stack for the same work. [Foundation Models updates](https://developer.apple.com/videos/play/wwdc2026/241/),
[prompt versioning](https://developer.apple.com/documentation/foundationmodels/updating-prompts-for-new-model-versions).

Use the larger on-device variant when an eligible test machine actually reports
it available, and benchmark separately. Do not infer public audio-input support
from Apple's internal speech-model research. Private Cloud Compute is a remote
service, despite its privacy protections, and is unnecessary for this proposed
user workflow. Apple's adapter toolkit explicitly does not support OS 27+, so
adapter fine-tuning is not a shared 26/27 solution.
[Apple adapter compatibility](https://developer.apple.com/apple-intelligence/foundation-models-adapter/).

**Recommended order and stopping rules**

| Order | Experiment | Evidence required to proceed |
| --- | --- | --- |
| 1 | Split observed failures into ASR, exclusion, meaning, prose, and judge disagreement; label a fresh small holdout. | Human-readable source/output pairs and fixed expected facts. |
| 2 | Compare current copyediting with evidence-first constrained edits. | Fewer false rejections without accepting new meaning reversals; inspect abstentions. |
| 3 | Add passage-level relevance and relative-audio evidence. | Remove unrelated passages without deleting qualifications, quiet notes, or useful quoted dialogue. |
| 4 | Calibrate readability rubric v2 separately; optionally benchmark a local independent verifier. | Better agreement with held-out human labels; report v1 and v2 independently. |
| 5 | Run full native comparisons and live-capture audio experiments. | Fresh repeated runs on available model/OS combinations, plus manual representative review. |

Build minimal pairs that alter one feature: keep/remove, open/closed, early/late,
possible/certain, optional/required, subject identity, or cut time. Add invariance
cases where fillers, sentence boundaries, names, or background volume change
without changing the note. This follows behavioral testing research and directly
targets CutNotes' known failure modes. [CheckList](https://aclanthology.org/2020.acl-main.442/).

A practical next benchmark is 80–120 short synthetic cases plus 12–20 locally
recorded audio cases, with development and unseen review sets separated before
prompt tuning. Repeat native generations and report variation. Track critical
meaning errors, missing facts, false exclusions, readability, latency, and review
rate independently. A formatter that avoids errors by deferring every note is
not a successful automatic formatter. Zero observed critical errors is a release
requirement for the tested cases, not proof of zero errors on future recordings.

Keep the frozen public suite, private local review, macOS 26 compatibility tests,
and real-device model-quality checks distinct. A passing macOS 26 build still
does not establish model quality on that OS. Release remains held until actual
generated output meets the agreed review standard.

Research scope: primary Apple documentation and installed SDK declarations,
TypeSafe documentation, research papers, and existing local run artifacts were
reviewed. Four local deterministic diagnostic pairs were executed. No new native
quality run, Jev call, capture change, model download, or deployment occurred.
