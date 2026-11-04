# Architecture

CutNotes is one product with two clients: the human terminal and the SwiftUI app. Both call the same Python pipeline.

`CutNotesLocal` now imports Platform's native speech adapter
through the pinned `shared/dust-wave-platform` submodule. The Python pipeline
still owns editorial policy, prompts, provider selection and source preservation;
FluidAudio stays at 0.15.6. See [the migration guide](SHARED_NATIVE_MIGRATION.md).

```text
SwiftUI app ── typed argv + FD 3/4 ─┐
                                    ├─> Python CLI/pipeline
Terminal user ── argparse + stdin ──┘        │
                                             ├─ FFmpeg / FFprobe
                                             ├─ CutNotesLocal (Parakeet)
                                             ├─ Bundled MLX (Gemma, offline)
                                             ├─ MacWhisper CLI (optional)
                                             └─ Codex CLI (optional)
```

## Ownership boundaries

`cutnotes_core` owns all workflow policy: dependencies, microphone selection, duration enforcement, session paths, chunking, provider adapters, formatting prompts, output validation, and artifact preservation. `macos/Sources/CutNotesCore` owns only safe command construction, subprocess isolation, descriptor plumbing, and contract decoding. `CutNotesApp` owns presentation and preferences. `CutNotesLocal` is a narrow native compute helper.

This boundary keeps the CLI independently useful and prevents app behavior from drifting away from terminal behavior.

## Local transcription

The app does not ship model weights. The CLI installs a single pinned Parakeet v3 manifest after explicit license acceptance. Every file has a fixed byte size and SHA-256. Imports and downloads stage into a temporary sibling directory, validate completely, then replace atomically.

Media is normalized by bundled FFmpeg into mono 16 kHz WAV chunks no longer than 15 minutes. `CutNotesLocal` uses Platform/FluidAudio offline APIs and Core ML. Chunk transcripts are joined in order.

Optional native word/token timing and confidence are validated and merged by the
core into a companion evidence file bound to the transcript and original audio
by SHA-256. These recording offsets never become video timecodes. The raw text
is preserved; no confidence-based word deletion or automatic audio repair is
enabled. See the [evidence contract](CLI_PROTOCOL.md#optional-transcription-evidence).

The Python `doctor` contract exposes the model's supported language codes and native display names. Swift renders that capability list rather than maintaining a second language table.

## Formatting

Gemma 4 12B 6-bit is the default local formatter. `gemma_model.py` owns the pinned revision and SHA-256 manifest, hardware/runtime availability, resumable download, import, and atomic installation. The model is 9,760,954,674 bytes and is never included in Git or the app bundle. A verified receipt makes setup checks fast; formatting performs full hash verification. Downloads and imports never modify the user's source media or supplied model folder.

`gemma_formatting.py` uses the accepted four synthetic demonstrations, source-projected timestamp markers, a 4,096-token reasoning budget, fixed sampling settings, and the strict timed/general body contract. No adapter weights are used. The complete dictation remains available to incorporate later qualifications into earlier notes. No private benchmark or Astra output is embedded in the prompt.

The core owns timestamp normalization, IDs and headings. The model produces paragraph bodies keyed by those IDs. Unknown, duplicate or missing locations, literal generated timecodes, malformed JSON and model control tokens reject the result. Ambiguous spoken restarts retain a visible timing-review note. These structural checks do not certify semantic completeness.

One bounded retry handles invalid output. An unsuccessful retry returns `gemma_formatting_failed` and preserves the transcript. Valid notes are published atomically without replacing prior artifacts. Reformatting chooses a new filename. The current input bound is 60,000 prompt tokens; longer transcripts require splitting and are never silently truncated. Audio capture retains its independent four-hour limit.

MLX loads only the local verified model directory with remote code disabled and Hugging Face offline/telemetry-disabled settings. There are no inference uploads, runtime package installs, audio-based source exclusions, automatic audio repairs or silent provider fallbacks. MacWhisper and Codex remain explicit optional providers. The native helper supports only status and Parakeet transcription; it no longer imports Apple generation frameworks. Legacy Apple status fields remain unavailable in the additive v1 doctor contract for compatibility.

Jev is a development-only evaluator on verified public synthetic fixtures. It is not bundled or invoked by the app or CLI. Its calibration questions and policy remain fixed when comparing formatters.

## Packaging

The DMG contains one arm64 app. Its Resources contain the CLI, Python framework with hash-pinned macOS 15 MLX dependencies, minimal FFmpeg/FFprobe runtime, native helper, licenses, and icon. Model weights remain in Application Support. Sparkle checks a signed GitHub Releases appcast once per launch and never installs silently.

## Pause and resume

The recording control channel is implemented in `cutnotes_core`, not Swift. A pause closes the current 16 kHz mono PCM WAV segment normally; resume starts another segment in the same session. Finish or cancel joins all usable segments into one WAV without adding silence, and only captured audio counts toward the 3-hour-45-minute warning and 4-hour limit. Swift sends typed control commands and renders progress acknowledgements from the CLI.
