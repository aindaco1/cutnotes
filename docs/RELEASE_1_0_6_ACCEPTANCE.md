# 1.0.6 acceptance status

Published [CutNotes 1.0.6](https://github.com/aindaco1/cutnotes/releases/tag/v1.0.6)
on September 23, 2026, from tag `v1.0.6` at
`b0fd86e00db5f123ad4391892f56122f1a0cd298`. The user confirmed the complete
Sparkle download, installation and relaunch from 1.0.5 to 1.0.6. The installed
app reports 1.0.6, build 7, and the terminal command reports 1.0.6.

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
| Python / Swift | 175 / 23 passed; final hosted CI passed on macOS 26 and Xcode 27 |
| Jev calibration | 42/42 passed |
| Native Apple comparison | 15/16 deterministic, same failure as 1.0.5; all 16 Markdown documents match except the review date |
| Native Jev review | Incomplete: two runs rejected an inconsistent model response on case 8; no threshold or parser changes |
| Representative Parakeet and reviewed formatting | Local candidate and downloaded public app: raw transcript and complete timing/confidence evidence match 1.0.5 exactly; accepted notes match except review date; source hashes unchanged; MacWhisper sentinel untouched |
| App bundle and Developer ID signing | Passed strict/deep validation; bundled CLI reports 1.0.6 and default workflow ready; Platform and Record licenses present |
| CutNotes hosted macOS 26 / Xcode 27 CI | Passed on the final PR and merged release commit |
| App and DMG notarization / stapling | Passed in the release workflow; downloaded artifacts independently verified, DMG mounted, Gatekeeper accepted |
| Public artifact and Sparkle feed | Published DMG checksum, feed version/build/length/URL and Ed25519 signature verified against the installed 1.0.5 public key; latest feed matches the tagged feed |
| Installed app and Sparkle update | User confirmed 1.0.5 → 1.0.6 download/install/relaunch; installed signature, staple and Gatekeeper checks passed; app binary, helper and Info.plist match the downloaded release |
| Installed terminal command | Existing /usr/local/bin/cutnotes resolves to the installed app's bundled CLI, reports 1.0.6 and default workflow ready; MacWhisper sentinel untouched |

At the user’s request, Platform PR #47 was finalized and merged as
`d45f14f2dab573ca57ab74995c219e9d1caf06cb` before CutNotes publication. The
existing exact pin is an ancestor of that merge and remains unchanged.
[CutNotes PR #7](https://github.com/aindaco1/cutnotes/pull/7) was then merged.
The [merged-commit CI](https://github.com/aindaco1/cutnotes/actions/runs/35890308010)
and [release workflow](https://github.com/aindaco1/cutnotes/actions/runs/35890375639)
both passed. The hosted workflow notarized and stapled the app and DMG separately
before publication.

Public asset SHA-256 values:

- `CutNotes-1.0.6-arm64.dmg`: `110630dcddf6dacfe3752d5d0151439288445296578dbf94ddf781d9ef698f9c`
- `appcast.xml`: `3749db92b362865472eebd6a6fafb1ca9042d75d7321317c7e4854e9c1ac1998`

Native macOS 26 and Core Advanced content quality remain unverified on this
macOS 27 / AFM 3 Core host. Hosted builds establish SDK and contract compatibility.

The complete development command remains failed. Jev calibration passed, but
both native-output evaluations stopped after 26 requests because Jev 1.13.0
returned `choice: pass` with probabilities `fail: 0.50`, `pass: 0.49`,
`uncertain: 0.01` for case 8 readability. The parser correctly rejected the
inconsistent result. Reports and raw public responses remain available in
`development/native/jev/` and `jev-complete/`; neither is a complete evaluation.
The earlier 12/16 combined result is historical evidence, not a current pass.

Jev remains enabled in development testing. It is not an end-user formatter or
runtime dependency: its code, credentials, fixtures and network requests stay
outside the shipped pipeline. Only public synthetic fixtures were sent to Jev;
the representative private recording and transcript remained local.

Native output equivalence establishes no detected migration regression; it does
not fix the known formatting failures or transcription ambiguities from 1.0.5.
Native UI automation could not operate the updater, so its end-to-end acceptance
was user-assisted. Independent filesystem checks confirm the installed version,
signature and public-binary parity after that update. The prior 1.0.5 app was
preserved outside iCloud for rollback.

Evidence includes `native-comparison.json`, `mounted-release-verification.log`,
`release-workflow.json`, `public-runtime/local-validation.json` and
`installed-validation.json` under the local diagnostics directory above.
