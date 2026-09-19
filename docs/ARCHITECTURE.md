# Architecture

CutNotes is one product with two clients: the human terminal and the SwiftUI app. Both call the same Python pipeline.

```text
SwiftUI app ── typed argv + FD 3/4 ─┐
                                    ├─> Python CLI/pipeline
Terminal user ── argparse + stdin ──┘        │
                                             ├─ FFmpeg / FFprobe
                                             ├─ CutNotesLocal (Parakeet / Apple)
                                             ├─ MacWhisper CLI (optional)
                                             └─ Codex CLI (optional)
```

## Ownership boundaries

`cutnotes_core` owns all workflow policy: dependencies, microphone selection, duration enforcement, session paths, chunking, provider adapters, formatting prompts, output validation, and artifact preservation. `macos/Sources/CutNotesCore` owns only safe command construction, subprocess isolation, descriptor plumbing, and contract decoding. `CutNotesApp` owns presentation and preferences. `CutNotesLocal` is a narrow native compute helper.

This boundary keeps the CLI independently useful and prevents app behavior from drifting away from terminal behavior.

## Local transcription

The app does not ship model weights. The CLI installs a single pinned Parakeet v3 manifest after explicit license acceptance. Every file has a fixed byte size and SHA-256. Imports and downloads stage into a temporary sibling directory, validate completely, then replace atomically.

Media is normalized by bundled FFmpeg into mono 16 kHz WAV chunks no longer than 15 minutes. `CutNotesLocal` uses Record/FluidAudio offline APIs and Core ML. Chunk transcripts are joined in order.

The Python `doctor` contract exposes the model's supported language codes and native display names. Swift renders that capability list rather than maintaining a second language table.

## Formatting

Python normalizes clear spoken and compact CUT timecodes before provider use, then groups coherent passages at timestamp and natural topic boundaries. Natural general-feedback transitions clear the active timestamp. Adjacent markers can form a range when the surrounding note is continuous. All passages remain eligible for formatting, including feedback after untimed opening conversation. Retrospective time corrections remain attached to the preceding passage; relative end-of-video suggestions stay separate from general feedback.

Apple and Codex return concise titles and bodies plus supporting source IDs through `cutnotes.local.draft.v1` or an equivalent Codex schema. Python rejects invalid grounding IDs and selected semantic contradictions, repairs empty titles, and renders validated timestamps itself. Editorial relevance is not determined by a finite vocabulary or scene-specific templates. The original transcript remains the preservation artifact.

Apple receives the core-owned task instructions in a separate `--instructions` file, passed to `LanguageModelSession.instructions`; its prompt contains only source observations and spelling context. The native helper generates the body before supporting IDs and title while retaining the existing response schema. Apple requests use alphabetic source-ID aliases so observation numbers cannot be confused with video times. Python maps them back before grounding validation. Temporary request files are removed on success and failure. See Apple's [prompting guidance](https://developer.apple.com/documentation/foundationmodels/prompting-an-on-device-foundation-model).

The renderer emits two sections: general feedback bullets and a chronological video-time table. Distinct issues can share a timestamp. Both general and timestamped requests use bounded source batches. Long single observations can be split again after context or guardrail rejection. If a timestamp cannot be rewritten, the document marks that moment as incomplete and the progress channel reports a content-free warning. CutNotes never substitutes a raw transcript dump or canned scene advice. If no usable notes remain, formatting returns `formatter_contract_failed` and preserves the transcript instead of reporting success. Invented or omitted detected CUT times still reject the document before atomic replacement.

There is no automatic provider fallback. MacWhisper is passively discovered during setup and invoked through `mw transcribe` only when explicitly selected; setup does not query its version or models.

## Packaging

The DMG contains one arm64 app. Its Resources contain the CLI, Python framework, minimal FFmpeg/FFprobe runtime, native helper, licenses, and icon. Model weights remain in Application Support. Sparkle checks a signed GitHub Releases appcast once per launch and never installs silently.

## Pause and resume

The recording control channel is implemented in `cutnotes_core`, not Swift. A pause closes the current 16 kHz mono PCM WAV segment normally; resume starts another segment in the same session. Finish or cancel joins all usable segments into one WAV without adding silence, and only captured audio counts toward the 3-hour-45-minute warning and 4-hour limit. Swift sends typed control commands and renders progress acknowledgements from the CLI.
