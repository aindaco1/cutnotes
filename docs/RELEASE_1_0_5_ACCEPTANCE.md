# 1.0.5 acceptance status

**Release held: native Apple formatting has not passed content acceptance.**

Acceptance means useful, faithful feedback comparable to prior working releases. It does not require the exact wording or polish of a Codex-authored reference.

The 1.0.5 work fixes unselected MacWhisper CLI probes and deterministic formatting defects. Source changes and mocked tests are insufficient evidence for publication. Real Apple inference on macOS 27.0 (26A428) still introduces unrelated background material, changes an observation's meaning, omits qualifications, and leaves a missing edit note. The system-model availability check reports ready; that does not establish output quality. The user reports the last good output was on macOS 26. Apple documents a model change in macOS 27. A separate invocation of the installed 1.0.4 helper on a short synthetic transcript produced 65 empty-mask errors and 66 empty-token-set errors from the OS guided-generation service. This reproduces a runtime problem independently of the candidate source changes; it does not establish that every content failure has that same cause.

| Gate | Status |
| --- | --- |
| Python regressions | 65 passed locally |
| Swift contracts/app support | 15 passed locally |
| CI on macOS 26 and Xcode 27 | Passed at `0521d93` |
| Local release build | Passed |
| Developer ID candidate signing | Passed; not notarized |
| Real Parakeet transcription | Passed on the supplied recording during diagnosis |
| Native Apple formatting | Failed content acceptance |
| App/DMG notarization and stapling | Held |
| Public DMG mount/install/launch | Held |
| Public Sparkle signature/feed and previous-version update | Held |

Private native prompts, responses, output and acceptance notes remain in ignored `build/diagnostics/release-1.0.5/`. Do not commit them. The installed public 1.0.4 remains unchanged. No 1.0.5 tag or public release should be created until the native formatting gate passes.

Local cleanup moved obsolete duplicate files, old output links and a superseded test build to a recoverable Trash folder with a restore manifest. The active SwiftPM cache, pinned media runtime, current candidate and diagnostic evidence remain available for development and testing. There were no stale merged branches to delete.

Apple references: [Foundation Models updates](https://developer.apple.com/documentation/updates/foundationmodels) confirms that model changes accompany OS updates; [developer forum topic](https://developer.apple.com/forums/thread/843310) reports the same empty-mask/tokenizer signature on macOS 27 betas. The local reproduction is the evidence for this machine; the forum report is corroboration, not an Apple-confirmed root cause or fix.
