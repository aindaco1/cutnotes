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

Python normalizes clear spoken and compact CUT timecodes before provider use, then separates general observations from timestamped edit moments. Repeated observations at one edit point share a synthetic source ID, and adjacent markers can form a range when the surrounding note is continuous. Apple and Codex return concise titles and bodies plus the source IDs that ground them through `cutnotes.local.draft.v1` or an equivalent Codex schema. Python rejects unknown IDs, cross-time grouping, selected semantic contradictions, and generic model-added rationale; common explicit rough-cut patterns are rendered locally. The final Markdown always uses the same Notion-style summary and chronological timestamp structure regardless of provider.

The original transcript remains the preservation artifact. The Markdown is intentionally an editorial synthesis: filler, background lyrics, false starts, and exact repetition are excluded. A detected timecode is never silently dropped; an unintelligible moment is rendered as an explicit “No clear actionable note captured” entry. Invented or omitted CUT times reject the document before atomic replacement.

Apple requests use context-safe source batches and split again when Foundation Models reports a context or guardrail rejection. Clear timestamped requests are handled deterministically when possible, so ordinary edit directions do not pay for unnecessary model calls. If an isolated source observation still triggers Apple's guardrail, the original transcript remains preserved and any validated timestamp receives a grounded local entry. The progress channel reports the omission without echoing source text.

There is no automatic provider fallback. A requested provider either succeeds or returns an actionable stable error while preserving earlier artifacts.

## Packaging

The DMG contains one arm64 app. Its Resources contain the CLI, Python framework, minimal FFmpeg/FFprobe runtime, native helper, licenses, and icon. Model weights remain in Application Support. Sparkle checks a signed GitHub Releases appcast once per launch and never installs silently.

## Pause and resume

The recording control channel is implemented in `cutnotes_core`, not Swift. A pause closes the current 16 kHz mono PCM WAV segment normally; resume starts another segment in the same session. Finish or cancel joins all usable segments into one WAV without adding silence, and only captured audio counts toward the 3-hour-45-minute warning and 4-hour limit. Swift sends typed control commands and renders progress acknowledgements from the CLI.
