# 1.0.5 acceptance status

**Release held: native Apple formatting has not passed content acceptance.**

Acceptance means useful, faithful feedback comparable to prior working releases. It does not require the exact wording or polish of a Codex-authored reference.

The user explicitly chose to hold the combined release until Apple formatting
passes and requires macOS 26 compatibility. Do not split out and publish the
MacWhisper change while this hold is in effect.

The 1.0.5 work fixes unselected MacWhisper CLI probes and deterministic formatting defects. Source changes and mocked tests are insufficient evidence for publication. Real Apple inference on macOS 27.0 (26A428) still introduces unrelated background material, changes an observation's meaning, omits qualifications, and leaves a missing edit note. The system-model availability check reports ready; that does not establish output quality. The user reports the last good output was on macOS 26. Apple documents a model change in macOS 27. A separate invocation of the installed 1.0.4 helper on a short synthetic transcript produced 65 empty-mask errors and 66 empty-token-set errors from the OS guided-generation service. This reproduces a runtime problem independently of the candidate source changes; it does not establish that every content failure has that same cause.

| Gate | Status |
| --- | --- |
| Python regressions | 116 passed locally, including disfluent acceptance checks, legacy/current contracts, provider isolation and development-only Jev evaluation |
| Swift contracts/app support | 21 passed locally, including native transcription evidence and optional model metadata |
| CI on macOS 26 and Xcode 27 | Both lanes are required for the candidate; see the current [PR checks](https://github.com/aindaco1/cutnotes/pull/6/checks) |
| Local release build | Passed |
| Developer ID candidate signing | Earlier candidate passed; subsequent source changes require rebuilding and re-signing; not notarized |
| Real Parakeet transcription | Passed on the supplied recording during diagnosis |
| Native Apple formatting | September 22: 9/12 original development cases and 1/4 new stress cases pass combined checks; fresh supplied-transcript run returns `formatter_incomplete` |
| App/DMG notarization and stapling | Held |
| Public DMG mount/install/launch | Held |
| Public Sparkle signature/feed and previous-version update | Held |

Private native prompts, responses, output and acceptance notes remain in ignored `build/diagnostics/release-1.0.5/`. Do not commit them. The installed public 1.0.4 remains unchanged. No 1.0.5 tag or public release should be created until the native formatting gate passes.

`scripts/check-apple-formatting.py` now provides repeatable native content checks
using synthetic fixtures. Its baseline on this macOS 27 host still finds missing
qualifications, an omitted end suggestion, and omitted positive feedback. The
last problem exposed another deterministic bug: the general-note deduplicator
discarded notes containing fewer than three content words. That word-count gate
has been removed and short positive/keep-as-is notes have a regression test. A
follow-up native run retained the missing music note. Vocabulary-overlap
deduplication has also been replaced by exact-text deduplication so similar but
distinct or opposite general notes survive. End-of-video placement now retains
the passage's location evidence when a generated note cites only its explanatory
sentence; that valid note was previously discarded by a later evidence check.

The draft-v1 request remains compatible with older local helpers that ignore
`--instructions`: the existing prompt file contains the complete task. New helpers
remove only its exact duplicated instruction prefix before using the separate
session instructions. Python and Swift tests cover both forms. Formatting still
uses the macOS 26 API path; only passive model metadata uses SDK/runtime-guarded
macOS 27 APIs. The deployment target is unchanged.

Experiments with free text, surrounding context, source quotations before writing,
more detailed generation guides, and a second editing pass have not reliably
restored the supplied review. Some recover individual observations while adding
advice or dropping other feedback. These experimental paths are not shipping code.
SDK/build compatibility and actual model output on macOS 26 remain separate gates;
this macOS 27 machine cannot establish the macOS 26 native result. The user confirms
that no macOS 26 Mac is available. Validate backward compatibility with the macOS
26 CI build/contracts and the unchanged API availability/wire contract, recording
the native-model testing limitation explicitly.

The approved small-schema experiment produced nine responses in each of two native
Apple runs. Both failed: qualifications disappeared, background speech remained,
and observations changed meaning. The example-based variant also copied optionality
into an unrelated note. These are private diagnostic prototypes, not shipping code.
The brief separate-model benchmark did not establish release readiness. The user
subsequently superseded that direction: focus on Apple Intelligence, with no model
download beyond Parakeet. No separate formatter or dependency was integrated.

The [deeper Apple-only investigation](APPLE_FORMATTING_INVESTIGATION.md) separates
ASR wording errors from editorial-generation errors, records the controlled native
API and audio-boundary experiments, and defines the next source-backed-statement
prototype. Targeted re-transcription recovered clearer wording, but neither the
alternate whole-file ASR settings nor the new Apple prompt variants passed the full
review. These findings do not lift the release hold.

Detected partial failures now return `formatter_incomplete` and preserve the
transcript and previous Markdown. A dropped timed passage cannot be hidden by
another note at the same timestamp. General semantic coverage still requires the
native acceptance gate; these checks do not claim to detect every omission.

Local cleanup moved obsolete duplicate files, old output links and a superseded test build to a recoverable Trash folder with a restore manifest. The active SwiftPM cache, pinned media runtime, current candidate and diagnostic evidence remain available for development and testing. There were no stale merged branches to delete.

Apple references: [Foundation Models updates](https://developer.apple.com/documentation/updates/foundationmodels) confirms that model changes accompany OS updates; [developer forum topic](https://developer.apple.com/forums/thread/843310) reports the same empty-mask/tokenizer signature on macOS 27 betas. The local reproduction is the evidence for this machine; the forum report is corroboration, not an Apple-confirmed root cause or fix.

The source-backed prototype retained optional transcription evidence but did not
establish reliable statement extraction. Per-sentence roles, quotation constraints,
separate output fields, sampling changes, chat examples and full-recording context
still failed the complete supplied review. They are diagnostic probes, not enabled
formatter paths. The latest native fixture run passes 10/12 development and 6/8
held-out cases; remaining failures concern missing meaning and unrelated speech.

A native response trace also exposed a real preservation defect: a valid lighting
paraphrase was discarded by a word-overlap percentage threshold. That threshold is
removed and regression-tested, while the narrower unrelated-vocabulary check
remains. Acceptance fixtures now allow ordinary equivalent phrases while retaining
direction and qualification tests. These corrections do not justify publication.

An independent Shortcuts On-Device benchmark also failed the complete synthetic
review by dropping qualifications and duplicating content. It used public synthetic
fixtures only; the temporary shortcut was exported locally and removed afterward.
No Shortcuts dependency was added. The supplied transcript and a fresh full-audio
transcription both still return `formatter_incomplete` through the final candidate;
their source files remain unchanged. The release hold remains in effect.

The September 20 clause-preservation experiment restored qualifications in the
combined synthetic review but still leaked unrelated speech. After manual review
exposed a false positive and strengthened the acceptance fixture, its saved output
scores 10/12 development cases. It is not the production formatter and was not
promoted to held-out evaluation. The unchanged production candidate's saved native
outputs still score 16/20 under the stricter check; no fresh inference run or
release acceptance is implied. See the investigation for the native capability,
embedding, audio-level and confidence-selected re-decoding findings.

The September 21 macOS 27 audit verified this host's AFM 3 Core identity and
capabilities, compared schema inclusion and required tool calls on nine identical
passages, and integrated passive model metadata into the existing status contract.
Neither experimental mode passes the supplied review. A fresh run through the
rebuilt production path still scores 10/12 development and 6/8 held-out cases.
The macOS 27 SDK sampling-initializer warnings are resolved while preserving the
same options and Xcode 26 compatibility. See the investigation for the current
Apple hardware requirements, API decisions and unsuccessful Instruments attempt.

A further required-field clause editor retained more qualifications but still
included unrelated conversation and leaked schema instructions. It passes only
8/12 development cases after manual review strengthened the check, and was not
promoted to held-out evaluation or production. Unedited private output is saved
for the user's review. The production formatter remains unchanged.

The user can test Core Advanced on eligible hardware later. The
[private model test kit](APPLE_MODEL_TEST_KIT.md) uses the same packaged core and
helper, runs all 20 public synthetic cases, and requires the actual model name
before inference. The requirement never selects or downloads a model. Legacy
status without model metadata remains supported when that prerequisite is omitted.
The documented `cutnotes-notary` keychain profile is unavailable on this Mac;
the new private development app is signed, not a notarized release candidate.

The September 22 [Jev development evaluation](JEV_EVALUATION.md) adds an optional
remote judge for saved public synthetic outputs, outside the app and default test
path. The fresh Apple development run still passes 10/12 cases. Saved 20-case
outputs pass 16/20 deterministic checks, 16/20 Jev judgments, and 14/20 combined;
manual review found both useful semantic omissions and judge false alarms/misses.
These diagnostic scores do not replace the content acceptance gate. No runtime
formatter, private-transcript upload, additional user dependency, or release was
introduced by this test integration.

## Default Jev development gate (September 22)

The standard `python3 scripts/test.py` workflow now includes Jev calibration and
native Apple plus Jev evaluation by default. The latest run passed 115 Python
and 21 Swift tests. Of 42 labeled judge examples, 41 received correct confident
decisions and one required review; none received a confident wrong decision.
Native Apple passed 10/12 exact and 9/12 combined checks. The standard suite
correctly fails on outstanding quality findings. See [Jev evaluation](JEV_EVALUATION.md)
for scoped questions, repeatability and unchanged-output comparisons. The app
remains fully local; these testing changes do not lift the 1.0.5 release hold.

## Disfluent regression follow-up (September 22)

The next sentence-preservation experiment retained the complex public example's
qualifications but failed to generalize: the plain-text prototype passes 19/20
exact checks and only 12/20 combined checks. It also retains unrelated speech and
misreads the supplied review. It was not integrated into the runtime.

Four newly authored public stress cases now run by default, with fixed Jev
question/policy behavior and explicit semantic requirements. The corrected
four-case native run passes 2/4 exact and 1/4 combined; omitted observations,
qualifications and duplicated requests remain. The full workflow passes 116
Python tests, 21 Swift tests, the helper build and all 42 labeled judge examples,
but correctly fails content acceptance. See the
[investigation](APPLE_FORMATTING_INVESTIGATION.md#september-22-sentence-preservation-and-disfluent-regressions)
for original reports, the corrected lighting-synonym false alarm, and the fresh
private-transcript check. No release or post-release cleanup was performed.
