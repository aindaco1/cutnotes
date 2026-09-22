# Jev development evaluation

22 September 2026. Jev 1.13.0 through Cloudflare; Apple AFM 3 Core on an M1 Max
running macOS 27. No formatter implementation change in this evaluation.

## Default workflow

`python3 scripts/test.py` now runs Python and Swift tests, live Jev calibration,
builds the current native helper, and runs Apple formatting followed by Jev.
The native acceptance checker and saved-output evaluator also use Jev by default.
See [Testing](TESTING.md#default-jev-development-evaluation) for setup, commands,
explicit offline modes, spending estimates and interpretation.

This is development tooling only. The app and CLI user pipeline contain no Jev
provider, credential or request. Private/custom sources are rejected before
remote authentication. The portable model test kit explicitly remains local;
its saved public output can be judged in the development checkout afterward.

## What improved

Coverage questions now receive only notes in the relevant section or timestamp.
Source facts cannot earn credit unless expressed in the candidate. Exclusions
use separate absence instructions; they no longer ask a generic coverage question
that can mistake omitted background conversation for missing feedback. Shared
Markdown parsing keeps exact and semantic scopes consistent.

Document checks distinguish omitted information from unsupported additions,
respect different timestamps when assessing duplication, and separate empty
section notices from invented editorial claims. Reports show the actual candidate
notes alongside each flagged requirement and its raw probabilities.

The committed review policy uses a 0.10 probability margin. It was selected from
a predeclared grid against calibration labels only, then checked separately.
Near ties and unseen judge model versions become `review`, never pass. Questions
and policy are frozen for subsequent formatter comparisons; they are not tuned
by the standard test run.

## Calibration and repeatability

The public set contains 13 calibration pairs (26 examples) and eight validation
pairs (16 examples). Each pairs a faithful concise result with a deliberately
flawed result. It covers qualification, purpose, ownership, optionality, polarity,
timing, attachment, exclusion, grounding, background speech and duplication.
Labels are source-based engineering judgments, not independent human ratings.

| Final question set | Correct confident decisions | Review | Confident errors |
| --- | ---: | ---: | ---: |
| Calibration fit | 26/26 | 0 | 0 |
| Separate validation run | 16/16 | 0 | 0 |
| Repeated calibration in the standard suite | 26/26 | 0 | 0 |
| Repeated validation in the standard suite | 15/16 | 1 | 0 |

On repetition, a deliberately bad curtain note that invents replacing the actor
received `fail: 0.53`, `pass: 0.46`, `uncertain: 0.01`. The margin routes it to
review. The standard suite correctly exits nonzero; the threshold was not lowered
to turn that result green. This small set supports useful diagnostics, not a
claim of universal judge reliability. Inspected validation examples become
regressions; use fresh examples for future final validation after prompt tuning.

## Identical saved Apple outputs

All 20 output hashes match the earlier evaluator's inputs. Both runs used
Jev 1.13.0. The new questions fix observed errors:

- The omitted limitation on improving the silhouette now fails coverage.
- The omitted purpose of making the ending quieter now fails coverage.
- Faithful short praise and unchanged music no longer fail grounding.
- Opposite red-light instructions at different timestamps no longer fail
  duplication. That output still receives a readability flag for its empty
  summary placeholder.
- The end-room still is marked optional but loses its time condition. The new
  evaluator flags that omission, which the broad exact check accepts.

| Same 20 outputs | Exact checks pass | Jev passes | Both pass |
| --- | ---: | ---: | ---: |
| Earlier evaluator | 16 | 16 | 14 |
| Scoped evaluator with review policy | 16 | 14 | 14 |

The lower semantic pass count reflects additional detected omissions. It is not
evidence that the unchanged Apple formatter became worse or better. Raw requests,
responses and a hash-verified comparison are retained for inspection.

## Fresh native run and release status

The final standard workflow passed all 115 Python tests and 21 Swift tests, and
built the native helper. Apple passed 10/12 exact checks and 9/12 combined checks.
The three cases needing work are:

1. The complex review loses the reaction limitation, optional end condition,
   stylization, crossfade and possible dialogue adjustment on our end.
2. The empty-room ending retains optionality but loses the time condition.
3. A quoted background command still appears as an editorial note.

The standard suite exits nonzero for these content failures and the calibration
review item. It does not treat successful API calls, output files, or unit tests
as release acceptance. CutNotes 1.0.5 remains held. Native macOS 26 and Core
Advanced quality are still unverified; this tooling change adds no runtime API
or model dependency to the app.

The final standard suite and saved-output recheck used 102,463 input tokens,
with estimated inference cost $0.004303446 at the dated $0.042/million input
rate. This excludes earlier diagnostic iterations and is not a billing receipt.
There were no purchases, automatic retries or top-ups in this work.

## Evidence retained locally

Under `build/diagnostics/release-1.0.5/jev-default/`:

- `calibration-exclusions/`: final question-set calibration and proposed policy.
- `validation-exclusions/`: separate validation with the frozen policy.
- `final-development/`: complete default workflow, calibration, native outputs,
  raw Jev evidence and human-readable reviews.
- `final-development.log`: Python, Swift, build and live test output.
- `final-saved-baseline/`: re-evaluation of the unchanged 20 saved outputs.
- `judge-comparison.json`: source-output identity and judge comparison.
- `final-preview/`: explicit dry run with zero network calls.

Earlier pilot/integration evidence remains under `jev-investigation/` and
`jev-integration/`. The first integrated evaluator passed 100 Python tests and
reported 10/12 combined on its fresh native corpus. The broader current checks
expose additional gaps. The private BS Girls recording and transcript were never
sent to Jev.

Question design follows TypeSafe's [atomic-question guidance](https://docs.typesafe.ai/introduction).
Review routing uses the returned distribution as described in its
[confidence documentation](https://docs.typesafe.ai/confidence); confidence is
not independent proof of correctness.
