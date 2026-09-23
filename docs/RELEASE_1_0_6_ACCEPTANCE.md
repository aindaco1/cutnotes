# 1.0.6 acceptance status

## Scope — September 23, 2026

Version 1.0.6, build 7, adopts the shared local speech and Apple generation
adapters at Platform commit `0affb6c5652611b87947bd87762d8aa17d35ea32`
([Platform PR #47](https://github.com/aindaco1/dust-wave-platform/pull/47)).
The exact commit is available remotely and its hosted native compatibility
matrix passes with FluidAudio 0.15.5, 0.15.6 and 0.15.7. CutNotes retains 0.15.6.
The four-consumer pin/lockfile check passes.

The migration preserves the Python pipeline, Parakeet model, editorial prompts,
response budgets, machine schemas, provider selection, source preservation and
macOS deployment targets. It removes the Record package dependency and its
unused argument parser, and bundles Platform's license with Record attribution.
This release does not claim new formatting-quality improvements.

## Validation

Local evidence is retained under ignored `build/diagnostics/release-1.0.6/`.
Compare native results against the 1.0.5 shipping suite with the same fixtures,
questions, policy and thresholds. The 1.0.5 baseline was 15/16 deterministic and
12/16 combined with Jev; these known failures remain failures. Unchanged results
establish migration equivalence, not a full quality pass.

| Gate | Status |
| --- | --- |
| Python / Swift | 175 / 23 passed before the version bump |
| Jev calibration | 42/42 passed |
| Native Apple comparison | 15/16 deterministic, same failure as 1.0.5; all 16 Markdown documents match except the review date |
| Native Jev review | Incomplete: two runs rejected an inconsistent model response on case 8; no threshold or parser changes |
| Representative Parakeet and reviewed formatting | Raw transcript and complete timing/confidence evidence match 1.0.5 exactly; accepted notes match except review date; source hashes unchanged; MacWhisper sentinel untouched |
| App bundle and Developer ID signing | Passed strict/deep validation; bundled CLI reports 1.0.6 and default workflow ready; Platform and Record licenses present |
| CutNotes hosted macOS 26 / Xcode 27 CI | Pending |
| App and DMG notarization / stapling | Pending; existing hosted release credentials are configured |
| Public artifact, installed app and Sparkle update | Pending |

At the user’s request, Platform PR #47 was finalized and merged as
`d45f14f2dab573ca57ab74995c219e9d1caf06cb` before CutNotes publication. The
existing exact pin is an ancestor of that merge and remains unchanged. The local
`cutnotes-notary` profile is unavailable; local signing alone is not a public
release candidate. The existing GitHub workflow handles notarization separately
for the app and DMG before publication.

Native macOS 26 and Core Advanced content quality remain unverified on this
macOS 27 / AFM 3 Core host. Hosted builds establish SDK and contract compatibility.

The complete development command remains failed. Jev calibration passed, but
both native-output evaluations stopped after 26 requests because Jev 1.13.0
returned `choice: pass` with probabilities `fail: 0.50`, `pass: 0.49`,
`uncertain: 0.01` for case 8 readability. The parser correctly rejected the
inconsistent result. Reports and raw public responses remain available in
`development/native/jev/` and `jev-complete/`; neither is a complete evaluation.
The earlier 12/16 combined result is historical evidence, not a current pass.

The local app process launches, but computer-use inspection was interrupted by
a closed native connection; visual readiness and update acceptance are still
pending. The installed public 1.0.5 remains available for the update test.
