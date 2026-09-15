# macOS 27 acceptance — 2026-09-15

Host: Apple Silicon, macOS 27.0 (26A428), Xcode 27.0 (27A266a), Swift 6.4.

## Verified

- 42 Python tests, including nine regression tests for model readiness, preserved artifacts, and spoken section boundaries.
- 12 Swift command and decoding tests; arm64 release builds of the app and local helper.
- Reproduced a packaging failure when separate product builds remove Sparkle from the shared output directory under Swift Build. Building the complete package retains both executables and the framework; CI checks these outputs together.
- Installed 1.0.2 passes strict deep signing, Gatekeeper, and stapled-ticket checks.
- A synthetic spoken-notes audio fixture transcribes through the installed Parakeet helper.
- Apple reports `modelNotReady` on this upgraded host. With the 1.0.3 source CLI and installed helper, real import returns `apple_model_unavailable`, exit 6, with both session audio and transcript preserved. A formatting retry preserves the transcript and explains how to retry once the model is ready.
- No implicit provider fallback is introduced; an unrelated helper failure retains its original error category.

- After model preparation completed, a full Parakeet-to-Apple import succeeded. Review exposed comma-only spoken section boundaries merging separate edit points; the fix retains the general note and individual 00:12 and 00:24 edits. A real Apple formatting retry produced both distinct instructions. Audio bytes remained identical to the synthetic source.

- Downloaded public 1.0.3 DMG and app pass checksums, strict signatures, stapled tickets, and Gatekeeper on macOS 27. The archive's Sparkle signature verifies with the public key from installed 1.0.2. Version 1.0.3 was installed, with the prior app preserved for updater testing.
- A 12,038-character, 60-edit-point synthetic transcript completed Apple formatting in 162.7 seconds and retained all timestamps. Review caught general dialogue/structure feedback being removed by the final lexical filter; 1.0.4 adds that missing editorial vocabulary with a rendering regression test. The long fixture is rerun against the fixed candidate before release.

## Pending acceptance

- Repeated record/pause/resume/cancel acceptance.
- Native record/pause/resume/cancel and visible recovery controls.
- Native launch, terminal command installation, and a real previous-version Sparkle update.

The native UI automation service crashed while inspecting this app; that is an automation failure, not evidence of a CutNotes crash. Source, installed 1.0.2, and future signed-release gates are separate claims. Track remaining work in issue #1.
