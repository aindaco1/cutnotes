# macOS 27 acceptance

Updated September 16, 2026. [Issue #1](https://github.com/aindaco1/cutnotes/issues/1)
remains open: the completed checks below do not cover the full physical runtime
matrix or the hosted GA Xcode 27 lane. This is the existing procedure and evidence
ledger; keep the issue as its high-level checklist rather than creating another
readiness document.

## Versions and evidence sources

The reviewed source is `3602d530807fc65ee68b652361634068f5851e39`, matching public
CutNotes **1.0.4 (5)** and the local installed app. The deployment target remains
macOS 15; Apple formatting requires macOS 26 or later and a ready system model.

| Environment | Recorded versions | Evidence |
|---|---|---|
| Local physical Apple Silicon Mac, upgraded account | macOS 27.0 `26A428`; Xcode 27.0 `27A266a`; Apple Swift 6.4 `swiftlang-6.4.0.34.1`; Python 3.14.7 | September 15 native acceptance and September 16 command/test checks |
| Latest successful hosted Xcode 27 job | Image `xcode-27-arm64`, version `20260907.0173.1`; macOS 27.0 `26A5406e`; Xcode 27.0 `27A5252f` | [CI job 104461176134](https://github.com/aindaco1/cutnotes/actions/runs/34992729426/job/104461176134), September 15 |
| Public 1.0.4 release | Release workflow uses `macos-26` | [Release run 34992736500](https://github.com/aindaco1/cutnotes/actions/runs/34992736500), September 15 |

The local OS and Xcode builds match Apple's September 14 releases. The hosted
Xcode 27 job used beta builds, and GitHub's image announcement still identifies
the image as preview at this review. Local GA testing and a successful preview
job do not establish a completed hosted GA lane. Record the exact Swift/Python
versions and dependency resolution with future hosted acceptance runs; the
current job explicitly prints only the OS and Xcode versions.

References: [Apple releases](https://developer.apple.com/news/releases/),
[GitHub runner status](https://github.com/actions/runner-images/issues/14404),
[public 1.0.4](https://github.com/aindaco1/cutnotes/releases/tag/v1.0.4), and
[September 15 native acceptance](https://github.com/aindaco1/cutnotes/issues/1#issuecomment-5684376143).

Dependency resolution is recorded in [Package.resolved](../macos/Package.resolved)
and [runtime-lock.json](../config/runtime-lock.json): Record 1.2.2, FluidAudio
0.15.6, Sparkle 2.9.6, Swift Argument Parser 1.8.2, Python 3.14.7, and
FFmpeg/FFprobe 8.1.1. These are the reviewed pins, not a completed RC/GA dependency
and release-note review.

## Completed checks

| Check | Result and scope |
|---|---|
| Python suite | All 42 tests passed again September 16, including readiness, preservation, formatting, allocation, progress, and mocked recording controls. |
| Swift suite | All 12 tests passed again September 16 on local Xcode 27 GA. The first build inside iCloud failed signing a generated test bundle because of Finder metadata. Retrying with a fresh build directory outside iCloud passed; the original checkout build failure is not a passing gate. |
| Hosted builds | Both `macos-26` and `xcode-27` jobs passed Python/Swift tests and arm64 release builds of the complete package, including both executables and Sparkle. Building products separately previously removed Sparkle from the shared output; 1.0.3 fixed that packaging sequence. |
| Installed 1.0.4 security checks | Strict deep signature verification, stapled-ticket validation, and Gatekeeper assessment passed September 16. This is installed-app evidence, separate from a fresh public-DMG installation and independent checks of every nested executable and entitlement. |
| Installed terminal launcher | The existing command link resolves to the installed app and independently reports 1.0.4. This does not rerun administrator-prompt installation or reinstall/uninstall guidance. |
| Native recording controls | September 15 Start/Pause/Resume/Finish produced a finalized 37.6-second PCM session. Physical microphone intelligibility was not verified: synthetic playback was not captured by the selected route. |
| Native import | September 15 public 1.0.4 transcribed and formatted a synthetic English fixture, retained general feedback and separate edit points, and left source audio byte-identical. This does not cover the representative audio/video matrix. |
| Apple readiness and preservation | During the September 15 audit, real import with the 1.0.3 source CLI and installed helper returned `apple_model_unavailable` (exit 6) while models prepared, preserving both audio and transcript. A format retry preserved its transcript. After readiness recovered, Parakeet-to-Apple import and Apple formatting succeeded. Unrelated helper failures retain their original error category. |
| Long formatting | The September 15 audit records a 12,038-character fixture retaining all 60 edit points; the issue's audit summary records preservation of general feedback after the 1.0.4 fix. The regression test for that fix passes. The earlier 162.7-second timing belongs to the original audit, not this September 16 rerun. |
| Public artifact history | Public 1.0.3 DMG/app checksum, signature, stapling, and Gatekeeper checks passed September 15; its Sparkle archive signature verified against the key in installed 1.0.2. Keep this evidence attached to 1.0.3. |
| Real Sparkle update | Native **1.0.2 → 1.0.4** completed replacement and relaunch September 15, followed by model-readiness and signature/staple/Gatekeeper checks. This is a completed update hop, not a pending one. It does not establish the issue's original 1.0.0-origin path or the immediately previous 1.0.3 path specified by the release procedure. |

Xcode 27 emits deprecation warnings for the Foundation Models
`GenerationOptions(sampling:...)` initializer at two call sites. Tests and prior
real inference pass, but the pinned-integration warning review remains distinct
from a successful build.

The earlier native UI automation service crash was an automation failure, not
evidence of a CutNotes crash. Later native acceptance is recorded above.

## Remaining acceptance procedure

Use fresh and upgraded macOS 27 accounts where applicable. For each run, record
the source commit, app/build number, account category, OS/Xcode/Swift/Python
versions, runner image where applicable, resolved dependency versions, and a
content-free pass/fail result. Use synthetic fixtures, retain the source for byte
comparison, and keep prior sessions and the previous app available for recovery.

| Area | Remaining checks and pass condition |
|---|---|
| GA toolchain and release | When GitHub marks the image GA, pin the supported toolchain, decide the required-check policy, and rerun tests and complete-package builds with exact environment evidence. Review Apple/dependency RC and GA notes and the Foundation Models warnings. Move signed production to Xcode 27 only after package layout, runtime loading, entitlements, nested signing, separate app/DMG notarization and stapling, Gatekeeper, public DMG, and Sparkle gates pass. |
| Fresh install and permissions | Download the current public DMG, compare its published checksum, mount/copy/launch through Gatekeeper, and independently verify nested signatures and entitlements. On fresh and upgraded accounts, verify existing microphone grants, first denial, later grant, and mid-session revocation without misleading success, hangs, crashes, or orphan processes. |
| Terminal command installation | Exercise the administrator-prompt installer and independent command execution, then verify documented reinstall/uninstall behavior. Existing-link/version evidence is already complete. |
| Recording and recovery | Capture intelligible synthetic spoken feedback using both System Default and an explicitly selected microphone. Exercise repeated pause/resume, finish and cancel while paused, active cancellation, input loss, and app quit. Verify finalized audio excludes paused intervals, preserved-artifact flags match files, recovery controls are visible, and no child processes remain. |
| Recording limits | Use an accelerated clock test to verify the 3:45 warning and 4:00 captured-audio stop, excluding paused time. The passing duration test currently covers the import boundary; it does not establish the recording warning/hard-stop gate. |
| Media and preservation | Import representative audio and video fixtures, compare source bytes, repeat sessions to verify unique output allocation, and exercise successful and failed Record/Import/Format paths against the final machine-contract preservation flags. |
| Models and languages | Exercise licensed model download and local import, manifest hashes, incomplete/corrupt-model recovery, and offline reuse. English inference is recorded; run at least one non-English language from the CLI-owned list and retain the experimental-language disclosure. |
| Optional providers | Exercise MacWhisper and Codex both absent and installed. Check provider-specific errors and explicit selection without any Apple-to-Codex or Parakeet-to-MacWhisper fallback. |
| App and privacy | Complete advanced options, language and output-folder selection, Open Notes, Reveal Folder, diagnostics export, and update-control acceptance. Inspect exported diagnostics for excluded content and confirm Swift consumes machine contracts while the CLI retains workflow policy. |
| Offline operation and network | After model setup, deny network access and test recording, import, transcription, and ready Apple formatting. Audit network behavior against the current [privacy contract](PRIVACY.md): model download, Sparkle, and explicitly reviewed support-report submission; no telemetry, automatic crash upload, or system profiling. Optional providers retain their separately selected behavior. |
| Update coverage | Verify the up-to-date path on macOS 27 and the original 1.0.0-origin update requirement. The completed 1.0.2 → 1.0.4 hop does not cover those checks or the immediately previous release path required by [RELEASE.md](RELEASE.md). |
| Final matrix and documentation | Record remaining RC/GA matrix coverage and macOS 27-only limitations in release notes. Keep composite checklist items open until every required part has evidence. |

Use the commands in [TESTING.md](TESTING.md) and the separate public-artifact and
updater gates in [RELEASE.md](RELEASE.md). A short native recording, a mocked
control test, a signed app, and a successful update hop are separate claims.
Attach only versions, build identifiers, stable errors, readiness states, and
pass/fail outcomes to the issue. Do not publish fixtures, transcripts, prompts,
project/media paths, microphone names, environment variables, credentials, or
raw logs.
