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

## Formatting

Both Apple and Codex receive bounded groups of source observations identified as `N0001`, `N0002`, and so on. A formatter may return only those IDs for classification and priority. Python dereferences them and renders the same required Markdown headings from source-owned note text deterministically. Provider output cannot directly enter the document. Invalid IDs are discarded, every source observation remains in Overall, obvious sound/praise categories are checked locally, and invented or omitted CUT times reject the document before atomic replacement. This keeps the no-invention/no-loss guarantee provider-independent while still using a selected model to organize the handoff.

There is no automatic provider fallback. A requested provider either succeeds or returns an actionable stable error while preserving earlier artifacts.

## Packaging

The DMG contains one arm64 app. Its Resources contain the CLI, Python framework, minimal FFmpeg/FFprobe runtime, native helper, licenses, and icon. Model weights remain in Application Support. Sparkle checks a signed GitHub Releases appcast once per launch and never installs silently.
