# Changelog

## 1.0.5 — Unreleased

- Stop setup checks from launching MacWhisper through version and model queries. Invoke its CLI only when MacWhisper is selected for transcription.
- Remove the keyword gate that discarded animation and facial-position feedback, repair unusable generated titles, and process feedback throughout the transcript even when it starts with unrelated speech.
- Recognize conversational second markers and adjacent spoken ranges, and separate natural general-feedback transitions from timestamped notes.
- Separate Apple model instructions from source material, bound long edit moments, and replace scene-specific canned notes and transcript dumps with explicit incomplete-formatting notices. Return an error when no usable notes are generated.
- Add regression coverage for provider isolation, source preservation, spoken timestamps, summary selection, model-request separation, malformed drafts, and formatting failures.

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
