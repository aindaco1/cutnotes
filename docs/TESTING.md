# Testing

Run the fast gates first:

```bash
python3 -m unittest discover -s tests -v
swift test --package-path macos
./script/build_and_run.sh --verify
```

After an OS upgrade, Apple Intelligence can report `modelNotReady` while its
models prepare. A failed Apple formatting request must report
`apple_model_unavailable`, explain how to retry when the model is ready, and
preserve the original transcript. A recording or import that already produced
audio and a transcript must report both as preserved. Test successful formatting
separately once the system model is ready; a graceful unavailable result does
not prove model inference.

Release acceptance is deliberately split into separate claims:

1. Python unit/integration tests pass.
2. Swift command/contract tests pass.
3. The app bundle builds arm64 with the pinned runtime and no non-system absolute load paths.
4. A generated speech fixture transcribes through the bundled CLI and installed Parakeet model.
5. Apple formatting succeeds when the system model reports ready.
6. Optional MacWhisper and Codex selections either work or return provider-specific errors without fallback.
7. Developer ID signatures verify under strict/deep validation.
8. Apple separately accepts the app and DMG notarization submissions, and both tickets staple and validate.
9. A clean mounted DMG can be copied to `/Applications`, launched, and used to install the terminal command.
10. The appcast signature verifies and a previously released app can discover, download, and install the new release.

The recording gate includes pause/resume with more than one pause, finish while paused, cancel while paused, and verification that the joined WAV contains no paused interval. The formatting gate includes a transcript large enough to require multiple Apple Foundation Models requests; no individual request may consume the full model context window.

Formatting fixtures must cover colon, compact-digit, explicit minute/second, and spoken shorthand timecodes; out-of-order source mentions; adjacent ranges; orphaned markers; false starts; background lyrics; and guardrail rejection. Acceptance requires a concise general summary, chronological notes with distinct issues at the same moment kept separate, no source IDs in reader-facing prose, no cross-time merging, no reversed negation, and exact preservation of the source transcript.

For 1.0.0 there is no earlier Sparkle-enabled public version, so the real previous-version update hop becomes a mandatory 1.0.1 release gate. Feed generation and archive signatures are still required for 1.0.0.

## Formatting and optional-provider regressions

The 1.0.5 tests cover mouth and facial-animation observations without keyword gating; generated source IDs used as titles; malformed and unknown grounding IDs; adjacent spoken ranges; conversational second markers; natural general-note transitions; opening conversation followed by actual feedback; bounded long single edit moments; and context-limit retries. Full formatting failure must preserve the source and return an error; partial failure must mark the affected timestamp and emit a bounded warning without copying unrelated speech into the output.

Apple request tests assert that task instructions and untrusted source/context travel in separate files and that both are removed afterward. Run native inference separately: mocked contract tests do not establish model output quality. Inspect the final summary and every timestamped body for instruction echoes, unsupported meaning changes, raw transcript dumps, omitted edits, and incorrectly attached general feedback.

Provider-isolation tests prohibit executing MacWhisper during setup and the Parakeet workflow, and verify that explicit MacWhisper selection invokes only its CLI transcription command. A detected CLI with null version and an empty model list must continue to decode in Swift.

The reference handoff test covers two general notes, adjacent lip-sync timestamps, a qualified reaction observation, separate face/impact notes at the same time, a retrospective approximate marker, and an optional relative end note. Native sample acceptance is required in addition to this mocked controller test.
