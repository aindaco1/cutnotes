# Changelog

## [1.0.8] - 2026-09-25

- Adopt the shared Apple support core through the compatible desktop diagnostics API. Preserve reviewed reports, explicit sending, update consent and existing app behavior.

## 1.0.7 - 2026-09-25

- Share Sparkle controller, bounded reviewed-report transport and acknowledgement validation through the pinned Dust Wave Platform dependency. Preserve existing update consent and product-specific diagnostics behavior. See the [migration record](docs/SHARED_DESKTOP_MIGRATION.md).

## 1.0.6 — 2026-09-23

- Use Dust Wave Platform’s shared local transcription and Apple Intelligence adapters. Keep the same Parakeet model, formatting behavior, provider choices, and source-preservation rules.
- Remove the dependency on the Record app package and its unused argument-parser dependency. Preserve FluidAudio 0.15.6 and the existing model verification.
- Pin the shared implementation to an exact revision, initialize it in CI and release builds, and include its license and original Record attribution.

## 1.0.5 — 2026-09-22

- Fix MacWhisper opening unexpectedly. CutNotes invokes its transcription CLI only when MacWhisper is selected; setup and other providers do not probe it.
- Rework Apple Intelligence formatting around short, source-backed passages. Keep usable observations as written, combine repeated feedback, and preserve conditions, uncertainty, and positive notes. When a proposed edit fails the meaning checks, retain the original wording for review.
- Improve spoken cut timestamps, adjacent ranges, retrospective timing corrections, general feedback, and end-of-video notes.
- Use local word alignment and relative audio levels to exclude very quiet background speech from formatted notes when exact evidence is available. Preserve the complete original audio and transcript, plus a local review record of excluded speech and proposed edits.
- Add quiet-place and headphone guidance to recording and import. Apple Intelligence formatting remains on-device and requires no additional model download beyond Parakeet for transcription.
- Expand regression coverage for source preservation, meaning changes, provider isolation, helper contracts, audio evidence, and malformed or incomplete results. Jev remains a development-only evaluator of public synthetic fixtures.
- Retain macOS 26 compatibility and report the system-selected Apple model on macOS 27. Output quality still depends on the recording, transcription, and available Apple model; review your notes before sharing.

## 1.0.4 — 2026-09-15

- Retain grounded general feedback about dialogue, beginnings, and endings through the final editorial-note filter.

## 1.0.3 — 2026-09-15

- Build the app and local helper together so Xcode 27's Swift Build retains the Sparkle framework required for packaging.
- Keep separate spoken timestamp and general-note sections when transcription joins them with commas or semicolons.
- Retain clear trim, shorten, and lengthen instructions when the formatter cannot rewrite them.
- Explain when Apple Intelligence models are unavailable or still preparing after an OS upgrade, and retain the existing `apple_model_unavailable` error code for formatting retries.
- Report preserved session audio and transcripts accurately when a later recording/import stage fails.

## 1.0.2 — 2026-09-07

- Fixes the installed `/usr/local/bin/cutnotes` command so the bundled launcher resolves its application symlink before locating the self-contained Python and media runtimes.
- Moves the signed GitHub Releases update check from the app menu to a top-right toolbar icon.
- Adds an explicit review-before-send support flow for a bounded current-state report and privacy-safe summaries of recent CutNotes crashes. Matching reports are aggregated in public GitHub issues; project names, editorial context, media, transcripts, paths, device names, raw logs, and crash stacks are excluded.
- Keeps polling an accepted notarization upload through transient status-service failures instead of abandoning the candidate.
- Notarizes and staples the signed app before placing it in the separately signed, notarized, and stapled DMG, matching the proven offline Gatekeeper release sequence used by the sibling macOS apps.

## 1.0.1 — 2026-09-07

- Splits large Apple on-device formatting work into context-safe source batches, retries rejected batches at a smaller size, and preserves isolated guardrail-rejected passages through deterministic local rendering without exposing internal Foundation Models errors.
- Replaces sentence-dump formatting with a concise Notion-style feedback summary and chronological timestamped notes. The core normalizes common spoken timecode forms before provider use, groups adjacent edit points, rejects cross-time or contradictory drafts, and handles clear rough-cut patterns locally while Apple or Codex rewrites unstructured prose.
- Adds pause and resume for app recordings. Pauses finalize lossless WAV segments, exclude paused time from the four-hour captured-audio cap, and rejoin the session without inserted silence.
- Updates the bundled Python runtime to 3.14.7.

## 1.0.0 — 2026-08-28

- Adds the native Apple Silicon SwiftUI app for record, import, and format workflows.
- Adds a native-name dropdown for all 25 Parakeet v3 languages and rounded monochrome panels.
- Makes local Parakeet TDT 0.6B v3 transcription the default with explicit, pinned, hash-verified model setup.
- Makes Apple Foundation Models the default formatter when available.
- Limits Apple Intelligence to source-ID classification and renders note text deterministically to prevent unsupported edits.
- Retains MacWhisper and Codex CLI as explicit optional providers without silent fallback.
- Adds versioned JSON result/error/progress contracts and a dedicated recording control channel.
- Adds the four-hour limit, 3:45 warning, 15-minute transcription chunks, preservation metadata, and collision-safe sessions.
- Bundles pinned Python, FFmpeg, FFprobe, and the native local helper.
- Adds terminal command installation, privacy-safe diagnostics, Developer ID release packaging, notarization gates, and signed Sparkle updates.
