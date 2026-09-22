# Evidence editing experiment — September 22, 2026

This is a development experiment, not the app's formatter. The representative
recording is substantially more readable, but public failures still prevent
promotion. User review and acceptance remain required before release.

## Changes and boundaries

`cutnotes_core/editorial_edits.py` preserves each source sentence and provides
small syntax hints before Apple proposes an edit. It permits ordinary synonyms
and deduplication that the old word-set comparison rejected. Targeted checks flag
observation/request changes in either direction, changed numbers or quoted
dialogue, lost conditions/uncertainty/degree/reasons, changed explicit negation,
and some subject/property swaps. A rejected proposal and the source both remain
in the audit; the rendered note retains source wording.

These checks are deliberately incomplete. An unflagged revision is only accepted
**for review**, and every result records `semantic_correctness_proven: false`.
An antonym substitution can trigger a false rejection; unrecognized constructions
or different wording can still conceal a meaning change. This is not a semantic
certification layer, and adding vocabulary lists is not the proposed solution.

Native structured evidence extraction was tested separately and rejected as a
dependency: Apple mislabeled explicit requests and omitted source statements.
The implementation therefore supplies literal source sentences with bounded
syntax hints rather than trusting model-generated fact labels. Plain-language
interpretation also invented details in the pilot. Those negative results are
preserved alongside the successful narrow editing examples.

Passage relevance is assessed after grouping. Two specific model answers are
required for a proposed background exclusion; uncertain answers retain the text.
Explicit requests, qualifications, general-feedback cues, and directly supplied
cut times prevent those exclusions. Inherited cut times do not protect an
unrelated aside. Exclusions remain reversible in the audit and require review.
These safeguards reduced failures but do not make text-only background detection
reliable. The native model mislabeled short praise, display caveats, and a title
observation in the diagnostic runs.

The private run uses the existing audio-derived foreground transcript plus the
user's two confirmed transcription clarifications. The low-volume proposal was
already confirmed against the original recording. This is not a fresh ASR result
or proof of fully automatic end-to-end acceptance. The source WAV hash is
unchanged. No private audio, transcript, or output is sent to Jev.

## Native comparison

All counts below are complete cases, not a percentage of product readiness.
The existing Jev questions, model policy, and 0.10 margin remain unchanged.

| Experiment | Fixed public content/structure | Frozen combined Jev |
| --- | --- | --- |
| Earlier protected copyedit | 12/16 | 6/16 |
| Evidence edit v1 | 10/16 | Incomplete: Cloudflare HTTP 401 |
| Evidence edit v2 | 14/16 | 9/16 |
| Evidence edit v3 | 15/16 | 11/16 |

The first v3 Jev attempt stopped after a transport/response error. A separately
saved evaluation of the **same, unchanged output** completed; it did not regenerate
Apple output, change questions, or alter thresholds. The failed attempt remains
available. These are development comparisons, not independent repeated trials
of an identical formatter version.

The v3 remaining fixed-check failure retains a quoted background command as a
note. It does not execute the command. Frozen Jev also flags readability in an
optional ending, borderline prose in the false-start and corrected-sound cases,
and duplication/readability in the extended-aside case. Retaining source text
avoids some meaning errors at the cost of rough prose.

The current app-path candidate was also exercised by the standard development
suite, separately from this experiment: 9/16 combined cases passed in that run.
The suite correctly remains failed at native acceptance. The experiment has not
replaced that candidate.

Eight additional stored holdout cases passed 7/8 fixed checks and 5/8 combined
frozen Jev checks. The fixed-check failure is a
genuine meaning change: Apple turns warm color grading into lenient grading. The
bounded revision checks miss it. This is a promotion blocker, not a harmless
wording difference. These are existing stored fixtures, not a newly collected
independent human evaluation.

All 166 Python tests pass, including 29 new tests beyond the prior 137-test
baseline. The 21 Swift tests and native-helper build pass. The frozen Jev
calibration passed 26/26 calibration and 16/16 validation examples. These gates
are distinct from the failed native content gate; none authorizes release.

On the private representative recording, all seven existing source-derived fact
checks pass. Five of six edit proposals pass the bounded checks, versus two of
six in the older protected run. The repeated closed-eye observation is condensed
without becoming a request; the uncertain audio diagnosis remains uncertain;
the final-frame comment remains praise. General praise is still repetitive.
Successful checks and a readable draft do not substitute for the user's review.

Local evidence is in the ignored
`build/diagnostics/release-1.0.5/evidence-editing-20260922/` directory. Native runs
save input/output hashes, implementation snapshots, prompts, responses, proposals,
exclusions, and review warnings. Private evidence must stay out of public commits.

## Separately calibrated readability rubric

`scripts/readability_evaluation.py` splits readability into fluency, redundant
meaning, dictation artifacts, organization, and machine-text leakage. Note bodies
and document organization receive separate inputs. It reuses the existing public
allowlist, transport, parser, calibration fitter, and decision rule. Private
evidence is rejected before authentication or a network request.

The new 40-example synthetic corpus was labeled with engineering judgments;
these are not independently collected human labels. Calibration produced 19
correct decisions and one review out of 20. Validation produced 20 correct out of
20. The proposed policy retains a minimum 0.10 margin and is not promoted over
the frozen gate.

On identical saved old formatter output, the new rubric gives 72 passes, three
failures, and five reviews across 80 individual questions. On v3 it gives 73
passes, four failures, and three reviews. This does not establish broad prose
improvement. It helps locate defects and judge disagreements without relabeling
old failures as successes. The applied per-question decisions are in
`readability.json`; the underlying raw calibration-format report remains intact.

## Acoustic stress checks and remaining work

New synthetic signal tests cover 12 gain-scaled variants, compressed/equal-level
speech, and a deliberately quiet utterance. Relative measurements are stable
under uniform gain, but compression can erase the distinction. A whispered note
can look exactly like background speech. These are measurement tests using tones,
not 12 real recordings and not a validated speaker classifier.

Before promotion, improve relevance without discarding real notes, resolve the
remaining generated-prose defects, and test varied real recordings and repeated
native runs. No live-capture voice-processing change was made: imported mixed
audio cannot validate echo cancellation on a physical microphone. Native quality
on macOS 26 and Core Advanced hardware remains untested. The experiment's Swift
probe compiles with a macOS 26 deployment target; the production bridge and
provider-selection contracts remain unchanged.

## Independent local verifier outcome

The optional MiniCheck-Flan-T5-Large development benchmark ran on this M1 Max
using MPS, entirely offline after the separately pinned public model download.
The model is not shipped, invoked by the app, or added to user setup. Loading
checks the weights hash and disables remote code/network model loading. The
download used about 3.13 GB; the isolated environment and weights remain under
ignored `build/development/` for local testing.

At the author's uncalibrated 0.5 decision boundary, the 80 new synthetic support
cases produced 34/40 correct development decisions and 37/40 correct validation
decisions. All 40 deliberately unsupported claims were rejected. Nine supported
paraphrases were also rejected, including ordinary timing instructions, a
subject relationship, and a soft/quiet synonym. The benchmark took 26.5 seconds
after the initial weight hashing, including model loading, on MPS.

A separate offline diagnostic rejected both actual Apple errors: changing a late
footstep plus an earlier-timing request into an observed earlier footstep, and
changing warm grading into lenient grading. It also rejected three of ten
engineering-labeled supported claims from the private proposals. Those private
scores never went to Jev and are not an independent human assessment.

This provides a useful development signal beyond Apple checking itself. It is
not a calibrated correctness gate: the false rejections are material, support
does not establish coverage, and the small targeted corpus cannot establish a
general false-acceptance rate. Keep it optional for local diagnosis; retain the
frozen Jev comparison and manual native-output review. Setup and pinned versions
are documented in [Testing](TESTING.md#optional-independent-local-support-verifier).
